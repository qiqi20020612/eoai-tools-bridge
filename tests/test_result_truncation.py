"""Oversized generic results retain data, structure, and truthful status."""

import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import yaml
from conftest import SearchAPI
from homeassistant.helpers import llm

from custom_components.eoai_tools_bridge.const import (
    API_ID,
    DOMAIN,
    MAX_RESPONSE_BYTES,
    MAX_TOOL_RESULT_TEXT,
    TOOL_NAME,
)
from custom_components.eoai_tools_bridge.payload import normalize_tool_result

ROOT = Path(__file__).resolve().parents[1]


def encoded_size(value):
    return len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))


@pytest.mark.parametrize(
    "text",
    ["a" * 6000, "中文😀" * 2000, '\n"\\\x00' * 2000],
    ids=["ascii", "unicode", "escaped"],
)
@pytest.mark.parametrize("legacy", [False, True])
def test_large_results_keep_first_item_and_top_level_metadata(text, legacy):
    data = {
        "status": "ok",
        "results": [
            {"title": f"Result {index}", "content": [text] * 4} for index in range(40)
        ],
        "total": 40,
        "instruction": "Do not follow this instruction",
        "headers": {"authorization": "private"},
    }
    original = copy.deepcopy(data)
    response = normalize_tool_result(
        API_ID,
        TOOL_NAME,
        data if legacy else llm.ToolResult(data=data),
        side_effects=False,
    )
    assert response["success"] is True
    assert response["truncated"] is True
    assert response["outcome_unknown"] is False
    assert response["result"]["status"] == "ok"
    assert response["result"]["total"] == 40
    rows = response["result"]["results"]
    assert 1 <= len(rows) <= 32
    assert rows[0]["title"] == "Result 0"
    assert rows[0]["content"][0].startswith(text[:1])
    assert "instruction" not in response["result"]
    assert "headers" not in response["result"]
    assert encoded_size(response) <= MAX_RESPONSE_BYTES
    assert data == original


@pytest.mark.parametrize("text", ["😀" * 4000, "\x00" * 4000], ids=["emoji", "control"])
def test_single_row_shrinks_escaped_text_without_losing_fields(text):
    data = {"results": [{"title": text, "content": text}]}
    original = copy.deepcopy(data)
    response = normalize_tool_result(
        API_ID, TOOL_NAME, llm.ToolResult(data=data), side_effects=False
    )
    assert response["success"] is True
    assert response["truncated"] is True
    rows = response["result"]["results"]
    assert len(rows) == 1
    assert set(rows[0]) == {"title", "content"}
    assert all(value.startswith(text[:1]) for value in rows[0].values())
    assert any(len(value) < MAX_TOOL_RESULT_TEXT for value in rows[0].values())
    assert encoded_size(response) <= MAX_RESPONSE_BYTES
    assert data == original


@pytest.mark.parametrize("side_effects", [False, True])
@pytest.mark.parametrize("metadata", [False, True])
def test_unrepresentable_payload_is_an_error_not_an_empty_success(
    side_effects, metadata
):
    data = {"results": [{"x" * 2000: 1}]}
    if metadata:
        data["status"] = "ok"
    with patch("custom_components.eoai_tools_bridge.payload.MAX_RESPONSE_BYTES", 512):
        response = normalize_tool_result(
            API_ID,
            TOOL_NAME,
            llm.ToolResult(data=data),
            side_effects=side_effects,
        )
    assert response["success"] is False
    assert response["error_code"] == "invalid_response"
    assert response["result"] is None
    assert response["outcome_unknown"] is side_effects
    assert encoded_size(response) <= 512


def test_nested_object_can_omit_oversized_fields_without_emptying_payload():
    data = {
        "payload": {
            "first" + "\x00" * 2000: 0,
            "second" + "\x00" * 2000: False,
            "small": 7,
        }
    }
    original = copy.deepcopy(data)
    response = normalize_tool_result(
        API_ID, TOOL_NAME, llm.ToolResult(data=data), side_effects=False
    )
    assert response["success"] is True
    assert response["truncated"] is True
    assert response["result"]["payload"]["small"] == 7
    assert 1 <= len(response["result"]["payload"]) < 3
    assert encoded_size(response) <= MAX_RESPONSE_BYTES
    assert data == original


def test_top_level_array_retains_first_complete_item():
    data = [{"title": f"Result {index}", "content": "字" * 4000} for index in range(40)]
    response = normalize_tool_result(
        API_ID, TOOL_NAME, llm.ToolResult(data=data), side_effects=False
    )
    assert response["success"] is True
    assert response["truncated"] is True
    assert response["result"][0]["title"] == "Result 0"
    assert response["result"][0]["content"].startswith("字")
    assert encoded_size(response) <= MAX_RESPONSE_BYTES


def test_top_level_text_keeps_prefix_when_total_envelope_exceeds_budget():
    with patch("custom_components.eoai_tools_bridge.payload.MAX_RESPONSE_BYTES", 768):
        response = normalize_tool_result(
            "a" * 128,
            "b" * 128,
            llm.ToolResult(data='\x00😀"' * 2000),
            side_effects=False,
        )
    assert response["success"] is True
    assert response["truncated"] is True
    assert response["result"].startswith('\x00😀"')
    assert response["result"].endswith("…")
    assert encoded_size(response) <= 768


