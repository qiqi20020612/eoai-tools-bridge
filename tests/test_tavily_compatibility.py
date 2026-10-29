"""Check unmodified Tools for Assist 1.11.0 against the controlled bridge runtime."""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from conftest import SearchAPI
from homeassistant.helpers import llm

from custom_components.eoai_tools_bridge.const import (
    DOMAIN,
    MAX_RESPONSE_BYTES,
    MAX_TOOL_RESULT_TEXT,
)

pytestmark = pytest.mark.tools_upstream


@pytest.fixture
def tavily_tool(hass, release_source):
    """Instantiate the original provider, never install its integration."""
    const = release_source("const")
    module = release_source("tavily_search")
    return module.TavilySearchTool(
        {
            const.CONF_PROVIDER_API_KEYS: {
                const.PROVIDER_TAVILY: "simulated-tavily-key"
            },
        },
        hass,
    )


@pytest.fixture
async def tavily_api(hass, tavily_tool):
    api = SearchAPI(hass, tavily_tool)
    unregister = llm.async_register_api(hass, api)
    try:
        yield api
    finally:
        unregister()


@pytest.fixture
def http_backend(release_source, release_version):
    """Simulate HTTP and cache only; execute original schemas and methods."""
    response = MagicMock(status=200)
    response.json = AsyncMock(
        return_value={
            "results": [
                {
                    "title": "Simulated title",
                    "content": "<b>Simulated</b> snippet",
                    "url": "https://example.invalid/source",
                }
            ],
        }
    )
    response.text = AsyncMock(return_value="simulated error body")
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    session = Mock()
    session.post.return_value = response
    cache = Mock()
    cache.get.return_value = None
    with (
        patch.object(
            release_source("base_web_search"),
            "SQLiteCache" if release_version == "1.11.0" else "InMemoryCache",
            return_value=cache,
        ),
        patch.object(
            release_source("tavily_search"),
            "async_get_clientsession",
            return_value=session,
        ),
    ):
        yield session, response


async def call(hass, action, data=None, context=None):
    return await hass.services.async_call(
        DOMAIN,
        action,
        data or {},
        context=context,
        blocking=True,
        return_response=True,
    )


async def search(hass, context, arguments):
    return await call(
        hass,
        "call_tool",
        {"api_id": "llm_intents", "tool_name": "search_web", "tool_args": arguments},
        context,
    )


async def test_new_provider_catalog_and_readiness_need_no_runtime_change(
    hass, gateway_entry, admin_context, tavily_api, tavily_tool, http_backend
):
    with patch.object(tavily_tool, "async_call", new_callable=AsyncMock) as invoke:
        catalog = await call(hass, "list_tools")
        assert catalog["success"] is True
        tool = catalog["tools"][0]
        assert (tool["api_id"], tool["name"]) == ("llm_intents", "search_web")
        assert tool["read_only_basis"] == "audited_allowlist"
        schema = tool["parameters"]
        assert schema["required"] == ["query"]
        assert schema["additionalProperties"] is False
        assert schema["properties"]["topic"]["enum"] == ["general", "news", "finance"]
        assert schema["properties"]["time_range"]["enum"] == [
            "day",
            "week",
            "month",
            "year",
        ]
        readiness = await call(hass, "check_tools", context=admin_context)
        assert readiness["success"] is True
        assert readiness["tools"][0]["status"] == "ready"
        assert readiness["tools"][0]["requires_side_effects"] is False
        invoke.assert_not_called()
        http_backend[0].post.assert_not_called()


@pytest.mark.parametrize("query", ["123", "{{ states('light.private') }}"])
async def test_generic_search_uses_original_tavily_with_unchanged_query_contract(
    hass, gateway_entry, admin_context, tavily_api, http_backend, query
):
    response = await search(hass, admin_context, {"query": query})
    assert response["success"] is True
    assert response["result"]["results"] == [
        {"title": "Simulated title", "content": "Simulated snippet"}
    ]
    payload = http_backend[0].post.call_args.kwargs["json"]
    assert payload["query"] == query
    assert "topic" not in payload
    assert "time_range" not in payload
    assert "instruction" not in json.dumps(response)
    assert "simulated-tavily-key" not in json.dumps(response)


