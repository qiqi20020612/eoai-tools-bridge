"""Real HA policy/script dispatch and simulated Amap route/geocode endpoints."""

import asyncio
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from homeassistant.core import Context
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import llm
from test_amap import FAKE_KEY, ORIGIN, instance

from custom_components.eoai_tools_bridge.amap import (
    AMAP_API_ID,
    CONF_AMAP_CITY,
    CONF_AMAP_HOME,
    CONF_AMAP_KEY,
    CONF_AMAP_LOCATION,
    CONF_AMAP_MODE,
)
from custom_components.eoai_tools_bridge.amap_client import AmapClient
from custom_components.eoai_tools_bridge.amap_routes import (
    FUTURE_DRIVING_PATH,
    ROUTE_MODES,
    ROUTE_PATHS,
)
from custom_components.eoai_tools_bridge.const import (
    CONF_ALLOWED_TOOLS,
    CONF_ENABLED,
    DOMAIN,
    MAX_RESPONSE_BYTES,
)

ROOT = Path(__file__).resolve().parents[1]
HOME = "116.434307,39.90909"
DESTINATION = "116.397499,39.908722"
OTHER = "116.412422,39.908966"
DEPARTURE = "2026-10-21T09:00:00+08:00"
START_MS = int(datetime.fromisoformat(DEPARTURE).timestamp()) * 1000
V5 = {
    "status": "1",
    "route": {"paths": [{"distance": "1234.5", "cost": {"duration": "600"}}]},
}
TRANSIT = {
    "status": "1",
    "route": {"transits": [{"distance": "2345", "duration": "1200"}]},
}
BICYCLE = {
    "status": "1",
    "route": {"paths": [{"distance": "1234.5", "duration": "600"}]},
}
FUTURE = {
    "errcode": 0,
    "data": {
        "paths": [{"distance": 3456}],
        "time_infos": [
            {"starttime": START_MS, "elements": [{"pathindex": 0, "duration": 12.5}]}
        ],
    },
}


@pytest.fixture
def routes_entry(hass, gateway_entry):
    hass.config_entries.async_update_entry(
        gateway_entry,
        options={
            **gateway_entry.options,
            CONF_ALLOWED_TOOLS: f"{AMAP_API_ID}/get_route",
            CONF_AMAP_KEY: FAKE_KEY,
            CONF_AMAP_HOME: HOME,
            CONF_AMAP_CITY: "北京市",
        },
    )
    return gateway_entry


@pytest.fixture(autouse=True)
def route_clock(freezer):
    freezer.move_to("2026-10-20T00:00:00+00:00")


async def call_route(hass, context, arguments=None):
    return await hass.services.async_call(
        DOMAIN,
        "call_tool",
        {
            "api_id": AMAP_API_ID,
            "tool_name": "get_route",
            "tool_args": {"destination": DESTINATION}
            if arguments is None
            else arguments,
        },
        context=context,
        blocking=True,
        return_response=True,
    )


def geocoded(address, location=HOME, city="北京市", *, ambiguous=False):
    longitude, latitude = map(float, location.split(","))
    row = {
        "address": address,
        "location": {"longitude": longitude, "latitude": latitude},
        "city": city,
        "match_level": "门牌号",
    }
    return {
        "results": [row] * (2 if ambiguous else 1),
        "ambiguous": ambiguous,
        "results_limited": False,
    }


