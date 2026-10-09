"""Read-only discovery through real HA services, registry, and Schema codecs."""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, Mock, patch

import probatio as vol
import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import llm

from custom_components.eoai_tools_bridge import async_setup
from custom_components.eoai_tools_bridge.catalog import catalog_response
from custom_components.eoai_tools_bridge.const import (
    API_ID,
    DOMAIN,
    MAX_CATALOG_DESCRIPTION_LENGTH,
    MAX_RESPONSE_BYTES,
    SERVICE_CALL_TOOL,
    SERVICE_CHECK_TOOLS,
    SERVICE_LIST_TOOLS,
    SERVICE_SEARCH_WEB,
    TOOL_NAME,
)


async def call_catalog(hass, data=None, **kwargs):
    return await hass.services.async_call(
        DOMAIN,
        SERVICE_LIST_TOOLS,
        {} if data is None else data,
        blocking=True,
        return_response=True,
        **kwargs,
    )


async def test_describes_search_without_calling_any_tool(
    hass, bridge_entry, search_api, search_tool
):
    with patch.object(
        llm.APIInstance, "async_call_tool", new_callable=AsyncMock
    ) as call:
        response = await call_catalog(hass)
    assert response == {
        **catalog_response(),
        "tools": [
            {
                "api_id": API_ID,
                "api_name": search_api.name,
                "name": TOOL_NAME,
                "title": "Web search",
                "description": search_tool.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                "read_only": True,
                "read_only_basis": "audited_allowlist",
            }
        ],
    }
    call.assert_not_called()
    search_tool.call.assert_not_called()
    assert "api_prompt" not in json.dumps(response)
    assert "Untrusted upstream" not in json.dumps(response)


async def test_preserves_original_caller_context(hass, bridge_entry, search_api):
    hass.config.language = "zh-Hans"
    original = Context(user_id="catalog-user", parent_id="catalog-request")
    await call_catalog(hass, context=original)
    context = search_api.contexts[0]
    assert context.context is original
    assert context.platform == DOMAIN
    assert context.language == "zh-Hans"
    assert context.assistant == "conversation"
    assert context.device_id is None


async def test_never_opens_unapproved_apis(hass, bridge_entry, search_api):
    unapproved = AsyncMock(spec=llm.API)
    unapproved.id = "home_control"
    unapproved.name = "Home control"
    unregister = llm.async_register_api(hass, unapproved)
    try:
        response = await call_catalog(hass)
        assert [tool["api_id"] for tool in response["tools"]] == [API_ID]
        unapproved.async_get_api_instance.assert_not_called()
    finally:
        unregister()


@pytest.mark.parametrize("name", ["unlock_door", "run_shell", "read_weather"])
async def test_read_only_annotation_does_not_expand_allowlist(
    hass, bridge_entry, search_api, search_tool, name
):
    search_tool.name = name
    search_tool.annotations = llm.ToolAnnotations(read_only=True, destructive=False)
    response = await call_catalog(hass)
    assert response == catalog_response()
    search_tool.call.assert_not_called()


@pytest.mark.parametrize(
    "read_only,destructive", [(False, True), (False, False), (True, True)]
)
async def test_explicit_unsafe_annotation_is_excluded(
    hass, bridge_entry, search_api, search_tool, read_only, destructive
):
    search_tool.annotations = llm.ToolAnnotations(
        read_only=read_only, destructive=destructive
    )
    assert await call_catalog(hass) == catalog_response()
    search_tool.call.assert_not_called()


async def test_explicit_read_only_annotation(
    hass, bridge_entry, search_api, search_tool
):
    search_tool.annotations = llm.ToolAnnotations(read_only=True, destructive=False)
    assert (await call_catalog(hass))["tools"][0]["read_only_basis"] == "annotation"


async def test_duplicate_names_follow_ha_dispatch_order(
    hass, bridge_entry, search_api, search_tool
):
    from conftest import SearchTool

    duplicate = SearchTool()
    search_api.tools = [search_tool, duplicate]
    assert len((await call_catalog(hass))["tools"]) == 1
    search_tool.annotations = llm.ToolAnnotations(read_only=False)
    assert await call_catalog(hass) == catalog_response()
    search_tool.call.assert_not_called()
    duplicate.call.assert_not_called()


