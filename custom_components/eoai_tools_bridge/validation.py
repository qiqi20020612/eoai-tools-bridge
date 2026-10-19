"""Shared validation for controlled tool calls."""

from typing import Any

import probatio as vol

from .const import MAX_QUERY_LENGTH


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
