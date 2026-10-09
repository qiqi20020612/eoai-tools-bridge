"""Config flow and lifecycle through HA Core, with no search dependencies."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eoai_tools_bridge import async_setup
from custom_components.eoai_tools_bridge.const import (
    DOMAIN,
    NAME,
    SERVICE_CALL_TOOL,
    SERVICE_CHECK_TOOLS,
    SERVICE_LIST_TOOLS,
    SERVICE_SEARCH_WEB,
)


async def test_ui_setup_and_single_instance(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {}
    assert result["result"].state is ConfigEntryState.LOADED
    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] in {"already_configured", "single_instance_allowed"}


async def test_register_once_and_response_only(
    hass: HomeAssistant, bridge_entry: MockConfigEntry
) -> None:
    with patch.object(
        type(hass.services), "async_register", wraps=hass.services.async_register
    ) as register:
        assert await async_setup(hass, {})
        assert await async_setup(hass, {})
    register.assert_not_called()
    assert set(hass.services.async_services()[DOMAIN]) == {
        SERVICE_CALL_TOOL,
        SERVICE_CHECK_TOOLS,
        SERVICE_SEARCH_WEB,
        SERVICE_LIST_TOOLS,
    }
    for service in (
        SERVICE_SEARCH_WEB,
        SERVICE_LIST_TOOLS,
        SERVICE_CALL_TOOL,
        SERVICE_CHECK_TOOLS,
    ):
        assert hass.services.supports_response(DOMAIN, service) is SupportsResponse.ONLY


async def test_missing_upstream_does_not_block_loading(
    hass: HomeAssistant, bridge_entry: MockConfigEntry
) -> None:
    assert bridge_entry.state is ConfigEntryState.LOADED
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_WEB,
        {"query": "test"},
        blocking=True,
        return_response=True,
    )
    assert response["error_code"] == "api_unavailable"


async def test_unload_reload_and_remove(
    hass: HomeAssistant, bridge_entry: MockConfigEntry, search_api, search_tool
) -> None:
    assert await hass.config_entries.async_unload(bridge_entry.entry_id)
    assert hass.services.has_service(DOMAIN, SERVICE_SEARCH_WEB)
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_WEB,
        {"query": "test"},
        blocking=True,
        return_response=True,
    )
    assert response["error_code"] == "bridge_not_loaded"
    search_tool.call.assert_not_called()
    assert await hass.config_entries.async_setup(bridge_entry.entry_id)
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_WEB,
        {"query": "test"},
        blocking=True,
        return_response=True,
    )
    assert response["success"] is True
    assert await hass.config_entries.async_reload(bridge_entry.entry_id)
    assert set(hass.services.async_services()[DOMAIN]) == {
        SERVICE_CALL_TOOL,
        SERVICE_CHECK_TOOLS,
        SERVICE_SEARCH_WEB,
        SERVICE_LIST_TOOLS,
    }
    await hass.config_entries.async_remove(bridge_entry.entry_id)
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_WEB,
        {"query": "test"},
        blocking=True,
        return_response=True,
    )
    assert response["error_code"] == "bridge_not_loaded"
    assert search_tool.call.await_count == 1
