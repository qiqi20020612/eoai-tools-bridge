# Repository instructions

- All Git commits must follow Conventional Commits.
- Keep the v0.1 MVP restricted to `eoai_tools_bridge.search_web`.
- v0.2 adds a read-only `eoai_tools_bridge.list_tools` catalog with an audited allowlist.
- v0.3 adds `eoai_tools_bridge.call_tool` with an explicit configurable allowlist, original administrator context, native parameter validation, and separate opt-in for tools with possible side effects. Preserve search and catalog compatibility.
- Do not modify EOAIC2, Tools for Assist, Home Assistant Core, or their installed files.
- Report simulated tests and live integration acceptance separately.