@pytest.mark.parametrize("mode", ROUTE_MODES)
@pytest.mark.parametrize("native", [False, True])
async def test_all_modes_map_to_their_own_endpoints_without_google_or_retries(
    hass, routes_entry, admin_context, aioclient_mock, mode, native
):
    aioclient_mock.get(
        f"{ORIGIN}{ROUTE_PATHS[mode]}",
        json=TRANSIT if mode == "TRANSIT" else BICYCLE if mode == "BICYCLE" else V5,
    )
    args = {"destination": DESTINATION, "mode": mode}
    if native:
        api = await instance(hass, admin_context)
        result = await api.async_call_tool(
            llm.ToolInput(tool_name="get_route", tool_args=args)
        )
        assert not result.error
        body = result.data
    else:
        response = await call_route(hass, admin_context, args)
        assert response["success"] is True
        assert response["outcome_unknown"] is False
        body = response["result"]
    assert body["status"] == "ok"
    assert body["origin_source"] == "configured_home"
    assert body["origin"]["query"] == HOME
    assert body["travel_mode"] == mode
    assert body["coordinate_system"] == "GCJ-02"
    assert body["route"]["duration_seconds"] == (1200 if mode == "TRANSIT" else 600)
    assert body["route"]["distance_meters"] == (2345 if mode == "TRANSIT" else 1234.5)
    assert body["route"]["duration"] == ("20 min" if mode == "TRANSIT" else "10 min")
    assert aioclient_mock.call_count == 1
    params = aioclient_mock.mock_calls[0][1].query
    assert params["origin"] == HOME
    assert params["destination"] == DESTINATION
    assert params["key"] == FAKE_KEY
    if mode == "TRANSIT":
        assert (params["city"], params["cityd"]) == ("北京市", "北京市")
        assert "date" not in params and "time" not in params
    else:
        assert params["show_fields"] == "cost"


@pytest.mark.parametrize("home", [HOME, "", "北京市示例路1号"])
async def test_explicit_origin_overrides_home_and_nearby_center(
    hass, routes_entry, admin_context, aioclient_mock, home
):
    hass.config_entries.async_update_entry(
        routes_entry,
        options={
            **routes_entry.options,
            CONF_AMAP_HOME: home,
            CONF_AMAP_LOCATION: "121.473701,31.230416",
            CONF_AMAP_MODE: "WALK",
        },
    )
    aioclient_mock.get(f"{ORIGIN}{ROUTE_PATHS['DRIVE']}", json=V5)
    response = await call_route(
        hass,
        admin_context,
        {"origin": OTHER, "destination": DESTINATION, "mode": "DRIVE"},
    )
    assert response["success"] is True
    assert response["result"]["origin_source"] == "argument"
    assert aioclient_mock.mock_calls[0][1].query["origin"] == OTHER
    assert aioclient_mock.call_count == 1


async def test_omitted_mode_inherits_configuration_not_static_function_default(
    hass, routes_entry, admin_context, aioclient_mock
):
    hass.config_entries.async_update_entry(
        routes_entry, options={**routes_entry.options, CONF_AMAP_MODE: "WALK"}
    )
    aioclient_mock.get(f"{ORIGIN}{ROUTE_PATHS['WALK']}", json=V5)
    assert (await call_route(hass, admin_context))["result"]["travel_mode"] == "WALK"


async def test_address_resolution_preserves_endpoint_identity_and_cross_city(
    hass, routes_entry, admin_context, aioclient_mock
):
    aioclient_mock.get(f"{ORIGIN}{ROUTE_PATHS['TRANSIT']}", json=TRANSIT)
    with patch.object(
        AmapClient,
        "geocode",
        side_effect=[
            geocoded("北京市示例起点", HOME),
            geocoded("上海市示例终点", DESTINATION, "上海市"),
        ],
    ) as resolve:
        response = await call_route(
            hass,
            admin_context,
            {
                "origin": "示例起点",
                "destination": "示例终点",
                "origin_city": "北京市",
                "destination_city": "上海市",
                "mode": "TRANSIT",
            },
        )
    assert response["success"] is True
    assert resolve.await_args_list[0].args == ("示例起点",)
    assert resolve.await_args_list[1].kwargs == {"city": "上海市"}
    params = aioclient_mock.mock_calls[0][1].query
    assert (params["city"], params["cityd"]) == ("北京市", "上海市")
    assert (params["origin"], params["destination"]) == (HOME, DESTINATION)
    assert response["result"]["destination"]["address"] == "上海市示例终点"


