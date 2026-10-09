"""Constants for the search bridge and its read-only catalog."""

DOMAIN = "eoai_tools_bridge"
NAME = "EOAIC2 Tools Bridge"
SERVICE_SEARCH_WEB = "search_web"
SERVICE_LIST_TOOLS = "list_tools"
API_ID = "llm_intents"
TOOL_NAME = "search_web"

# Audited against the pinned Tools for Assist source in docs/UPSTREAM.md.
# An upstream read_only annotation alone never extends this allowlist.
CATALOG_ALLOWLIST = frozenset({(API_ID, TOOL_NAME)})
CATALOG_TIMEOUT_SECONDS = 10
MAX_CATALOG_DESCRIPTION_LENGTH = 2000
MAX_CATALOG_SCHEMA_BYTES = 8192
MAX_CATALOG_SCHEMA_DEPTH = 12
MAX_CATALOG_SCHEMA_NODES = 256

CATALOG_ERROR_MESSAGES = {
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
