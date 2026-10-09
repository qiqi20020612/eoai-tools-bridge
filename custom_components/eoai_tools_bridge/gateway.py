"""Execute one explicitly enabled LLM tool with the original admin context."""

import asyncio
import logging
from typing import Any

import probatio as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import llm

from .const import API_ID, DOMAIN, TOOL_NAME, TOOL_TIMEOUT_SECONDS
from .payload import normalize_tool_result, tool_response, validate_tool_args
from .policy import async_is_admin, get_policy, read_only_basis, validate_identifier
from .search import validate_query

_LOGGER = logging.getLogger(__name__)
CALL_TOOL_SCHEMA = vol.Schema(
    {
        vol.Required("api_id"): validate_identifier,
        vol.Required("tool_name"): validate_identifier,
        vol.Optional("tool_args", default=dict): validate_tool_args,
    },
    extra=vol.PREVENT_EXTRA,
)


async def async_call_tool(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Validate and dispatch once; never retry an uncertain side effect."""
    api_id = call.data["api_id"]
    name = call.data["tool_name"]
    original_user_id = call.context.user_id
    policy = get_policy(hass)
    if policy is None:
        return tool_response(api_id, name, "bridge_not_loaded")
    if not policy.enabled:
        return tool_response(api_id, name, "gateway_disabled")
    if (api_id, name) not in policy.allowed_tools:
        return tool_response(api_id, name, "tool_not_allowed")

    stage = "permission_denied"
    dispatched = False
    side_effects = False
    try:
        async with asyncio.timeout(TOOL_TIMEOUT_SECONDS):
            if not await async_is_admin(hass, call):
                return tool_response(api_id, name, "permission_denied")
            stage = "api_failed"
            if not any(api.id == api_id for api in llm.async_get_apis(hass)):
                return tool_response(api_id, name, "api_unavailable")
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
            tool = next((tool for tool in instance.tools if tool.name == name), None)
            if tool is None:
                return tool_response(api_id, name, "tool_unavailable")
            basis = read_only_basis(api_id, tool)
            side_effects = basis is None
            if side_effects and not policy.allow_side_effects:
                return tool_response(api_id, name, "side_effects_blocked")

            # Acquiring the API may await. Check revocation and identity again
            # before any schema validator/default factory or tool code executes.
            stage = "permission_denied"
            if call.context.user_id != original_user_id or not await async_is_admin(
                hass, call
            ):
                return tool_response(api_id, name, "permission_denied")
            if get_policy(hass) != policy:
                return tool_response(api_id, name, "policy_changed")
            stage = "invalid_schema"
            parameters = tool.parameters
            if not isinstance(parameters, vol.Schema):
                return tool_response(api_id, name, "invalid_schema")
            stage = "invalid_args"
            arguments = validate_tool_args(parameters(call.data["tool_args"]))
            if (api_id, name) == (API_ID, TOOL_NAME):
                arguments["query"] = validate_query(arguments["query"])
            stage = "permission_denied"
            if call.context.user_id != original_user_id or not await async_is_admin(
                hass, call
            ):
                return tool_response(api_id, name, "permission_denied")
            if get_policy(hass) != policy:
                return tool_response(api_id, name, "policy_changed")
            stage = "tool_changed"
            if (
                next((item for item in instance.tools if item.name == name), None)
                is not tool
                or tool.parameters is not parameters
                or read_only_basis(api_id, tool) != basis
            ):
                return tool_response(api_id, name, "tool_changed")
            stage = "call_failed"
            dispatched = True
            result = await instance.async_call_tool(
                llm.ToolInput(
                    tool_name=name,
                    tool_args=arguments,
                )
            )
            return normalize_tool_result(
                api_id, name, result, side_effects=side_effects
            )
    except TimeoutError:
        return tool_response(
            api_id, name, "timeout", outcome_unknown=dispatched and side_effects
        )
    except Exception as err:
        # Error text may contain credentials or arguments; log only its category.
        _LOGGER.debug("Controlled tool call failed: %s (%s)", stage, type(err).__name__)
        return tool_response(
            api_id, name, stage, outcome_unknown=dispatched and side_effects
        )
