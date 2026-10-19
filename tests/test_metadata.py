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
    SERVICE_CHECK_TOOLS,
    SERVICE_DESCRIBE_TOOL,
    SERVICE_LIST_TOOLS,
)

ROOT = Path(__file__).resolve().parents[1]


async def test_runtime_action_description(hass, bridge_entry):
    descriptions = await async_get_all_descriptions(hass)
    assert "search_web" not in descriptions[DOMAIN]
    english = await async_get_translations(hass, "en", "services", {DOMAIN})
    chinese = await async_get_translations(hass, "zh-Hans", "services", {DOMAIN})
    assert not any(".services.search_web." in key for key in english | chinese)
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
    checker = descriptions[DOMAIN][SERVICE_CHECK_TOOLS]
    assert checker["fields"] == {}
    assert checker["response"] == {"optional": False}
    key = f"component.{DOMAIN}.services.{SERVICE_CHECK_TOOLS}"
    assert english[f"{key}.name"] == "Check tool readiness"
    assert chinese[f"{key}.name"] == "检查工具就绪状态"
    descriptor = descriptions[DOMAIN][SERVICE_DESCRIBE_TOOL]
    assert descriptor["response"] == {"optional": False}
    assert set(descriptor["fields"]) == {"api_id", "tool_name"}
    key = f"component.{DOMAIN}.services.{SERVICE_DESCRIBE_TOOL}"
    assert english[f"{key}.name"] == "Describe an allowed tool"
    assert chinese[f"{key}.name"] == "查看白名单工具参数"


def test_documented_yaml_matches_delivered_example():
    blocks = re.findall(r"```yaml\n(.*?)\n```", (ROOT / "README.md").read_text(), re.S)
    documented = next(yaml.safe_load(block) for block in blocks if "- spec:" in block)
    delivered = yaml.safe_load((ROOT / "examples/eoaic2_search_web.yaml").read_text())
    assert documented == delivered


def test_runtime_english_translation_and_chinese_keys():
    path = ROOT / "custom_components" / DOMAIN
    source = json.loads((path / "strings.json").read_text())
    english = json.loads((path / "translations/en.json").read_text())
    chinese = json.loads((path / "translations/zh-Hans.json").read_text())
    assert source == english
    assert chinese["config"]["abort"]["already_configured"]
    assert "search_web" not in chinese["services"]
    assert chinese["services"][SERVICE_LIST_TOOLS]["name"]
    assert chinese["services"][SERVICE_CHECK_TOOLS]["name"]
    assert chinese["services"][SERVICE_CALL_TOOL]["fields"]["tool_args"]["name"]
    assert set(chinese["options"]["step"]["init"]["data"]) == {
        "enabled",
        "allowed_tools",
        "allow_side_effects",
        "amap_api_key",
        "amap_city",
        "amap_location",
        "amap_home_address",
        "amap_route_mode",
    }


def test_catalog_action_example_has_no_arguments():
    action = yaml.safe_load((ROOT / "examples/list_tools_action.yaml").read_text())
    assert action == {"action": f"{DOMAIN}.{SERVICE_LIST_TOOLS}", "data": {}}


def test_check_action_example_has_no_arguments():
    action = yaml.safe_load((ROOT / "examples/check_tools_action.yaml").read_text())
    assert action == {"action": f"{DOMAIN}.{SERVICE_CHECK_TOOLS}", "data": {}}
