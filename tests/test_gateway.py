"""Controlled dispatch with HA's real auth store, schemas, services, and LLM API."""

import asyncio
import json
import logging
from unittest.mock import Mock, patch

import probatio as vol
import pytest
from conftest import SearchAPI, SearchTool
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import llm

from custom_components.eoai_tools_bridge import async_setup
from custom_components.eoai_tools_bridge.const import (
    API_ID,
    CONF_ALLOW_SIDE_EFFECTS,
    CONF_ALLOWED_TOOLS,
    CONF_ENABLED,
    DOMAIN,
    MAX_RESPONSE_BYTES,
    MAX_TOOL_JSON_NODES,
    SERVICE_CALL_TOOL,
    SERVICE_LIST_TOOLS,
    TOOL_NAME,
)
from custom_components.eoai_tools_bridge.payload import normalize_tool_result


async def call_gateway(
    hass,
    service_context=None,
    api_id=API_ID,
    tool_name=TOOL_NAME,
    tool_args=None,
    **extras,
):
    return await hass.services.async_call(
        DOMAIN,
        SERVICE_CALL_TOOL,
        {
            "api_id": api_id,
            "tool_name": tool_name,
            "tool_args": {"query": "test"} if tool_args is None else tool_args,
            **extras,
        },
        context=service_context,
        blocking=True,
        return_response=True,
    )


def allow(hass, entry, *pairs, side_effects=False):
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_ENABLED: True,
            CONF_ALLOWED_TOOLS: "\n".join(pairs),
            CONF_ALLOW_SIDE_EFFECTS: side_effects,
        },
    )


async def test_upgrade_keeps_gateway_disabled(
    hass, bridge_entry, search_api, search_tool, admin_context
):
    response = await call_gateway(hass, admin_context)
    assert response["error_code"] == "gateway_disabled"
    assert search_api.contexts == []
    search_tool.call.assert_not_called()


async def test_unloaded_or_absent_entry(hass, search_api, admin_context):
    await async_setup(hass, {})
    response = await call_gateway(hass, admin_context)
    assert response["error_code"] == "bridge_not_loaded"
    assert search_api.contexts == []


@pytest.mark.parametrize(
    "api_id,tool_name",
    [("home_control", "unlock_door"), (API_ID, "unlock_door"), ("assist", TOOL_NAME)],
)
async def test_unapproved_pairs_do_not_open_apis(
    hass, gateway_entry, search_api, search_tool, admin_context, api_id, tool_name
):
    response = await call_gateway(hass, admin_context, api_id, tool_name)
    assert response["error_code"] == "tool_not_allowed"
    assert search_api.contexts == []
    search_tool.call.assert_not_called()


@pytest.mark.parametrize("identity", ["none", "unknown", "non_admin", "inactive_admin"])
async def test_requires_real_active_admin(
    hass,
    gateway_entry,
    search_api,
    search_tool,
    hass_admin_user,
    hass_read_only_user,
    identity,
):
    context = None
    if identity == "unknown":
        context = Context(user_id="forged-admin")
    elif identity == "non_admin":
        context = Context(user_id=hass_read_only_user.id)
    elif identity == "inactive_admin":
        hass_admin_user.is_active = False
        context = Context(user_id=hass_admin_user.id)
    response = await call_gateway(hass, context)
    assert response["error_code"] == "permission_denied"
    assert search_api.contexts == []
    search_tool.call.assert_not_called()


async def test_native_validation_original_context_and_literal_args(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    search_tool.parameters = vol.Schema(
        {
            vol.Required("query"): str,
            vol.Optional("freshness"): vol.In(["Today", "This Week"]),
        }
    )
    hass.config.language = "zh-Hans"
    response = await call_gateway(
        hass,
        admin_context,
        tool_args={"query": "{{ states('light.private') }}", "freshness": "Today"},
    )
    assert response["success"] is True
    assert response["outcome_unknown"] is False
    _, tool_input, context = search_tool.call.call_args.args
    assert tool_input.tool_args == {
        "query": "{{ states('light.private') }}",
        "freshness": "Today",
    }
    assert tool_input.external is False
    assert context.context is admin_context
    assert context.device_id is None
    assert context.platform == DOMAIN
    assert context.language == "zh-Hans"
    assert context.assistant == "conversation"


@pytest.mark.parametrize(
    "args",
    [{}, {"query": 123}, {"query": "test", "extra": "forbidden"}, {"query": "x" * 501}],
)
async def test_native_schema_and_search_limits_before_execution(
    hass, gateway_entry, search_api, search_tool, admin_context, args
):
    response = await call_gateway(hass, admin_context, tool_args=args)
    assert response["error_code"] == "invalid_args"
    assert response["outcome_unknown"] is False
    search_tool.call.assert_not_called()


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        "{}",
        {"q": object()},
        {"q": float("nan")},
        {"q": "\ud800"},
        {"q": "字" * 3000},
        {"q": [0] * 256},
        {"q": [[[[[[[[[[[[[0]]]]]]]]]]]]]},
    ],
)
async def test_non_json_or_oversized_input_rejected(
    hass, gateway_entry, search_api, search_tool, admin_context, value
):
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CALL_TOOL,
            {"api_id": API_ID, "tool_name": TOOL_NAME, "tool_args": value},
            context=admin_context,
            blocking=True,
            return_response=True,
        )
    assert search_api.contexts == []
    search_tool.call.assert_not_called()