async def test_actual_geocoding_http_is_used_for_text_home_and_destination(
    hass, routes_entry, admin_context, aioclient_mock
):
    hass.config_entries.async_update_entry(
        routes_entry,
        options={**routes_entry.options, CONF_AMAP_HOME: "北京市示例家庭地址"},
    )
    aioclient_mock.get(
        f"{ORIGIN}/v3/geocode/geo",
        json={
            "status": "1",
            "geocodes": [
                {
                    "formatted_address": "北京市示例地址",
                    "location": HOME,
                    "city": "北京市",
                    "level": "门牌号",
                }
            ],
        },
    )
    aioclient_mock.get(f"{ORIGIN}{ROUTE_PATHS['DRIVE']}", json=V5)
    response = await call_route(hass, admin_context, {"destination": "北京市示例终点"})
    assert response["success"] is True
    assert aioclient_mock.call_count == 3
    assert [c[1].query.get("address") for c in aioclient_mock.mock_calls[:2]] == [
        "北京市示例家庭地址",
        "北京市示例终点",
    ]


@pytest.mark.parametrize("endpoint", ["origin", "destination"])
@pytest.mark.parametrize("rows", [0, 2, 7])
async def test_ambiguous_and_missing_addresses_stop_before_routing(
    hass, routes_entry, admin_context, aioclient_mock, endpoint, rows
):
    row = {"formatted_address": "北京市示例地址", "location": HOME, "city": "北京市"}
    aioclient_mock.get(
        f"{ORIGIN}/v3/geocode/geo", json={"status": "1", "geocodes": [row] * rows}
    )
    args = {"origin": HOME, "destination": DESTINATION, endpoint: "示例地址"}
    response = await call_route(hass, admin_context, args)
    assert response["success"] is True
    result = response["result"]
    assert result["route"] is None
    assert result["status"] == ("needs_clarification" if rows else "no_match")
    assert result["endpoint"] == endpoint
    assert len(result["candidates"]) == min(rows, 5)
    assert result["ambiguous"] is bool(rows)
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize("city", ["", "110000"])
async def test_transit_coordinates_need_city_names_or_citycodes_not_adcodes(
    hass, routes_entry, admin_context, aioclient_mock, city
):
    hass.config_entries.async_update_entry(
        routes_entry, options={**routes_entry.options, CONF_AMAP_CITY: city}
    )
    response = await call_route(
        hass, admin_context, {"destination": DESTINATION, "mode": "TRANSIT"}
    )
    assert response["result"]["status"] == "city_required"
    assert response["result"]["route"] is None
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize("mode", ["DRIVE", "TRANSIT"])
async def test_future_departure_uses_actual_time_endpoint_units_and_timezone(
    hass, routes_entry, admin_context, aioclient_mock, mode
):
    path = FUTURE_DRIVING_PATH if mode == "DRIVE" else ROUTE_PATHS[mode]
    aioclient_mock.get(f"{ORIGIN}{path}", json=FUTURE if mode == "DRIVE" else TRANSIT)
    response = await call_route(
        hass,
        admin_context,
        {"destination": DESTINATION, "mode": mode, "departure_time": DEPARTURE},
    )
    assert response["success"] is True
    body = response["result"]
    assert body["departure_time"] == "2026-10-21T01:00:00+00:00"
    assert body["route"]["duration_seconds"] == (750 if mode == "DRIVE" else 1200)
    assert body["estimated_arrival"] == (
        "2026-10-21T01:12:30+00:00" if mode == "DRIVE" else "2026-10-21T01:20:00+00:00"
    )
    params = aioclient_mock.mock_calls[0][1].query
    if mode == "DRIVE":
        assert params["firsttime"] == str(START_MS // 1000)
        assert params["count"] == "1"
        assert "show_fields" not in params
    else:
        assert (params["date"], params["time"]) == ("2026-10-21", "09:00")
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize("mode", ["WALK", "BICYCLE", "TWO_WHEELER"])
async def test_timed_static_modes_fail_without_dropping_departure_time(
    hass, routes_entry, admin_context, aioclient_mock, mode
):
    response = await call_route(
        hass,
        admin_context,
        {"destination": DESTINATION, "mode": mode, "departure_time": DEPARTURE},
    )
    assert response["success"] is False
    assert response["outcome_unknown"] is False
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "value", ["2026-10-19T00:00:00+00:00", "2026-10-28T00:00:00+00:00"]
)
async def test_past_or_beyond_seven_days_is_not_replaced_by_now(
    hass, routes_entry, admin_context, aioclient_mock, value
):
    assert not (
        await call_route(
            hass, admin_context, {"destination": DESTINATION, "departure_time": value}
        )
    )["success"]
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"destination": None},
        {"destination": " "},
        {"destination": "字" * 501},
        {"destination": "181,39"},
        {"destination": "116.1234567,39"},
        {"destination": "1e2,39"},
        {"destination": "nan,39"},
        {"destination": "116 39"},
        {"destination": "116;39"},
        {"destination": "116|39"},
        {"destination": "116,91"},
        {"destination": DESTINATION, "origin": "这里"},
        {"destination": DESTINATION, "origin": None},
        {"destination": DESTINATION, "origin": ""},
        {"destination": DESTINATION, "mode": "ELECTRIC_BICYCLE"},
        {"destination": DESTINATION, "departure_time": "tomorrow"},
        {"destination": DESTINATION, "departure_time": "2026-10-21T09:00:00"},
        {"destination": DESTINATION, "departure_time": 123},
        {"destination": DESTINATION, "departure_time": "0001-01-01T00:00:00+23:00"},
        {"destination": DESTINATION, "origin_city": 10},
        {"destination": DESTINATION, "waypoints": [HOME]},
        {"destination": DESTINATION, "key": FAKE_KEY},
        {"destination": DESTINATION, "url": "https://evil.invalid"},
    ],
)
async def test_invalid_native_arguments_are_rejected_before_any_http(
    hass, routes_entry, admin_context, aioclient_mock, arguments
):
    response = await call_route(hass, admin_context, arguments)
    assert response["error_code"] == "invalid_args"
    assert aioclient_mock.call_count == 0


