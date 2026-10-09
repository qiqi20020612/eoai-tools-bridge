# Repository instructions

- All Git commits must follow Conventional Commits.
- Keep the v0.1 MVP restricted to `eoai_tools_bridge.search_web`.
- v0.2 adds a read-only `eoai_tools_bridge.list_tools` catalog with an audited allowlist.
- v0.3 adds `eoai_tools_bridge.call_tool` with an explicit configurable allowlist, original administrator context, native parameter validation, and separate opt-in for tools with possible side effects. Preserve search and catalog compatibility.
- v0.4 adds administrator-only readiness checks for explicitly configured tools. Do not execute tools, parameter schemas, default factories, or serialization hooks while checking. Continue incremental 0.x releases; do not jump to v1.0.
- v0.5 extends the audited read-only classification for explicitly configured Tools for Assist query tools and supports catalog metadata for plain Optional defaults without evaluating them. Preserve the legacy catalog allowlist and all existing service contracts.
- Before v1.0, cover all Tools for Assist tool families, including calculator, media playback, Home Control's dynamic tools/scripts, and device-dependent tools. Maintain the source inventory and remaining 0.x acceptance gates in docs/TOOLS_COMPATIBILITY.md; do not call simulated coverage live acceptance.
- Do not modify EOAIC2, Tools for Assist, Home Assistant Core, or their installed files.
- Report simulated tests and live integration acceptance separately.