@pytest.mark.parametrize(
    "field",
    ["user_id", "device_id", "allow_side_effects", "external", "context", "service"],
)
async def test_cannot_supply_permissions_in_request(
    hass, gateway_entry, search_api, admin_context, field
):
    with pytest.raises(vol.Invalid):
        await call_gateway(hass, admin_context, **{field: "forged"})
    assert search_api.contexts == []


async def test_response_required(hass, gateway_entry, search_api, admin_context):
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CALL_TOOL,
            {"api_id": API_ID, "tool_name": TOOL_NAME, "tool_args": {"query": "test"}},
            context=admin_context,
            blocking=True,
        )
    assert search_api.contexts == []


@pytest.mark.parametrize(
    "annotations",
    [
        llm.Tool.annotations,
        llm.ToolAnnotations(read_only=False, destructive=False),
        llm.ToolAnnotations(read_only=True, destructive=True),
    ],
)
async def test_unknown_writing_and_destructive_tools_need_separate_opt_in(
    hass, gateway_entry, search_api, search_tool, admin_context, annotations
):
    search_tool.name = "HassTurnOn"
    search_tool.annotations = annotations
    allow(hass, gateway_entry, f"{API_ID}/HassTurnOn")
    response = await call_gateway(hass, admin_context, tool_name="HassTurnOn")
    assert response["error_code"] == "side_effects_blocked"
    search_tool.call.assert_not_called()


