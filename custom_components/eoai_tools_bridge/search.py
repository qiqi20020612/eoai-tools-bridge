"""Validate searches, call a fixed LLM tool, and bound untrusted results."""

import asyncio
import json
import logging
from itertools import islice
from typing import Any
from urllib.parse import urlsplit

import probatio as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import llm

from .const import (
    API_ID,
    DOMAIN,
    ERROR_MESSAGES,
    MAX_CONTENT_LENGTH,
    MAX_QUERY_LENGTH,
    MAX_RESPONSE_BYTES,
    MAX_RESULTS,
    MAX_TITLE_LENGTH,
    MAX_URL_LENGTH,
    SEARCH_TIMEOUT_SECONDS,
    TOOL_NAME,
)

_LOGGER = logging.getLogger(__name__)


def validate_query(value: Any) -> str:
    """Reject coercion, empty values, and oversized input before tool execution."""
    if not isinstance(value, str):
        raise vol.Invalid("query must be a string")
    query = value.strip()
    if not query:
        raise vol.Invalid("query must not be empty")
    if len(query) > MAX_QUERY_LENGTH:
        raise vol.Invalid(f"query must be at most {MAX_QUERY_LENGTH} characters")
    try:
        query.encode("utf-8")
    except UnicodeEncodeError:
        raise vol.Invalid("query must contain valid Unicode text") from None
    return query


SEARCH_SCHEMA = vol.Schema(
    {vol.Required("query"): validate_query}, extra=vol.PREVENT_EXTRA
)


def failure_response(query: str, code: str) -> dict[str, Any]:
    """Return only fixed messages, never raw exceptions or provider errors."""
    return {
        "success": False,
        "query": query,
        "results": [],
        "error": ERROR_MESSAGES[code],
        "error_code": code,
        "truncated": False,
    }


def _bounded_text(value: str, limit: int) -> tuple[str, bool]:
    """Keep an exact prefix and mark visibly when text was cut."""
    value = value.strip()
    truncated = len(value) > limit
    value = value[: limit - 1] + "…" if truncated else value
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Unsupported search text") from None
    return value, truncated


def _content_text(value: Any) -> tuple[str, bool]:
    """Handle text, Brave snippets, and Brave LLM Context's JSON snippets."""
    if isinstance(value, str):
        return _bounded_text(value, MAX_CONTENT_LENGTH)
    snippets = value if isinstance(value, list) else [value]
    parts: list[str] = []
    size = 0
    truncated = False
    for index, snippet in enumerate(snippets):
        if isinstance(snippet, str):
            text = snippet
        elif isinstance(snippet, dict):
            # Some Brave LLM Context snippets are parsed JSON by the upstream.
            # Serialize as data; never execute it or promote it to instructions.
            try:
                text = json.dumps(snippet, ensure_ascii=False, allow_nan=False)
            except TypeError, ValueError, RecursionError:
                raise ValueError("Unsupported search content") from None
        else:
            raise ValueError("Unsupported search content")
        remaining = MAX_CONTENT_LENGTH - size - (1 if parts else 0)
        if remaining <= 1:
            truncated = True
            break
        text, cut = _bounded_text(text, remaining)
        if text:
            size += len(text) + (1 if parts else 0)
            parts.append(text)
        if cut:
            truncated = True
            break
        if index == MAX_CONTENT_LENGTH:
            # Bound work even for a very large list of empty snippets.
            truncated = True
            break
    return "\n".join(parts), truncated


def _source_url(value: Any) -> str | None:
    """Preserve usable upstream links verbatim, without guessing or shortening."""
    if not isinstance(value, str) or not value or len(value) > MAX_URL_LENGTH:
        return None
    if any(ord(char) < 33 or ord(char) == 127 for char in value):
        return None
    try:
        value.encode("utf-8")
        parsed = urlsplit(value)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return None
        # Reject malformed ports and IPv6 addresses without opening the URL.
        _ = parsed.port
    except ValueError, UnicodeEncodeError:
        return None
    return value


def normalize_result(query: str, result: llm.ToolResult | dict[str, Any]) -> dict:
    """Produce a small, JSON-safe search response; discard upstream instructions."""
    if isinstance(result, llm.ToolResult):
        if result.error:
            return failure_response(query, "upstream_error")
        data = result.data
    elif isinstance(result, dict):
        # Defensive compatibility; HA 2026.10 normally wraps this itself.
        data = result
    else:
        return failure_response(query, "invalid_response")

    if not isinstance(data, dict):
        return failure_response(query, "invalid_response")
    if data.get("error") or data.get("success") is False:
        return failure_response(query, "upstream_error")
    results = data.get("results")
    if isinstance(results, str) and results.strip().casefold() in {
        "no results found",
        "no results",
    }:
        results = []
    if not isinstance(results, list):
        return failure_response(query, "invalid_response")

    response: dict[str, Any] = {
        "success": True,
        "query": query,
        "results": [],
        "error": None,
        "error_code": None,
        "truncated": len(results) > MAX_RESULTS,
    }
    for item in islice(results, MAX_RESULTS):
        if not isinstance(item, dict):
            return failure_response(query, "invalid_response")
        title = item.get("title")
        if title is not None and not isinstance(title, str):
            return failure_response(query, "invalid_response")
        try:
            title, title_cut = _bounded_text(title or "", MAX_TITLE_LENGTH)
            content, content_cut = _content_text(
                item.get("content", item.get("description", item.get("snippet", "")))
            )
        except ValueError:
            return failure_response(query, "invalid_response")
        url = _source_url(item.get("url", item.get("link")))
        if not title and not content and not url:
            return failure_response(query, "invalid_response")
        normalized = {"title": title, "content": content}
        if url is not None:
            normalized["url"] = url
        response["truncated"] |= title_cut or content_cut
        response["results"].append(normalized)
        if (
            len(json.dumps(response, ensure_ascii=False).encode("utf-8"))
            > MAX_RESPONSE_BYTES
        ):
            response["results"].pop()
            response["truncated"] = True
            break
    return response


async def async_search(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """Resolve the fixed API afresh so backend changes need no bridge reload."""
    query = call.data["query"]
    llm_context = llm.LLMContext(
        platform=DOMAIN,
        context=call.context,
        language=hass.config.language,
        assistant="conversation",
        device_id=None,
    )
    _LOGGER.debug("Starting web search (%s characters)", len(query))
    stage = "api"
    try:
        async with asyncio.timeout(SEARCH_TIMEOUT_SECONDS):
            if not any(api.id == API_ID for api in llm.async_get_apis(hass)):
                response = failure_response(query, "api_unavailable")
            else:
                instance = await llm.async_get_api(hass, API_ID, llm_context)
                if not any(tool.name == TOOL_NAME for tool in instance.tools):
                    response = failure_response(query, "tool_unavailable")
                else:
                    stage = "tool"
                    result = await instance.async_call_tool(
                        llm.ToolInput(tool_name=TOOL_NAME, tool_args={"query": query})
                    )
                    response = normalize_result(query, result)
    except TimeoutError:
        response = failure_response(query, "timeout")
    except Exception as err:
        # No traceback/message: third-party exception text can include API keys,
        # authentication headers, provider URLs, and the private search query.
        _LOGGER.debug("Web search failed during %s (%s)", stage, type(err).__name__)
        response = failure_response(
            query, "api_failed" if stage == "api" else "call_failed"
        )

    if response["success"]:
        _LOGGER.debug(
            "Web search completed (%s results, truncated=%s)",
            len(response["results"]),
            response["truncated"],
        )
    else:
        _LOGGER.warning("Web search unavailable: %s", response["error_code"])
    return response
