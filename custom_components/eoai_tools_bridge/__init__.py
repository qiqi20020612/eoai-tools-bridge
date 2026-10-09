"""Expose one response-only web search action through HA's LLM API."""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SERVICE_SEARCH_WEB
from .search import SEARCH_SCHEMA, async_search, failure_response

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the action once, independently of entry reloads."""
    if hass.services.has_service(DOMAIN, SERVICE_SEARCH_WEB):
        return True

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

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_WEB,
        handle_search,
        schema=SEARCH_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the bridge even if Tools for Assist is not available yet."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload without removing the component's registered action.

    HA keeps component actions registered so scripts remain editable. The
    handler checks entry state on every call; unloaded entries cannot search.
    """
    return True
