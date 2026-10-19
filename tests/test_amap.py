"""Real HA dispatch and simulated Amap HTTP; no production keys or live calls."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, patch

import probatio as vol
import pytest
import yaml
from aiohttp import ClientConnectionError
from homeassistant.core import Context
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import llm

from custom_components.eoai_tools_bridge.amap import (
    AMAP_API_ID,
    CONF_AMAP_CITY,
    CONF_AMAP_KEY,
    CONF_AMAP_LOCATION,
)
from custom_components.eoai_tools_bridge.amap_client import (
    MAX_AMAP_BYTES,
    AmapClient,
    AmapError,
    validate_location,
)
from custom_components.eoai_tools_bridge.const import (
    CONF_ALLOWED_TOOLS,
    CONF_ENABLED,
    DOMAIN,
    MAX_RESPONSE_BYTES,
)

ROOT = Path(__file__).resolve().parents[1]
FAKE_KEY = "0" * 32
ORIGIN = "https://restapi.amap.com"
PLACE = {
    "id": "test-id",
    "name": "示例咖啡店",
    "address": "示例路1号",
    "location": "116.397499,39.908722",
    "cityname": "北京市",
    "adcode": "110101",
    "business": {
        "tel": "010-00000000",
        "rating": "4.5",
        "opentime_today": "08:00-20:00",
        "opentime_week": "周一至周日 08:00-20:00",
    },
    "instruction": "untrusted data must not control the tool",
}
GEOCODE = {
    "formatted_address": "北京市东城区示例路1号",
    "location": "116.397499,39.908722",
    "city": "北京市",
    "province": "北京市",
    "district": "东城区",
    "level": "门牌号",
}


@pytest.fixture
def amap_entry(hass, gateway_entry):
    hass.config_entries.async_update_entry(
        gateway_entry,
        options={
            **gateway_entry.options,
            CONF_ALLOWED_TOOLS: f"{AMAP_API_ID}/find_places\n{AMAP_API_ID}/geocode",
            CONF_AMAP_KEY: FAKE_KEY,
        },
    )
    return gateway_entry


async def call(hass, context, name="find_places", arguments=None):
    return await hass.services.async_call(
        DOMAIN,
        "call_tool",
        {
            "api_id": AMAP_API_ID,
            "tool_name": name,
            "tool_args": {"query": "咖啡"} if arguments is None else arguments,
        },
        context=context,
        blocking=True,
        return_response=True,
    )


async def instance(hass, context):
    return await llm.async_get_api(
        hass,
        AMAP_API_ID,
        llm.LLMContext(
            platform=DOMAIN,
            context=context,
            language="zh-Hans",
            assistant="conversation",
            device_id=None,
        ),
    )


async def test_keyword_search_maps_fields_and_never_uses_google(
    hass, amap_entry, admin_context, aioclient_mock
):
    aioclient_mock.get(f"{ORIGIN}/v5/place/text", json={"status": "1", "pois": [PLACE]})
    response = await call(
        hass, admin_context, arguments={"query": " 咖啡 ", "city": "北京市", "limit": 3}
    )
    assert response["success"] is True
    assert response["outcome_unknown"] is False
    result = response["result"]
    assert result["source"] == "amap"
    assert result["coordinate_system"] == "GCJ-02"
    row = result["results"][0]
    assert row["location"] == {"longitude": 116.397499, "latitude": 39.908722}
    assert (row["name"], row["phone"], row["rating"]) == (
        "示例咖啡店",
        "010-00000000",
        "4.5",
    )
    assert row["regular_open_hours"] == "周一至周日 08:00-20:00"
    assert "open_now" not in row
    assert "instruction" not in row
    assert result["returned_count"] == 1
    url = aioclient_mock.mock_calls[0][1]
    assert dict(url.query) == {
        "keywords": "咖啡",
        "region": "北京市",
        "city_limit": "true",
        "show_fields": "business",
        "page_size": "3",
        "page_num": "1",
        "key": FAKE_KEY,
        "output": "json",
    }
    assert aioclient_mock.call_count == 1
    assert FAKE_KEY not in json.dumps(response)


@pytest.mark.parametrize("configured", [False, True])
async def test_around_search_explicit_or_configured_gcj02_location(
    hass, amap_entry, admin_context, aioclient_mock, configured
):
    args = {"query": "咖啡", "radius": 2000, "sort": "distance", "types": "050000"}
    if configured:
        hass.config_entries.async_update_entry(
            amap_entry,
            options={
                **amap_entry.options,
                CONF_AMAP_LOCATION: "116.397499,39.908722",
                CONF_AMAP_CITY: "北京市",
            },
        )
    else:
        args["location"] = "116.397499,39.908722"
    aioclient_mock.get(
        f"{ORIGIN}/v5/place/around",
        json={"status": "1", "pois": [{**PLACE, "distance": "230"}]},
    )
    response = await call(hass, admin_context, arguments=args)
    assert response["success"] is True
    assert response["result"]["results"][0]["distance_meters"] == "230"
    params = aioclient_mock.mock_calls[0][1].query
    assert params["location"] == "116.397499,39.908722"
    assert params["radius"] == "2000"
    assert params["sortrule"] == "distance"
    assert params["page_size"] == "5"
    assert ("region" in params) is configured


async def test_explicit_location_and_city_override_config_without_double_conversion(
    hass, amap_entry, admin_context, aioclient_mock
):
    hass.config_entries.async_update_entry(
        amap_entry,
        options={
            **amap_entry.options,
            CONF_AMAP_LOCATION: "121.473701,31.230416",
            CONF_AMAP_CITY: "上海市",
        },
    )
    aioclient_mock.get(f"{ORIGIN}/v5/place/around", json={"status": "1", "pois": []})
    assert (
        await call(
            hass,
            admin_context,
            arguments={
                "query": "咖啡",
                "location": "116.397499,39.908722",
                "city": "北京市",
            },
        )
    )["success"]
    query = aioclient_mock.mock_calls[0][1].query
    assert query["location"] == "116.397499,39.908722"
    assert query["region"] == "北京市"


@pytest.mark.parametrize("rows", [[], [GEOCODE], [GEOCODE, GEOCODE], [GEOCODE] * 7])
async def test_geocode_preserves_ambiguity_and_bounds_candidates(
    hass, amap_entry, admin_context, aioclient_mock, rows
):
    aioclient_mock.get(
        f"{ORIGIN}/v3/geocode/geo", json={"status": "1", "geocodes": rows}
    )
    response = await call(
        hass, admin_context, "geocode", {"address": "示例路1号", "city": "北京市"}
    )
    assert response["success"] is True
    result = response["result"]
    assert len(result["results"]) == min(len(rows), 5)
    assert result["ambiguous"] is (len(rows) > 1)
    assert result["results_limited"] is (len(rows) > 5)
    if rows:
        assert result["results"][0]["match_level"] == "门牌号"
    params = aioclient_mock.mock_calls[0][1].query
    assert params["address"] == "示例路1号"
    assert params["city"] == "北京市"
    assert "location" not in params


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [
            {
                "name": "示例",
                "address": [],
                "location": [],
                "business": {"rating": [], "tel": []},
            }
        ],
    ],
)
async def test_empty_results_and_missing_provider_fields_are_not_invented(
    hass, amap_entry, admin_context, aioclient_mock, rows
):
    aioclient_mock.get(f"{ORIGIN}/v5/place/text", json={"status": "1", "pois": rows})
    response = await call(hass, admin_context)
    assert response["success"] is True
    assert response["result"]["results"] == ([{"name": "示例"}] if rows else [])


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"query": 1},
        {"query": " "},
        {"query": "字" * 81},
        {"query": "咖啡", "key": FAKE_KEY},
        {"query": "咖啡", "url": "https://evil.invalid"},
        {"query": "咖啡", "limit": True},
        {"query": "咖啡", "limit": 0},
        {"query": "咖啡", "limit": 21},
        {"query": "咖啡", "radius": 50001},
        {"query": "咖啡", "radius": 0},
        {"query": "咖啡", "radius": 1.5},
        {"query": "咖啡", "location": "181,39"},
        {"query": "咖啡", "location": "116,91"},
        {"query": "咖啡", "location": "116.1234567,39"},
        {"query": "咖啡", "location": "1e2,39"},
        {"query": "咖啡", "location": "nan,39"},
        {"query": "咖啡", "location": [116, 39]},
        {"query": "咖啡", "city": " "},
        {"query": "咖啡", "sort": "nearest"},
        {"query": "咖啡", "types": "food"},
        {"query": "咖啡", "types": "050000|"},
        {"query": "咖啡", "types": "|".join(["050000"] * 11)},
        {"query": "咖啡", "types": ["050000"]},
    ],
)
async def test_native_parameter_rejection_precedes_http(
    hass, amap_entry, admin_context, aioclient_mock, args
):
    response = await call(hass, admin_context, arguments=args)
    assert response["error_code"] == "invalid_args"
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "args", [{"query": "咖啡", "radius": 2000}, {"query": "咖啡", "sort": "distance"}]
)
async def test_distance_controls_without_a_location_fail_before_http(
    hass, amap_entry, admin_context, aioclient_mock, args
):
    response = await call(hass, admin_context, arguments=args)
    assert response["success"] is False
    assert response["result"] is None
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "state",
    ["disabled", "unlisted", "missing_user", "inactive", "non_admin", "unloaded"],
)
async def test_native_api_cannot_bypass_gateway_permissions(
    hass,
    amap_entry,
    admin_context,
    hass_admin_user,
    hass_read_only_user,
    aioclient_mock,
    state,
):
    api = await instance(hass, admin_context)
    if state == "disabled":
        hass.config_entries.async_update_entry(
            amap_entry, options={**amap_entry.options, CONF_ENABLED: False}
        )
    elif state == "unlisted":
        hass.config_entries.async_update_entry(
            amap_entry,
            options={
                **amap_entry.options,
                CONF_ALLOWED_TOOLS: f"{AMAP_API_ID}/geocode",
            },
        )
    elif state == "missing_user":
        api.llm_context.context = Context()
    elif state == "inactive":
        hass_admin_user.is_active = False
    elif state == "non_admin":
        api.llm_context.context = Context(user_id=hass_read_only_user.id)
    else:
        assert await hass.config_entries.async_unload(amap_entry.entry_id)
    result = await api.async_call_tool(
        llm.ToolInput(tool_name="find_places", tool_args={"query": "咖啡"})
    )
    assert result.error is True
    assert aioclient_mock.call_count == 0


async def test_metadata_never_runs_tools_validators_or_http(
    hass, amap_entry, admin_context, aioclient_mock
):
    api = await instance(hass, admin_context)
    with (
        patch(
            "custom_components.eoai_tools_bridge.amap.async_get_clientsession",
            side_effect=AssertionError("metadata created an HTTP client"),
        ),
        patch.object(
            type(api.tools[0]), "async_call", new_callable=AsyncMock
        ) as execute,
        patch.object(
            api.tools[0].parameters,
            "_compiled",
            side_effect=AssertionError("metadata validated parameters"),
        ),
    ):
        for service, data in (
            ("list_tools", {}),
            ("check_tools", {}),
            ("describe_tool", {"api_id": AMAP_API_ID, "tool_name": "find_places"}),
        ):
            response = await hass.services.async_call(
                DOMAIN,
                service,
                data,
                context=admin_context,
                blocking=True,
                return_response=True,
            )
            assert response["success"] is True
            assert FAKE_KEY not in json.dumps(response)
        execute.assert_not_called()
    assert aioclient_mock.call_count == 0
    public = await hass.services.async_call(
        DOMAIN, "list_tools", {}, blocking=True, return_response=True
    )
    assert public["tools"] == []


async def test_amap_metadata_has_independent_identity_and_readonly_schema(
    hass, amap_entry, admin_context
):
    response = await hass.services.async_call(
        DOMAIN,
        "list_tools",
        {},
        context=admin_context,
        blocking=True,
        return_response=True,
    )
    assert {tool["name"] for tool in response["tools"]} == {"find_places", "geocode"}
    for tool in response["tools"]:
        assert tool["api_id"] == AMAP_API_ID
        assert tool["read_only_basis"] == "annotation"
        assert tool["parameters"]["additionalProperties"] is False
    places = next(tool for tool in response["tools"] if tool["name"] == "find_places")
    assert places["parameters"]["properties"]["query"]["maxLength"] == 80
    assert places["parameters"]["properties"]["limit"]["maximum"] == 20
    assert "default" not in places["parameters"]["properties"]["limit"]


@pytest.mark.parametrize(
    "data",
    [
        {"status": "0", "infocode": "10001", "info": FAKE_KEY},
        {"status": "0", "infocode": "10003"},
        {"status": "0", "infocode": "10044"},
        {},
        [],
        {"status": "1"},
        {"status": "1", "pois": {}},
        {"status": "1", "pois": [{}]},
        {"status": "1", "pois": ["bad"]},
        {"status": "1", "pois": [{"name": "示例", "location": "91,181"}]},
    ],
)
async def test_key_quota_and_malformed_responses_do_not_become_empty_success(
    hass, amap_entry, admin_context, aioclient_mock, caplog, data
):
    aioclient_mock.get(f"{ORIGIN}/v5/place/text", json=data)
    response = await call(hass, admin_context)
    assert response["error_code"] == "upstream_error"
    assert response["result"] is None
    assert response["outcome_unknown"] is False
    assert FAKE_KEY not in json.dumps(response) + caplog.text
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize("status", [301, 302, 403, 429, 500])
async def test_http_errors_do_not_follow_redirects_or_retry(
    hass, amap_entry, admin_context, aioclient_mock, status
):
    aioclient_mock.get(
        f"{ORIGIN}/v5/place/text",
        status=status,
        text=FAKE_KEY,
        headers={"Location": "https://evil.invalid"},
    )
    response = await call(hass, admin_context)
    assert response["error_code"] == "upstream_error"
    assert FAKE_KEY not in json.dumps(response)
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    "body", [b"not json", b"\xff", b"[" * 10000, b" " * (MAX_AMAP_BYTES + 1)]
)
async def test_bounded_response_reader_rejects_invalid_or_oversized_body(
    hass, amap_entry, admin_context, aioclient_mock, body
):
    aioclient_mock.get(f"{ORIGIN}/v5/place/text", content=body)
    assert (await call(hass, admin_context))["error_code"] == "upstream_error"


@pytest.mark.parametrize(
    "error", [ClientConnectionError(FAKE_KEY), TimeoutError(FAKE_KEY)]
)
async def test_network_failures_are_fixed_and_private(
    hass, amap_entry, admin_context, aioclient_mock, caplog, error
):
    aioclient_mock.get(f"{ORIGIN}/v5/place/text", exc=error)
    response = await call(hass, admin_context)
    assert response["error_code"] == "upstream_error"
    assert FAKE_KEY not in json.dumps(response) + caplog.text
    assert aioclient_mock.call_count == 1


async def test_cancellation_propagates_without_retry(hass, amap_entry, admin_context):
    with patch.object(
        AmapClient, "find_places", side_effect=asyncio.CancelledError
    ) as execute:
        with pytest.raises(asyncio.CancelledError):
            await call(hass, admin_context)
        assert execute.call_count == 1


async def test_large_pois_keep_useful_nested_content_under_result_budget(
    hass, amap_entry, admin_context, aioclient_mock
):
    rows = [
        {
            **deepcopy(PLACE),
            "name": f"示例{index}",
            "business": {"opentime_week": "资料😀" * 1000},
        }
        for index in range(20)
    ]
    aioclient_mock.get(f"{ORIGIN}/v5/place/text", json={"status": "1", "pois": rows})
    response = await call(hass, admin_context, arguments={"query": "咖啡", "limit": 20})
    assert response["success"] is True
    assert response["truncated"] is True
    assert response["result"]["results"][0]["name"] == "示例0"
    assert response["result"]["results"][0]["regular_open_hours"]
    assert len(json.dumps(response, ensure_ascii=False).encode()) <= MAX_RESPONSE_BYTES


async def test_upstream_key_echo_is_redacted_even_from_public_fields(
    hass, amap_entry, admin_context, aioclient_mock
):
    aioclient_mock.get(
        f"{ORIGIN}/v5/place/text",
        json={"status": "1", "pois": [{"name": f"provider echoed {FAKE_KEY}"}]},
    )
    response = await call(hass, admin_context)
    assert response["success"] is True
    assert FAKE_KEY not in json.dumps(response)


async def test_keyless_setup_and_configuration_changes_grant_no_access(
    hass, bridge_entry, admin_context, aioclient_mock
):
    result = await hass.config_entries.options.async_init(bridge_entry.entry_id)
    saved = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_AMAP_KEY: FAKE_KEY,
            CONF_AMAP_CITY: "北京市",
            CONF_AMAP_LOCATION: "116.397499,39.908722",
        },
    )
    assert saved["type"] is FlowResultType.CREATE_ENTRY
    assert not bridge_entry.options[CONF_ENABLED]
    assert bridge_entry.options[CONF_ALLOWED_TOOLS] == ""
    assert (await call(hass, admin_context))["error_code"] == "gateway_disabled"
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "field,value",
    [
        (CONF_AMAP_KEY, "bad"),
        (CONF_AMAP_LOCATION, "181,39"),
        (CONF_AMAP_CITY, "字" * 81),
    ],
)
async def test_invalid_amap_settings_are_not_saved(hass, bridge_entry, field, value):
    flow = await hass.config_entries.options.async_init(bridge_entry.entry_id)
    response = await hass.config_entries.options.async_configure(
        flow["flow_id"], {field: value}
    )
    assert response["type"] is FlowResultType.FORM
    assert response["errors"] == {"base": "invalid_amap_options"}
    assert bridge_entry.options == {}


async def test_missing_key_and_native_arguments_fail_without_http(
    hass, amap_entry, admin_context, aioclient_mock
):
    hass.config_entries.async_update_entry(
        amap_entry, options={**amap_entry.options, CONF_AMAP_KEY: ""}
    )
    assert (await call(hass, admin_context))["error_code"] == "upstream_error"
    api = await instance(hass, admin_context)
    result = await api.async_call_tool(
        llm.ToolInput(tool_name="find_places", tool_args={"query": 123})
    )
    assert result.error is True
    assert aioclient_mock.call_count == 0


async def test_amap_registry_unloads_reloads_and_removes_once(
    hass, amap_entry, admin_context
):
    assert sum(api.id == AMAP_API_ID for api in llm.async_get_apis(hass)) == 1
    assert await hass.config_entries.async_unload(amap_entry.entry_id)
    assert not any(api.id == AMAP_API_ID for api in llm.async_get_apis(hass))
    assert await hass.config_entries.async_setup(amap_entry.entry_id)
    assert await hass.config_entries.async_reload(amap_entry.entry_id)
    assert sum(api.id == AMAP_API_ID for api in llm.async_get_apis(hass)) == 1
    await hass.config_entries.async_remove(amap_entry.entry_id)
    assert not any(api.id == AMAP_API_ID for api in llm.async_get_apis(hass))


@pytest.mark.upstream
async def test_original_eoaic2_script_calls_amap_through_generic_example(
    hass, amap_entry, admin_context, aioclient_mock, upstream_script_function
):
    config = yaml.safe_load((ROOT / "examples/eoaic2_call_tool.yaml").read_text())[0][
        "function"
    ]
    aioclient_mock.get(f"{ORIGIN}/v5/place/text", json={"status": "1", "pois": [PLACE]})
    api = await instance(hass, admin_context)
    response = await upstream_script_function.execute(
        hass,
        upstream_script_function.validate_schema(config),
        {
            "api_id": AMAP_API_ID,
            "tool_name": "find_places",
            "tool_args": {"query": "咖啡"},
        },
        api.llm_context,
        [],
    )
    assert response["success"] is True
    assert response["result"]["results"][0]["name"] == "示例咖啡店"


@pytest.mark.parametrize("value", ["180,90", "-180,-90", "0,0", "116.397499,39.908722"])
def test_gcj02_coordinate_boundaries(value):
    assert validate_location(value) == value


async def test_client_cannot_send_to_arbitrary_endpoints():
    client = AmapClient(AsyncMock(), FAKE_KEY)
    with pytest.raises(AmapError, match="unsupported_endpoint"):
        await client._request("https://evil.invalid", {})


@pytest.mark.parametrize("change", ["key", "permission", "user"])
async def test_native_call_rechecks_configuration_and_identity_after_await(
    hass, amap_entry, admin_context, aioclient_mock, change
):
    api = await instance(hass, admin_context)
    checks = 0

    async def revoke(*args):
        nonlocal checks
        checks += 1
        if checks == 2:
            if change == "user":
                admin_context.user_id = None
            else:
                field, value = (
                    (CONF_AMAP_KEY, "") if change == "key" else (CONF_ENABLED, False)
                )
                hass.config_entries.async_update_entry(
                    amap_entry, options={**amap_entry.options, field: value}
                )
        return True

    with patch(
        "custom_components.eoai_tools_bridge.amap.async_is_admin", side_effect=revoke
    ):
        result = await api.async_call_tool(
            llm.ToolInput(tool_name="find_places", tool_args={"query": "咖啡"})
        )
    assert result.error is True
    assert aioclient_mock.call_count == 0


def test_invalid_coordinate_types():
    with pytest.raises(vol.Invalid):
        validate_location(None)


async def test_readiness_does_not_call_amap_serializer(hass, amap_entry, admin_context):
    with patch(
        "custom_components.eoai_tools_bridge.amap.amap_serializer",
        side_effect=AssertionError("readiness serialized parameters"),
    ):
        response = await hass.services.async_call(
            DOMAIN,
            "check_tools",
            {},
            context=admin_context,
            blocking=True,
            return_response=True,
        )
    assert response["success"] is True
    assert {row["status"] for row in response["tools"]} == {"ready"}


async def test_bad_map_settings_do_not_disable_existing_search(
    hass, gateway_entry, search_api, admin_context
):
    hass.config_entries.async_update_entry(
        gateway_entry,
        options={
            **gateway_entry.options,
            CONF_AMAP_KEY: "bad stored key",
            CONF_AMAP_LOCATION: "invalid",
        },
    )
    response = await hass.services.async_call(
        DOMAIN,
        "call_tool",
        {
            "api_id": "llm_intents",
            "tool_name": "search_web",
            "tool_args": {"query": "test"},
        },
        context=admin_context,
        blocking=True,
        return_response=True,
    )
    assert response["success"] is True


@pytest.mark.parametrize(
    "rows", [[{}], ["bad"], [{"formatted_address": "示例", "location": "bad"}]]
)
async def test_malformed_geocodes_fail_instead_of_selecting_a_destination(
    hass, amap_entry, admin_context, aioclient_mock, rows
):
    aioclient_mock.get(
        f"{ORIGIN}/v3/geocode/geo", json={"status": "1", "geocodes": rows}
    )
    response = await call(hass, admin_context, "geocode", {"address": "示例路1号"})
    assert response["error_code"] == "upstream_error"
    assert response["result"] is None
