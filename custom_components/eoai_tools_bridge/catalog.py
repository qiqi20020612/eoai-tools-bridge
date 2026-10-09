"""Read public LLM metadata without executing tools or exposing API prompts."""

import asyncio
import json
import logging
import math
from typing import Any

import probatio as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import llm

from .const import (
    CATALOG_ALLOWLIST,
    CATALOG_ERROR_MESSAGES,
    CATALOG_TIMEOUT_SECONDS,
    DOMAIN,
    MAX_CATALOG_DESCRIPTION_LENGTH,
    MAX_CATALOG_SCHEMA_BYTES,
    MAX_CATALOG_SCHEMA_DEPTH,
    MAX_CATALOG_SCHEMA_NODES,
    MAX_RESPONSE_BYTES,
    MAX_TITLE_LENGTH,
)

_LOGGER = logging.getLogger(__name__)
LIST_TOOLS_SCHEMA = vol.Schema({}, extra=vol.PREVENT_EXTRA)

# Retain constraints, omit defaults/examples and private serializer extensions.
# Mapping keys in `properties` are parameter names, not schema keywords.
_SCHEMA_MAPS = {"properties", "patternProperties", "$defs", "dependentSchemas"}
_SCHEMA_LISTS = {"allOf", "anyOf", "oneOf", "prefixItems"}
_SCHEMA_CHILDREN = {
    "additionalProperties",
    "items",
    "contains",
    "not",
    "propertyNames",
    "if",
    "then",
    "else",
    "unevaluatedProperties",
    "unevaluatedItems",
}
_SCHEMA_VALUES = {
    "type",
    "title",
    "description",
    "format",
    "enum",
    "const",
    "required",
    "minLength",
    "maxLength",
    "pattern",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minContains",
    "maxContains",
    "minProperties",
    "maxProperties",
    "dependentRequired",
}
_OMITTED_ANNOTATIONS = {"default", "example", "examples", "$comment"}


def catalog_response(code: str | None = None) -> dict[str, Any]:
    """Keep success, empty discovery, and failures distinguishable."""
    return {
        "success": code is None,
        "tools": [],
        "error": CATALOG_ERROR_MESSAGES[code] if code else None,
        "error_code": code,
        "truncated": False,
    }


def _read_only_basis(tool: llm.Tool) -> str | None:
    """Allow audited legacy tools; reject explicit unsafe declarations."""
    annotations = tool.annotations
    if annotations is llm.Tool.annotations:
        # Tools for Assist's pinned search tool predates these annotations.
        return "audited_allowlist"
    if (
        isinstance(annotations, llm.ToolAnnotations)
        and annotations.read_only is True
        and annotations.destructive is False
    ):
        return "annotation"
    return None


def _metadata_text(value: Any, limit: int) -> tuple[str | None, bool]:
    """Bound display metadata without coercing arbitrary objects to strings."""
    if value is None:
        return None, False
    if not isinstance(value, str):
        raise ValueError("Unsupported metadata")
    value.encode("utf-8")
    cut = len(value) > limit
    return (value[: limit - 1] + "…" if cut else value), cut


