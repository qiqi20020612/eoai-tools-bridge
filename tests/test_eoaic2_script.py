"""Run EOAIC2's original ScriptFunction and our YAML on HA Core 2026.10.0.

The model and network search provider remain simulated. This is an upstream
script contract test, not a live Assist/conversation/TTS end-to-end test.
"""

import hashlib
import importlib
import sys
from pathlib import Path
from types import ModuleType

import probatio as vol
import pytest
import yaml
from homeassistant.core import Context
from homeassistant.helpers import llm

from custom_components.eoai_tools_bridge.const import (
    API_ID,
    CONF_ALLOWED_TOOLS,
    CONF_ENABLED,
    TOOL_NAME,
)
from scripts.fetch_test_upstream import DESTINATION, FILES

pytestmark = pytest.mark.upstream
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def upstream_script_function():
    """Load original modules without starting the full upstream integration."""
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
def function_config():
    example = yaml.safe_load((ROOT / "examples/eoaic2_functions.yaml").read_text())
    assert example[0]["spec"]["name"] == "web_search"
    return example[0]["function"]


@pytest.mark.parametrize(
    "query",
    [
        "搜索今天 AI 新闻",
        "123",
        "true",
        "[1, 2]",
        "{}",
        "None",
        "{{ states('light.secret') }}",
    ],
)
async def test_original_script_returns_function_result(
    hass,
    bridge_entry,
    search_api,
    search_tool,
    upstream_script_function,
    function_config,
    query,
):
    context = Context(user_id="original-user", parent_id="voice-request")
    source_context = llm.LLMContext(
        platform="extended_openai_conversation",
        context=context,
        language="zh-Hans",
        assistant="conversation",
        device_id="real-device-not-available-to-the-service",
    )
    config = upstream_script_function.validate_schema(function_config)
    response = await upstream_script_function.execute(
        hass, config, {"query": query}, source_context, []
    )
    assert response["success"] is True
    assert response["query"] == query
    assert response["results"] == [{"title": "Test title", "content": "Test snippet"}]
    tool_input = search_tool.call.call_args.args[1]
    bridge_context = search_tool.call.call_args.args[2]
    assert tool_input.tool_args == {"query": query}
    assert bridge_context.context is context
    assert bridge_context.device_id is None


async def test_original_script_returns_friendly_search_failure(
    hass, bridge_entry, upstream_script_function, function_config
):
    response = await upstream_script_function.execute(
        hass,
        upstream_script_function.validate_schema(function_config),
        {"query": "today AI news"},
        None,
        [],
    )
    assert response["success"] is False
    assert response["error_code"] == "api_unavailable"
    assert response["results"] == []


async def test_field_template_would_coerce_a_numeric_query(
    hass,
    bridge_entry,
    search_api,
    search_tool,
    upstream_script_function,
    function_config,
):
    # Reproduce why the task brief's suggested per-field template was adjusted.
    function_config["sequence"][0]["data"] = {"query": "{{ query }}"}
    with pytest.raises(vol.Invalid):
        await upstream_script_function.execute(
            hass,
            upstream_script_function.validate_schema(function_config),
            {"query": "123"},
            None,
            [],
        )
    search_tool.call.assert_not_called()


@pytest.mark.parametrize("available", [False, True])
async def test_original_script_returns_read_only_catalog(
    hass, bridge_entry, search_api, search_tool, upstream_script_function, available
):
    if not available:
        search_api.tools = []
    example = yaml.safe_load((ROOT / "examples/eoaic2_list_tools.yaml").read_text())[0]
    assert example["spec"]["parameters"]["properties"] == {}
    config = upstream_script_function.validate_schema(example["function"])
    response = await upstream_script_function.execute(hass, config, {}, None, [])
    assert response["success"] is True
    assert len(response["tools"]) == int(available)
    if available:
        assert response["tools"][0]["parameters"]["required"] == ["query"]
    search_tool.call.assert_not_called()


def gateway_config(function):
    example = yaml.safe_load((ROOT / "examples/eoaic2_call_tool.yaml").read_text())[0]
    assert example["spec"]["name"] == "call_allowed_tool"
    return function.validate_schema(example["function"])


@pytest.mark.parametrize("query", ["123", "{}", "{{ states('light.private') }}"])
async def test_original_script_calls_allowed_tool_with_original_admin(
    hass,
    gateway_entry,
    search_api,
    search_tool,
    upstream_script_function,
    admin_context,
    query,
):
    original = llm.LLMContext(
        platform="extended_openai_conversation",
        context=admin_context,
        language="zh-Hans",
        assistant="conversation",
        device_id="voice-device",
    )
    response = await upstream_script_function.execute(
        hass,
        gateway_config(upstream_script_function),
        {"api_id": API_ID, "tool_name": TOOL_NAME, "tool_args": {"query": query}},
        original,
        [],
    )
    assert response["success"] is True
    assert response["result"] == {
        "results": [{"title": "Test title", "content": "Test snippet"}]
    }
    search_tool.call.assert_awaited_once()
    _, tool_input, bridge_context = search_tool.call.call_args.args
    assert tool_input.tool_args == {"query": query}
    assert bridge_context.context is admin_context
    assert bridge_context.device_id is None


@pytest.mark.parametrize("identity", ["none", "non_admin", "inactive_admin"])
async def test_original_script_cannot_create_admin_identity(
    hass,
    gateway_entry,
    search_api,
    search_tool,
    upstream_script_function,
    hass_admin_user,
    hass_read_only_user,
    identity,
):
    original = None
    if identity != "none":
        user = hass_read_only_user if identity == "non_admin" else hass_admin_user
        if identity == "inactive_admin":
            user.is_active = False
        original = llm.LLMContext(
            platform="extended_openai_conversation",
            context=Context(user_id=user.id),
            language="zh-Hans",
            assistant="conversation",
            device_id=None,
        )
    response = await upstream_script_function.execute(
        hass,
        gateway_config(upstream_script_function),
        {"api_id": API_ID, "tool_name": TOOL_NAME, "tool_args": {"query": "test"}},
        original,
        [],
    )
    assert response["error_code"] == "permission_denied"
    assert response["outcome_unknown"] is False
    assert search_api.contexts == []
    search_tool.call.assert_not_called()


@pytest.mark.parametrize("enabled", [False, True])
async def test_original_script_handles_disabled_and_invalid_args(
    hass,
    gateway_entry,
    search_api,
    search_tool,
    upstream_script_function,
    admin_context,
    enabled,
):
    hass.config_entries.async_update_entry(
        gateway_entry,
        options={CONF_ENABLED: enabled, CONF_ALLOWED_TOOLS: f"{API_ID}/{TOOL_NAME}"},
    )
    original = llm.LLMContext(
        platform="extended_openai_conversation",
        context=admin_context,
        language="zh-Hans",
        assistant="conversation",
        device_id=None,
    )
    response = await upstream_script_function.execute(
        hass,
        gateway_config(upstream_script_function),
        {"api_id": API_ID, "tool_name": TOOL_NAME, "tool_args": {"query": 123}},
        original,
        [],
    )
    assert response["error_code"] == ("invalid_args" if enabled else "gateway_disabled")
    search_tool.call.assert_not_called()
