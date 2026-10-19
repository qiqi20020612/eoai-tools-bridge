"""Static Functions against original schemas and the existing EOAIC2 ScriptFunction.

Only provider execution is replaced: HA, gateway authorization, native parameter
validation and the hash-pinned original ScriptFunction all execute normally.
No generator, modified upstream module, live provider, or runtime dependency.
"""

import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

import probatio as vol
import pytest
import yaml
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import Context
from homeassistant.helpers import llm
from test_tools_for_assist import QueryAPI

from custom_components.eoai_tools_bridge.catalog import serialize_parameters
from custom_components.eoai_tools_bridge.const import AUDITED_READ_ONLY_TOOLS, DOMAIN

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ExampleCase:
    file: str
    api: str
    name: str
    module: str | None
    cls: str
    minimal: dict
    optional: dict


CASES = [
    ExampleCase(
        "search_web", "llm_intents", "search_web", module, cls, {"query": "123"}, {}
    )
    for module, cls in (
        ("brave_web_search", "BraveSearchTool"),
        ("brave_llm_context_search", "BraveLlmContextSearchTool"),
        ("searxng_search", "SearXngSearchTool"),
        ("tavily_search", "TavilySearchTool"),
    )
] + [
    ExampleCase(
        "search_web_brave_llm_context",
        "llm_intents",
        "search_web",
        "brave_llm_context_search",
        "BraveLlmContextSearchTool",
        {"query": "true"},
        {"freshness": "This Week"},
    ),
    ExampleCase(
        "search_web_tavily",
        "llm_intents",
        "search_web",
        "tavily_search",
        "TavilySearchTool",
        {"query": "{}"},
        {"topic": "news", "time_range": "week"},
    ),
    ExampleCase(
        "find_places_google",
        "llm_intents",
        "find_places",
        "google_places",
        "FindPlacesTool",
        {"query": "{{ states('light.private') }}"},
        {},
    ),
    ExampleCase(
        "get_route",
        "llm_intents",
        "get_route",
        "google_routes",
        "GetRouteTool",
        {"destination": "123"},
        {"mode": "WALK", "departure_time": "2026-10-20T09:00:00+08:00"},
    ),
    ExampleCase(
        "search_wikipedia",
        "llm_intents",
        "search_wikipedia",
        "wikipedia",
        "SearchWikipediaTool",
        {"query": "None"},
        {},
    ),
    ExampleCase(
        "search_youtube",
        "llm_intents",
        "search_youtube",
        "youtube",
        "SearchYouTubeTool",
        {"query": "[1, 2]"},
        {"num_results": 25},
    ),
    ExampleCase(
        "get_weather_forecast",
        "weather_forecast",
        "get_weather_forecast",
        "weather",
        "WeatherForecastTool",
        {"range": "today"},
        {},
    ),
    ExampleCase(
        "unit_convert",
        "basic_utilities",
        "unit_convert",
        "unit_converter",
        "UnitConverterTool",
        {"amount": "1 1/2", "from_unit": "cup", "to_unit": "ml"},
        {},
    ),
    ExampleCase(
        "calendar_day_info",
        "basic_utilities",
        "calendar_day_info",
        "date_info",
        "DateInfoTool",
        {"day": 19, "month": 10},
        {"year": 2026},
    ),
    ExampleCase(
        "calculate",
        "basic_utilities",
        "calculate",
        "calculator",
        "CalculatorTool",
        {"operation": "expression", "data": ["12.5*2+3"]},
        {},
    ),
    ExampleCase(
        "play_video",
        "media_services",
        "play_video",
        "play_media",
        "PlayVideoTool",
        {"video_url": "https://example.invalid/video"},
        {},
    ),
    ExampleCase(
        "find_places_amap",
        "eoai_tools_bridge_amap",
        "find_places",
        None,
        "",
        {"query": "咖啡"},
        {
            "city": "北京市",
            "location": "116.397499,39.908722",
            "radius": 2000,
            "sort": "distance",
            "types": "050000",
            "limit": 20,
        },
    ),
    ExampleCase(
        "geocode",
        "eoai_tools_bridge_amap",
        "geocode",
        None,
        "",
        {"address": "北京市东城区天安门"},
        {"city": "北京市"},
    ),
]
PARAMETERS = [
    pytest.param(
        case,
        id=f"{case.file}-{case.module or 'bridge'}",
        marks=pytest.mark.tools_upstream if case.module else (),
    )
    for case in CASES
]


@pytest.fixture
def case(request):
    return request.param


@pytest.fixture
def example(case):
    return yaml.safe_load((ROOT / "examples" / f"eoaic2_{case.file}.yaml").read_text())[
        0
    ]


