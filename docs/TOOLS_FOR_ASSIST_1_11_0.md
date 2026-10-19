# Tools for Assist 1.11.0 兼容核对

> 历史记录：下文固定搜索服务的说明属于 v0.5 核对时行为。v0.7 已移除独立 `eoai_tools_bridge.search_web`，当前所有搜索均通过 `call_tool`；请按 [迁移说明](MIGRATION_0_7.md) 更新 Functions 和授权。上游工具身份及 Tavily 原生参数继续保留。

核对日期：**2026-10-19（Asia/Shanghai）**。本记录保留 v0.5.0 的独立上游核对结论；后续 v0.6.0 的开发、发布和当前范围见 [兼容清单](TOOLS_COMPATIBILITY.md) 与 [测试记录](TESTING.md)。核对对象：桥接 **v0.5.0**、HA Core **2026.10.0**、Tools for Assist **1.11.0**。

**该阶段结论：v0.5.0 运行代码无需兼容修复，可继续配合 Tools for Assist 1.11.0 使用已支持的工具。** Tavily 复用既有搜索入口；新增的两个可选筛选参数可由现有 `call_tool` 原样传入。该阶段仅补充测试、固定源码快照和文档，未改变桥接运行代码或发布版本。随后用户明确取消 Home Control API；v0.6.0 推进计算器和媒体播放，Home Control 不再属于后续开发或 1.0 验收范围。

## 核对依据

- [1.11.0 Release](https://github.com/skye-harris/llm_intents/releases/tag/1.11.0)，固定提交 `198e37885fe06e6452d2d6e26bc5e532b1686acc`。
- [与原核对基线的完整差异](https://github.com/skye-harris/llm_intents/compare/100e740b93a2a1a6d304329883937193a4571ac0...198e37885fe06e6452d2d6e26bc5e532b1686acc)：新增 Tavily 提供商、配置/翻译/测试，及上游配置表单修复。
- 原快照已包含发布说明所述的 HA 弃用修复（`BaseTool.integration`），不是本次桥接新增的缺口。旧的 18 个工具实现/公共依赖文件与 1.11.0 逐字节相同；`const.py`、`llm_functions.py` 增加 Tavily，Manifest 只改版本，不新增依赖。
- 新快照在独立的 `.cache/upstream/llm_intents-1.11.0/` 中保存 22 个原版文件。初次核对时验证 Git blob SHA，自动化获取及导入时验证固定 SHA-256；原有 20 文件快照保留。

## 对桥接的影响

| 范围 | 1.11.0 行为 | 桥接结论 |
| --- | --- | --- |
| API / 工具标识 | Tavily 仍为 `llm_intents/search_web` | 不增加白名单组合，已有网页搜索配置继续有效 |
| 固定 `search_web` 动作 | 必填 `query` 即可调用 Tavily | 原有 EOAIC2 `web_search` 示例继续使用；固定动作仍只接受 `query` |
| 通用调用参数 | 新增 `topic`：`general/news/finance`，`time_range`：`day/week/month/year`，均可选 | `list_tools` 已能展示原生枚举，`call_tool` 已能校验并透传；需要原始有效管理员及既有授权 |
| 只读判断与检查 | 继承原版 SearchWebTool，公开 integration 与工具名不变 | 已审核搜索依据及 `check_tools` 就绪逻辑继续适用，无需副作用许可 |
| 返回数据 | 仍是 `results` 中的 `title/content`；可将生成答案作为首条结果 | 现有固定搜索和通用结果处理支持；继续丢弃上游指令 |
| 全文选项 | Tavily 可返回较长的页面正文 | 桥接仍执行 1600/2048 字符和 16 KiB 等既有预算，省略时标记 `truncated` |
| 错误与空结果 | HTTP 错误由原版工具包装；无结果使用原有空结果格式 | 桥接继续返回固定错误消息或成功空列表，不暴露错误正文 |
| 其他工具与 Home Control | 实现文件未改变，没有新增固定工具名或设备上下文要求 | 没有新增桥接兼容缺口；原有尚未完成的工具验收范围不因此变为已完成 |

[Tavily 原版实现](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/tavily_search.py) 仍不把 Tavily 原始结果中的 URL 转发到工具结果；桥接不能据此生成真实来源链接。Tavily 的 `topic/time_range` 与 Brave LLM Context 的 `freshness` 是不同的原生参数；更换提供商后应重新读取工具清单。

上游将 Brave Context 的配置字段改为 Required，以及修复搜索提供商/时区清空选项，均发生在 Tools for Assist 的配置流中。这些配置 Schema 不属于工具公开的 `parameters`，不会触发桥接对必填参数默认值的目录限制，也不需要修改桥接选项流。

## 使用方式

继续使用 Brave、Brave LLM Context 或 SearXNG 的用户可保持原有搜索方式。使用 Tavily 时，在 **Tools for Assist 自身配置**中选择 Tavily 并配置密钥；桥接不保存该密钥。

只查询 `query` 时继续使用现有 `search_web` 动作和 EOAIC2 YAML。需要 Tavily 的额外筛选时，管理员通过现有通用调用：

```yaml
action: eoai_tools_bridge.call_tool
data:
  api_id: llm_intents
  tool_name: search_web
  tool_args:
    query: "Home Assistant updates"
    topic: news
    time_range: week
```

仍需在桥接中启用 `call_tool`，并明确允许 `llm_intents/search_web`；仅更新上游不会自动扩大授权。

## 自动化与实际验收

新增 **17 项**原版 Tavily 契约测试，使用真实 HA 服务、LLM 注册表/APIInstance、认证 Context、Schema 和原版 Tavily/SearchWebTool 方法，HTTP 和缓存模拟。覆盖目录枚举、就绪检查、查询字面值、筛选参数透传、非法参数/额外字段拒绝、生成答案、空结果、全文截断、错误正文隔离和管理员限制。

本地完整回归：**362 passed，0 skipped**，包含原有 345 项与新增 17 项用例；Ruff 静态、格式检查及 Git diff 空白检查通过。本次没有发布新版本或重新运行 GitHub CI，不将旧版本 CI 结果冒充此次检查证据。测试使用固定 Python 3.14.6、HA Core 2026.10.0 与原锁定依赖，不修改 HA Core、EOAIC2 或 Tools for Assist 的安装文件。

**真实集成验收仍待进行：**没有使用真实 Tavily API Key 发起联网搜索，没有连接用户 HA、执行实际对话/Assist/TTS 或验证用户此次上游更新后的运行状态。用户尚未报告 v0.5.0 或 1.11.0 组合的实际验收通过。

复现：先按锁文件安装开发依赖，再运行 `python scripts/fetch_test_upstream.py`、`python scripts/fetch_tools_upstream.py` 和 `pytest -q --timeout=30`；仅运行新增核对用例可用 `pytest -q tests/test_tavily_compatibility.py --timeout=30`。