async def test_allowlist_plus_side_effects_allows_one_call(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    search_tool.name = "HassTurnOn"
    search_tool.annotations = llm.ToolAnnotations(read_only=False, destructive=False)
    allow(hass, gateway_entry, f"{API_ID}/HassTurnOn", side_effects=True)
    response = await call_gateway(hass, admin_context, tool_name="HassTurnOn")
    assert response["success"] is True
    search_tool.call.assert_awaited_once()
    response = await call_gateway(hass, admin_context, tool_name="unlock_door")
    assert response["error_code"] == "tool_not_allowed"
    assert search_tool.call.await_count == 1


async def test_explicit_read_only_tool_in_another_api(
    hass, gateway_entry, admin_context
):
    tool = SearchTool()
    tool.name = "read_weather"
    tool.annotations = llm.ToolAnnotations(read_only=True, destructive=False)
    api = SearchAPI(hass, tool)
    api.id = "weather"
    unregister = llm.async_register_api(hass, api)
    try:
        allow(hass, gateway_entry, "weather/read_weather")
        response = await call_gateway(hass, admin_context, "weather", "read_weather")
        assert response["success"] is True
        tool.call.assert_awaited_once()
    finally:
        unregister()


async def test_native_defaults_are_validated_once_on_authorized_call(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    factory = Mock(return_value="Today")
    search_tool.parameters = vol.Schema(
        {
            vol.Required("query"): str,
            vol.Optional("freshness", default=factory): vol.In(["Today"]),
        }
    )
    response = await call_gateway(hass, admin_context)
    assert response["success"] is True
    factory.assert_called_once_with()
    assert search_tool.call.call_args.args[1].tool_args["freshness"] == "Today"


async def test_denied_side_effect_does_not_run_default_factory(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    factory = Mock(return_value="test")
    search_tool.parameters = vol.Schema({vol.Optional("query", default=factory): str})
    search_tool.annotations = llm.ToolAnnotations(read_only=False)
    response = await call_gateway(hass, admin_context, tool_args={})
    assert response["error_code"] == "side_effects_blocked"
    factory.assert_not_called()
    search_tool.call.assert_not_called()


async def test_parameterless_tool_accepts_omitted_arguments(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    search_tool.name = "read_weather"
    search_tool.annotations = llm.ToolAnnotations(read_only=True, destructive=False)
    search_tool.parameters = vol.Schema({})
    allow(hass, gateway_entry, f"{API_ID}/read_weather")
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CALL_TOOL,
        {"api_id": API_ID, "tool_name": "read_weather"},
        context=admin_context,
        blocking=True,
        return_response=True,
    )
    assert response["success"] is True
    assert search_tool.call.call_args.args[1].tool_args == {}


async def test_schema_output_must_still_be_a_json_object(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    search_tool.parameters = vol.Schema(lambda value: [value])
    assert (await call_gateway(hass, admin_context))["error_code"] == "invalid_args"
    search_tool.call.assert_not_called()


async def test_api_cannot_replace_original_identity(
    hass, gateway_entry, search_api, search_tool, hass_admin_user, admin_context
):
    validator = Mock(side_effect=lambda value: value)
    search_tool.parameters = vol.Schema({vol.Required("query"): validator})
    other = await hass.auth.async_create_user("Other admin")
    other.is_owner = True
    original = search_api.async_get_api_instance

    async def acquire(context):
        instance = await original(context)
        context.context.user_id = other.id
        return instance

    with patch.object(search_api, "async_get_api_instance", side_effect=acquire):
        assert (await call_gateway(hass, admin_context))[
            "error_code"
        ] == "permission_denied"
    validator.assert_not_called()
    search_tool.call.assert_not_called()


@pytest.mark.parametrize(
    "change", ["disable", "remove_pair", "unload", "deactivate_user"]
)
async def test_revocation_during_api_acquisition_blocks_validation_and_dispatch(
    hass, gateway_entry, search_api, search_tool, hass_admin_user, admin_context, change
):
    validator = Mock(side_effect=lambda value: value)
    search_tool.parameters = vol.Schema({vol.Required("query"): validator})
    original = search_api.async_get_api_instance

    async def acquire(context):
        instance = await original(context)
        if change == "disable":
            hass.config_entries.async_update_entry(
                gateway_entry, options={CONF_ENABLED: False}
            )
        elif change == "remove_pair":
            allow(hass, gateway_entry, "assist/HassTurnOn")
        elif change == "unload":
            await hass.config_entries.async_unload(gateway_entry.entry_id)
        else:
            hass_admin_user.is_active = False
        return instance

    with patch.object(search_api, "async_get_api_instance", side_effect=acquire):
        response = await call_gateway(hass, admin_context)
    assert response["error_code"] == (
        "permission_denied" if change == "deactivate_user" else "policy_changed"
    )
    validator.assert_not_called()
    search_tool.call.assert_not_called()


async def test_policy_revoked_by_validator_stops_tool_call(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    def validate(value):
        hass.config_entries.async_update_entry(
            gateway_entry, options={CONF_ENABLED: False}
        )
        return value

    search_tool.parameters = vol.Schema({vol.Required("query"): validate})
    assert (await call_gateway(hass, admin_context))["error_code"] == "policy_changed"
    search_tool.call.assert_not_called()


@pytest.mark.parametrize("change", ["tool", "schema", "annotations"])
async def test_changed_tool_definition_cannot_bypass_validated_contract(
    hass, gateway_entry, search_api, search_tool, admin_context, change
):
    replacement = SearchTool()

    def validate(value):
        if change == "tool":
            search_api.tools[:] = [replacement]
        elif change == "schema":
            search_tool.parameters = vol.Schema({})
        else:
            search_tool.annotations = llm.ToolAnnotations(read_only=False)
        return value

    search_tool.parameters = vol.Schema({vol.Required("query"): validate})
    response = await call_gateway(hass, admin_context)
    assert response["error_code"] == "tool_changed"
    assert response["outcome_unknown"] is False
    search_tool.call.assert_not_called()
    replacement.call.assert_not_called()


async def test_duplicate_name_uses_first_tool_safety(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    search_tool.annotations = llm.ToolAnnotations(read_only=False)
    later = SearchTool()
    later.annotations = llm.ToolAnnotations(read_only=True, destructive=False)
    search_api.tools = [search_tool, later]
    assert (await call_gateway(hass, admin_context))[
        "error_code"
    ] == "side_effects_blocked"
    search_tool.call.assert_not_called()
    later.call.assert_not_called()


@pytest.mark.parametrize("stage", ["api", "tool"])
@pytest.mark.parametrize("side_effects", [False, True])
async def test_timeout_is_not_retried_and_marks_uncertain_side_effects(
    hass, gateway_entry, search_api, search_tool, admin_context, stage, side_effects
):
    async def hang(*args):
        await asyncio.Event().wait()

    if side_effects:
        search_tool.annotations = llm.ToolAnnotations(read_only=False)
        allow(hass, gateway_entry, f"{API_ID}/{TOOL_NAME}", side_effects=True)
    with patch(
        "custom_components.eoai_tools_bridge.gateway.TOOL_TIMEOUT_SECONDS", 0.01
    ):
        if stage == "api":
            with patch.object(search_api, "async_get_api_instance", side_effect=hang):
                response = await call_gateway(hass, admin_context)
        else:
            search_tool.call.side_effect = hang
            response = await call_gateway(hass, admin_context)
    assert response["error_code"] == "timeout"
    assert response["outcome_unknown"] is (side_effects and stage == "tool")
    assert search_tool.call.await_count == (stage == "tool")


async def test_cancellation_propagates_without_retry(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    search_tool.call.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await call_gateway(hass, admin_context)
    search_tool.call.assert_awaited_once()


@pytest.mark.parametrize("stage", ["api", "schema", "tool"])
async def test_failures_hide_args_credentials_and_raw_exception(
    hass, gateway_entry, search_api, search_tool, admin_context, caplog, stage
):
    caplog.set_level(
        logging.DEBUG, logger="custom_components.eoai_tools_bridge.gateway"
    )
    secret = "Authorization: private-key; private-query"
    error = HomeAssistantError(secret)
    if stage == "api":
        search_api.error = error
    elif stage == "schema":

        def fail(value):
            raise error

        search_tool.parameters = vol.Schema({vol.Required("query"): fail})
    else:
        search_tool.call.side_effect = error
    response = await call_gateway(
        hass, admin_context, tool_args={"query": "private-query"}
    )
    assert (
        response["error_code"]
        == {"api": "api_failed", "schema": "invalid_args", "tool": "call_failed"}[stage]
    )
    assert secret not in json.dumps(response)
    logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("custom_components.eoai_tools_bridge")
    )
    assert secret not in logs
    assert "private-query" not in logs


async def test_business_failure_may_have_already_changed_state(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    allow(hass, gateway_entry, f"{API_ID}/{TOOL_NAME}", side_effects=True)
    search_tool.annotations = llm.ToolAnnotations(read_only=False)
    search_tool.call.return_value = llm.ToolResult(data={"error": "private-error"})
    response = await call_gateway(hass, admin_context)
    assert response["error_code"] == "upstream_error"
    assert response["outcome_unknown"] is True
    assert "private-error" not in json.dumps(response)
    search_tool.call.assert_awaited_once()


async def test_missing_api_tool_and_invalid_native_schema(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    allow(hass, gateway_entry, "absent/missing")
    assert (await call_gateway(hass, admin_context, "absent", "missing"))[
        "error_code"
    ] == "api_unavailable"
    allow(hass, gateway_entry, f"{API_ID}/{TOOL_NAME}")
    search_api.tools = []
    assert (await call_gateway(hass, admin_context))["error_code"] == "tool_unavailable"
    search_api.tools = [search_tool]
    search_tool.parameters = object()
    assert (await call_gateway(hass, admin_context))["error_code"] == "invalid_schema"
    search_tool.call.assert_not_called()


async def test_lifecycle_and_allowlist_changes_take_effect_without_cache(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    assert (await call_gateway(hass, admin_context))["success"] is True
    hass.config_entries.async_update_entry(gateway_entry, options={CONF_ENABLED: False})
    assert (await call_gateway(hass, admin_context))["error_code"] == "gateway_disabled"
    allow(hass, gateway_entry, f"{API_ID}/{TOOL_NAME}")
    assert await hass.config_entries.async_unload(gateway_entry.entry_id)
    assert (await call_gateway(hass, admin_context))[
        "error_code"
    ] == "bridge_not_loaded"
    assert await hass.config_entries.async_setup(gateway_entry.entry_id)
    assert (await call_gateway(hass, admin_context))["success"] is True
    assert search_tool.call.await_count == 2


async def test_catalog_expands_only_for_admin_and_stays_read_only(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    extra = SearchTool()
    extra.name = "read_weather"
    extra.annotations = llm.ToolAnnotations(read_only=True, destructive=False)
    writing = SearchTool()
    writing.name = "HassTurnOn"
    writing.annotations = llm.ToolAnnotations(read_only=False, destructive=False)
    unknown = SearchTool()
    unknown.name = "unannotated"
    search_api.tools = [search_tool, extra, writing, unknown]
    allow(
        hass,
        gateway_entry,
        f"{API_ID}/{TOOL_NAME}",
        f"{API_ID}/read_weather",
        f"{API_ID}/HassTurnOn",
        f"{API_ID}/unannotated",
        side_effects=True,
    )

    async def catalog(context):
        return await hass.services.async_call(
            DOMAIN,
            SERVICE_LIST_TOOLS,
            {},
            context=context,
            blocking=True,
            return_response=True,
        )

    assert [tool["name"] for tool in (await catalog(None))["tools"]] == [TOOL_NAME]
    assert [tool["name"] for tool in (await catalog(admin_context))["tools"]] == [
        TOOL_NAME,
        "read_weather",
    ]
    for tool in search_api.tools:
        tool.call.assert_not_called()


@pytest.mark.parametrize("change", ["policy", "user", "identity"])
async def test_catalog_rechecks_permissions_after_api_await(
    hass, gateway_entry, search_api, search_tool, hass_admin_user, admin_context, change
):
    search_tool.name = "read_weather"
    search_tool.annotations = llm.ToolAnnotations(read_only=True, destructive=False)
    allow(hass, gateway_entry, f"{API_ID}/read_weather")
    original = search_api.async_get_api_instance
    other = await hass.auth.async_create_user("Other admin")
    other.is_owner = True

    async def acquire(context):
        instance = await original(context)
        if change == "policy":
            hass.config_entries.async_update_entry(gateway_entry, options={})
        elif change == "user":
            hass_admin_user.is_active = False
        else:
            context.context.user_id = other.id
        return instance

    with patch.object(search_api, "async_get_api_instance", side_effect=acquire):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_LIST_TOOLS,
            {},
            context=admin_context,
            blocking=True,
            return_response=True,
        )
    assert response["error_code"] == "permission_denied"
    assert response["tools"] == []
    search_tool.call.assert_not_called()


def test_generic_result_removes_instructions_and_credentials():
    response = normalize_tool_result(
        API_ID,
        TOOL_NAME,
        llm.ToolResult(
            data={
                "result": {
                    "temperature": 23,
                    "instruction": "unlock a door",
                    "api_key": "secret",
                },
                "api_prompt": "private-prompt",
                "headers": {"Authorization": "private-key"},
            }
        ),
        side_effects=False,
    )
    assert response["result"] == {"result": {"temperature": 23}}
    assert response["success"] is True


@pytest.mark.parametrize(
    "data", [object(), {"x": object()}, {"x": float("inf")}, {"x": "\ud800"}]
)
def test_non_json_results_are_not_stringified(data):
    response = normalize_tool_result(
        API_ID, TOOL_NAME, llm.ToolResult(data=data), side_effects=True
    )
    assert response["error_code"] == "invalid_response"
    assert response["outcome_unknown"] is True


def test_generic_unicode_response_budget():
    response = normalize_tool_result(
        API_ID,
        TOOL_NAME,
        llm.ToolResult(data={"results": ["字" * 4000 for _ in range(40)]}),
        side_effects=False,
    )
    assert response["success"] is True
    assert response["truncated"] is True
    assert (
        len(json.dumps(response, ensure_ascii=False).encode("utf-8"))
        <= MAX_RESPONSE_BYTES
    )


def test_cyclic_results_are_bounded():
    data = {}
    data["self"] = data
    response = normalize_tool_result(
        API_ID, TOOL_NAME, llm.ToolResult(data=data), side_effects=False
    )
    assert response["success"] is True
    assert response["truncated"] is True
    json.dumps(response, allow_nan=False)


def test_result_nodes_are_bounded_without_excess_null_placeholders():
    response = normalize_tool_result(
        API_ID,
        TOOL_NAME,
        llm.ToolResult(data=[list(range(32)) for _ in range(32)]),
        side_effects=False,
    )

    def count(node):
        return 1 + sum(count(item) for item in node) if isinstance(node, list) else 1

    assert count(response["result"]) <= MAX_TOOL_JSON_NODES
    assert response["truncated"] is True
    assert response["result"][0] == list(range(32))
