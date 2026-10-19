"""Expose controlled tools and read-only checks through HA's LLM API."""

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm
from homeassistant.helpers.typing import ConfigType

from .amap import CONF_AMAP_MODE, AmapAPI
from .catalog import LIST_TOOLS_SCHEMA, async_list_tools, catalog_response
from .const import (
    DOMAIN,
    SERVICE_CALL_TOOL,
    SERVICE_CHECK_TOOLS,
    SERVICE_DESCRIBE_TOOL,
    SERVICE_LIST_TOOLS,
)
from .describe import DESCRIBE_TOOL_SCHEMA, async_describe_tool
from .gateway import CALL_TOOL_SCHEMA, async_call_tool
from .readiness import CHECK_TOOLS_SCHEMA, async_check_tools

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register each action once, independently of entry reloads."""

    async def handle_list_tools(call: ServiceCall) -> ServiceResponse:
        """Expose metadata only while a bridge entry is loaded."""
        if not any(
            entry.state is ConfigEntryState.LOADED
            for entry in hass.config_entries.async_entries(DOMAIN)
        ):
            return catalog_response("bridge_not_loaded")
        return await async_list_tools(hass, call)

    async def handle_call_tool(call: ServiceCall) -> ServiceResponse:
        """Apply the current explicit policy for every controlled call."""
        return await async_call_tool(hass, call)

    async def handle_check_tools(call: ServiceCall) -> ServiceResponse:
        """Inspect only the administrator's explicitly configured tools."""
        return await async_check_tools(hass, call)

    async def handle_describe_tool(call: ServiceCall) -> ServiceResponse:
        """Inspect a single explicitly configured tool as the original admin."""
        return await async_describe_tool(hass, call)

    # Remove a stale registration if this process previously loaded v0.6.x.
    if hass.services.has_service(DOMAIN, "search_web"):
        hass.services.async_remove(DOMAIN, "search_web")
    if not hass.services.has_service(DOMAIN, SERVICE_LIST_TOOLS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_LIST_TOOLS,
            handle_list_tools,
            schema=LIST_TOOLS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CALL_TOOL):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CALL_TOOL,
            handle_call_tool,
            schema=CALL_TOOL_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CHECK_TOOLS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CHECK_TOOLS,
            handle_check_tools,
            schema=CHECK_TOOLS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_DESCRIBE_TOOL):
        hass.services.async_register(
            DOMAIN,
            SERVICE_DESCRIBE_TOOL,
            handle_describe_tool,
            schema=DESCRIBE_TOOL_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the bridge even if Tools for Assist is not available yet."""
    if entry.options.get(CONF_AMAP_MODE) == "TWO_WHEELER":
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_AMAP_MODE: "DRIVE"}
        )
    entry.async_on_unload(llm.async_register_api(hass, AmapAPI(hass, entry)))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload without removing the component's registered actions.

    HA keeps component actions registered so scripts remain editable. The
    handlers check entry state on every call; unloaded entries cannot use them.
    """
    return True
