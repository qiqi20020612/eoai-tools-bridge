"""Original media API/selector/dispatch with real HA registries, simulated service."""

import asyncio
import json
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.eoai_tools_bridge.const import DOMAIN

pytestmark = pytest.mark.tools_upstream


@pytest.fixture
def media_entry(hass, gateway_entry):
    hass.config_entries.async_update_entry(
        gateway_entry,
        options={
            "enabled": True,
            "allowed_tools": "media_services/play_video",
            "allow_side_effects": False,
        },
    )
    return gateway_entry


@pytest.fixture
def playback(hass):
    calls = []

    async def handle(call):
        calls.append(call)

    hass.services.async_register("media_player", "play_media", handle)
    return calls


def allow_playback(hass, entry):
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "allow_side_effects": True,
        },
    )


async def call(hass, action, context, args=None):
    data = {"api_id": "media_services", "tool_name": "play_video"}
    if action == "call_tool":
        data["tool_args"] = {
            "video_url": "https://example.invalid/video",
            **(args or {}),
        }
    return await hass.services.async_call(
        DOMAIN, action, data, context=context, blocking=True, return_response=True
    )


async def test_describe_native_dynamic_selector_without_playback_permission(
    hass, media_entry, media_api, admin_context, video_entities, playback
):
    response = await call(hass, "describe_tool", admin_context)
    assert response["success"] is True
    tool = response["tool"]
    assert tool["requires_side_effects"] is True
    assert tool["side_effects_allowed"] is False
    schema = tool["parameters"]
    assert schema["required"] == ["video_url"]
    selector = schema["properties"]["entity_id"]
    assert selector["type"] == "array"
    assert selector["items"]["enum"] == [item[0].entity_id for item in video_entities]
    assert playback == []
    denied = await call(
        hass,
        "call_tool",
        admin_context,
        {"entity_id": [video_entities[0][0].entity_id]},
    )
    assert denied["error_code"] == "side_effects_blocked"
    assert playback == []
    catalog = await hass.services.async_call(
        DOMAIN,
        "list_tools",
        {},
        context=admin_context,
        blocking=True,
        return_response=True,
    )
    assert catalog["tools"] == []


@pytest.mark.parametrize("target", ["entity", "area", "device"])
async def test_native_playback_targets_and_success_result(
    hass, media_entry, media_api, admin_context, video_entities, playback, target
):
    allow_playback(hass, media_entry)
    entity, device, area = video_entities[0]
    args = (
        {"entity_id": [entity.entity_id]}
        if target == "entity"
        else ({"area": area.name} if target == "area" else {"device_id": device.id})
    )
    response = await call(hass, "call_tool", admin_context, args)
    assert response["success"] is True, response
    assert response["result"]["success"] is True
    assert response["outcome_unknown"] is False
    assert len(playback) == 1
    assert playback[0].data["media_content_id"] == "https://example.invalid/video"
    assert playback[0].data["media_content_type"] == "url"
    if target in {"entity", "area"}:
        assert playback[0].data["entity_id"] == [entity.entity_id]
    else:
        assert playback[0].data["device_id"] == device.id
    # The upstream tool does not forward llm_context.context into its own HA
    # service call. Record that limitation rather than inventing an identity.
    assert playback[0].context.user_id is None


async def test_native_selector_rejects_unknown_entity_before_dispatch(
    hass, media_entry, media_api, admin_context, playback
):
    allow_playback(hass, media_entry)
    response = await call(
        hass, "call_tool", admin_context, {"entity_id": ["media_player.absent"]}
    )
    assert response["error_code"] == "invalid_args"
    assert response["outcome_unknown"] is False
    assert playback == []


async def test_media_metadata_refreshes_after_entity_changes(
    hass, media_entry, media_api, admin_context, video_entities, playback
):
    first = await call(hass, "describe_tool", admin_context)
    entity = video_entities[1][0]
    er.async_get(hass).async_remove(entity.entity_id)
    hass.states.async_remove(entity.entity_id)
    second = await call(hass, "describe_tool", admin_context)

    def values(response):
        return response["tool"]["parameters"]["properties"]["entity_id"]["items"][
            "enum"
        ]

    assert entity.entity_id in values(first)
    assert entity.entity_id not in values(second)
    assert playback == []


async def test_native_single_player_default(
    hass, media_entry, media_api, admin_context, video_entities, playback
):
    allow_playback(hass, media_entry)
    second = video_entities[1][0]
    er.async_get(hass).async_remove(second.entity_id)
    hass.states.async_remove(second.entity_id)
    response = await call(hass, "call_tool", admin_context)
    assert response["success"] is True
    assert len(playback) == 1
    assert playback[0].data["entity_id"] == [video_entities[0][0].entity_id]


async def test_ambiguous_target_reports_uncertain_outcome_without_retry(
    hass, media_entry, media_api, admin_context, playback
):
    allow_playback(hass, media_entry)
    response = await call(hass, "call_tool", admin_context)
    assert response["error_code"] == "upstream_error"
    assert response["outcome_unknown"] is True
    assert playback == []


async def test_timeout_after_native_service_dispatch_is_uncertain(
    hass, media_entry, media_api, admin_context, video_entities, playback
):
    allow_playback(hass, media_entry)
    count = 0

    async def hang(call):
        nonlocal count
        count += 1
        await asyncio.Event().wait()

    hass.services.async_register("media_player", "play_media", hang)
    with patch(
        "custom_components.eoai_tools_bridge.gateway.TOOL_TIMEOUT_SECONDS", 0.02
    ):
        response = await call(
            hass,
            "call_tool",
            admin_context,
            {"entity_id": [video_entities[0][0].entity_id]},
        )
    assert response["error_code"] == "timeout"
    assert response["outcome_unknown"] is True
    assert count == 1


async def test_native_playback_receives_original_admin_llm_context(
    hass,
    media_entry,
    media_api,
    admin_context,
    release_source,
    video_entities,
    playback,
):
    allow_playback(hass, media_entry)
    cls = release_source("play_media").PlayVideoTool
    original = cls.async_call
    contexts = []

    async def record(tool, hass, tool_input, llm_context):
        contexts.append(llm_context)
        return await original(tool, hass, tool_input, llm_context)

    with patch.object(cls, "async_call", record):
        assert (
            await call(
                hass,
                "call_tool",
                admin_context,
                {"entity_id": [video_entities[0][0].entity_id]},
            )
        )["success"] is True
    assert contexts[0].context is admin_context
    assert len(playback) == 1


async def test_native_service_error_is_fixed_and_not_retried(
    hass, media_entry, media_api, admin_context, video_entities, playback
):
    from homeassistant.exceptions import HomeAssistantError

    allow_playback(hass, media_entry)
    count = 0

    async def fail(call):
        nonlocal count
        count += 1
        raise HomeAssistantError("private-media-error")

    hass.services.async_register("media_player", "play_media", fail)
    response = await call(
        hass,
        "call_tool",
        admin_context,
        {"entity_id": [video_entities[0][0].entity_id]},
    )
    assert response["error_code"] == "upstream_error"
    assert response["outcome_unknown"] is True
    assert "private-media-error" not in json.dumps(response)
    assert count == 1