async def test_registry_and_provider_changes_are_not_cached(
    hass, bridge_entry, search_tool
):
    from conftest import SearchAPI

    assert await call_catalog(hass) == catalog_response()
    api = SearchAPI(hass, search_tool)
    unregister = llm.async_register_api(hass, api)
    try:
        assert len((await call_catalog(hass))["tools"]) == 1
        # The Brave LLM Context provider advertises an optional enum in addition
        # to the query-only schema of Brave Web Search and SearXNG.
        search_tool.parameters = vol.Schema(
            {
                vol.Required("query"): str,
                vol.Optional("freshness"): vol.In(
                    ["Today", "This Week", "This Month", "This Year"]
                ),
            }
        )
        schema = (await call_catalog(hass))["tools"][0]["parameters"]
        assert schema["required"] == ["query"]
        assert schema["properties"]["freshness"]["enum"] == [
            "Today",
            "This Week",
            "This Month",
            "This Year",
        ]
        api.tools = []
        assert await call_catalog(hass) == catalog_response()
        api.tools = [search_tool]
        assert len((await call_catalog(hass))["tools"]) == 1
    finally:
        unregister()
    assert await call_catalog(hass) == catalog_response()
    assert len(api.contexts) == 4
    search_tool.call.assert_not_called()


@pytest.mark.parametrize(
    "field", ["api_id", "tool_name", "query", "include_all", "service"]
)
async def test_action_accepts_no_input(hass, bridge_entry, search_api, field):
    with pytest.raises(vol.Invalid):
        await call_catalog(hass, {field: "forbidden"})
    assert not search_api.contexts


async def test_response_required(hass, bridge_entry, search_api):
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, SERVICE_LIST_TOOLS, {}, blocking=True)
    assert not search_api.contexts


async def test_api_errors_hide_secrets(hass, bridge_entry, search_api, caplog):
    caplog.set_level(
        logging.DEBUG, logger="custom_components.eoai_tools_bridge.catalog"
    )
    secret = "Authorization: private-api-key; private-search-text"
    search_api.error = HomeAssistantError(secret)
    response = await call_catalog(hass)
    assert response == catalog_response("api_failed")
    assert secret not in json.dumps(response)
    assert secret not in "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("custom_components.eoai_tools_bridge")
    )


async def test_api_timeout(hass, bridge_entry, search_api, search_tool):
    async def hang(context):
        await asyncio.Event().wait()

    with (
        patch(
            "custom_components.eoai_tools_bridge.catalog.CATALOG_TIMEOUT_SECONDS", 0.01
        ),
        patch.object(search_api, "async_get_api_instance", side_effect=hang),
    ):
        assert await call_catalog(hass) == catalog_response("timeout")
    search_tool.call.assert_not_called()


async def test_cancellation_propagates(hass, bridge_entry, search_api):
    search_api.error = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await call_catalog(hass)


async def test_custom_serializer_and_nested_constraints(
    hass, bridge_entry, search_api, search_tool
):
    token = object()
    search_tool.parameters = vol.Schema({vol.Required("query"): token})

    def serialize(node):
        if node is token:
            return {"type": "string", "minLength": 1, "maxLength": 500}
        return vol.UNSUPPORTED

    search_api.custom_serializer = serialize
    response = await call_catalog(hass)
    assert response["tools"][0]["parameters"]["properties"]["query"] == {
        "type": "string",
        "minLength": 1,
        "maxLength": 500,
    }


async def test_defaults_examples_and_extensions_are_not_returned(
    hass, bridge_entry, search_api, search_tool
):
    def serialize(node):
        return {
            "type": "object",
            "properties": {
                "default": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "default": "secret-key",
                            "examples": ["private-query"],
                            "x-private": {"Authorization": "secret-key"},
                        }
                    },
                }
            },
            "default": {"config": "private-config"},
            "x-api-prompt": "private-prompt",
        }

    search_api.custom_serializer = serialize
    response = await call_catalog(hass)
    schema = response["tools"][0]["parameters"]
    assert schema["properties"]["default"]["properties"]["query"] == {"type": "string"}
    for secret in ("secret-key", "private-query", "private-config", "private-prompt"):
        assert secret not in json.dumps(response)


async def test_unrepresentable_schema_is_not_widened(
    hass, bridge_entry, search_api, search_tool
):
    search_tool.parameters = vol.Schema({vol.Required("query"): lambda value: value})
    assert await call_catalog(hass) == catalog_response("invalid_schema")
    search_tool.call.assert_not_called()


