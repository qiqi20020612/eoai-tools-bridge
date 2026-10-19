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


@pytest.fixture
def tools_source():
    """Import immutable originals in a namespace without upstream setup."""
    import hashlib
    import importlib
    import sys
    from types import ModuleType

    from scripts.fetch_tools_upstream import DESTINATION, FILES

    for name, expected in FILES.items():
        path = DESTINATION / name
        assert path.exists(), "Run python scripts/fetch_tools_upstream.py first"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    prefix = "_eoai_bridge_tools_contract"
    package = ModuleType(prefix)
    package.__path__ = [str(DESTINATION)]
    sys.modules[prefix] = package
    try:
        yield lambda name: importlib.import_module(f"{prefix}.{name}")
    finally:
        for name in list(sys.modules):
            if name == prefix or name.startswith(prefix + "."):
                sys.modules.pop(name)


@pytest.fixture
def release_source():
    """Use a separate release cache, preserving the existing source baseline."""
    import hashlib
    import importlib
    import sys
    from types import ModuleType

    from scripts.fetch_tools_upstream import RELEASE_DESTINATION, RELEASE_FILES

    for name, expected in RELEASE_FILES.items():
        path = RELEASE_DESTINATION / name
        assert path.exists(), "Run python scripts/fetch_tools_upstream.py first"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    prefix = "_eoai_bridge_tools_1_11_contract"
    package = ModuleType(prefix)
    package.__path__ = [str(RELEASE_DESTINATION)]
    sys.modules[prefix] = package
    try:
        yield lambda name: importlib.import_module(f"{prefix}.{name}")
    finally:
        for name in list(sys.modules):
            if name == prefix or name.startswith(prefix + "."):
                sys.modules.pop(name)


@pytest.fixture
def upstream_script_function():
    """Load original modules without starting the full upstream integration."""
    import hashlib
    import importlib
    import sys
    from types import ModuleType

    from scripts.fetch_test_upstream import DESTINATION, FILES

    for relative_path, expected in FILES.items():
        path = DESTINATION / relative_path
        if not path.exists():
            pytest.skip("Run python scripts/fetch_test_upstream.py first")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected

    prefix = "_eoai_bridge_contract_upstream"
    # Namespace packages avoid executing upstream's unrelated full integration
    # and function registry. const/base/exceptions/script themselves are original.
    for suffix, directory in [
        ("", DESTINATION),
        (".functions", DESTINATION / "functions"),
    ]:
        module = ModuleType(prefix + suffix)
        module.__path__ = [str(directory)]
        sys.modules[prefix + suffix] = module
    try:
        script_module = importlib.import_module(prefix + ".functions.script")
        yield script_module.ScriptFunction()
    finally:
        for name in list(sys.modules):
            if name == prefix or name.startswith(prefix + "."):
                sys.modules.pop(name)


@pytest.fixture
def release_apis(release_source):
    """Load original API classes without running integration setup."""
    import sys

    const = release_source("const")
    package = sys.modules[const.__package__]
    # The original __init__ re-exports these; use its original const values
    # while avoiding full integration setup/circular initialization.
    package.CONF_SEARCH_PROVIDER = const.CONF_SEARCH_PROVIDER
    package.CONF_SEARCH_PROVIDER_BRAVE = const.CONF_SEARCH_PROVIDER_BRAVE
    return release_source("llm_functions")


@pytest.fixture
async def calculator_api(hass, release_apis, release_source):
    const = release_source("const")
    api = release_apis.BasicUtilitiesAPI(
        hass, {const.CONF_CALCULATOR_ENABLED: True}, const.BASIC_UTILITIES_API_NAME
    )
    unregister = llm.async_register_api(hass, api)
    yield api
    unregister()


@pytest.fixture
def video_entities(hass, bridge_entry):
    """Real HA registries/states with simulated media devices, never hardware."""
    from homeassistant.components.media_player import MediaPlayerEntityFeature
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    entities = []
    for index, room in enumerate(("Living Room", "Kitchen")):
        area = ar.async_get(hass).async_create(room)
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=bridge_entry.entry_id,
            identifiers={("test", str(index))},
        )
        device = dr.async_get(hass).async_update_device(device.id, area_id=area.id)
        entity = er.async_get(hass).async_get_or_create(
            "media_player",
            "test",
            str(index),
            suggested_object_id=f"video_{index}",
            device_id=device.id,
        )
        hass.states.async_set(
            entity.entity_id,
            "off",
            {
                "device_class": "tv",
                "supported_features": int(MediaPlayerEntityFeature.PLAY_MEDIA),
            },
        )
        entities.append((entity, device, area))
    return entities


@pytest.fixture
async def media_api(hass, release_apis, release_source, video_entities):
    const = release_source("const")
    api = release_apis.MediaAPI(
        hass, {const.CONF_YOUTUBE_ENABLED: True}, const.MEDIA_API_NAME
    )
    unregister = llm.async_register_api(hass, api)
    yield api
    unregister()