async def test_missing_home_does_not_use_ha_home_or_nearby_center(
    hass, routes_entry, admin_context, aioclient_mock
):
    hass.config_entries.async_update_entry(
        routes_entry,
        options={**routes_entry.options, CONF_AMAP_HOME: "", CONF_AMAP_LOCATION: HOME},
    )
    assert not (await call_route(hass, admin_context))["success"]
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "state",
    ["disabled", "unlisted", "missing_user", "non_admin", "inactive", "unloaded"],
)
async def test_route_native_api_preserves_gateway_permissions(
    hass,
    routes_entry,
    admin_context,
    hass_read_only_user,
    hass_admin_user,
    aioclient_mock,
    state,
):
    api = await instance(hass, admin_context)
    if state == "disabled":
        hass.config_entries.async_update_entry(
            routes_entry, options={**routes_entry.options, CONF_ENABLED: False}
        )
    elif state == "unlisted":
        hass.config_entries.async_update_entry(
            routes_entry,
            options={
                **routes_entry.options,
                CONF_ALLOWED_TOOLS: f"{AMAP_API_ID}/geocode",
            },
        )
    elif state == "missing_user":
        api.llm_context.context = Context()
    elif state == "non_admin":
        api.llm_context.context = Context(user_id=hass_read_only_user.id)
    elif state == "inactive":
        hass_admin_user.is_active = False
    else:
        assert await hass.config_entries.async_unload(routes_entry.entry_id)
    result = await api.async_call_tool(
        llm.ToolInput(tool_name="get_route", tool_args={"destination": DESTINATION})
    )
    assert result.error
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize("change", ["policy", "key", "home", "user"])
@pytest.mark.parametrize("stage", ["geocode", "route"])
async def test_authorization_is_rechecked_between_requests_and_before_returning_data(
    hass, routes_entry, admin_context, aioclient_mock, change, stage
):
    def revoke():
        if change == "user":
            admin_context.user_id = None
        else:
            field, value = {
                "policy": (CONF_ENABLED, False),
                "key": (CONF_AMAP_KEY, ""),
                "home": (CONF_AMAP_HOME, OTHER),
            }[change]
            hass.config_entries.async_update_entry(
                routes_entry, options={**routes_entry.options, field: value}
            )

    async def resolved(*args, **kwargs):
        revoke()
        return geocoded("不得在撤权后继续使用的地址")

    async def routed(*args, **kwargs):
        revoke()
        return deepcopy(V5)

    method, replacement = (
        ("geocode", resolved) if stage == "geocode" else ("_request", routed)
    )
    with patch.object(AmapClient, method, side_effect=replacement) as execute:
        response = await call_route(
            hass,
            admin_context,
            {
                "origin": "示例地址" if stage == "geocode" else HOME,
                "destination": DESTINATION,
            },
        )
    assert response["success"] is False
    assert response["result"] is None
    assert "不得在撤权后" not in json.dumps(response, ensure_ascii=False)
    assert execute.await_count == 1
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize("mode", ROUTE_MODES)
async def test_provider_permission_failures_never_fallback_or_echo_key(
    hass, routes_entry, admin_context, aioclient_mock, caplog, mode
):
    aioclient_mock.get(
        f"{ORIGIN}{ROUTE_PATHS[mode]}", json={"status": "0", "info": FAKE_KEY}
    )
    response = await call_route(
        hass, admin_context, {"destination": DESTINATION, "mode": mode}
    )
    assert response["error_code"] == "upstream_error"
    assert response["result"] is None
    assert FAKE_KEY not in json.dumps(response) + caplog.text
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    "data",
    [
        {"status": "1"},
        {"status": "1", "route": []},
        {"status": "1", "route": {"paths": {}}},
        {"status": "1", "route": {"paths": [{}]}},
        {"status": "1", "route": {"paths": [{"distance": "1", "cost": {}}]}},
        {
            "status": "1",
            "route": {"paths": [{"distance": "NaN", "cost": {"duration": "600"}}]},
        },
        {
            "status": "1",
            "route": {"paths": [{"distance": "1", "cost": {"duration": True}}]},
        },
    ],
)
async def test_malformed_routes_are_not_empty_success_or_zero_estimates(
    hass, routes_entry, admin_context, aioclient_mock, data
):
    aioclient_mock.get(f"{ORIGIN}{ROUTE_PATHS['DRIVE']}", json=data)
    response = await call_route(hass, admin_context)
    assert response["success"] is False
    assert response["result"] is None


