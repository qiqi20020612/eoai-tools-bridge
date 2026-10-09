"""Use HA Core's real registry, context, service, and config-entry machinery."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import probatio as vol
import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eoai_tools_bridge.const import (
    API_ID,
    CONF_ALLOW_SIDE_EFFECTS,
    CONF_ALLOWED_TOOLS,
    CONF_ENABLED,
    DOMAIN,
    TOOL_NAME,
)


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations: None) -> None:
    """Enable only this repository's custom integration."""


@pytest.fixture
async def bridge_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Load a real config entry without installing any upstream integration."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def gateway_entry(
    hass: HomeAssistant, bridge_entry: MockConfigEntry
) -> MockConfigEntry:
    """Explicitly opt in; upgraded entries without options remain disabled."""
    hass.config_entries.async_update_entry(
        bridge_entry,
        options={
            CONF_ENABLED: True,
            CONF_ALLOWED_TOOLS: f"{API_ID}/{TOOL_NAME}",
            CONF_ALLOW_SIDE_EFFECTS: False,
        },
    )
    return bridge_entry


@pytest.fixture
def admin_context(hass_admin_user) -> Context:
    """Use a real active user in HA's auth store, not a fabricated admin ID."""
    return Context(user_id=hass_admin_user.id, parent_id="original-tool-request")


class SearchTool(llm.Tool):
    """Simulate only the provider's output, not HA's tool dispatch."""

    name = TOOL_NAME
    integration = API_ID
    title = "Web search"
    description = "Search the web for current information."
    parameters = vol.Schema({vol.Required("query", description="Search query"): str})

    def __init__(self) -> None:
        self.call = AsyncMock(
            return_value=llm.ToolResult(
                data={"results": [{"title": "Test title", "content": "Test snippet"}]}
            )
        )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> Any:
        """Record inputs while allowing legacy and error responses in tests."""
        return await self.call(hass, tool_input, llm_context)


class SearchAPI(llm.API):
    """Create real APIInstance objects for HA's public LLM API."""

    def __init__(self, hass: HomeAssistant, tool: SearchTool) -> None:
        super().__init__(hass=hass, id=API_ID, name="Simulated Tools for Assist")
        self.tools: list[llm.Tool] = [tool]
        self.contexts: list[llm.LLMContext] = []
        self.error: Exception | None = None
        self.custom_serializer = None

    async def async_get_api_instance(self, context: llm.LLMContext) -> llm.APIInstance:
        """Simulate API acquisition while preserving its real HA implementation."""
        self.contexts.append(context)
        if self.error:
            raise self.error
        return llm.APIInstance(
            api=self,
            api_prompt="Untrusted upstream API prompt; must not be returned.",
            llm_context=context,
            tools=self.tools,
            custom_serializer=self.custom_serializer,
        )


@pytest.fixture
def search_tool() -> SearchTool:
    """A controllable search provider."""
    return SearchTool()


@pytest.fixture
async def search_api(
    hass: HomeAssistant, search_tool: SearchTool
) -> AsyncGenerator[SearchAPI]:
    """Register a provider using HA's public API and clean it up afterwards."""
    api = SearchAPI(hass, search_tool)
    unregister = llm.async_register_api(hass, api)
    yield api
    unregister()
