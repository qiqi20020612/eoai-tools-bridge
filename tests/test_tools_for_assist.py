"""Original Tools for Assist query contracts; all backends remain simulated."""

import ast
import json
import sys
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import probatio as vol
import pytest
from homeassistant.core import State
from homeassistant.helpers import llm

from custom_components.eoai_tools_bridge.const import (
    AUDITED_READ_ONLY_TOOLS,
    CONF_ALLOWED_TOOLS,
    CONF_ENABLED,
    DOMAIN,
)
from scripts.fetch_tools_upstream import DESTINATION

pytestmark = pytest.mark.tools_upstream

# Every audited query class, including all three web-search provider variants.
QUERIES = [
    ("llm_intents", "brave_web_search", "BraveSearchTool", {"query": "123"}),
    (
        "llm_intents",
        "brave_llm_context_search",
        "BraveLlmContextSearchTool",
        {"query": "123", "freshness": "This Week"},
    ),
    ("llm_intents", "searxng_search", "SearXngSearchTool", {"query": "123"}),
    ("llm_intents", "google_places", "FindPlacesTool", {"query": "library"}),
    (
        "llm_intents",
        "google_routes",
        "GetRouteTool",
        {"destination": "library", "mode": "WALK"},
    ),
    ("llm_intents", "wikipedia", "SearchWikipediaTool", {"query": "library"}),
    ("llm_intents", "youtube", "SearchYouTubeTool", {"query": "library"}),
    ("weather_forecast", "weather", "WeatherForecastTool", {"range": "today"}),
    (
        "basic_utilities",
        "unit_converter",
        "UnitConverterTool",
        {"amount": "1 1/2", "from_unit": "cup", "to_unit": "ml"},
    ),
    (
        "basic_utilities",
        "date_info",
        "DateInfoTool",
        {"day": 10, "month": 10, "year": 2026},
    ),
    (
        "HomeControl",
        "entity_history",
        "EntityHistoryTool",
        {
            "name": "Kitchen",
            "domain": "sensor",
            "start_date_time": "2026-10-09 08:00",
            "end_date_time": "2026-10-09 09:00",
        },
    ),
]
QUERY_IDS = [item[1] for item in QUERIES]


class QueryAPI(llm.API):
    """Simulate API acquisition while dispatching original query tools."""

    def __init__(self, hass, api_id, tool):
        super().__init__(hass=hass, id=api_id, name=api_id)
        self.tools = [tool]
        self.contexts = []

    async def async_get_api_instance(self, context):
        self.contexts.append(context)
        return llm.APIInstance(
            api=self,
            api_prompt="private upstream prompt",
            llm_context=context,
            tools=self.tools,
            custom_serializer=llm.selector_serializer,
        )


def make_tool(hass, tools_source, case):
    _, module_name, class_name, _ = case
    module = tools_source(module_name)
    const = tools_source("const")
    config = {
        const.CONF_PROVIDER_API_KEYS: {const.PROVIDER_GOOGLE: "simulated-private-key"},
        const.CONF_GOOGLE_ROUTES_HOME_ADDRESS: "simulated origin",
    }
    return module, getattr(module, class_name)(config, hass)


async def call_service(hass, action, context, data=None):
    return await hass.services.async_call(
        DOMAIN,
        action,
        {} if data is None else data,
        context=context,
        blocking=True,
        return_response=True,
    )


def enable(hass, entry, api_id, tool):
    hass.config_entries.async_update_entry(
        entry,
        options={CONF_ENABLED: True, CONF_ALLOWED_TOOLS: f"{api_id}/{tool.name}"},
    )


@pytest.mark.parametrize("case", QUERIES, ids=QUERY_IDS)
async def test_original_query_catalog_and_readiness(
    hass, bridge_entry, admin_context, tools_source, case
):
    api_id, _, _, args = case
    _, tool = make_tool(hass, tools_source, case)
    original_schema = tool.parameters
    assert isinstance(original_schema, vol.Schema)
    assert tool.annotations is llm.Tool.annotations
    api = QueryAPI(hass, api_id, tool)
    unregister = llm.async_register_api(hass, api)
    enable(hass, bridge_entry, api_id, tool)
    try:
        with patch.object(tool, "async_call", new_callable=AsyncMock) as invoke:
            catalog = await call_service(hass, "list_tools", admin_context)
            assert catalog["success"] is True
            assert len(catalog["tools"]) == 1
            metadata = catalog["tools"][0]
            assert metadata["name"] == tool.name
            assert metadata["read_only_basis"] == "audited_allowlist"
            assert set(args) <= metadata["parameters"]["properties"].keys()
            if tool.name == "search_youtube":
                schema = metadata["parameters"]
                assert schema["required"] == ["query"]
                assert schema["properties"]["num_results"] == {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 25,
                    "description": (
                        "Number of videos to return (1-25). Use more when the user "
                        "wants multiple options."
                    ),
                }
            check = await call_service(hass, "check_tools", admin_context)
            assert check["success"] is True
            assert check["tools"][0]["status"] == "ready"
            assert check["tools"][0]["requires_side_effects"] is False
            invoke.assert_not_called()
            assert tool.parameters is original_schema
            assert original_schema(args) == (
                args | {"num_results": 1} if tool.name == "search_youtube" else args
            )
            assert all(context.context is admin_context for context in api.contexts)
    finally:
        unregister()