@pytest.mark.parametrize("mode", ROUTE_MODES)
async def test_legitimate_no_routes_are_explicit_and_have_no_invented_duration(
    hass, routes_entry, admin_context, aioclient_mock, mode
):
    aioclient_mock.get(
        f"{ORIGIN}{ROUTE_PATHS[mode]}",
        json={
            "status": "1",
            "route": {"transits" if mode == "TRANSIT" else "paths": []},
        },
    )
    response = await call_route(
        hass, admin_context, {"destination": DESTINATION, "mode": mode}
    )
    assert response["success"] is True
    assert response["result"]["status"] == "no_route"
    assert response["result"]["route"] is None
    assert "duration" not in json.dumps(response)


async def test_future_driving_missing_or_wrong_time_does_not_use_current_route(
    hass, routes_entry, admin_context, aioclient_mock
):
    body = deepcopy(FUTURE)
    body["data"]["time_infos"][0]["starttime"] += 1000
    aioclient_mock.get(f"{ORIGIN}{FUTURE_DRIVING_PATH}", json=body)
    response = await call_route(
        hass, admin_context, {"destination": DESTINATION, "departure_time": DEPARTURE}
    )
    assert response["error_code"] == "upstream_error"
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize("errcode", [False, 0.0, 1, "10044", None])
async def test_future_driving_errors_and_bad_statuses_never_fallback(
    hass, routes_entry, admin_context, aioclient_mock, errcode
):
    data = {**deepcopy(FUTURE), "errcode": errcode, "errmsg": FAKE_KEY}
    aioclient_mock.get(f"{ORIGIN}{FUTURE_DRIVING_PATH}", json=data)
    response = await call_route(
        hass, admin_context, {"destination": DESTINATION, "departure_time": DEPARTURE}
    )
    assert response["error_code"] == "upstream_error"
    assert FAKE_KEY not in json.dumps(response)
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize("body", [V5, BICYCLE])
async def test_bicycle_accepts_documented_cost_or_live_top_level_duration(
    hass, routes_entry, admin_context, aioclient_mock, body
):
    aioclient_mock.get(f"{ORIGIN}{ROUTE_PATHS['BICYCLE']}", json=body)
    response = await call_route(
        hass, admin_context, {"destination": DESTINATION, "mode": "BICYCLE"}
    )
    assert response["result"]["route"]["duration_seconds"] == 600