def serialize_parameters(instance: llm.APIInstance, tool: llm.Tool) -> dict:
    """Use HA's public converter and fail closed on unrepresentable schemas."""

    def serialize_node(node: Any) -> Any:
        if isinstance(node, dict):
            for key in node:
                marker = key
                for _ in range(MAX_CATALOG_SCHEMA_DEPTH):
                    if not isinstance(marker, vol.Marker):
                        break
                    # The codec resolves default factories. Discovery must not
                    # invoke them, even when a factory just produces a literal.
                    if not isinstance(
                        getattr(marker, "default", vol.UNDEFINED), vol.Undefined
                    ):
                        raise ValueError("Default factories are not supported")
                    marker = marker.schema
                else:
                    raise ValueError("Unsupported schema marker")
        if instance.custom_serializer is not None:
            return instance.custom_serializer(node)
        return vol.UNSUPPORTED

    schema = vol.to_openapi(
        tool.parameters,
        custom_serializer=serialize_node,
        openapi_version="3.1.0",
        strict=True,
    )
    remaining = MAX_CATALOG_SCHEMA_NODES

    def copy_json(value: Any, depth: int, *, schema_node: bool = False) -> Any:
        nonlocal remaining
        remaining -= 1
        if remaining < 0 or depth > MAX_CATALOG_SCHEMA_DEPTH:
            raise ValueError("Oversized schema")
        if schema_node and not isinstance(value, dict | bool):
            raise ValueError("Unsupported schema node")
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                if not isinstance(key, str):
                    raise ValueError("Unsupported schema key")
                key.encode("utf-8")
                if schema_node:
                    if key in _OMITTED_ANNOTATIONS or key.startswith("x-"):
                        continue
                    if key in _SCHEMA_MAPS:
                        if not isinstance(child, dict):
                            raise ValueError("Unsupported schema mapping")
                        # Preserve parameter names even when named 'default'.
                        result[key] = {
                            name: copy_json(node, depth + 2, schema_node=True)
                            for name, node in child.items()
                            if isinstance(name, str) and name.encode("utf-8")
                        }
                        if len(result[key]) != len(child):
                            raise ValueError("Unsupported parameter name")
                        continue
                    if key in _SCHEMA_LISTS:
                        if not isinstance(child, list):
                            raise ValueError("Unsupported schema alternatives")
                        result[key] = [
                            copy_json(node, depth + 2, schema_node=True)
                            for node in child
                        ]
                        continue
                    if key not in _SCHEMA_CHILDREN | _SCHEMA_VALUES:
                        raise ValueError("Unsupported schema keyword")
                result[key] = copy_json(
                    child,
                    depth + 1,
                    schema_node=schema_node and key in _SCHEMA_CHILDREN,
                )
            return result
        if isinstance(value, list):
            return [copy_json(item, depth + 1) for item in value]
        if isinstance(value, str):
            value.encode("utf-8")
            return value
        if value is None or isinstance(value, bool | int):
            return value
        if isinstance(value, float) and math.isfinite(value):
            return value
        raise ValueError("Unsupported schema value")

    result = copy_json(schema, 0, schema_node=True)
    if not isinstance(result, dict) or result.get("type") != "object":
        raise ValueError("Tool parameters must describe an object")
    if (
        len(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        > MAX_CATALOG_SCHEMA_BYTES
    ):
        raise ValueError("Oversized schema")
    return result


async def async_list_tools(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Discover currently enabled, allowlisted tools for the caller's context."""
    response = catalog_response()
    context = llm.LLMContext(
        platform=DOMAIN,
        context=call.context,
        language=hass.config.language,
        assistant="conversation",
        device_id=None,
    )
    stage = "api_failed"
    try:
        async with asyncio.timeout(CATALOG_TIMEOUT_SECONDS):
            for api in llm.async_get_apis(hass):
                # Never instantiate unapproved APIs, even to inspect annotations.
                if not any(api_id == api.id for api_id, _ in CATALOG_ALLOWLIST):
                    continue
                stage = "api_failed"
                instance = await llm.async_get_api(hass, api.id, context)
                seen_names: set[str] = set()
                for tool in instance.tools:
                    stage = "invalid_metadata"
                    if (api.id, tool.name) not in CATALOG_ALLOWLIST:
                        continue
                    # HA dispatches the first tool with a matching name. A later
                    # duplicate cannot replace that tool's safety declaration.
                    if tool.name in seen_names:
                        continue
                    seen_names.add(tool.name)
                    basis = _read_only_basis(tool)
                    if basis is None:
                        continue
                    api_name, api_cut = _metadata_text(api.name, MAX_TITLE_LENGTH)
                    title, title_cut = _metadata_text(tool.title, MAX_TITLE_LENGTH)
                    description, description_cut = _metadata_text(
                        tool.description, MAX_CATALOG_DESCRIPTION_LENGTH
                    )
                    stage = "invalid_schema"
                    parameters = serialize_parameters(instance, tool)
                    response["tools"].append(
                        {
                            "api_id": api.id,
                            "api_name": api_name,
                            "name": tool.name,
                            "title": title,
                            "description": description,
                            "parameters": parameters,
                            "read_only": True,
                            "read_only_basis": basis,
                        }
                    )
                    response["truncated"] |= api_cut or title_cut or description_cut
                    if (
                        len(json.dumps(response, ensure_ascii=False).encode("utf-8"))
                        > MAX_RESPONSE_BYTES
                    ):
                        response["tools"].pop()
                        response["truncated"] = True
                        return response
    except TimeoutError:
        return catalog_response("timeout")
    except Exception as err:
        # No raw metadata, API prompts, tracebacks, or exception messages in logs.
        _LOGGER.debug("Tool catalog unavailable: %s (%s)", stage, type(err).__name__)
        return catalog_response(stage)
    return response
