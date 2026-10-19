"""Bridge-owned read-only Amap tools, subject to the existing gateway policy."""

import re
from typing import Any

import probatio as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .amap_client import AmapClient, AmapError, validate_location
from .const import DOMAIN, SERVICE_CALL_TOOL
from .policy import async_is_admin, get_policy
from .validation import validate_query

AMAP_API_ID = "eoai_tools_bridge_amap"
CONF_AMAP_KEY = "amap_api_key"
CONF_AMAP_CITY = "amap_city"
CONF_AMAP_LOCATION = "amap_location"
_KEY = re.compile(r"[a-fA-F0-9]{32}\Z")


def validate_place_text(value: Any) -> str:
    """Amap POI keywords are limited to 80 characters."""
    value = validate_query(value)
    if len(value) > 80:
        raise vol.Invalid("Expected at most 80 characters")
    return value


def validate_limit(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 20:
        raise vol.Invalid("Expected an integer from 1 to 20")
    return value


def validate_radius(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 50_000:
        raise vol.Invalid("Expected a radius from 1 to 50000 meters")
    return value


def validate_types(value: Any) -> str:
    """Use published six-digit POI type codes, at most ten per request."""
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{6}(?:\|[0-9]{6}){0,9}", value
    ):
        raise vol.Invalid("Expected 1 to 10 six-digit POI type codes separated by |")
    return value


def normalize_amap_options(options: dict[str, Any]) -> dict[str, str]:
    """Optional provider settings grant no permission and perform no I/O."""
    values = {}
    for field, validator in (
        (CONF_AMAP_KEY, None),
        (CONF_AMAP_CITY, validate_place_text),
        (CONF_AMAP_LOCATION, validate_location),
    ):
        if field not in options:
            continue
        value = options[field]
        if not isinstance(value, str):
            raise vol.Invalid("Expected a text option")
        value = value.strip()
        if value:
            if field == CONF_AMAP_KEY:
                if not _KEY.fullmatch(value):
                    raise vol.Invalid("Expected a Web Service key")
            else:
                value = validator(value)
        values[field] = value
    return values


def amap_serializer(node: Any) -> Any:
    """Describe owned validators without invoking them or their defaults."""
    if node is validate_place_text:
        return {"type": "string", "minLength": 1, "maxLength": 80, "pattern": r"\S"}
    if node is validate_query:
        return {"type": "string", "minLength": 1, "maxLength": 500, "pattern": r"\S"}
    if node is validate_location:
        return {
            "type": "string",
            "description": "GCJ-02 longitude,latitude; 6 decimals max",
        }
    if node is validate_limit:
        return {"type": "integer", "minimum": 1, "maximum": 20}
    if node is validate_radius:
        return {"type": "integer", "minimum": 1, "maximum": 50_000}
    if node is validate_types:
        return {"type": "string", "pattern": r"^[0-9]{6}(?:\|[0-9]{6}){0,9}$"}
    return vol.UNSUPPORTED


class AmapTool(llm.Tool):
    """Recheck native calls too: selecting this API cannot bypass bridge policy."""

    integration = DOMAIN
    annotations = llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True
    )

    def __init__(self, entry: ConfigEntry, name: str) -> None:
        self._entry = entry
        self.name = name
        if name == "find_places":
            self.description = (
                "Search Amap places by keyword or near explicit/configured GCJ-02 "
                "coordinates. City restricts the search. Missing phone/hours/rating "
                "are omitted. Radius/sort require coordinates; default radius 5000m, "
                "sort weight, limit 5 (first page). Distance sorting also requires "
                "types (six-digit Amap POI codes). Never assume the user's location."
            )
            self.parameters = vol.Schema(
                {
                    vol.Required("query"): validate_place_text,
                    vol.Optional("city"): validate_place_text,
                    vol.Optional("location"): validate_location,
                    vol.Optional("radius"): validate_radius,
                    vol.Optional("sort"): vol.In(["weight", "distance"]),
                    vol.Optional("types"): validate_types,
                    vol.Optional("limit", default=5): validate_limit,
                },
                extra=vol.PREVENT_EXTRA,
            )
        else:
            self.description = (
                "Resolve an address to Amap GCJ-02 longitude/latitude candidates. "
                "Use city to disambiguate. Return up to 5 candidates; ask the user "
                "to choose if ambiguous. Does not plan routes or track devices."
            )
            self.parameters = vol.Schema(
                {
                    vol.Required("address"): validate_query,
                    vol.Optional("city"): validate_place_text,
                },
                extra=vol.PREVENT_EXTRA,
            )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        policy = get_policy(hass)
        if (
            policy is None
            or policy.entry_id != self._entry.entry_id
            or not policy.enabled
            or (AMAP_API_ID, self.name) not in policy.allowed_tools
        ):
            return llm.ToolResult(data={"error": "tool_not_allowed"}, error=True)
        original_user_id = llm_context.context.user_id
        call = ServiceCall(DOMAIN, SERVICE_CALL_TOOL, {}, context=llm_context.context)
        if not await async_is_admin(hass, call):
            return llm.ToolResult(data={"error": "permission_denied"}, error=True)
        try:
            args = self.parameters(tool_input.tool_args)
            options = dict(self._entry.options)
            config = normalize_amap_options(options)
            key = config.get(CONF_AMAP_KEY, "")
            if not key:
                raise AmapError("credentials_missing")
            city = args.pop("city", config.get(CONF_AMAP_CITY, ""))
            if self.name == "find_places":
                args["location"] = args.get(
                    "location", config.get(CONF_AMAP_LOCATION, "")
                )
                if not args["location"] and ("radius" in args or "sort" in args):
                    raise vol.Invalid("Radius/sort require coordinates")
                if args.get("sort") == "distance" and not args.get("types"):
                    raise vol.Invalid("Distance sorting requires POI types")
            if (
                not await async_is_admin(hass, call)
                or call.context.user_id != original_user_id
                or get_policy(hass) != policy
                or dict(self._entry.options) != options
            ):
                return llm.ToolResult(data={"error": "permission_denied"}, error=True)
            client = AmapClient(async_get_clientsession(hass), key)
            if self.name == "find_places":
                data = await client.find_places(city=city, **args)
            else:
                data = await client.geocode(city=city, **args)
            return llm.ToolResult(data=data)
        except vol.Invalid:
            return llm.ToolResult(data={"error": "invalid_args"}, error=True)
        except AmapError as err:
            return llm.ToolResult(data={"error": str(err)}, error=True)


class AmapAPI(llm.API):
    """Metadata acquisition does not create HTTP sessions or validate credentials."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass=hass, id=AMAP_API_ID, name="EOAIC2 Tools Bridge: Amap")
        self._tools = [AmapTool(entry, name) for name in ("find_places", "geocode")]

    async def async_get_api_instance(self, context: llm.LLMContext) -> llm.APIInstance:
        return llm.APIInstance(
            api=self,
            api_prompt="Use only explicitly authorized read-only Amap tools.",
            llm_context=context,
            tools=self._tools,
            custom_serializer=amap_serializer,
        )
