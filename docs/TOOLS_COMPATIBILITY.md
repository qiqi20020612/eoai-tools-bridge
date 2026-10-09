# Tools for Assist 全工具兼容清单

核对日期：**2026-10-10（Asia/Shanghai）**。用户要求继续 0.x 小版本迭代，并在 1.0 之前兼容 Tools for Assist 支持的所有工具。**全部工具家族的兼容与实际验收完成前，不发布 1.0。** 当前交付 v0.5.0，后续版本逐项关闭本文件中的缺口。

源码基准为 [Tools for Assist 的固定提交](https://github.com/skye-harris/llm_intents/tree/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents)，SHA `100e740b93a2a1a6d304329883937193a4571ac0`；2026-10-10 复核时为 master 当前提交。HA 基准为 2026.10.0，SHA `6a811d3359c7b2076dc9e1cf900843a129c044af`。升级上游后必须重新核对清单、参数和动态工具，不能把固定快照的检查当成未来版本保证。

## 完整范围

[llm_functions.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/llm_functions.py) 与 [home_control.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/home_control.py) 合计定义 **11 个固定工具名、13 个实现**（网页搜索的三个提供商共用一个工具名），另加 Home Control 从 HA Assist 平台聚合的动态工具。API 标识区分大小写，`HomeControl` 不等于 `home_control`。

| API / 工具 | 参数要点 | v0.5.0 开发验证 | 实际运行 |
| --- | --- | --- | --- |
| `llm_intents/search_web` | `query`；Brave LLM Context 另有可选 `freshness` 枚举；Brave、Brave LLM Context、SearXNG 三个实现 | 原有固定搜索接口保留；三个原版 Schema、只读目录、检查和调用契约通过 | 旧版搜索总体验收已由用户报告通过；未取得提供商逐项证据 |
| `llm_intents/find_places` | `query` | 原版 Schema、目录、检查、模拟 HTTP 调用通过；保留地点字段 | v0.5 待实际验收 |
| `llm_intents/get_route` | `destination`，可选 `departure_time`、`mode` 枚举 | 原版 Schema、目录、检查、模拟路线 HTTP 调用通过；保留距离与耗时 | v0.5 待实际验收 |
| `llm_intents/search_wikipedia` | `query` | 原版 Schema、目录、检查、模拟搜索及摘要 HTTP 调用通过 | v0.5 待实际验收 |
| `llm_intents/search_youtube` | `query`，可选 `num_results` 默认 1、范围 1–25 | 原版 Schema、目录、检查、模拟 HTTP 调用通过；默认值仅在授权调用时求值 | v0.5 待实际验收 |
| `weather_forecast/get_weather_forecast` | `range`：`week`、`today`、`tomorrow` 或星期枚举 | 原版 Schema、目录、检查、模拟天气数据调用通过；支持上游文本结果 | v0.5 待实际验收 |
| `basic_utilities/unit_convert` | 字符串 `amount`、`from_unit`、`to_unit`；支持分数 | 原版 Schema、目录、检查和换算代码通过；原版 EOAIC2 脚本接线通过 | v0.5 待实际验收 |
| `basic_utilities/calendar_day_info` | 整数 `day`、`month`，可选 `year` | 原版 Schema、目录、检查和日期代码通过；原版 EOAIC2 脚本接线通过 | v0.5 待实际验收 |
| `HomeControl/get_device_history_context` | `name`、`domain`、起止日期时间，可选 `area` | 原版 Schema、目录、检查和模拟 Recorder 调用通过；保留统计及状态采样 | v0.5 待实际验收 |
| `basic_utilities/calculate` | `operation` 选择器：`expression/min/max/avg`；`data` 字符串数组 | 已盘点；现有通用传输保留，但原版计算器与参数发现的完整契约待后续版本；未加入审核只读集合 | 后续 0.x 验收 |
| `media_services/play_video` | `video_url`，可选动态 `entity_id` 数组、`area`、`device_id` | 已盘点；现有副作用许可保留，动态选择器、原版媒体调度和参数发现待后续版本 | 后续 0.x 验收 |
| `HomeControl/homeassistant__GetLiveContext` | 按原生 HA 的当前 Schema | 已盘点；原版 Home Control API 聚合与状态读取待后续版本 | 后续 0.x 验收 |
| `HomeControl/intent__Hass…`、各域原生工具 | 如开关、位置、灯光、媒体等；工具名及参数随加载的平台和暴露实体变化 | 已盘点；动态注册、上游禁用列表、参数转换、原生权限及副作用失败语义待后续版本 | 后续 0.x 验收 |
| `HomeControl/script__<脚本名>` | 当前被暴露脚本的字段/选择器 | 已盘点；动态脚本字段、默认值、调用及响应待后续版本 | 后续 0.x 验收 |
| `HomeControl/intent__Hass…Timer…` | 计时器参数与可信设备上下文 | 已盘点；当前桥接的 LLMContext `device_id=None`，无法取得依赖设备的完整工具集合，须在后续 0.x 补齐 | 后续 0.x 验收 |
| `HomeControl/<其他平台>__<工具名>` | 其他加载的 HA LLM 平台提供的当前 Schema | Home Control 会聚合所有已加载的 Assist 工具平台；必须在实际环境枚举，不能仅核对上述常见名称 | 后续 0.x 验收 |

HA 动态工具来源见 [LLM 平台聚合](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/homeassistant/components/llm/__init__.py)、[原生意图与计时器](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/homeassistant/components/intent/llm.py)、[脚本工具](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/homeassistant/components/script/llm.py) 及 [实时状态工具](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/homeassistant/components/homeassistant/llm.py)。其数量随安装环境变化，不能宣称一个固定工具数量就是“全部支持”。

## v0.5.0 使用方式

Tools for Assist 仍负责启用工具、配置密钥、天气实体、路线起点、Recorder 和实体暴露。桥接只使用 HA 公开的 LLM 注册/调度接口；原版测试副本仅保存在开发缓存中，不导入生产集成、不安装、不修改上游文件。

在桥接选项中逐项添加需要的工具并启用 `call_tool`。下面是本版本已审核的 **9 个只读 API/工具组合**，可按需复制；不会自动加入选项：

```text
llm_intents/search_web
llm_intents/find_places
llm_intents/get_route
llm_intents/search_wikipedia
llm_intents/search_youtube
weather_forecast/get_weather_forecast
basic_utilities/unit_convert
basic_utilities/calendar_day_info
HomeControl/get_device_history_context
```

这些工具在上游仍使用默认注释；桥接依据固定源码审核并返回 `read_only_basis=audited_allowlist`。额外工具必须同时满足精确白名单、通用调用开启和原始有效管理员身份，因此可在副作用许可关闭时发现、检查和调用。审核判断不会覆盖上游显式声明的非只读或破坏性行为，也不适用于其他集成冒用相同标识。默认清单仍只开放旧的网页搜索组合。

`calculate` 调用 SymPy 的 `sympify` 处理表达式，桥接尚未完成其表达式边界验证，继续按没有只读依据的工具处理；媒体播放和未知动态工具继续遵守独立副作用许可。工具在白名单内并不代表 Python 代码已被隔离。后续版本要完成这些工具的完整发现、参数与调用契约，不能通过批量把未知工具标为只读实现“全兼容”。

管理员先调用 `check_tools`，再用 `list_tools` 查看当前可发现工具及原生参数，然后调用 `call_tool`。示例见 [query_tools_actions.yaml](../examples/query_tools_actions.yaml)。EOAIC2 继续使用已有的 [call_allowed_tool](../examples/eoaic2_call_tool.yaml) 和 [list_search_tools](../examples/eoaic2_list_tools.yaml) 示例；后者名称为历史名称，但能返回当前管理员明确启用的全部只读工具。

目录支持普通 `Optional` 的默认值，通过有预算的元数据视图省略默认值，不调用工厂、不重新编译校验器、不修改原版 Schema。原生授权调用仍由上游 Schema 应用默认值及范围约束。会影响必填/分组约束的默认值或无法准确表达的 Schema 仍返回 `invalid_schema`，不能放宽约束。`check_tools` 的不执行参数逻辑承诺保持不变。

## 后续 0.x 迭代与 1.0 门槛

- **v0.6 目标：**补齐计算器、媒体播放、Home Control 状态/控制/脚本的可信参数发现与原版调用契约，保留单独副作用许可及不自动重试；覆盖动态实体选择器、脚本默认值和上游禁用工具。
- **v0.7 目标：**补齐可信设备上下文、设备相关计时器和动态平台工具，验证实际运行时的完整工具集合；检查当前 32 项白名单与 16 KiB 目录预算是否限制完整配置，并提供适当容量/发现方式。
- **后续 0.x：**修复逐项实际验收发现的问题，复核最新上游工具变化；通过门槛后再确定 1.0 日期，必要时继续发布更多小版本。

1.0 发布前必须全部完成：

- [ ] 固定工具及所有实际启用的 Home Control 动态工具均可安全获得确切标识、原生参数和调用结果；没有“传输大致可用”但缺少参数发现的工具家族。
- [ ] 所有工具家族有原版参数/调用契约测试，并覆盖认证、白名单、副作用、默认值/选择器、取消、超时、输出边界与上游失败；CI 无遗漏或跳过。
- [ ] 真实 HA 中逐项确认 Tools for Assist 实际启用的工具，并记录版本、启用范围及参数/响应证据；查询、计算器、播放、设备控制、脚本、计时器等家族分别验收。
- [ ] EOAIC2 原始 Context 与 `_function_result` 接线、模型选择工具、现有设备控制 Functions、HACS/Release 升级经过实际验收。
- [ ] 上游已支持但因设备上下文、参数转换、白名单容量或结果类型而无法使用的工具为零；只有用户明确没有启用或没有后端条件的工具可以记录为环境缺项。

开发模拟和契约测试不等于真实联网、设备、Assist/TTS 或安装验收；版本总体验收声明也不用于补写未提供的逐工具证据。各版本结果见 [TESTING.md](TESTING.md)。
