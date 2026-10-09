"""Read explicit options and caller identity without granting new permissions."""

import re
from dataclasses import dataclass
from typing import Any

import probatio as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import llm

from .const import (
    CATALOG_ALLOWLIST,
    CONF_ALLOW_SIDE_EFFECTS,
    CONF_ALLOWED_TOOLS,
    CONF_ENABLED,
    DOMAIN,
    MAX_ALLOWED_TOOLS,
    MAX_IDENTIFIER_LENGTH,
)

_IDENTIFIER = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]*\Z")


def validate_identifier(value: Any) -> str:
    """Accept identifiers, not templates, wildcards, URLs, or merged API lists."""
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= MAX_IDENTIFIER_LENGTH
        or not _IDENTIFIER.fullmatch(value)
    ):
        raise vol.Invalid("Expected a supported API or tool identifier")
    return value


def parse_allowed_tools(value: Any) -> frozenset[tuple[str, str]]:
    """Use exact API/tool pairs; empty lists grant nothing."""
    if not isinstance(value, str) or len(value) > 10_000:
        raise vol.Invalid("Expected one API/tool pair per line")
    pairs: set[tuple[str, str]] = set()
    for line in value.splitlines():
        if not (line := line.strip()):
            continue
        parts = line.split("/")
        if len(parts) != 2:
            raise vol.Invalid("Expected one API/tool pair per line")
        pairs.add((validate_identifier(parts[0]), validate_identifier(parts[1])))
        if len(pairs) > MAX_ALLOWED_TOOLS:
            raise vol.Invalid("Too many allowed tools")
    return frozenset(pairs)


def normalize_options(options: dict[str, Any]) -> dict[str, Any]:
    """Validate settings and keep a stable, readable representation in storage."""
    enabled = options.get(CONF_ENABLED, False)
    effects = options.get(CONF_ALLOW_SIDE_EFFECTS, False)
    if type(enabled) is not bool or type(effects) is not bool:
        raise vol.Invalid("Expected boolean options")
    pairs = parse_allowed_tools(options.get(CONF_ALLOWED_TOOLS, ""))
    if enabled and not pairs:
        raise vol.Invalid("An enabled gateway needs an explicit allowlist")
    return {
        CONF_ENABLED: enabled,
        CONF_ALLOWED_TOOLS: "\n".join(f"{api}/{tool}" for api, tool in sorted(pairs)),
        CONF_ALLOW_SIDE_EFFECTS: effects,
    }


@dataclass(frozen=True)
class GatewayPolicy:
    """Snapshot compared again just before a tool is dispatched."""

    entry_id: str
    enabled: bool = False
    allowed_tools: frozenset[tuple[str, str]] = frozenset()
    allow_side_effects: bool = False


def get_policy(hass: HomeAssistant) -> GatewayPolicy | None:
    """Read options on every request; invalid stored options fail closed."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        try:
            options = normalize_options(dict(entry.options))
        except vol.Invalid:
            return GatewayPolicy(entry_id=entry.entry_id)
        return GatewayPolicy(
            entry_id=entry.entry_id,
            enabled=options[CONF_ENABLED],
            allowed_tools=parse_allowed_tools(options[CONF_ALLOWED_TOOLS]),
            allow_side_effects=options[CONF_ALLOW_SIDE_EFFECTS],
        )
    return None


async def async_is_admin(hass: HomeAssistant, call: ServiceCall) -> bool:
    """Require the original caller; never replace a missing user or elevate it."""
    if call.context.user_id is None:
        return False
    user = await hass.auth.async_get_user(call.context.user_id)
    return bool(user and user.is_active and user.is_admin)


def read_only_basis(api_id: str, tool: llm.Tool) -> str | None:
    """Default annotations are unknown except for the audited legacy search."""
    annotations = tool.annotations
    if annotations is llm.Tool.annotations:
        return "audited_allowlist" if (api_id, tool.name) in CATALOG_ALLOWLIST else None
    if (
        isinstance(annotations, llm.ToolAnnotations)
        and annotations.read_only is True
        and annotations.destructive is False
    ):
        return "annotation"
    return None


async def async_catalog_allowlist(
    hass: HomeAssistant, call: ServiceCall
) -> frozenset[tuple[str, str]]:
    """Keep the legacy catalog; expose configured additions only to admins."""
    policy = get_policy(hass)
    if policy and policy.enabled and await async_is_admin(hass, call):
        return CATALOG_ALLOWLIST | policy.allowed_tools
    return CATALOG_ALLOWLIST