@pytest.mark.parametrize("case", QUERIES[3:], ids=QUERY_IDS[3:])
async def test_audited_queries_require_explicit_access(
    hass, bridge_entry, admin_context, tools_source, case
):
    api_id, _, _, args = case
    _, tool = make_tool(hass, tools_source, case)
    api = QueryAPI(hass, api_id, tool)
    unregister = llm.async_register_api(hass, api)
    try:
        with patch.object(tool, "async_call", new_callable=AsyncMock) as invoke:
            assert (await call_service(hass, "list_tools", admin_context))[
                "tools"
            ] == []
            # Legacy search discovery can open llm_intents to find search_web;
            # it never exposes this additional, unapproved query tool.
            expected_opens = int(api_id == "llm_intents")
            assert len(api.contexts) == expected_opens
            enable(hass, bridge_entry, api_id, tool)
            assert (await call_service(hass, "list_tools", None))["tools"] == []
            assert len(api.contexts) == expected_opens * 2
            response = await call_service(
                hass,
                "call_tool",
                None,
                {"api_id": api_id, "tool_name": tool.name, "tool_args": args},
            )
            assert response["error_code"] == "permission_denied"
            invoke.assert_not_called()
    finally:
        unregister()


def mock_http(payloads):
    """Use complete HTTP JSON fixtures, with no network sockets."""
    session = MagicMock()
    responses = []
    for payload in payloads:
        response = MagicMock(status=200)
        response.json = AsyncMock(return_value=payload)
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=False)
        responses.append(response)
    session.get.side_effect = list(responses)
    session.post.side_effect = list(responses)
    return session


def simulate_backend(stack, module, tool, module_name, hass):
    """Replace external data acquisition; keep original tool execution."""
    if module_name in {
        "brave_web_search",
        "brave_llm_context_search",
        "searxng_search",
    }:
        stack.enter_context(
            patch.object(
                tool,
                "async_search",
                new=AsyncMock(
                    return_value=[
                        {"title": "Library", "content": ["simulated snippet"]}
                    ]
                ),
            )
        )
        module = sys.modules[tool.async_call.__module__]
    if hasattr(module, "SQLiteCache"):
        cache = Mock()
        cache.get.return_value = None
        stack.enter_context(patch.object(module, "SQLiteCache", return_value=cache))
    payloads = {
        "google_places": [
            {
                "places": [
                    {
                        "displayName": {"text": "Library"},
                        "shortFormattedAddress": "simulated address",
                        "rating": 4.5,
                    }
                ]
            }
        ],
        "google_routes": [{"routes": [{"distanceMeters": 1000, "duration": "600s"}]}],
        "youtube": [
            {
                "items": [
                    {
                        "id": {"videoId": "test123"},
                        "snippet": {
                            "title": "Library",
                            "channelTitle": "Channel",
                            "description": "simulated",
                            "publishedAt": "2026-10-09T00:00:00Z",
                        },
                    }
                ]
            }
        ],
        "wikipedia": [
            {"query": {"search": [{"title": "Library", "snippet": "book"}]}},
            {"extract": "simulated encyclopedia summary"},
        ],
    }
    if module_name in payloads:
        stack.enter_context(
            patch.object(
                module,
                "async_get_clientsession",
                return_value=mock_http(payloads[module_name]),
            )
        )
    if module_name == "google_routes":
        stack.enter_context(
            patch.object(
                tool,
                "_resolve_destination_via_places",
                new=AsyncMock(return_value=None),
            )
        )
    if module_name == "weather":
        const = sys.modules[module.__package__ + ".const"]
        tool.config[const.CONF_DAILY_WEATHER_ENTITY] = "weather.simulated"
        stack.enter_context(
            patch.object(tool, "has_twice_daily_data", return_value=False)
        )
        stack.enter_context(
            patch.object(
                tool,
                "_get_daily_forecast",
                new=AsyncMock(return_value="simulated forecast"),
            )
        )
    if module_name == "entity_history":
        hass.states.async_set("sensor.kitchen", "23", {"friendly_name": "Kitchen"})
        stack.enter_context(
            patch.object(
                module,
                "async_get_exposed_entities",
                return_value={"sensor.kitchen": {}},
            )
        )
        stack.enter_context(
            patch.object(
                module.recorder.util, "session_scope", return_value=MagicMock()
            )
        )
        instance = Mock()
        instance.async_add_executor_job = AsyncMock(
            side_effect=lambda function: function()
        )
        stack.enter_context(
            patch.object(module.recorder, "get_instance", return_value=instance)
        )
        states = [State("sensor.kitchen", "20"), State("sensor.kitchen", "23")]
        stack.enter_context(
            patch.object(
                module.history,
                "get_significant_states_with_session",
                return_value={"sensor.kitchen": states},
            )
        )


