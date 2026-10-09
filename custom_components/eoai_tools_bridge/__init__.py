"""Expose web search and a response-only tool catalog through HA's LLM API."""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers.typing import ConfigType

from .catalog import LIST_TOOLS_SCHEMA, async_list_tools, catalog_response
from .const import DOMAIN, SERVICE_LIST_TOOLS, SERVICE_SEARCH_WEB
from .search import SEARCH_SCHEMA, async_search, failure_response

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register each action once, independently of entry reloads."""

    async def handle_search(call: ServiceCall) -> ServiceResponse:
        """Return a friendly failure when no bridge entry is loaded."""
        query = call.data["query"]
        if not any(
            entry.state is ConfigEntryState.LOADED
            for entry in hass.config_entries.async_entries(DOMAIN)
        ):
            _LOGGER.debug("Search action called without a loaded bridge entry")
            return failure_response(query, "bridge_not_loaded")
        return await async_search(hass, call)

    async def handle_list_tools(call: ServiceCall) -> ServiceResponse:
        """Expose metadata only while a bridge entry is loaded."""
        if not any(
            entry.state is ConfigEntryState.LOADED
            for entry in hass.config_entries.async_entries(DOMAIN)
        ):
            return catalog_response("bridge_not_loaded")
        return await async_list_tools(hass, call)

    if not hass.services.has_service(DOMAIN, SERVICE_SEARCH_WEB):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEARCH_WEB,
            handle_search,
            schema=SEARCH_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_LIST_TOOLS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_LIST_TOOLS,
            handle_list_tools,
            schema=LIST_TOOLS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the bridge even if Tools for Assist is not available yet."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload without removing the component's registered actions.

    HA keeps component actions registered so scripts remain editable. The
    handlers check entry state on every call; unloaded entries cannot use them.
    """
    return True
