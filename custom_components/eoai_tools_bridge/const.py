"""Constants for the search bridge and its read-only catalog."""

DOMAIN = "eoai_tools_bridge"
NAME = "EOAIC2 Tools Bridge"
SERVICE_SEARCH_WEB = "search_web"
SERVICE_LIST_TOOLS = "list_tools"
SERVICE_CALL_TOOL = "call_tool"
SERVICE_CHECK_TOOLS = "check_tools"
API_ID = "llm_intents"
TOOL_NAME = "search_web"

CONF_ENABLED = "enabled"
CONF_ALLOWED_TOOLS = "allowed_tools"
CONF_ALLOW_SIDE_EFFECTS = "allow_side_effects"
MAX_ALLOWED_TOOLS = 32
MAX_IDENTIFIER_LENGTH = 128
MAX_TOOL_ARGS_BYTES = 8192
MAX_TOOL_JSON_DEPTH = 12
MAX_TOOL_JSON_NODES = 256
MAX_TOOL_RESULT_ITEMS = 32
MAX_TOOL_RESULT_TEXT = 2048
TOOL_TIMEOUT_SECONDS = 20
CHECK_TIMEOUT_SECONDS = 10

CHECK_ERROR_MESSAGES = {
    "bridge_not_loaded": "Add or enable the EOAIC2 Tools Bridge integration first.",
    "permission_denied": (
        "Checking tool readiness requires the original active administrator."
    ),
    "policy_changed": "Bridge permissions changed during the check. Check again.",
    "api_failed": "Could not read the LLM API registry. Check its integrations.",
    "timeout": "Checking tool readiness timed out. No tool was called.",
}

TOOL_ERROR_MESSAGES = {
    "bridge_not_loaded": "Add or enable the EOAIC2 Tools Bridge integration first.",
    "gateway_disabled": "Enable controlled tool calls in the bridge options first.",
    "tool_not_allowed": "This API/tool pair is not enabled in the bridge allowlist.",
    "permission_denied": (
        "Controlled tool calls require an active administrator context."
    ),
    "side_effects_blocked": (
        "This tool may change state or has not declared read-only behavior. "
        "Enable side effects in the bridge options to allow it."
    ),
    "api_unavailable": "The allowed LLM API is not currently registered.",
    "tool_unavailable": "The allowed tool is not currently available in its LLM API.",
    "tool_changed": "The tool definition changed before execution. It was not called.",
    "api_failed": "Could not open the allowed LLM API. Check its integration.",
    "invalid_schema": "The tool does not provide a supported native parameter schema.",
    "invalid_args": (
        "Tool arguments do not satisfy the tool's parameter schema or limits."
    ),
    "policy_changed": (
        "Bridge permissions changed before execution. The tool was not called."
    ),
    "timeout": "The tool request timed out. Check its integration before retrying.",
    "upstream_error": "The tool reported an error. Check its integration.",
    "call_failed": "The tool call failed. Check its integration.",
    "invalid_response": "The tool returned an unsupported result format.",
}

# The unauthenticated legacy catalog stays limited to web search.
CATALOG_ALLOWLIST = frozenset({(API_ID, TOOL_NAME)})
# Audited against the immutable source in docs/TOOLS_COMPATIBILITY.md. These
# classifications grant no access: additional tools still need exact opt-in and
# the original active administrator. Calculator and control tools stay unknown.
AUDITED_READ_ONLY_TOOLS = CATALOG_ALLOWLIST | frozenset(
    {
        (API_ID, "find_places"),
        (API_ID, "get_route"),
        (API_ID, "search_wikipedia"),
        (API_ID, "search_youtube"),
        ("weather_forecast", "get_weather_forecast"),
        ("basic_utilities", "unit_convert"),
        ("basic_utilities", "calendar_day_info"),
        ("HomeControl", "get_device_history_context"),
    }
)
CATALOG_TIMEOUT_SECONDS = 10
MAX_CATALOG_DESCRIPTION_LENGTH = 2000
MAX_CATALOG_SCHEMA_BYTES = 8192
MAX_CATALOG_SCHEMA_DEPTH = 12
MAX_CATALOG_SCHEMA_NODES = 256

CATALOG_ERROR_MESSAGES = {
    "permission_denied": (
        "Catalog permissions changed before metadata could be returned."
    ),
    "bridge_not_loaded": "Add or enable the EOAIC2 Tools Bridge integration first.",
    "api_failed": "Could not read the allowed LLM API. Check Tools for Assist.",
    "timeout": "Reading the tool catalog timed out. Try again later.",
    "invalid_schema": (
        "An allowed tool has an unsupported or oversized parameter schema."
    ),
    "invalid_metadata": "An allowed tool has unsupported catalog metadata.",
}

MAX_QUERY_LENGTH = 500
SEARCH_TIMEOUT_SECONDS = 20
MAX_RESULTS = 5
MAX_TITLE_LENGTH = 200
MAX_CONTENT_LENGTH = 1600
MAX_URL_LENGTH = 1024
MAX_RESPONSE_BYTES = 16_384

ERROR_MESSAGES = {
    "bridge_not_loaded": "Add or enable the EOAIC2 Tools Bridge integration first.",
    "api_unavailable": (
        "Tools for Assist search API is unavailable. Install and configure "
        "Tools for Assist, enable Brave or SearXNG web search, and try again."
    ),
    "tool_unavailable": (
        "Tools for Assist search_web is not enabled. Enable Brave or SearXNG "
        "web search in Tools for Assist and try again."
    ),
    "api_failed": "Could not open the Tools for Assist search API. Check its setup.",
    "timeout": "Web search timed out. Try again later.",
    "upstream_error": "The search provider reported an error. Check Tools for Assist.",
    "invalid_response": "The search provider returned an unsupported response format.",
    "call_failed": "Web search could not be completed. Check Tools for Assist.",
}
