# 版本记录

## 0.2.0 — 2026-10-09

- 新增无入参、仅返回响应的 `eoai_tools_bridge.list_tools`，读取当前启用的白名单工具。
- 固定白名单仅含 `llm_intents/search_web`，不会打开其他 API 或执行工具；显式非只读或有破坏性的声明会被排除。
- 通过 HA 的公开 Schema 转换接口输出描述和参数，支持上游的可选 `freshness`，严格处理不支持的 Schema、敏感元数据、大小限制及超时。
- 提供英文和简体中文动作描述、HA 动作示例及可选的 EOAIC2 `list_search_tools` 追加 YAML。
- `search_web` 的入参、响应及既有搜索 YAML 保持兼容。升级后重启 HA，无需重新配置桥接或覆盖设备控制函数。
- v0.1.0 的真实验收由用户报告通过；v0.2.0 的自动化和真实验收状态见 [TESTING.md](TESTING.md)。

## 0.1.0 — 2026-10-09

- 独立 HACS 搜索桥接，固定调用 HA LLM API 的 `llm_intents/search_web`。
- 严格查询校验、搜索结果规范化、固定失败消息及输出预算。
- 提供 EOAIC2 ScriptFunction 追加 YAML，并通过原版脚本契约测试。
- 80 项模拟/契约测试、Ruff、Hassfest 和 HACS 仓库校验通过。
- 用户在当前开发对话中报告“验收通过”，并要求继续下一版本。用户未提供逐项结果或环境版本，未据此补写具体后端、TTS 或 HACS 更新的通过记录。
