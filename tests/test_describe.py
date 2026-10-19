"""Describe deliberately allowed tools without granting execution or defaults."""

import asyncio
import json
from unittest.mock import Mock, patch

import probatio as vol
import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import llm

from custom_components.eoai_tools_bridge import async_setup
from custom_components.eoai_tools_bridge.const import DOMAIN
from custom_components.eoai_tools_bridge.describe import describe_response


async def describe(hass, context=None, **changes):
    return await hass.services.async_call(
        DOMAIN,
        "describe_tool",
        {
            "api_id": "llm_intents",
            "tool_name": "search_web",
            **changes,
        },
        context=context,
        blocking=True,
        return_response=True,
    )


async def test_original_context_and_public_metadata_only(
    hass, gateway_entry, admin_context, search_api, search_tool
):
    response = await describe(hass, admin_context)
    assert response["success"] is True
    assert response["tool"]["parameters"]["required"] == ["query"]
    assert response["tool"]["requires_side_effects"] is False
    assert search_api.contexts[0].context is admin_context
    assert search_api.contexts[0].device_id is None
    assert "api_prompt" not in json.dumps(response)
    assert "Untrusted upstream" not in json.dumps(response)
    search_tool.call.assert_not_called()


async def test_unsafe_metadata_does_not_require_or_grant_execution_permission(
    hass, gateway_entry, admin_context, search_api, search_tool
):
    search_tool.annotations = llm.ToolAnnotations(read_only=False, destructive=True)
    factory = Mock(return_value="private-default")
    validator = Mock(side_effect=AssertionError("parameter validation"))
    search_tool.parameters = vol.Schema(
        {vol.Optional("query", default=factory): validator}
    )
    search_api.custom_serializer = lambda node: (
        {"type": "string"} if node is validator else vol.UNSUPPORTED
    )
    options = dict(gateway_entry.options)
    response = await describe(hass, admin_context)
    assert response["success"] is True
    assert response["tool"]["requires_side_effects"] is True
    assert response["tool"]["side_effects_allowed"] is False
    assert "private-default" not in json.dumps(response)
    factory.assert_not_called()
    validator.assert_not_called()
    assert dict(gateway_entry.options) == options
    denied = await hass.services.async_call(
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
    assert denied["error_code"] == "side_effects_blocked"
    search_tool.call.assert_not_called()


@pytest.mark.parametrize("identity", [None, "unknown", "ordinary", "inactive"])
async def test_requires_original_active_admin(
    hass,
    gateway_entry,
    search_api,
    search_tool,
    hass_read_only_user,
    hass_admin_user,
    identity,
):
    user_id = identity
    if identity == "ordinary":
        user_id = hass_read_only_user.id
    elif identity == "inactive":
        hass_admin_user.is_active = False
        user_id = hass_admin_user.id
    response = await describe(hass, Context(user_id=user_id))
    assert response == describe_response(
        "llm_intents", "search_web", "permission_denied"
    )
    assert search_api.contexts == []
    search_tool.call.assert_not_called()


@pytest.mark.parametrize("case", ["unloaded", "disabled", "unapproved"])
async def test_loaded_enabled_exact_allowlist_required(
    hass, bridge_entry, admin_context, search_api, search_tool, case
):
    code = "gateway_disabled"
    if case == "unloaded":
        await hass.config_entries.async_unload(bridge_entry.entry_id)
        code = "bridge_not_loaded"
    elif case == "unapproved":
        hass.config_entries.async_update_entry(
            bridge_entry,
            options={
                "enabled": True,
                "allowed_tools": "another/tool",
            },
        )
        code = "tool_not_allowed"
    assert (await describe(hass, admin_context))["error_code"] == code
    assert search_api.contexts == []
    search_tool.call.assert_not_called()


async def test_no_entry_and_response_required(hass, admin_context):
    assert await async_setup(hass, {})
    assert (await describe(hass, admin_context))["error_code"] == "bridge_not_loaded"
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "describe_tool",
            {
                "api_id": "llm_intents",
                "tool_name": "search_web",
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "change",
    [
        {"api_id": "*"},
        {"tool_name": "../play"},
        {"tool_args": {}},
        {"include_all": True},
    ],
)
async def test_strict_inputs(hass, gateway_entry, admin_context, search_api, change):
    with pytest.raises(vol.Invalid):
        await describe(hass, admin_context, **change)
    assert search_api.contexts == []


@pytest.mark.parametrize(
    "failure", ["missing_api", "missing_tool", "api_error", "schema", "metadata"]
)
async def test_fixed_errors_never_partial_metadata(
    hass, gateway_entry, admin_context, search_api, search_tool, failure
):
    if failure == "missing_api":
        hass.config_entries.async_update_entry(
            gateway_entry,
            options={
                "enabled": True,
                "allowed_tools": "absent/search_web",
            },
        )
        assert (await describe(hass, admin_context, api_id="absent"))[
            "error_code"
        ] == "api_unavailable"
        return
    code = {
        "missing_tool": "tool_unavailable",
        "api_error": "api_failed",
        "schema": "invalid_schema",
        "metadata": "invalid_metadata",
    }[failure]
    if failure == "missing_tool":
        search_api.tools = []
    elif failure == "api_error":
        search_api.error = HomeAssistantError("private-api-key")
    elif failure == "schema":
        search_tool.parameters = vol.Schema({"query": lambda x: x})
    else:
        search_tool.title = object()
    response = await describe(hass, admin_context)
    assert response["error_code"] == code
    assert response["tool"] is None
    assert "private-api-key" not in json.dumps(response)
    search_tool.call.assert_not_called()


@pytest.mark.parametrize(
    "change", ["permission", "identity", "schema", "annotation", "serializer"]
)
async def test_changes_while_serializing_discard_metadata(
    hass, gateway_entry, admin_context, search_api, search_tool, change
):
    def serializer(node):
        if change == "permission":
            hass.config_entries.async_update_entry(gateway_entry, options={})
        elif change == "identity":
            admin_context.user_id = "changed-user"
        elif change == "schema":
            search_tool.parameters = vol.Schema({})
        elif change == "annotation":
            search_tool.annotations = llm.ToolAnnotations(read_only=False)
        else:
            search_api.custom_serializer = None
            # Also mutate this instance: the API stores it on acquisition.
            instance.custom_serializer = None
        return {"type": "object", "properties": {}}

    original = search_api.async_get_api_instance
    instance = None

    async def acquire(context):
        nonlocal instance
        instance = await original(context)
        return instance

    search_api.custom_serializer = serializer
    with patch.object(search_api, "async_get_api_instance", side_effect=acquire):
        response = await describe(hass, admin_context)
    expected = {"permission": "policy_changed", "identity": "permission_denied"}.get(
        change, "tool_changed"
    )
    assert response["error_code"] == expected
    assert response["tool"] is None
    search_tool.call.assert_not_called()


async def test_timeout_and_cancellation(hass, gateway_entry, admin_context, search_api):
    async def hang(context):
        await asyncio.Event().wait()

    with (
        patch(
            "custom_components.eoai_tools_bridge.describe.CATALOG_TIMEOUT_SECONDS", 0.01
        ),
        patch.object(search_api, "async_get_api_instance", side_effect=hang),
    ):
        assert (await describe(hass, admin_context))["error_code"] == "timeout"
    search_api.error = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await describe(hass, admin_context)
