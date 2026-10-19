"""Read one allowed tool's public metadata without dispatching it."""

import asyncio
import json
import logging
from typing import Any

import probatio as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import llm

from .calculator import calculator_constraints, is_calculator
from .catalog import metadata_text, serialize_parameters
from .const import (
    CATALOG_TIMEOUT_SECONDS,
    DESCRIBE_ERROR_MESSAGES,
    DOMAIN,
    MAX_CATALOG_DESCRIPTION_LENGTH,
    MAX_RESPONSE_BYTES,
    MAX_TITLE_LENGTH,
)
from .policy import async_is_admin, get_policy, read_only_basis, validate_identifier

_LOGGER = logging.getLogger(__name__)
DESCRIBE_TOOL_SCHEMA = vol.Schema(
    {
        vol.Required("api_id"): validate_identifier,
        vol.Required("tool_name"): validate_identifier,
    },
    extra=vol.PREVENT_EXTRA,
)


def describe_response(
    api_id: str, name: str, code: str | None = None
) -> dict[str, Any]:
    """Never return partial metadata on failure or permission revocation."""
    return {
        "success": code is None,
        "api_id": api_id,
        "tool_name": name,
        "tool": None,
        "error": DESCRIBE_ERROR_MESSAGES[code] if code else None,
        "error_code": code,
        "truncated": False,
    }


async def async_describe_tool(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Allow deliberate inspection before granting side-effect execution."""
    api_id, name = call.data["api_id"], call.data["tool_name"]
    policy = get_policy(hass)
    if policy is None:
        return describe_response(api_id, name, "bridge_not_loaded")
    if not policy.enabled:
        return describe_response(api_id, name, "gateway_disabled")
    if (api_id, name) not in policy.allowed_tools:
        return describe_response(api_id, name, "tool_not_allowed")
    original_user_id = call.context.user_id
    stage = "permission_denied"

    async def access_error() -> str | None:
        if call.context.user_id != original_user_id or not await async_is_admin(
            hass, call
        ):
            return "permission_denied"
        if get_policy(hass) != policy:
            return "policy_changed"
        return None

    try:
        async with asyncio.timeout(CATALOG_TIMEOUT_SECONDS):
            if code := await access_error():
                return describe_response(api_id, name, code)
            stage = "api_failed"
            if not any(api.id == api_id for api in llm.async_get_apis(hass)):
                return describe_response(api_id, name, "api_unavailable")
            instance = await llm.async_get_api(
                hass,
                api_id,
                llm.LLMContext(
                    platform=DOMAIN,
                    context=call.context,
                    language=hass.config.language,
                    assistant="conversation",
                    device_id=None,
                ),
            )
            if code := await access_error():
                return describe_response(api_id, name, code)
            tool = next((tool for tool in instance.tools if tool.name == name), None)
            if tool is None:
                return describe_response(api_id, name, "tool_unavailable")
            parameters, serializer = tool.parameters, instance.custom_serializer
            basis = read_only_basis(api_id, tool)
            stage = "invalid_metadata"
            api_name, api_cut = metadata_text(instance.api.name, MAX_TITLE_LENGTH)
            title, title_cut = metadata_text(tool.title, MAX_TITLE_LENGTH)
            description, description_cut = metadata_text(
                tool.description, MAX_CATALOG_DESCRIPTION_LENGTH
            )
            stage = "invalid_schema"
            if not isinstance(parameters, vol.Schema):
                return describe_response(api_id, name, "invalid_schema")
            schema = serialize_parameters(instance, tool)
            response = describe_response(api_id, name)
            response["tool"] = {
                "api_name": api_name,
                "name": name,
                "title": title,
                "description": description,
                "parameters": schema,
                "read_only": basis is not None,
                "read_only_basis": basis,
                "requires_side_effects": basis is None,
                "side_effects_allowed": policy.allow_side_effects,
            }
            if is_calculator(api_id, tool):
                response["tool"]["bridge_constraints"] = calculator_constraints()
            response["truncated"] = api_cut or title_cut or description_cut
            if code := await access_error():
                return describe_response(api_id, name, code)
            if (
                next((item for item in instance.tools if item.name == name), None)
                is not tool
                or tool.parameters is not parameters
                or instance.custom_serializer is not serializer
                or read_only_basis(api_id, tool) != basis
            ):
                return describe_response(api_id, name, "tool_changed")
            if (
                len(json.dumps(response, ensure_ascii=False).encode())
                > MAX_RESPONSE_BYTES
            ):
                return describe_response(api_id, name, "invalid_metadata")
            return response
    except TimeoutError:
        return describe_response(api_id, name, "timeout")
    except Exception as err:
        _LOGGER.debug("Tool metadata unavailable: %s (%s)", stage, type(err).__name__)
        return describe_response(api_id, name, stage)
