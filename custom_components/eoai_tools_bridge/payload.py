"""Bound JSON arguments and untrusted generic tool results."""

import json
import math
from itertools import islice
from typing import Any

import probatio as vol
from homeassistant.helpers import llm

from .const import (
    MAX_RESPONSE_BYTES,
    MAX_TOOL_ARGS_BYTES,
    MAX_TOOL_JSON_DEPTH,
    MAX_TOOL_JSON_NODES,
    MAX_TOOL_RESULT_ITEMS,
    MAX_TOOL_RESULT_TEXT,
    TOOL_ERROR_MESSAGES,
)

_PRIVATE_KEYS = {
    "instruction",
    "instructions",
    "api_prompt",
    "headers",
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "password",
}


def validate_tool_args(value: Any) -> dict[str, Any]:
    """Make a bounded copy, without templating, coercing, or changing values."""
    remaining = MAX_TOOL_JSON_NODES

    def copy_json(node: Any, depth: int) -> Any:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > MAX_TOOL_JSON_DEPTH:
            raise ValueError
        if isinstance(node, dict):
            if any(not isinstance(key, str) for key in node):
                raise ValueError
            return {
                copy_json(key, depth + 1): copy_json(item, depth + 1)
                for key, item in node.items()
            }
        if isinstance(node, list):
            return [copy_json(item, depth + 1) for item in node]
        if isinstance(node, str):
            node.encode("utf-8")
            return node
        if node is None or isinstance(node, bool | int):
            return node
        if isinstance(node, float) and math.isfinite(node):
            return node
        raise ValueError

    try:
        if not isinstance(value, dict):
            raise ValueError
        result = copy_json(value, 0)
        if (
            len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8"))
            > MAX_TOOL_ARGS_BYTES
        ):
            raise ValueError
        return result
    except TypeError, ValueError, UnicodeError, RecursionError:
        raise vol.Invalid("tool_args must be a bounded JSON object") from None


def tool_response(
    api_id: str,
    tool_name: str,
    code: str | None = None,
    *,
    outcome_unknown: bool = False,
) -> dict[str, Any]:
    """Use fixed errors; a failed side-effect call does not imply rollback."""
    return {
        "success": code is None,
        "api_id": api_id,
        "tool_name": tool_name,
        "result": None,
        "error": TOOL_ERROR_MESSAGES[code] if code else None,
        "error_code": code,
        "truncated": False,
        "outcome_unknown": outcome_unknown,
    }


def normalize_tool_result(
    api_id: str, tool_name: str, result: Any, *, side_effects: bool
) -> dict[str, Any]:
    """Copy JSON data only; discard known instructions and credential fields."""
    if isinstance(result, llm.ToolResult):
        if result.error:
            return tool_response(
                api_id, tool_name, "upstream_error", outcome_unknown=side_effects
            )
        data = result.data
    elif isinstance(result, dict):
        data = result
    else:
        return tool_response(
            api_id, tool_name, "invalid_response", outcome_unknown=side_effects
        )
    if isinstance(data, dict) and (data.get("error") or data.get("success") is False):
        return tool_response(
            api_id, tool_name, "upstream_error", outcome_unknown=side_effects
        )

    response = tool_response(api_id, tool_name)
    remaining = MAX_TOOL_JSON_NODES

    def copy_json(node: Any, depth: int) -> Any:
        nonlocal remaining
        remaining -= 1
        if depth > MAX_TOOL_JSON_DEPTH:
            response["truncated"] = True
            return None
        if isinstance(node, dict):
            if len(node) > MAX_TOOL_RESULT_ITEMS:
                response["truncated"] = True
            copied = {}
            for key, item in islice(node.items(), MAX_TOOL_RESULT_ITEMS):
                if remaining <= 0:
                    response["truncated"] = True
                    break
                if not isinstance(key, str):
                    raise ValueError
                key.encode("utf-8")
                if key.casefold().replace("-", "_") in _PRIVATE_KEYS:
                    continue
                if len(key) > MAX_TOOL_RESULT_TEXT:
                    response["truncated"] = True
                    continue
                copied[key] = copy_json(item, depth + 1)
            return copied
        if isinstance(node, list):
            if len(node) > MAX_TOOL_RESULT_ITEMS:
                response["truncated"] = True
            copied = []
            for item in islice(node, MAX_TOOL_RESULT_ITEMS):
                if remaining <= 0:
                    response["truncated"] = True
                    break
                copied.append(copy_json(item, depth + 1))
            return copied
        if isinstance(node, str):
            node.encode("utf-8")
            if len(node) > MAX_TOOL_RESULT_TEXT:
                response["truncated"] = True
                return node[: MAX_TOOL_RESULT_TEXT - 1] + "…"
            return node
        if node is None or isinstance(node, bool | int):
            return node
        if isinstance(node, float) and math.isfinite(node):
            return node
        raise ValueError

    try:
        response["result"] = copy_json(data, 0)
        while (
            len(
                json.dumps(response, ensure_ascii=False, allow_nan=False).encode(
                    "utf-8"
                )
            )
            > MAX_RESPONSE_BYTES
        ):
            response["truncated"] = True
            body = response["result"]
            if isinstance(body, dict) and body:
                body.popitem()
            elif isinstance(body, list) and body:
                body.pop()
            elif isinstance(body, str) and len(body) > 1:
                response["result"] = body[: len(body) // 2] + "…"
            else:
                response["result"] = None
                break
    except TypeError, ValueError, UnicodeError, RecursionError:
        return tool_response(
            api_id, tool_name, "invalid_response", outcome_unknown=side_effects
        )
    return response