@pytest.mark.parametrize(
    "topic,time_range",
    [
        ("general", "day"),
        ("news", "week"),
        ("finance", "month"),
        ("general", "year"),
    ],
)
async def test_native_tavily_filters_pass_through_existing_gateway(
    hass, gateway_entry, admin_context, tavily_api, http_backend, topic, time_range
):
    response = await call(
        hass,
        "call_tool",
        {
            "api_id": "llm_intents",
            "tool_name": "search_web",
            "tool_args": {"query": "123", "topic": topic, "time_range": time_range},
        },
        admin_context,
    )
    assert response["success"] is True
    assert response["outcome_unknown"] is False
    assert response["result"] == {
        "results": [{"title": "Simulated title", "content": "Simulated snippet"}]
    }
    payload = http_backend[0].post.call_args.kwargs["json"]
    assert payload["query"] == "123"
    assert payload["topic"] == topic
    assert payload["time_range"] == time_range
    assert tavily_api.contexts[0].context is admin_context


@pytest.mark.parametrize(
    "extra",
    [
        {"topic": "sport"},
        {"time_range": "yesterday"},
        {"Authorization": "forbidden"},
    ],
)
async def test_new_provider_keeps_native_argument_rejection(
    hass, gateway_entry, admin_context, tavily_api, http_backend, extra
):
    response = await call(
        hass,
        "call_tool",
        {
            "api_id": "llm_intents",
            "tool_name": "search_web",
            "tool_args": {"query": "123", **extra},
        },
        admin_context,
    )
    assert response["error_code"] == "invalid_args"
    http_backend[0].post.assert_not_called()


async def test_tavily_generated_answer_and_empty_results_are_supported(
    hass,
    gateway_entry,
    admin_context,
    tavily_api,
    tavily_tool,
    release_source,
    http_backend,
):
    tavily_tool.config[release_source("const").CONF_TAVILY_INCLUDE_ANSWER] = True
    http_backend[1].json.return_value = {"answer": "Simulated answer", "results": []}
    response = await search(hass, admin_context, {"query": "123"})
    assert response["result"]["results"] == [
        {"title": "Tavily answer", "content": "Simulated answer"}
    ]
    http_backend[1].json.return_value = {"results": []}
    empty = await search(hass, admin_context, {"query": "123"})
    assert empty["success"] is True
    assert empty["result"]["results"] == "No results found"


async def test_tavily_full_page_content_keeps_bridge_output_limits(
    hass,
    gateway_entry,
    admin_context,
    tavily_api,
    tavily_tool,
    release_source,
    http_backend,
):
    tavily_tool.config[release_source("const").CONF_TAVILY_INCLUDE_RAW_CONTENT] = True
    http_backend[1].json.return_value = {
        "results": [
            {
                "title": "Simulated page",
                "content": "snippet",
                "raw_content": "字" * 10_000,
            }
        ]
    }
    response = await search(hass, admin_context, {"query": "123"})
    assert response["success"] is True
    assert response["truncated"] is True
    body = response["result"]
    assert len(body["results"][0]["content"]) == MAX_TOOL_RESULT_TEXT
    assert len(json.dumps(response, ensure_ascii=False).encode()) <= MAX_RESPONSE_BYTES


async def test_tavily_http_error_does_not_escape_bridge_response(
    hass, gateway_entry, admin_context, tavily_api, http_backend
):
    http_backend[1].status = 502
    http_backend[1].text.return_value = "<html>simulated private error</html>"
    response = await search(hass, admin_context, {"query": "123"})
    assert response["error_code"] == "upstream_error"
    assert "simulated private error" not in json.dumps(response)


async def test_unauthenticated_tavily_gateway_call_still_denied(
    hass, gateway_entry, tavily_api, http_backend
):
    response = await call(
        hass,
        "call_tool",
        {
            "api_id": "llm_intents",
            "tool_name": "search_web",
            "tool_args": {"query": "123"},
        },
    )
    assert response["error_code"] == "permission_denied"
    assert tavily_api.contexts == []
    http_backend[0].post.assert_not_called()
