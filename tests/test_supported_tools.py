"""The complete non-Home-Control tool inventory through original 1.11.0 APIs."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from homeassistant.helpers import llm

from custom_components.eoai_tools_bridge.const import AUDITED_READ_ONLY_TOOLS, DOMAIN

pytestmark = pytest.mark.tools_upstream
ROOT = Path(__file__).resolve().parents[1]


async def test_complete_original_supported_apis_fit_catalog_and_descriptions(
    hass, gateway_entry, admin_context, release_apis, release_source, video_entities
):
    const = release_source("const")
    config = {
        const.CONF_SEARCH_PROVIDER: const.CONF_SEARCH_PROVIDER_TAVILY,
        const.CONF_GOOGLE_PLACES_ENABLED: True,
        const.CONF_GOOGLE_ROUTES_ENABLED: True,
        const.CONF_YOUTUBE_ENABLED: True,
        const.CONF_WIKIPEDIA_ENABLED: True,
        const.CONF_WEATHER_ENABLED: True,
        const.CONF_CALCULATOR_ENABLED: True,
        const.CONF_UNIT_CONVERTER_ENABLED: True,
        const.CONF_DATE_INFO_ENABLED: True,
    }
    apis = [
        release_apis.SearchAPI(hass, config, const.SEARCH_API_NAME),
        release_apis.WeatherAPI(hass, config, const.WEATHER_API_NAME),
        release_apis.BasicUtilitiesAPI(hass, config, const.BASIC_UTILITIES_API_NAME),
        release_apis.MediaAPI(hass, config, const.MEDIA_API_NAME),
    ]
    pairs = {(api.id, tool.name) for api in apis for tool in api.get_enabled_tools()}
    assert pairs == AUDITED_READ_ONLY_TOOLS | {("media_services", "play_video")}
    assert len(pairs) == 10
    assert all(api_id != "HomeControl" for api_id, _ in pairs)
    hass.config_entries.async_update_entry(
        gateway_entry,
        options={
            "enabled": True,
            "allow_side_effects": False,
            "allowed_tools": "\n".join(f"{api}/{tool}" for api, tool in sorted(pairs)),
        },
    )
    unregister = [llm.async_register_api(hass, api) for api in apis]
    try:
        with patch.object(llm.APIInstance, "async_call_tool", new=Mock()) as invoke:
            catalog = await hass.services.async_call(
                DOMAIN,
                "list_tools",
                {},
                context=admin_context,
                blocking=True,
                return_response=True,
            )
            assert catalog["success"] is True
            assert catalog["truncated"] is False
            assert {
                (tool["api_id"], tool["name"]) for tool in catalog["tools"]
            } == AUDITED_READ_ONLY_TOOLS
            assert len(json.dumps(catalog, ensure_ascii=False).encode()) <= 16_384
            for api_id, name in sorted(pairs):
                response = await hass.services.async_call(
                    DOMAIN,
                    "describe_tool",
                    {
                        "api_id": api_id,
                        "tool_name": name,
                    },
                    context=admin_context,
                    blocking=True,
                    return_response=True,
                )
                assert response["success"] is True, response
                assert response["tool"]["parameters"]["type"] == "object"
                assert response["truncated"] is False
            check = await hass.services.async_call(
                DOMAIN,
                "check_tools",
                {},
                context=admin_context,
                blocking=True,
                return_response=True,
            )
            assert len(check["tools"]) == 10
            assert sum(row["status"] == "ready" for row in check["tools"]) == 9
            assert (
                next(row for row in check["tools"] if row["tool_name"] == "play_video")[
                    "status"
                ]
                == "side_effects_blocked"
            )
            invoke.assert_not_called()
    finally:
        for stop in unregister:
            stop()


@pytest.mark.upstream
@pytest.mark.parametrize("action", ["describe", "calculator", "media"])
async def test_original_eoaic2_script_with_original_new_tool_apis(
    hass,
    gateway_entry,
    admin_context,
    calculator_api,
    media_api,
    video_entities,
    upstream_script_function,
    action,
):
    hass.config_entries.async_update_entry(
        gateway_entry,
        options={
            "enabled": True,
            "allow_side_effects": action == "media",
            "allowed_tools": "basic_utilities/calculate\nmedia_services/play_video",
        },
    )
    recorded = []

    async def playback(call):
        recorded.append(call)

    hass.services.async_register("media_player", "play_media", playback)
    file = (
        "eoaic2_describe_tool.yaml" if action == "describe" else "eoaic2_call_tool.yaml"
    )
    example = yaml.safe_load((ROOT / "examples" / file).read_text())[0]
    api_id, name = (
        ("basic_utilities", "calculate")
        if action == "calculator"
        else ("media_services", "play_video")
    )
    arguments = {"api_id": api_id, "tool_name": name}
    if action != "describe":
        arguments["tool_args"] = (
            {"operation": "expression", "data": ["12.5*2+3"]}
            if action == "calculator"
            else {
                "video_url": "https://example.invalid/video",
                "entity_id": [video_entities[0][0].entity_id],
            }
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
        upstream_script_function.validate_schema(example["function"]),
        arguments,
        original,
        [],
    )
    assert response["success"] is True, response
    if action == "describe":
        assert response["tool"]["requires_side_effects"] is True
        assert response["tool"]["side_effects_allowed"] is False
        assert recorded == []
    elif action == "calculator":
        assert response["result"] == {"value": "28"}
        assert recorded == []
    else:
        assert response["result"]["success"] is True
        assert len(recorded) == 1