@pytest.mark.parametrize("nested", [False, True])
async def test_parameter_default_factory_is_not_executed(
    hass, bridge_entry, search_api, search_tool, nested
):
    factory = Mock(return_value="private-default")
    schema = {vol.Optional("query", default=factory): str}
    if nested:
        schema = {vol.Required("options"): vol.Schema(schema)}
    search_tool.parameters = vol.Schema(schema)
    response = await call_catalog(hass)
    assert response["success"] is True
    properties = response["tools"][0]["parameters"]["properties"]
    if nested:
        properties = properties["options"]["properties"]
    assert properties["query"] == {"type": "string"}
    assert "private-default" not in json.dumps(response)
    factory.assert_not_called()
    search_tool.call.assert_not_called()


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "array", "items": {"type": "string"}},
        {
            "type": "object",
            "properties": {"q": {"type": "string", "const": float("nan")}},
        },
        {
            "type": "object",
            "properties": {"q": {"type": "string", "default": object()}},
            "config": "secret-key",
        },
        {"type": "object", "properties": {"q": None}},
        {
            "type": "object",
            "properties": {"q": {"type": "string", "description": "\ud800"}},
        },
    ],
)
async def test_invalid_converted_schema(hass, bridge_entry, search_api, schema):
    search_api.custom_serializer = lambda node: schema
    assert await call_catalog(hass) == catalog_response("invalid_schema")


@pytest.mark.parametrize("kind", ["bytes", "depth", "nodes"])
async def test_schema_budget_is_enforced(hass, bridge_entry, search_api, kind):
    schema = {"type": "object", "properties": {"query": {"type": "string"}}}
    if kind == "bytes":
        schema["properties"]["query"]["description"] = "字" * 4000
    elif kind == "nodes":
        schema["properties"] = {str(index): {"type": "string"} for index in range(300)}
    else:
        nested = schema
        for _ in range(20):
            nested["properties"] = {"nested": {"type": "object"}}
            nested = nested["properties"]["nested"]
    search_api.custom_serializer = lambda node: schema
    assert await call_catalog(hass) == catalog_response("invalid_schema")


async def test_description_is_bounded(hass, bridge_entry, search_api, search_tool):
    search_tool.description = "字" * (MAX_CATALOG_DESCRIPTION_LENGTH + 1)
    response = await call_catalog(hass)
    assert response["truncated"] is True
    assert (
        response["tools"][0]["description"]
        == "字" * (MAX_CATALOG_DESCRIPTION_LENGTH - 1) + "…"
    )
    assert (
        len(json.dumps(response, ensure_ascii=False).encode("utf-8"))
        <= MAX_RESPONSE_BYTES
    )


@pytest.mark.parametrize("description", [123, object(), "\ud800"])
async def test_invalid_metadata(
    hass, bridge_entry, search_api, search_tool, description
):
    search_tool.description = description
    assert await call_catalog(hass) == catalog_response("invalid_metadata")


async def test_catalog_unload_reload_remove(
    hass, bridge_entry, search_api, search_tool
):
    assert await hass.config_entries.async_unload(bridge_entry.entry_id)
    assert hass.services.has_service(DOMAIN, SERVICE_LIST_TOOLS)
    assert await call_catalog(hass) == catalog_response("bridge_not_loaded")
    assert not search_api.contexts
    assert await hass.config_entries.async_setup(bridge_entry.entry_id)
    assert len((await call_catalog(hass))["tools"]) == 1
    assert await hass.config_entries.async_reload(bridge_entry.entry_id)
    assert len((await call_catalog(hass))["tools"]) == 1
    await hass.config_entries.async_remove(bridge_entry.entry_id)
    assert await call_catalog(hass) == catalog_response("bridge_not_loaded")
    search_tool.call.assert_not_called()


@pytest.mark.parametrize(
    "missing",
    [SERVICE_LIST_TOOLS, SERVICE_SEARCH_WEB, SERVICE_CALL_TOOL, SERVICE_CHECK_TOOLS],
)
async def test_setup_registers_only_missing_action(hass, bridge_entry, missing):
    other = SERVICE_SEARCH_WEB if missing == SERVICE_LIST_TOOLS else SERVICE_LIST_TOOLS
    hass.services.async_remove(DOMAIN, missing)
    with patch.object(
        type(hass.services), "async_register", wraps=hass.services.async_register
    ) as register:
        assert await async_setup(hass, {})
    assert register.call_count == 1
    assert register.call_args.args[:2] == (DOMAIN, missing)
    assert hass.services.has_service(DOMAIN, other)
