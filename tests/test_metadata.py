"""Verify runtime action descriptions and consistency of the shipped YAML."""

import json
import re
from pathlib import Path

import yaml
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.helpers.translation import async_get_translations

from custom_components.eoai_tools_bridge.const import (
    DOMAIN,
    SERVICE_CALL_TOOL,
    SERVICE_LIST_TOOLS,
    SERVICE_SEARCH_WEB,
)

ROOT = Path(__file__).resolve().parents[1]


async def test_runtime_action_description(hass, bridge_entry):
    descriptions = await async_get_all_descriptions(hass)
    description = descriptions[DOMAIN][SERVICE_SEARCH_WEB]
    assert description["fields"]["query"]["required"] is True
    assert description["response"] == {"optional": False}
    english = await async_get_translations(hass, "en", "services", {DOMAIN})
    chinese = await async_get_translations(hass, "zh-Hans", "services", {DOMAIN})
    key = f"component.{DOMAIN}.services.{SERVICE_SEARCH_WEB}"
    assert english[f"{key}.name"] == "Search the web"
    assert english[f"{key}.fields.query.name"] == "Search query"
    assert chinese[f"{key}.name"] == "搜索网页"
    assert chinese[f"{key}.fields.query.name"] == "搜索内容"
    catalog = descriptions[DOMAIN][SERVICE_LIST_TOOLS]
    assert catalog["fields"] == {}
    assert catalog["response"] == {"optional": False}
    key = f"component.{DOMAIN}.services.{SERVICE_LIST_TOOLS}"
    assert english[f"{key}.name"] == "List available tools"
    assert chinese[f"{key}.name"] == "列出可用工具"
    gateway = descriptions[DOMAIN][SERVICE_CALL_TOOL]
    assert gateway["response"] == {"optional": False}
    assert gateway["fields"]["api_id"]["required"] is True
    assert gateway["fields"]["tool_name"]["required"] is True
    assert gateway["fields"]["tool_args"]["selector"] == {"object": {"multiple": False}}
    key = f"component.{DOMAIN}.services.{SERVICE_CALL_TOOL}"
    assert english[f"{key}.name"] == "Call an allowed tool"
    assert chinese[f"{key}.name"] == "调用白名单工具"


def test_documented_yaml_matches_delivered_example():
    blocks = re.findall(r"```yaml\n(.*?)\n```", (ROOT / "README.md").read_text(), re.S)
    documented = next(yaml.safe_load(block) for block in blocks if "- spec:" in block)
    delivered = yaml.safe_load((ROOT / "examples/eoaic2_functions.yaml").read_text())
    assert documented == delivered


def test_runtime_english_translation_and_chinese_keys():
    path = ROOT / "custom_components" / DOMAIN
    source = json.loads((path / "strings.json").read_text())
    english = json.loads((path / "translations/en.json").read_text())
    chinese = json.loads((path / "translations/zh-Hans.json").read_text())
    assert source == english
    assert chinese["config"]["abort"]["already_configured"]
    assert chinese["services"][SERVICE_SEARCH_WEB]["fields"]["query"]["name"]
    assert chinese["services"][SERVICE_LIST_TOOLS]["name"]
    assert chinese["services"][SERVICE_CALL_TOOL]["fields"]["tool_args"]["name"]
    assert set(chinese["options"]["step"]["init"]["data"]) == {
        "enabled",
        "allowed_tools",
        "allow_side_effects",
    }


def test_catalog_action_example_has_no_arguments():
    action = yaml.safe_load((ROOT / "examples/list_tools_action.yaml").read_text())
    assert action == {"action": f"{DOMAIN}.{SERVICE_LIST_TOOLS}", "data": {}}