@pytest.mark.parametrize("case", QUERIES, ids=QUERY_IDS)
async def test_original_query_calls_with_simulated_backends(
    hass, bridge_entry, admin_context, tools_source, case
):
    api_id, module_name, _, args = case
    module, tool = make_tool(hass, tools_source, case)
    api = QueryAPI(hass, api_id, tool)
    unregister = llm.async_register_api(hass, api)
    enable(hass, bridge_entry, api_id, tool)
    try:
        with ExitStack() as stack:
            simulate_backend(stack, module, tool, module_name, hass)
            invoke = stack.enter_context(
                patch.object(tool, "async_call", wraps=tool.async_call)
            )
            response = await call_service(
                hass,
                "call_tool",
                admin_context,
                {
                    "api_id": api_id,
                    "tool_name": tool.name,
                    "tool_args": args,
                },
            )
            assert response["success"] is True, response
            assert response["truncated"] is False
            assert response["outcome_unknown"] is False
            invoke.assert_awaited_once()
            assert invoke.call_args.args[2].context is admin_context
            body = response["result"]
            if module_name == "weather":
                assert body == "simulated forecast"
            elif module_name == "unit_converter":
                assert body == {"value": 354.8824}
            elif module_name == "date_info":
                assert body["day"] == "Saturday"
                assert body["date"] == "October 10, 2026"
            elif module_name == "entity_history":
                assert body["stats"]["state_at_search_start"] == "20"
                assert body["stats"]["state_at_end"] == "23"
                assert body["sampled_states"][0]["entity_id"] == "sensor.kitchen"
            elif module_name == "google_routes":
                assert body["result"]["distance"] == "1.0 km"
                assert body["result"]["duration"] == "10 min"
            else:
                assert len(body["results"]) == 1
            serialized = json.dumps(response)
            for secret in (
                "instruction",
                "private upstream prompt",
                "simulated-private-key",
            ):
                assert secret not in serialized
    finally:
        unregister()


def test_full_upstream_inventory_and_remaining_families(tools_source):
    """Fail when audited pairs drift; record write/dynamic tools as remaining."""
    const = tools_source("const")
    assert const.DOMAIN == "llm_intents"
    assert const.WEATHER_API_NAME.lower().replace(" ", "_") == "weather_forecast"
    assert const.BASIC_UTILITIES_API_NAME.lower().replace(" ", "_") == "basic_utilities"
    pairs = set()
    for api_id, module_name, class_name, _ in QUERIES:
        module = tools_source(module_name)
        pairs.add((api_id, getattr(module, class_name).name))
    assert pairs == AUDITED_READ_ONLY_TOOLS
    for module, name in [("calculator", "calculate"), ("play_media", "play_video")]:
        tree = ast.parse((DESTINATION / f"{module}.py").read_text())
        names = [
            node.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "name"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
        ]
        assert names == [name]
        assert not any(tool == name for _, tool in pairs)
    home = (DESTINATION / "home_control.py").read_text()
    assert 'self.id = "HomeControl"' in home
    assert "async_get_tools(self.hass, llm_context, llm.LLM_API_ASSIST)" in home
    assert "CONF_HOME_CONTROL_DISABLED_TOOLS" in home
    tree = ast.parse((DESTINATION / "llm_functions.py").read_text())
    tool_maps = {
        node.targets[0].id: [item.elts[1].id for item in node.value.elts]
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id.endswith("_CONF_ENABLED_MAP")
    }
    assert set(tool_maps) == {
        "SEARCH_CONF_ENABLED_MAP",
        "WEATHER_CONF_ENABLED_MAP",
        "MEDIA_CONF_ENABLED_MAP",
        "BASIC_UTILITIES_CONF_ENABLED_MAP",
    }
    mapped = {name for names in tool_maps.values() for name in names}
    assert mapped == {item[2] for item in QUERIES[:-1]} | {
        "CalculatorTool",
        "PlayVideoTool",
    }


