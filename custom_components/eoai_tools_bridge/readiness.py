"""Inspect allowed tools without parameter validation or tool calls."""

import asyncio
import json
import logging
from itertools import groupby
from typing import Any

import probatio as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import llm

from .const import (
    CHECK_ERROR_MESSAGES,
    CHECK_TIMEOUT_SECONDS,
    DOMAIN,
    MAX_RESPONSE_BYTES,
)
from .policy import GatewayPolicy, async_is_admin, get_policy, read_only_basis

_LOGGER = logging.getLogger(__name__)
CHECK_TOOLS_SCHEMA = vol.Schema({}, extra=vol.PREVENT_EXTRA)


def check_response(code: str | None = None) -> dict[str, Any]:
    """Keep denied/incomplete checks distinct from individual tool readiness."""
    return {
        "success": code is None,
        "enabled": None,
        "allow_side_effects": None,
        "tools": [],
        "error": CHECK_ERROR_MESSAGES[code] if code else None,
        "error_code": code,
        "truncated": False,
    }


async def _async_access_error(
    hass: HomeAssistant,
    call: ServiceCall,
    policy: GatewayPolicy,
    original_user_id: str | None,
) -> str | None:
    """Do not return a snapshot after identity or permissions were revoked."""
    if call.context.user_id != original_user_id or not await async_is_admin(hass, call):
        return "permission_denied"
    if get_policy(hass) != policy:
        return "policy_changed"
    return None


def _bound_response(response: dict[str, Any]) -> dict[str, Any]:
    """Never truncate identifiers or suggest an omitted tool was checked."""
    while (
        len(json.dumps(response, ensure_ascii=False).encode("utf-8"))
        > MAX_RESPONSE_BYTES
    ):
        response["tools"].pop()
        response["truncated"] = True
    return response


async def async_check_tools(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Read registry and native metadata; never call tools or schema factories."""
    policy = get_policy(hass)
    if policy is None:
        return check_response("bridge_not_loaded")
    original_user_id = call.context.user_id
    stage = "permission_denied"
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS):
            if code := await _async_access_error(hass, call, policy, original_user_id):
                return check_response(code)
            stage = "api_failed"
            registered = {api.id for api in llm.async_get_apis(hass)}
            response = check_response()
            response["enabled"] = policy.enabled
            response["allow_side_effects"] = policy.allow_side_effects
            for api_id, name in sorted(policy.allowed_tools):
                response["tools"].append(
                    {
                        "api_id": api_id,
                        "tool_name": name,
                        "status": "not_checked"
                        if policy.enabled
                        else "gateway_disabled",
                        "api_registered": api_id in registered,
                        "read_only_basis": None,
                        "requires_side_effects": None,
                        "schema_supported": None,
                    }
                )
            if policy.enabled:
                context = llm.LLMContext(
                    platform=DOMAIN,
                    context=call.context,
                    language=hass.config.language,
                    assistant="conversation",
                    device_id=None,
                )
                for api_id, rows in groupby(
                    response["tools"], key=lambda row: row["api_id"]
                ):
                    rows = list(rows)
                    if code := await _async_access_error(
                        hass, call, policy, original_user_id
                    ):
                        return check_response(code)
                    if api_id not in registered:
                        for row in rows:
                            row["status"] = "api_unavailable"
                        continue
                    try:
                        instance = await llm.async_get_api(hass, api_id, context)
                        if code := await _async_access_error(
                            hass, call, policy, original_user_id
                        ):
                            return check_response(code)
                        for row in rows:
                            tool = next(
                                (
                                    tool
                                    for tool in instance.tools
                                    if tool.name == row["tool_name"]
                                ),
                                None,
                            )
                            if tool is None:
                                row["status"] = "tool_unavailable"
                                continue
                            basis = read_only_basis(api_id, tool)
                            row["read_only_basis"] = basis
                            row["requires_side_effects"] = basis is None
                            # Type check only. Conversion and validation can run
                            # default factories or custom code, so avoid both.
                            row["schema_supported"] = isinstance(
                                tool.parameters, vol.Schema
                            )
                            if basis is None and not policy.allow_side_effects:
                                row["status"] = "side_effects_blocked"
                            elif not row["schema_supported"]:
                                row["status"] = "invalid_schema"
                            else:
                                row["status"] = "ready"
                    except Exception as err:
                        _LOGGER.debug(
                            "Tool readiness API unavailable (%s)", type(err).__name__
                        )
                        for row in rows:
                            row.update(
                                status="api_failed",
                                read_only_basis=None,
                                requires_side_effects=None,
                                schema_supported=None,
                            )
            if code := await _async_access_error(hass, call, policy, original_user_id):
                return check_response(code)
            return _bound_response(response)
    except TimeoutError:
        # Drop partial metadata rather than leak a stale permission snapshot.
        return check_response("timeout")
    except Exception as err:
        _LOGGER.debug("Tool readiness check failed: %s (%s)", stage, type(err).__name__)
        return check_response(stage)