@pytest.fixture
async def native(
    hass, gateway_entry, admin_context, release_source, video_entities, case
):
    context = llm.LLMContext(
        platform="extended_openai_conversation",
        context=admin_context,
        language="zh-Hans",
        assistant="conversation",
        device_id=None,
    )
    hass.config_entries.async_update_entry(
        gateway_entry,
        options={
            **gateway_entry.options,
            "allowed_tools": f"{case.api}/{case.name}",
            "allow_side_effects": case.name == "play_video",
        },
    )
    if case.module is None:
        api = await llm.async_get_api(hass, case.api, context)
        yield api, next(tool for tool in api.tools if tool.name == case.name)
        return
    const = release_source("const")
    tool = getattr(release_source(case.module), case.cls)(
        {
            const.CONF_GOOGLE_ROUTES_DEFAULT_TRAVEL_MODE: "WALK",
        },
        hass,
    )
    if case.name == "play_video":
        tool.update_args(hass)
    api = QueryAPI(hass, case.api, tool)
    stop = llm.async_register_api(hass, api)
    try:
        yield await llm.async_get_api(hass, case.api, context), tool
    finally:
        stop()


def arguments(case, optional, video_entities):
    supplied = deepcopy(case.minimal)
    if optional:
        supplied.update(case.optional)
        if case.name == "play_video":
            entity, device, area = video_entities[0]
            supplied.update(
                entity_id=[entity.entity_id], area=area.name, device_id=device.id
            )
    return supplied


@pytest.mark.parametrize("case", PARAMETERS, indirect=True)
def test_native_parameter_names_required_enums_and_types(case, example, native):
    api, tool = native
    spec = example["spec"]
    assert spec["name"] == case.name
    schema = spec["parameters"]
    vol.from_json_schema(schema)
    upstream = serialize_parameters(api, tool)
    fields = set(schema["properties"])
    assert fields.isdisjoint({"api_id", "tool_name", "tool_args"})
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(upstream["required"])
    if case.file == "search_web":
        assert fields == {"query"}
    else:
        assert fields == set(upstream["properties"])
    for name in fields:
        advertised, original = schema["properties"][name], upstream["properties"][name]
        assert advertised["type"] == original["type"]
        if "enum" in original:
            assert advertised["enum"] == original["enum"]
        for bound in ("minimum", "maximum", "minLength", "maxLength"):
            if bound in original:
                assert advertised[bound] == original[bound]
        if advertised["type"] == "array":
            assert advertised["items"]["type"] == original["items"]["type"]
    if case.name == "play_video":
        # Live enum depends on HA; portable YAML must not contain made-up players.
        assert upstream["properties"]["entity_id"]["items"]["enum"]
        assert "enum" not in schema["properties"]["entity_id"]["items"]


@pytest.mark.upstream
@pytest.mark.parametrize("case", PARAMETERS, indirect=True)
@pytest.mark.parametrize("optional", [False, True], ids=["minimal", "all_optional"])
async def test_original_script_maps_native_arguments_without_nested_model_fields(
    hass, case, example, native, upstream_script_function, video_entities, optional
):
    api, tool = native
    supplied = arguments(case, optional, video_entities)
    vol.from_json_schema(example["spec"]["parameters"])(supplied)
    before = deepcopy(supplied)
    services = []

    def record(event):
        if event.data["domain"] == DOMAIN and event.data["service"] == "call_tool":
            services.append(deepcopy(event.data["service_data"]))

    stop = hass.bus.async_listen(EVENT_CALL_SERVICE, record)
    execute = AsyncMock(return_value=llm.ToolResult(data={"value": "simulated output"}))
    try:
        with patch.object(tool, "async_call", execute):
            result = await upstream_script_function.execute(
                hass,
                upstream_script_function.validate_schema(example["function"]),
                supplied,
                api.llm_context,
                [],
            )
        await hass.async_block_till_done()
    finally:
        stop()
    assert result["success"] is True, result
    assert result["result"] == {"value": "simulated output"}
    assert supplied == before
    assert services == [
        {"api_id": case.api, "tool_name": case.name, "tool_args": supplied}
    ]
    execute.assert_awaited_once()
    tool_input, passed_context = execute.call_args.args[1:]
    expected = deepcopy(supplied)
    if case.name == "search_youtube":
        expected.setdefault("num_results", 1)
    if case.api == "eoai_tools_bridge_amap" and case.name == "find_places":
        expected.setdefault("limit", 5)
    assert tool_input.tool_args == expected
    assert passed_context.context is api.llm_context.context


