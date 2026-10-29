"""Original 1.11.1 changes through real HA dispatch; providers remain simulated."""

from unittest.mock import patch

import pytest
from conftest import SearchAPI
from homeassistant.helpers import llm
from test_calculator import calculate
from test_tools_for_assist import QUERIES
from test_tools_for_assist import (
    test_original_query_calls_with_simulated_backends as assert_query_contract,
)

from custom_components.eoai_tools_bridge.const import DOMAIN

pytestmark = pytest.mark.tools_upstream


@pytest.mark.parametrize("case", QUERIES[3:-1], ids=[item[1] for item in QUERIES[3:-1]])
async def test_current_original_query_methods_keep_their_output_contracts(
    hass, bridge_entry, admin_context, release_source, case
):
    await assert_query_contract(hass, bridge_entry, admin_context, release_source, case)


@pytest.fixture
def release_version():
    return "1.11.1"


@pytest.fixture
async def searxng_api(hass, release_source):
    const = release_source("const")
    tool = release_source("searxng_search").SearXngSearchTool(
        {const.CONF_SEARXNG_URL: "https://search.example.invalid/search"}, hass
    )
    unregister = llm.async_register_api(hass, SearchAPI(hass, tool))
    yield
    unregister()


async def search(hass, context, query):
    return await hass.services.async_call(
        DOMAIN,
        "call_tool",
        {
            "api_id": "llm_intents",
            "tool_name": "search_web",
            "tool_args": {"query": query},
        },
        context=context,
        blocking=True,
        return_response=True,
    )


@pytest.mark.parametrize(
    "query", ["北京 天气", "C++ & A/B? #name=100%", "q&format=xml"]
)
async def test_searxng_preserves_query_as_one_encoded_parameter(
    hass, gateway_entry, searxng_api, admin_context, aioclient_mock, query
):
    aioclient_mock.get(
        "https://search.example.invalid/search",
        json={"results": [{"title": "Title", "content": "Text"}]},
    )
    result = await search(hass, admin_context, query)
    assert result["success"] is True
    assert result["result"]["results"] == [{"title": "Title", "content": "Text"}]
    assert aioclient_mock.call_count == 1
    assert dict(aioclient_mock.mock_calls[0][1].query) == {"format": "json", "q": query}


async def test_real_memory_cache_does_not_bypass_gateway_authorization(
    hass, gateway_entry, searxng_api, admin_context, aioclient_mock
):
    aioclient_mock.get(
        "https://search.example.invalid/search",
        json={"results": [{"title": "Cached title", "content": "Cached text"}]},
    )
    first = await search(hass, admin_context, "cache regression")
    second = await search(hass, admin_context, "cache regression")
    assert first["success"] is True and second["success"] is True
    assert first["result"] == second["result"]
    assert aioclient_mock.call_count == 1
    hass.config_entries.async_update_entry(
        gateway_entry, options={**gateway_entry.options, "enabled": False}
    )
    denied = await search(hass, admin_context, "cache regression")
    assert denied["error_code"] == "gateway_disabled" and denied["result"] is None
    assert aioclient_mock.call_count == 1


def test_memory_cache_shares_entries_isolates_filters_and_expires(
    release_source, freezer
):
    cls = release_source("cache").InMemoryCache
    params = {"query": "cache test", "freshness": "This Week"}
    cls().set("search", params, {"results": ["cached"]})
    assert cls().get("search", params) == {"results": ["cached"]}
    assert cls().get("search", {**params, "freshness": "This Day"}) is None
    assert cls().get("other_provider", params) is None
    freezer.tick(cls.DEFAULT_MAX_AGE)
    assert cls().get("search", params) is None


async def test_new_calculator_runs_once_in_executor_with_original_arguments(
    hass, gateway_entry, calculator_api, release_source, admin_context
):
    hass.config_entries.async_update_entry(
        gateway_entry,
        options={**gateway_entry.options, "allowed_tools": "basic_utilities/calculate"},
    )
    helper = release_source("calculator")._calculate_expression
    with patch.object(
        hass, "async_add_executor_job", wraps=hass.async_add_executor_job
    ) as executor:
        result = await calculate(hass, admin_context, data=["2**3+5%2"])
    assert result["success"] is True and result["result"] == {"value": "9"}
    assert [
        call.args for call in executor.call_args_list if call.args[0] is helper
    ] == [(helper, ["2**3+5%2"])]
