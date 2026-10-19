# Repository instructions

- All Git commits must follow Conventional Commits.
- Use Home Assistant Core 2026.10.2 as the source and automated-test baseline. Keep historical release and acceptance records tied to their original versions.
- Keep the v0.1 MVP restricted to `eoai_tools_bridge.search_web`.
- v0.2 adds a read-only `eoai_tools_bridge.list_tools` catalog with an audited allowlist.
- v0.3 adds `eoai_tools_bridge.call_tool` with an explicit configurable allowlist, original administrator context, native parameter validation, and separate opt-in for tools with possible side effects. Preserve search and catalog compatibility.
- v0.4 adds administrator-only readiness checks for explicitly configured tools. Do not execute tools, parameter schemas, default factories, or serialization hooks while checking. Continue incremental 0.x releases; do not jump to v1.0.
- v0.5 extends the audited read-only classification for explicitly configured Tools for Assist query tools and supports catalog metadata for plain Optional defaults without evaluating them. Preserve the legacy catalog allowlist and all existing service contracts.
- v0.6 adds administrator-only metadata for one explicitly allowed tool, bounded numeric calculator arguments before native dispatch, and original calculator/media contracts. Preserve list_tools as a read-only catalog and check_tools as a non-executing type/status check.
- Home Control is out of scope by user decision: EOAIC2 already provides native HA control. Do not implement its dynamic controls/scripts, device context, or timers. Preserve existing manual gateway behavior and the v0.5 history classification only for compatibility; do not include Home Control in new support claims or v1.0 gates.
- Before v1.0, cover Tools for Assist's non-Home-Control tools, including calculator and media playback. Maintain the source inventory and remaining 0.x acceptance gates in docs/TOOLS_COMPATIBILITY.md; do not call simulated coverage live acceptance.
- The pre-v1.0 roadmap also includes bridge-owned Amap-backed counterparts of Tools for Assist's place/location and route tools, including their location resolution. Keep existing upstream Google tool passthrough compatible and use a distinct identity for the new provider. This planning-only request authorizes documentation changes, not implementation.
- Do not modify EOAIC2, Tools for Assist, Home Assistant Core, or their installed files.
- Report simulated tests and live integration acceptance separately.