def test_all_twelve_tool_identities_have_static_standalone_examples():
    pairs = {(case.api, case.name) for case in CASES}
    assert pairs == AUDITED_READ_ONLY_TOOLS | {
        ("media_services", "play_video"),
        ("eoai_tools_bridge_amap", "find_places"),
        ("eoai_tools_bridge_amap", "geocode"),
    }
    assert len(pairs) == 12
    assert len({case.file for case in CASES}) == 14  # 12 tools + 2 search variants
    for file in {case.file for case in CASES}:
        entries = yaml.safe_load(
            (ROOT / "examples" / f"eoaic2_{file}.yaml").read_text()
        )
        assert len(entries) == 1
        function = entries[0]["function"]
        assert function["type"] == "script"
        assert len(function["sequence"]) == 1
        action = function["sequence"][0]
        assert action["action"] == f"{DOMAIN}.call_tool"
        assert action["response_variable"] == "_function_result"
    assert not (ROOT / "examples/eoaic2_web_search.yaml").exists()
    for path in (ROOT / "examples").glob("*.yaml"):
        text = path.read_text()
        assert "action: eoai_tools_bridge.search_web" not in text
        assert "name: web_search" not in text


@pytest.mark.parametrize("provider", ["google", "amap"])
@pytest.mark.parametrize(
    "search", ["search_web", "search_web_brave_llm_context", "search_web_tavily"]
)
def test_recommended_selection_has_no_duplicate_function_names(provider, search):
    files = {
        case.file for case in CASES if case.name not in {"find_places", "search_web"}
    }
    files |= {search, f"find_places_{provider}"}
    names = [
        yaml.safe_load((ROOT / "examples" / f"eoaic2_{file}.yaml").read_text())[0][
            "spec"
        ]["name"]
        for file in files
    ]
    assert len(names) == len(set(names)) == 11
    assert names.count("find_places") == names.count("search_web") == 1


@pytest.mark.upstream
@pytest.mark.parametrize("case", [PARAMETERS[5]], indirect=True)
@pytest.mark.parametrize(
    "supplied",
    [
        {"query": "news", "topic": "news"},
        {"query": "news", "time_range": "day"},
        {"query": "news", "topic": None},
    ],
)
async def test_tavily_optionals_are_independent_and_null_is_not_omitted(
    hass, case, example, native, upstream_script_function, supplied
):
    api, tool = native
    execute = AsyncMock(return_value=llm.ToolResult(data={"results": []}))
    with patch.object(tool, "async_call", execute):
        result = await upstream_script_function.execute(
            hass,
            upstream_script_function.validate_schema(example["function"]),
            supplied,
            api.llm_context,
            [],
        )
    if supplied.get("topic", "") is None:
        assert result["error_code"] == "invalid_args"
        execute.assert_not_called()
    else:
        assert result["success"] is True
        assert execute.call_args.args[1].tool_args == supplied


@pytest.mark.upstream
@pytest.mark.parametrize(
    "case", [PARAMETERS[0], PARAMETERS[5], PARAMETERS[14]], indirect=True
)
@pytest.mark.parametrize("identity", ["missing", "ordinary"])
async def test_independent_functions_do_not_create_administrator_identity(
    hass, case, example, native, upstream_script_function, hass_read_only_user, identity
):
    api, tool = native
    context = api.llm_context
    context.context = (
        Context() if identity == "missing" else Context(user_id=hass_read_only_user.id)
    )
    with patch.object(tool, "async_call", new_callable=AsyncMock) as execute:
        response = await upstream_script_function.execute(
            hass,
            upstream_script_function.validate_schema(example["function"]),
            case.minimal,
            context,
            [],
        )
    assert response["error_code"] == "permission_denied"
    execute.assert_not_called()


@pytest.mark.parametrize("case", [PARAMETERS[4], PARAMETERS[5]], indirect=True)
def test_provider_specific_schemas_do_not_advertise_other_provider_filters(
    case, example
):
    schema = example["spec"]["parameters"]
    wrong = {"topic": "news"} if "brave" in case.file else {"freshness": "Today"}
    with pytest.raises(vol.Invalid):
        vol.from_json_schema(schema)({"query": "news", **wrong})


def test_documentation_code_blocks_match_all_static_examples():
    document = (ROOT / "docs/EOAIC2_FUNCTIONS.md").read_text()
    blocks = re.findall(
        r"<!-- example: ([a-z0-9_]+\.yaml) -->\n```yaml\n(.*?)\n```", document, re.S
    )
    assert len(blocks) == len({case.file for case in CASES}) == 14
    assert {file for file, _ in blocks} == {
        f"eoaic2_{case.file}.yaml" for case in CASES
    }
    for file, block in blocks:
        assert block == (ROOT / "examples" / file).read_text().rstrip("\n")