@pytest.mark.parametrize("case", QUERIES, ids=QUERY_IDS)
async def test_native_query_argument_errors_never_dispatch(
    hass, bridge_entry, admin_context, tools_source, case
):
    api_id, _, _, args = case
    _, tool = make_tool(hass, tools_source, case)
    invalid = dict(args)
    field = next(iter(invalid))
    invalid[field] = []
    api = QueryAPI(hass, api_id, tool)
    unregister = llm.async_register_api(hass, api)
    enable(hass, bridge_entry, api_id, tool)
    try:
        with patch.object(tool, "async_call", new_callable=AsyncMock) as invoke:
            response = await call_service(
                hass,
                "call_tool",
                admin_context,
                {
                    "api_id": api_id,
                    "tool_name": tool.name,
                    "tool_args": invalid,
                },
            )
            assert response["error_code"] == "invalid_args"
            invoke.assert_not_called()
    finally:
        unregister()


async def test_all_nine_query_pairs_fit_catalog_and_readiness(
    hass, bridge_entry, admin_context, tools_source
):
    pairs = sorted(AUDITED_READ_ONLY_TOOLS)
    hass.config_entries.async_update_entry(
        bridge_entry,
        options={
            CONF_ENABLED: True,
            CONF_ALLOWED_TOOLS: "\n".join(f"{api}/{tool}" for api, tool in pairs),
        },
    )
    with ExitStack() as stack:
        apis = {}
        # Include the most expressive search_web schema; exclude duplicate names.
        for case in [QUERIES[1], *QUERIES[3:]]:
            api_id = case[0]
            _, tool = make_tool(hass, tools_source, case)
            stack.enter_context(
                patch.object(tool, "async_call", new_callable=AsyncMock)
            )
            if api_id not in apis:
                apis[api_id] = QueryAPI(hass, api_id, tool)
                stack.callback(llm.async_register_api(hass, apis[api_id]))
            else:
                apis[api_id].tools.append(tool)
        for service in ("list_tools", "check_tools"):
            response = await call_service(hass, service, admin_context)
            assert response["success"] is True
            assert response["truncated"] is False
            assert len(response["tools"]) == 9
            assert len(json.dumps(response, ensure_ascii=False).encode()) <= 16_384
        for api in apis.values():
            for tool in api.tools:
                tool.async_call.assert_not_called()


async def test_youtube_default_runs_once_only_on_authorized_call(
    hass, bridge_entry, admin_context, tools_source
):
    module, tool = make_tool(hass, tools_source, QUERIES[6])
    key = next(key for key in tool.parameters.schema if key.schema == "num_results")
    factory = Mock(wraps=key.default)
    key.default = factory
    api = QueryAPI(hass, "llm_intents", tool)
    unregister = llm.async_register_api(hass, api)
    enable(hass, bridge_entry, api.id, tool)
    try:
        await call_service(hass, "list_tools", admin_context)
        await call_service(hass, "check_tools", admin_context)
        factory.assert_not_called()
        with patch.object(
            tool,
            "async_call",
            new_callable=AsyncMock,
            return_value=llm.ToolResult(data={"results": []}),
        ) as invoke:
            response = await call_service(
                hass,
                "call_tool",
                admin_context,
                {
                    "api_id": api.id,
                    "tool_name": tool.name,
                    "tool_args": {"query": "123"},
                },
            )
            assert response["success"] is True
            factory.assert_called_once()
            assert invoke.call_args.args[1].tool_args == {
                "query": "123",
                "num_results": 1,
            }
            invalid = await call_service(
                hass,
                "call_tool",
                admin_context,
                {
                    "api_id": api.id,
                    "tool_name": tool.name,
                    "tool_args": {"query": "123", "num_results": 26},
                },
            )
            assert invalid["error_code"] == "invalid_args"
            invoke.assert_awaited_once()
    finally:
        unregister()
