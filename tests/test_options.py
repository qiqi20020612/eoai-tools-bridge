"""Explicit allowlist options, empty defaults, and fail-closed stored settings."""

import probatio as vol
import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.eoai_tools_bridge.const import (
    CONF_ALLOW_SIDE_EFFECTS,
    CONF_ALLOWED_TOOLS,
    CONF_ENABLED,
)
from custom_components.eoai_tools_bridge.policy import get_policy, normalize_options


async def test_options_start_disabled_and_do_not_open_apis(
    hass, bridge_entry, search_api
):
    result = await hass.config_entries.options.async_init(bridge_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    fields = {key.schema: key.default() for key in result["data_schema"].schema}
    assert fields == {
        CONF_ENABLED: False,
        CONF_ALLOWED_TOOLS: "",
        CONF_ALLOW_SIDE_EFFECTS: False,
    }
    assert get_policy(hass).enabled is False
    assert search_api.contexts == []


async def test_options_validate_then_apply_immediately(hass, bridge_entry, search_api):
    result = await hass.config_entries.options.async_init(bridge_entry.entry_id)
    rejected = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLED: True,
            CONF_ALLOWED_TOOLS: "*/*",
            CONF_ALLOW_SIDE_EFFECTS: False,
        },
    )
    assert rejected["type"] is FlowResultType.FORM
    assert rejected["errors"] == {"base": "invalid_allowlist"}
    assert get_policy(hass).enabled is False
    accepted = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLED: True,
            CONF_ALLOWED_TOOLS: (
                " llm_intents/search_web\n\nassist/HassTurnOn\nllm_intents/search_web "
            ),
            CONF_ALLOW_SIDE_EFFECTS: True,
        },
    )
    assert accepted["type"] is FlowResultType.CREATE_ENTRY
    assert (
        bridge_entry.options[CONF_ALLOWED_TOOLS]
        == "assist/HassTurnOn\nllm_intents/search_web"
    )
    assert get_policy(hass).enabled is True
    assert get_policy(hass).allow_side_effects is True
    assert search_api.contexts == []


@pytest.mark.parametrize(
    "allowlist",
    [
        "*/*",
        "llm_intents/*",
        "llm_intents",
        "/search_web",
        "api/tool/extra",
        "http://example/tool",
        "api /tool",
        "{{ user }}/tool",
        "api/工具",
        "x" * 129 + "/tool",
        "\n".join(f"api/tool_{i}" for i in range(33)),
        "x" * 10_001,
        ["api/tool"],
    ],
)
def test_invalid_allowlists(allowlist):
    with pytest.raises(vol.Invalid):
        normalize_options({CONF_ENABLED: True, CONF_ALLOWED_TOOLS: allowlist})


@pytest.mark.parametrize(
    "options",
    [
        {CONF_ENABLED: True},
        {CONF_ENABLED: "true"},
        {CONF_ALLOW_SIDE_EFFECTS: "false"},
        {CONF_ALLOWED_TOOLS: None},
    ],
)
def test_invalid_stored_options_disable_gateway(hass, bridge_entry, options):
    hass.config_entries.async_update_entry(bridge_entry, options=options)
    assert get_policy(hass).enabled is False
    assert not get_policy(hass).allowed_tools


def test_empty_allowlist_grants_nothing():
    assert normalize_options({}) == {
        CONF_ENABLED: False,
        CONF_ALLOWED_TOOLS: "",
        CONF_ALLOW_SIDE_EFFECTS: False,
    }