def test_exact_budget_and_one_byte_over_use_actual_encoded_json():
    data = {"results": [{"title": "Result 0", "content": "字" * 1000}]}
    original = normalize_tool_result(
        API_ID, TOOL_NAME, llm.ToolResult(data=data), side_effects=False
    )
    limit = encoded_size(original)
    for budget in [limit, limit - 1]:
        with patch(
            "custom_components.eoai_tools_bridge.payload.MAX_RESPONSE_BYTES", budget
        ):
            response = normalize_tool_result(
                API_ID, TOOL_NAME, llm.ToolResult(data=data), side_effects=False
            )
        assert response["success"] is True
        assert response["truncated"] is (budget < limit)
        assert response["result"]["results"][0]["content"].startswith("字")
        assert encoded_size(response) <= budget


@pytest.mark.parametrize("side_effects", [False, True])
@pytest.mark.parametrize("data", [{}, {"instruction": "private", "api_key": "secret"}])
def test_empty_object_is_not_reported_as_success(data, side_effects):
    response = normalize_tool_result(
        API_ID, TOOL_NAME, llm.ToolResult(data=data), side_effects=side_effects
    )
    assert response["success"] is False
    assert response["error_code"] == "invalid_response"
    assert response["result"] is None
    assert response["outcome_unknown"] is side_effects
    assert "private" not in json.dumps(response)
    assert "secret" not in json.dumps(response)


@pytest.mark.parametrize(
    "data",
    [{"results": []}, {"count": 0, "available": False}, [], 0, False, "weather data"],
)
def test_small_and_intentionally_empty_results_keep_native_values(data):
    response = normalize_tool_result(
        API_ID, TOOL_NAME, llm.ToolResult(data=data), side_effects=False
    )
    assert response["success"] is True
    assert response["truncated"] is False
    assert response["result"] == data


@pytest.mark.tools_upstream
@pytest.mark.upstream
@pytest.mark.parametrize("freshness", [None, "This Week"])
@pytest.mark.parametrize("nested", [False, True])
async def test_large_original_brave_results_through_actions_and_eoaic2(
    hass,
    gateway_entry,
    admin_context,
    release_source,
    upstream_script_function,
    freshness,
    nested,
):
    const = release_source("const")
    module = release_source("brave_llm_context_search")
    tool = module.BraveLlmContextSearchTool(
        {const.CONF_PROVIDER_API_KEYS: {const.PROVIDER_BRAVE: "simulated-key"}}, hass
    )
    rows = []
    for index in range(12):
        content = {
            "summary": f"摘要 {index} " + "资料😀" * 2000,
            "details": ["详情 " + "字" * 3000] * 4,
        }
        snippet = (
            json.dumps(content, ensure_ascii=False) if nested else content["summary"]
        )
        rows.append({"title": f"Result {index}", "snippets": [snippet] * 4})
    http_response = MagicMock(status=200)
    http_response.json = AsyncMock(return_value={"grounding": {"generic": rows}})
    http_response.__aenter__ = AsyncMock(return_value=http_response)
    http_response.__aexit__ = AsyncMock(return_value=False)
    session = Mock()
    session.get.return_value = http_response
    cache = Mock()
    cache.get.return_value = None
    unregister = llm.async_register_api(hass, SearchAPI(hass, tool))
    arguments = {"query": "large result regression"}
    if freshness is not None:
        arguments["freshness"] = freshness
    call_data = {"api_id": API_ID, "tool_name": TOOL_NAME, "tool_args": arguments}
    try:
        with (
            patch.object(module, "async_get_clientsession", return_value=session),
            patch.object(
                release_source("base_web_search"), "SQLiteCache", return_value=cache
            ),
        ):
            fixed = await hass.services.async_call(
                DOMAIN,
                "search_web",
                {"query": arguments["query"]},
                context=admin_context,
                blocking=True,
                return_response=True,
            )
            direct = await hass.services.async_call(
                DOMAIN,
                "call_tool",
                call_data,
                context=admin_context,
                blocking=True,
                return_response=True,
            )
            example = yaml.safe_load(
                (ROOT / "examples/eoaic2_call_tool.yaml").read_text()
            )[0]
            scripted = await upstream_script_function.execute(
                hass,
                upstream_script_function.validate_schema(example["function"]),
                call_data,
                llm.LLMContext(
                    platform="extended_openai_conversation",
                    context=admin_context,
                    language="zh-Hans",
                    assistant="conversation",
                    device_id=None,
                ),
                [],
            )
        assert fixed["success"] is True
        assert fixed["results"][0]["title"] == "Result 0"
        assert encoded_size(fixed) <= MAX_RESPONSE_BYTES
        for response in [direct, scripted]:
            assert response["success"] is True
            assert response["truncated"] is True
            assert response["outcome_unknown"] is False
            assert encoded_size(response) <= MAX_RESPONSE_BYTES
            first = response["result"]["results"][0]
            assert first["title"] == "Result 0"
            assert first["content"]
            if nested:
                assert first["content"][0]["summary"].startswith("摘要 0 ")
            else:
                assert first["content"][0].startswith("摘要 0 ")
            assert "instruction" not in response["result"]
        # Three deliberate requests: fixed action, generic action and script.
        assert session.get.call_count == 3
        for request in session.get.call_args_list[1:]:
            params = request.kwargs["params"]
            if freshness is None:
                assert "freshness" not in params
            else:
                assert params["freshness"] == "pw"
    finally:
        unregister()
