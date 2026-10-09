"""Read-only readiness with native HA auth, services, registry and APIInstance."""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, Mock, patch

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
    SERVICE_CHECK_TOOLS,
    TOOL_NAME,
)
from custom_components.eoai_tools_bridge.readiness import check_response


async def check(hass, context=None, data=None):
    return await hass.services.async_call(
        DOMAIN,
        SERVICE_CHECK_TOOLS,
        {} if data is None else data,
        context=context,
        blocking=True,
        return_response=True,
    )


def configure(hass, entry, *pairs, enabled=True, side_effects=False):
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_ENABLED: enabled,
            CONF_ALLOWED_TOOLS: "\n".join(pairs),
            CONF_ALLOW_SIDE_EFFECTS: side_effects,
        },
    )


async def test_reports_ready_without_dispatch_and_keeps_original_context(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    hass.config.language = "zh-Hans"
    before = dict(gateway_entry.options)
    with patch.object(
        llm.APIInstance, "async_call_tool", new_callable=AsyncMock
    ) as dispatch:
        response = await check(hass, admin_context)
    assert response == {
        **check_response(),
        "enabled": True,
        "allow_side_effects": False,
        "tools": [
            {
                "api_id": API_ID,
                "tool_name": TOOL_NAME,
                "status": "ready",
                "api_registered": True,
                "read_only_basis": "audited_allowlist",
                "requires_side_effects": False,
                "schema_supported": True,
            }
        ],
    }
    dispatch.assert_not_called()
    search_tool.call.assert_not_called()
    assert dict(gateway_entry.options) == before
    context = search_api.contexts[0]
    assert context.context is admin_context
    assert context.platform == DOMAIN
    assert context.language == "zh-Hans"
    assert context.assistant == "conversation"
    assert context.device_id is None


async def test_upgrade_without_options_returns_empty_disabled_check(
    hass, bridge_entry, search_api, search_tool, admin_context
):
    assert await check(hass, admin_context) == {
        **check_response(),
        "enabled": False,
        "allow_side_effects": False,
    }
    assert search_api.contexts == []
    search_tool.call.assert_not_called()
    assert bridge_entry.options == {}


async def test_disabled_gateway_only_checks_api_registration(
    hass, bridge_entry, search_api, search_tool, admin_context
):
    configure(
        hass, bridge_entry, f"{API_ID}/{TOOL_NAME}", "missing/read", enabled=False
    )
    response = await check(hass, admin_context)
    assert response["success"] is True
    assert response["enabled"] is False
    assert [row["status"] for row in response["tools"]] == ["gateway_disabled"] * 2
    assert [row["api_registered"] for row in response["tools"]] == [True, False]
    assert all(row["schema_supported"] is None for row in response["tools"])
    assert search_api.contexts == []
    search_tool.call.assert_not_called()


async def test_no_loaded_entry(hass, search_api, admin_context):
    await async_setup(hass, {})
    assert (await check(hass, admin_context))["error_code"] == "bridge_not_loaded"
    assert search_api.contexts == []


@pytest.mark.parametrize("identity", ["none", "unknown", "non_admin", "inactive_admin"])
async def test_denied_identity_does_not_expose_options_or_open_apis(
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
        context = Context(user_id="fake-admin")
    elif identity == "non_admin":
        context = Context(user_id=hass_read_only_user.id)
    elif identity == "inactive_admin":
        hass_admin_user.is_active = False
        context = Context(user_id=hass_admin_user.id)
    assert await check(hass, context) == check_response("permission_denied")
    assert search_api.contexts == []
    search_tool.call.assert_not_called()


@pytest.mark.parametrize("field", ["api_id", "tool_name", "tool_args", "user_id"])
async def test_action_has_no_arguments(
    hass, gateway_entry, search_api, admin_context, field
):
    with pytest.raises(vol.Invalid):
        await check(hass, admin_context, {field: "forged"})
    assert search_api.contexts == []


async def test_response_required(hass, gateway_entry, search_api, admin_context):
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_CHECK_TOOLS, {}, context=admin_context, blocking=True
        )
    assert search_api.contexts == []


@pytest.mark.parametrize("side_effects", [False, True])
@pytest.mark.parametrize(
    "annotations",
    [
        llm.Tool.annotations,
        llm.ToolAnnotations(read_only=False, destructive=False),
        llm.ToolAnnotations(read_only=True, destructive=True),
        llm.ToolAnnotations(read_only=True, destructive=False),
    ],
)
async def test_reports_safety_gate_without_executing_any_tool(
    hass,
    gateway_entry,
    search_api,
    search_tool,
    admin_context,
    side_effects,
    annotations,
):
    search_tool.name = "read_weather"
    search_tool.annotations = annotations
    configure(hass, gateway_entry, f"{API_ID}/read_weather", side_effects=side_effects)
    row = (await check(hass, admin_context))["tools"][0]
    read_only = annotations.read_only and not annotations.destructive
    assert row["status"] == (
        "ready" if side_effects or read_only else "side_effects_blocked"
    )
    assert row["requires_side_effects"] is not read_only
    assert row["read_only_basis"] == ("annotation" if read_only else None)
    assert row["schema_supported"] is True
    search_tool.call.assert_not_called()


async def test_reports_unsupported_parameter_schema(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    search_tool.parameters = object()
    row = (await check(hass, admin_context))["tools"][0]
    assert row["status"] == "invalid_schema"
    assert row["schema_supported"] is False
    search_tool.call.assert_not_called()


async def test_does_not_run_validators_defaults_or_serializers(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    factory = Mock(return_value="test")
    validator = Mock(side_effect=lambda value: value)
    serializer = Mock(side_effect=AssertionError("must not serialize"))
    search_tool.parameters = vol.Schema(
        {vol.Optional("query", default=factory): validator}
    )
    search_api.custom_serializer = serializer
    with patch.object(
        vol, "to_openapi", side_effect=AssertionError("must not convert")
    ) as convert:
        assert (await check(hass, admin_context))["tools"][0]["status"] == "ready"
    factory.assert_not_called()
    validator.assert_not_called()
    serializer.assert_not_called()
    convert.assert_not_called()
    search_tool.call.assert_not_called()


async def test_never_opens_api_outside_configured_allowlist(
    hass, gateway_entry, search_api, admin_context
):
    other = AsyncMock(spec=llm.API)
    other.id = "home_control"
    unregister = llm.async_register_api(hass, other)
    try:
        assert (await check(hass, admin_context))["tools"][0]["status"] == "ready"
        other.async_get_api_instance.assert_not_called()
    finally:
        unregister()


async def test_opens_each_api_once_and_reports_missing_tool(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    extra = SearchTool()
    extra.name = "read_weather"
    extra.annotations = llm.ToolAnnotations(read_only=True, destructive=False)
    search_api.tools.append(extra)
    configure(
        hass,
        gateway_entry,
        f"{API_ID}/{TOOL_NAME}",
        f"{API_ID}/read_weather",
        f"{API_ID}/absent",
    )
    response = await check(hass, admin_context)
    assert [row["status"] for row in response["tools"]] == [
        "tool_unavailable",
        "ready",
        "ready",
    ]
    assert len(search_api.contexts) == 1
    search_tool.call.assert_not_called()
    extra.call.assert_not_called()


async def test_api_failure_is_local_to_its_rows_and_hides_private_data(
    hass, gateway_entry, search_api, search_tool, admin_context, caplog
):
    caplog.set_level(
        logging.DEBUG, logger="custom_components.eoai_tools_bridge.readiness"
    )
    broken = SearchAPI(hass, SearchTool())
    broken.id = "broken"
    broken.error = HomeAssistantError("Authorization: private-key; private-query")
    unregister = llm.async_register_api(hass, broken)
    try:
        configure(
            hass,
            gateway_entry,
            "broken/search_web",
            f"{API_ID}/{TOOL_NAME}",
            "missing/read",
        )
        response = await check(hass, admin_context)
    finally:
        unregister()
    assert response["success"] is True
    assert [row["status"] for row in response["tools"]] == [
        "api_failed",
        "ready",
        "api_unavailable",
    ]
    assert response["tools"][0]["schema_supported"] is None
    logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("custom_components.eoai_tools_bridge")
    )
    assert "private-key" not in json.dumps(response) + logs
    assert "private-query" not in json.dumps(response) + logs
    search_tool.call.assert_not_called()


async def test_duplicate_name_follows_first_tool_safety(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    search_tool.annotations = llm.ToolAnnotations(read_only=False)
    later = SearchTool()
    later.annotations = llm.ToolAnnotations(read_only=True, destructive=False)
    search_api.tools.append(later)
    assert (await check(hass, admin_context))["tools"][0][
        "status"
    ] == "side_effects_blocked"
    search_tool.call.assert_not_called()
    later.call.assert_not_called()


async def test_private_metadata_and_tool_configuration_are_never_returned(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    search_tool.title = "private-title"
    search_tool.description = "private-description"
    search_tool.config = {"api_key": "private-key"}
    response = await check(hass, admin_context)
    assert response["success"] is True
    assert "private-" not in json.dumps(response)
    assert "Untrusted upstream" not in json.dumps(response)


@pytest.mark.parametrize(
    "change", ["disable", "remove_pair", "unload", "deactivate", "identity"]
)
async def test_revocation_after_api_await_drops_all_metadata(
    hass, gateway_entry, search_api, search_tool, hass_admin_user, admin_context, change
):
    other = await hass.auth.async_create_user("Other admin")
    other.is_owner = True
    original = search_api.async_get_api_instance

    async def acquire(context):
        instance = await original(context)
        if change == "disable":
            configure(hass, gateway_entry, f"{API_ID}/{TOOL_NAME}", enabled=False)
        elif change == "remove_pair":
            configure(hass, gateway_entry, "weather/read")
        elif change == "unload":
            await hass.config_entries.async_unload(gateway_entry.entry_id)
        elif change == "deactivate":
            hass_admin_user.is_active = False
        else:
            context.context.user_id = other.id
        return instance

    with patch.object(search_api, "async_get_api_instance", side_effect=acquire):
        response = await check(hass, admin_context)
    assert response == check_response(
        "permission_denied"
        if change in {"deactivate", "identity"}
        else "policy_changed"
    )
    search_tool.call.assert_not_called()


async def test_policy_changed_during_initial_identity_lookup_opens_no_api(
    hass, gateway_entry, search_api, admin_context
):
    async def authorize(*args):
        configure(hass, gateway_entry, f"{API_ID}/{TOOL_NAME}", enabled=False)
        return True

    with patch(
        "custom_components.eoai_tools_bridge.readiness.async_is_admin",
        side_effect=authorize,
    ):
        assert await check(hass, admin_context) == check_response("policy_changed")
    assert search_api.contexts == []


async def test_metadata_getter_cannot_return_permissions_revoked_mid_check(
    hass, gateway_entry, admin_context
):
    class RevokingTool(SearchTool):
        @property
        def parameters(self):
            configure(hass, gateway_entry, f"{API_ID}/{TOOL_NAME}", enabled=False)
            return vol.Schema({})

    tool = RevokingTool()
    api = SearchAPI(hass, tool)
    unregister = llm.async_register_api(hass, api)
    try:
        assert await check(hass, admin_context) == check_response("policy_changed")
        tool.call.assert_not_called()
    finally:
        unregister()


async def test_timeout_clears_partial_check_and_never_dispatches(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    delayed = SearchAPI(hass, SearchTool())
    delayed.id = "zz_delayed"
    unregister = llm.async_register_api(hass, delayed)

    async def hang(context):
        await asyncio.Event().wait()

    try:
        configure(hass, gateway_entry, f"{API_ID}/{TOOL_NAME}", "zz_delayed/search_web")
        with patch.object(delayed, "async_get_api_instance", side_effect=hang):
            with patch(
                "custom_components.eoai_tools_bridge.readiness.CHECK_TIMEOUT_SECONDS",
                0.01,
            ):
                assert await check(hass, admin_context) == check_response("timeout")
        assert len(search_api.contexts) == 1
        search_tool.call.assert_not_called()
    finally:
        unregister()


async def test_cancellation_propagates(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    with patch.object(
        search_api, "async_get_api_instance", side_effect=asyncio.CancelledError
    ):
        with pytest.raises(asyncio.CancelledError):
            await check(hass, admin_context)
    search_tool.call.assert_not_called()


@pytest.mark.parametrize("stage", ["auth", "registry"])
async def test_global_failures_clear_options_and_hide_error_text(
    hass, gateway_entry, admin_context, stage, caplog
):
    caplog.set_level(
        logging.DEBUG, logger="custom_components.eoai_tools_bridge.readiness"
    )
    target = (
        "custom_components.eoai_tools_bridge.readiness.async_is_admin"
        if stage == "auth"
        else "homeassistant.helpers.llm.async_get_apis"
    )
    with patch(target, side_effect=HomeAssistantError("private-token")):
        assert await check(hass, admin_context) == check_response(
            "permission_denied" if stage == "auth" else "api_failed"
        )
    assert "private-token" not in "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("custom_components.eoai_tools_bridge")
    )


async def test_dynamic_registration_and_tool_changes_are_not_cached(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    assert (await check(hass, admin_context))["tools"][0]["status"] == "ready"
    search_api.tools = []
    assert (await check(hass, admin_context))["tools"][0][
        "status"
    ] == "tool_unavailable"
    search_api.tools = [search_tool]
    search_tool.parameters = object()
    assert (await check(hass, admin_context))["tools"][0]["status"] == "invalid_schema"
    with patch.object(llm, "async_get_apis", return_value=[]):
        assert (await check(hass, admin_context))["tools"][0][
            "status"
        ] == "api_unavailable"
    assert len(search_api.contexts) == 3
    search_tool.call.assert_not_called()


async def test_unload_reload_and_remove_keep_registration_with_loaded_guard(
    hass, gateway_entry, search_api, search_tool, admin_context
):
    assert await hass.config_entries.async_unload(gateway_entry.entry_id)
    assert hass.services.has_service(DOMAIN, SERVICE_CHECK_TOOLS)
    assert await check(hass, admin_context) == check_response("bridge_not_loaded")
    assert await hass.config_entries.async_setup(gateway_entry.entry_id)
    assert (await check(hass, admin_context))["tools"][0]["status"] == "ready"
    await hass.config_entries.async_remove(gateway_entry.entry_id)
    assert await check(hass, admin_context) == check_response("bridge_not_loaded")
    search_tool.call.assert_not_called()


async def test_maximum_allowlist_stays_within_response_budget(
    hass, gateway_entry, admin_context
):
    api_id = "a" * 128
    tools = []
    for i in range(32):
        tool = SearchTool()
        tool.name = f"tool_{i:02d}" + "x" * 121
        tool.annotations = llm.ToolAnnotations(read_only=True, destructive=False)
        tools.append(tool)
    api = SearchAPI(hass, tools[0])
    api.id = api_id
    api.tools = tools
    unregister = llm.async_register_api(hass, api)
    try:
        configure(hass, gateway_entry, *(f"{api_id}/{tool.name}" for tool in tools))
        response = await check(hass, admin_context)
        assert response["success"] is True
        assert len(response["tools"]) == 32
        assert (
            len(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            <= MAX_RESPONSE_BYTES
        )
        for tool in tools:
            tool.call.assert_not_called()
    finally:
        unregister()


async def test_output_budget_omits_whole_rows_instead_of_cutting_ids(
    hass, gateway_entry, admin_context
):
    pairs = [f"{'a' * 128}/tool_{i:02d}{'x' * 121}" for i in range(3)]
    configure(hass, gateway_entry, *pairs)
    with patch(
        "custom_components.eoai_tools_bridge.readiness.MAX_RESPONSE_BYTES", 1024
    ):
        response = await check(hass, admin_context)
    assert response["truncated"] is True
    assert 0 < len(response["tools"]) < 3
    assert len(json.dumps(response, ensure_ascii=False).encode("utf-8")) <= 1024
    assert all(
        f"{row['api_id']}/{row['tool_name']}" in pairs for row in response["tools"]
    )