@pytest.mark.upstream
@pytest.mark.parametrize(
    "case,extra",
    [
        (CASES[7], {"mode": "TRANSIT"}),
        (CASES[7], {"departure_time": "2026-10-20T09:00:00+08:00"}),
        (CASES[15], {"city": "北京市"}),
        (CASES[15], {"limit": 1}),
        (CASES[15], {"types": "050000"}),
        (CASES[15], {"location": "116.397499,39.908722"}),
        (CASES[15], {"location": "116.397499,39.908722", "radius": 1}),
        (CASES[15], {"location": "116.397499,39.908722", "sort": "weight"}),
    ],
    indirect=["case"],
)
async def test_optional_parameters_do_not_depend_on_unrelated_optionals(
    hass, case, extra, example, native, upstream_script_function
):
    api, tool = native
    supplied = {**case.minimal, **extra}
    execute = AsyncMock(return_value=llm.ToolResult(data={"value": "ok"}))
    with patch.object(tool, "async_call", execute):
        result = await upstream_script_function.execute(
            hass,
            upstream_script_function.validate_schema(example["function"]),
            supplied,
            api.llm_context,
            [],
        )
    assert result["success"] is True
    expected = {**supplied}
    if case.api == "eoai_tools_bridge_amap":
        expected.setdefault("limit", 5)
    assert execute.call_args.args[1].tool_args == expected


@pytest.mark.upstream
@pytest.mark.parametrize(
    "case,wrong",
    [
        (CASES[9], {"num_results": "2"}),
        (CASES[12], {"year": "2026"}),
        (CASES[13], {"data": [123]}),
        (CASES[14], {"entity_id": "media_player.video_0"}),
        (CASES[15], {"radius": "3000"}),
    ],
    indirect=["case"],
)
async def test_wrong_argument_types_are_not_coerced_or_hidden_by_templates(
    hass, case, wrong, example, native, upstream_script_function
):
    api, tool = native
    supplied = {**case.minimal, **wrong}
    with pytest.raises(vol.Invalid):
        vol.from_json_schema(example["spec"]["parameters"])(supplied)
    with patch.object(tool, "async_call", new_callable=AsyncMock) as execute:
        result = await upstream_script_function.execute(
            hass,
            upstream_script_function.validate_schema(example["function"]),
            supplied,
            api.llm_context,
            [],
        )
    assert result["error_code"] == "invalid_args"
    execute.assert_not_called()


@pytest.mark.upstream
@pytest.mark.parametrize("case", [PARAMETERS[4], PARAMETERS[5]], indirect=True)
async def test_stale_provider_specific_function_fails_closed_after_provider_switch(
    hass, case, example, native, upstream_script_function, release_source
):
    api, tool = native
    replacement = (
        release_source("tavily_search").TavilySearchTool
        if "brave" in case.file
        else release_source("brave_llm_context_search").BraveLlmContextSearchTool
    )
    tool.parameters = replacement.parameters
    with patch.object(tool, "async_call", new_callable=AsyncMock) as execute:
        result = await upstream_script_function.execute(
            hass,
            upstream_script_function.validate_schema(example["function"]),
            {**case.minimal, **case.optional},
            api.llm_context,
            [],
        )
    assert result["error_code"] == "invalid_args"
    execute.assert_not_called()


@pytest.mark.upstream
@pytest.mark.parametrize("target", ["entity_id", "area", "device_id"])
@pytest.mark.parametrize("case", [PARAMETERS[14]], indirect=True)
async def test_each_native_playback_target_is_optional_independently(
    hass, case, target, example, native, upstream_script_function, video_entities
):
    api, tool = native
    entity, device, area = video_entities[0]
    value = {
        "entity_id": [entity.entity_id],
        "area": area.name,
        "device_id": device.id,
    }[target]
    supplied = {**case.minimal, target: value}
    execute = AsyncMock(return_value=llm.ToolResult(data={"success": True}))
    with patch.object(tool, "async_call", execute):
        result = await upstream_script_function.execute(
            hass,
            upstream_script_function.validate_schema(example["function"]),
            supplied,
            api.llm_context,
            [],
        )
    assert result["success"] is True
    assert execute.call_args.args[1].tool_args == supplied


@pytest.mark.upstream
@pytest.mark.parametrize("case", [PARAMETERS[14]], indirect=True)
async def test_playback_example_does_not_bypass_side_effect_permission(
    hass, case, example, native, upstream_script_function, gateway_entry
):
    api, tool = native
    hass.config_entries.async_update_entry(
        gateway_entry, options={**gateway_entry.options, "allow_side_effects": False}
    )
    with patch.object(tool, "async_call", new_callable=AsyncMock) as execute:
        result = await upstream_script_function.execute(
            hass,
            upstream_script_function.validate_schema(example["function"]),
            case.minimal,
            api.llm_context,
            [],
        )
    assert result["error_code"] == "side_effects_blocked"
    execute.assert_not_called()