async def test_transit_uses_china_calendar_date_and_effective_minute_precision(
    hass, routes_entry, admin_context, aioclient_mock
):
    aioclient_mock.get(f"{ORIGIN}{ROUTE_PATHS['TRANSIT']}", json=TRANSIT)
    response = await call_route(
        hass,
        admin_context,
        {
            "destination": DESTINATION,
            "mode": "TRANSIT",
            "departure_time": "2026-10-21T20:30:59-04:00",
        },
    )
    assert response["success"]
    assert response["result"]["departure_time"] == "2026-10-22T00:30:00+00:00"
    params = aioclient_mock.mock_calls[0][1].query
    assert (params["date"], params["time"]) == ("2026-10-22", "08:30")


async def test_new_route_options_on_disabled_entry_grant_no_access(
    hass, bridge_entry, admin_context, aioclient_mock
):
    flow = await hass.config_entries.options.async_init(bridge_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {CONF_AMAP_HOME: HOME, CONF_AMAP_MODE: "WALK"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not bridge_entry.options[CONF_ENABLED]
    assert bridge_entry.options[CONF_ALLOWED_TOOLS] == ""
    assert (await call_route(hass, admin_context))["error_code"] == "gateway_disabled"
    assert aioclient_mock.call_count == 0


async def test_route_metadata_performs_no_http_or_parameter_execution_and_hides_home(
    hass, routes_entry, admin_context, aioclient_mock
):
    hass.config_entries.async_update_entry(
        routes_entry, options={**routes_entry.options, CONF_AMAP_HOME: "私有家庭地址"}
    )
    api = await instance(hass, admin_context)
    tool = next(t for t in api.tools if t.name == "get_route")
    with (
        patch.object(
            AmapClient,
            "_request",
            side_effect=AssertionError("metadata requested HTTP"),
        ),
        patch.object(
            tool.parameters,
            "_compiled",
            side_effect=AssertionError("metadata executed parameters"),
        ),
    ):
        for service, arguments in (
            ("list_tools", {}),
            ("check_tools", {}),
            ("describe_tool", {"api_id": AMAP_API_ID, "tool_name": "get_route"}),
        ):
            result = await hass.services.async_call(
                DOMAIN,
                service,
                arguments,
                context=admin_context,
                blocking=True,
                return_response=True,
            )
            assert result["success"] is True
            assert "私有家庭地址" not in json.dumps(result, ensure_ascii=False)
            assert FAKE_KEY not in json.dumps(result)
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    "field,value",
    [
        (CONF_AMAP_HOME, "这里"),
        (CONF_AMAP_HOME, "181,30"),
        (CONF_AMAP_HOME, "字" * 501),
        (CONF_AMAP_MODE, "CAR"),
    ],
)
async def test_bad_home_and_route_mode_options_are_not_saved(
    hass, bridge_entry, field, value
):
    flow = await hass.config_entries.options.async_init(bridge_entry.entry_id)
    if field == CONF_AMAP_MODE:
        with pytest.raises(InvalidData):
            await hass.config_entries.options.async_configure(
                flow["flow_id"], {field: value}
            )
        assert bridge_entry.options == {}
        return
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {field: value}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_amap_options"}
    assert bridge_entry.options == {}


async def test_route_settings_do_not_grant_permission_and_empty_home_clears_saved_value(
    hass, routes_entry, admin_context, aioclient_mock
):
    flow = await hass.config_entries.options.async_init(routes_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {CONF_AMAP_HOME: "", CONF_AMAP_MODE: "WALK"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert routes_entry.options[CONF_AMAP_HOME] == ""
    assert routes_entry.options[CONF_ENABLED] is True
    assert routes_entry.options[CONF_ALLOWED_TOOLS] == f"{AMAP_API_ID}/get_route"
    assert not (await call_route(hass, admin_context))["success"]
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize("failure", ["cancel", "timeout"])
async def test_multi_request_work_propagates_cancellation_and_has_a_total_deadline(
    hass, routes_entry, admin_context, failure
):
    async def slow(*args, **kwargs):
        await asyncio.sleep(0)

    if failure == "cancel":
        with patch.object(AmapClient, "_request", side_effect=asyncio.CancelledError):
            with pytest.raises(asyncio.CancelledError):
                await call_route(hass, admin_context)
    else:
        with (
            patch("custom_components.eoai_tools_bridge.amap.TOOL_TIMEOUT_SECONDS", 0),
            patch.object(AmapClient, "_request", side_effect=slow),
        ):
            assert not (await call_route(hass, admin_context))["success"]


@pytest.mark.upstream
@pytest.mark.parametrize("explicit_origin", [False, True])
async def test_original_script_uses_default_home_or_explicit_origin_with_real_gateway(
    hass,
    routes_entry,
    admin_context,
    aioclient_mock,
    upstream_script_function,
    explicit_origin,
):
    example = yaml.safe_load(
        (ROOT / "examples/eoaic2_get_route_amap.yaml").read_text()
    )[0]
    api = await instance(hass, admin_context)
    aioclient_mock.get(f"{ORIGIN}{ROUTE_PATHS['DRIVE']}", json=V5)
    args = {
        "destination": DESTINATION,
        **({"origin": OTHER} if explicit_origin else {}),
    }
    response = await upstream_script_function.execute(
        hass,
        upstream_script_function.validate_schema(example["function"]),
        args,
        api.llm_context,
        [],
    )
    assert response["success"] is True
    assert response["result"]["origin_source"] == (
        "argument" if explicit_origin else "configured_home"
    )
    assert aioclient_mock.mock_calls[0][1].query["origin"] == (
        OTHER if explicit_origin else HOME
    )
    assert aioclient_mock.call_count == 1


async def test_large_ambiguity_keeps_valid_candidates_within_existing_payload_budget(
    hass, routes_entry, admin_context, aioclient_mock
):
    aioclient_mock.get(
        f"{ORIGIN}/v3/geocode/geo",
        json={
            "status": "1",
            "geocodes": [
                {
                    "formatted_address": "地址😀" * 1000,
                    "location": HOME,
                    "city": "北京市",
                }
            ]
            * 6,
        },
    )
    response = await call_route(hass, admin_context, {"destination": "示例模糊地址"})
    assert response["success"] is True and response["truncated"] is True
    assert response["result"]["status"] == "needs_clarification"
    assert response["result"]["candidates"][0]["address"]
    assert len(json.dumps(response, ensure_ascii=False).encode()) <= MAX_RESPONSE_BYTES
