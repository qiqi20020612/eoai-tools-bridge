# Tools for Assist 工具兼容清单

核对日期：**2026-10-19（Asia/Shanghai）**。当前版本 **v0.6.1**，继续 0.x 小版本迭代。用户已明确取消 Home Control API：EOAIC2 已有原生 HA 控制，因此 Home Control 的状态/历史、动态控制、脚本、设备上下文和计时器均从本项目后续开发与 1.0 门槛中移除。既有 EOAIC2 设备控制 Functions 继续使用原来的路径。

源码基准为 [Tools for Assist 1.11.0](https://github.com/skye-harris/llm_intents/tree/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents)，提交 `198e37885fe06e6452d2d6e26bc5e532b1686acc`；保留原基线 `100e740b93a2a1a6d304329883937193a4571ac0` 回归。HA 源码与自动化测试基准已升级为 **2026.10.2**，提交 `8d7fd8b68677c2585be36ec86043308f403875b8`；基准升级后的 443 项回归通过。v0.6.0 初始发布时的 2026.10.0 证据保留在测试记录中；v0.6.1 在新基准下通过 473 项回归，并修复通用调用的大结果裁剪。上游更新后重新核对入口、参数及实现，固定快照不保证未来版本兼容。Tavily 的增量核对见 [1.11.0 记录](TOOLS_FOR_ASSIST_1_11_0.md)。

## 当前范围与证据

本节只列已交付的 Tools for Assist 直通能力。下文新增的高德地点/位置工具尚在规划中，不计入当前工具数量、源码契约覆盖或真实验收结果。

原版 [llm_functions.py](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/llm_functions.py) 中的四个非 Home Control API 为 `llm_intents`、`weather_forecast`、`basic_utilities`、`media_services`，合计 **10 个固定工具名、13 个实现**；四个搜索提供商共用 `search_web`。v0.6 在隔离测试中实例化这四个原版 API，核对其全部启用工具与此清单一致。原版参数、工具方法或 API 的模拟契约通过不代表真实后端或设备验收通过。

| API / 工具 | 参数与条件 | v0.6 开发验证 | 真实验收 |
| --- | --- | --- | --- |
| `llm_intents/search_web` | `query`；Brave LLM Context 可选 `freshness`，Tavily 可选 `topic/time_range`；另含 Brave、SearXNG | 四个实现的原版参数和模拟调用；固定搜索、目录、就绪及通用调用回归；v0.6.1 用原版 Brave LLM Context 与 EOAIC2 脚本验证带/不带 freshness 的大结果仍保留正文 | 旧版搜索总体验收由用户报告通过；提供商逐项及 1.11.0 组合待确认 |
| `llm_intents/find_places` | `query`；上游地点后端配置 | 原版参数、目录、就绪和模拟 HTTP 调用 | 待逐项实际验收 |
| `llm_intents/get_route` | `destination`，可选 `departure_time/mode`；上游起点与路线配置 | 原版参数及模拟 HTTP 调用；保留距离、耗时和嵌套结果 | 待逐项实际验收 |
| `llm_intents/search_wikipedia` | `query` | 原版搜索与摘要方法，HTTP 模拟 | 待逐项实际验收 |
| `llm_intents/search_youtube` | `query`，可选 `num_results` 默认 1、范围 1–25；上游密钥 | 原版 Schema 默认值/范围及模拟 HTTP 调用 | 待逐项实际验收 |
| `weather_forecast/get_weather_forecast` | `range` 枚举；配置上游天气实体 | 原版参数与方法、模拟天气数据、文本响应 | 待逐项实际验收 |
| `basic_utilities/unit_convert` | 字符串 `amount/from_unit/to_unit`，支持分数 | 原版参数和计算代码、原版 EOAIC2 脚本接线 | 待逐项实际验收 |
| `basic_utilities/calendar_day_info` | 整数 `day/month`，可选 `year` | 原版参数和日期代码、原版 EOAIC2 脚本接线 | 待逐项实际验收 |
| `basic_utilities/calculate` | `operation=expression/min/max/avg`，字符串数组 `data`；遵守下述数值边界 | 原版 BasicUtilitiesAPI、选择器和 SymPy 计算；表达式拒绝边界、目录、描述、检查及 EOAIC2 脚本 | 待实际计算与对话验收 |
| `media_services/play_video` | `video_url`，可选动态 `entity_id` 数组、`area/device_id`；上游启用 YouTube、HA 中有适用播放器 | 原版 MediaAPI、动态实体选择器、显式实体/区域/设备及单设备回退；调用模拟 HA 播放服务；错误、超时不重试；EOAIC2 脚本 | 待物理播放器与对话验收 |

播放是本次明确保留的 Tools for Assist 媒体工具；HA 原生设备控制、脚本及计时器由 EOAIC2 承担。上游 PlayVideoTool 会接收桥接传入的原始管理员 `LLMContext`，但它调用 `media_player.play_media` 时**没有继续传入 Context**，因此下游服务 Context 的 `user_id` 为空。桥接仍执行入口管理员、精确白名单及副作用许可检查；不据此宣称用户身份贯穿下游服务，也不修改上游或 HA Core 来改变该行为。真实环境需确认此行为符合自身使用条件。

## 配置与发现

Tools for Assist 管理工具启用、密钥、天气、路线起点及播放器条件。桥接生产代码只通过 HA 公开 LLM 注册/调度接口访问它，不导入或复制其内部实现；原版测试副本只在开发缓存中加载。

按需把下列确切组合加入桥接白名单并启用 `call_tool`。**9 个当前范围内的只读组合**如下；不会自动添加配置，默认清单仍只开放搜索：

```text
llm_intents/search_web
llm_intents/find_places
llm_intents/get_route
llm_intents/search_wikipedia
llm_intents/search_youtube
weather_forecast/get_weather_forecast
basic_utilities/unit_convert
basic_utilities/calendar_day_info
basic_utilities/calculate
```

管理员可在副作用许可关闭时使用这些组合。审核依据要求公开 `integration=llm_intents`，返回 `read_only_basis=audited_allowlist`，且不覆盖上游明确的危险声明。原始有效管理员、精确白名单和通用调用开关始终分别检查。

播放另行加入 `media_services/play_video`，执行还须开启独立副作用许可。先调用 `describe_tool` 查看其当前动态实体枚举和参数；读取描述不要求开启副作用许可，不执行工具或默认工厂，也不授予权限。`list_tools` 仍只返回只读工具，`check_tools` 仍只检查状态和 Schema 类型，完全不执行工具、参数 Schema、默认工厂或序列化钩子。参数描述转换可能调用原生序列化器，不能与就绪检查混为一谈。

`describe_tool` 一次返回一个已授权工具的元数据，因此可查看播放参数而无需把副作用工具加入只读目录。参数仍是当前快照；设备、工具或配置变化后重新获取。授权调用使用未修改的原生 Schema 应用默认值和校验约束，桥接最多调度一次。播放失败或超时可能已经改变设备，响应中的 `outcome_unknown=true` 要求先核对实际状态。

示例：[查询](../examples/query_tools_actions.yaml)、[参数描述](../examples/describe_tool_action.yaml)、[计算器](../examples/calculator_action.yaml)、[播放](../examples/play_video_action.yaml)、[EOAIC2 参数描述](../examples/eoaic2_describe_tool.yaml)；调用沿用 [call_allowed_tool](../examples/eoaic2_call_tool.yaml)。所有 HA 脚本调用须接收响应。

## 计算器边界

上游使用 SymPy `sympify`，其官方文档说明内部使用 `eval`。v0.6 在调用原版工具前，用标准库 AST 和有限数值运算校验输入；估算值丢弃，实际结果仍由原版工具生成。桥接不接受任意 SymPy/Python 表达式：

- `data` 为 1–32 个字符串；`expression` 必须恰好一个，最多 256 字符、64 个 AST 节点、8 层深度。
- 仅有限实数、常量 `pi/E`、运算 `+ - * / // % ** ^` 及函数 `sqrt/sin/cos/tan/exp/log/Abs/abs/floor/ceiling/Min/Max`；函数仅接受位置参数。拒绝属性、索引、字符串、任意名称或代码。
- 数字及中间估算绝对值最多 `1e100`，非零值至少 `1e-100`，幂指数绝对值最多 32；非法运算、非有限结果和可检测的下溢拒绝。
- `min/max/avg` 每个数值字符串最多 64 字符，使用相同有限数值边界。

限制作为 `bridge_constraints` 随计算器目录项及单工具描述返回；超出限制时返回 `invalid_args`，不调度计算器。受信任的同步上游代码仍须正常返回，20 秒异步超时不能强制中断同步计算；这些限制不构成 Python 沙箱或 CPU 隔离。

## Home Control 的既有兼容

v0.5 曾提供 `HomeControl/get_device_history_context` 的审核分类。为保持已有手工配置可用，v0.6 保留该旧分类及通用网关行为，不自动删除已保存白名单。它属于历史兼容，不再列入当前支持范围、示例或后续验收门槛。不会新增 Home Control API 聚合、动态控制/脚本、设备上下文或计时器实现；旧版本测试及发布记录保留供追溯。

## 1.0 前新增范围：高德地点与位置工具（仅规划）

2026-10-19 按用户要求加入：**复刻 Tools for Assist 中地点位置相关工具的使用能力，将新实现的数据源由 Google 地图改为高德地图。当前只修改规划，不启动实现。** 以原版 1.11.0 的 `google_places.py`、`google_routes.py` 为功能参考，在本项目维护独立的高德工具；继续遵守不修改 EOAIC2、Tools for Assist、HA Core 或其安装文件的边界。

| 参考能力 | 高德实现的规划范围 | 参数与结果要求 |
| --- | --- | --- |
| `find_places` 地点/商户查询 | 地名或关键词检索、按配置位置查找附近地点、城市/区域与范围约束、排序及数量限制；保留名称、地址、位置，以及上游实际提供的电话、营业时间、评分等信息 | 保留 `query` 的基本使用语义；额外参数在设计阶段确定。高德未提供的字段明确缺失或省略，不编造字段，也不承诺 Google 与高德数据完全一致 |
| `get_route` 路线查询 | 从配置起点到用户描述的目的地，解析地点后返回距离、耗时及适用的路线摘要，支持明确的出行方式与时间语义 | 以 `destination`、可选 `departure_time/mode` 为兼容设计起点。逐项核对出行方式、未来出发时间等能力；无法等价映射时明确报出限制，不静默换成其他方式或当前出发时间 |
| 两者所需的位置解析 | 地名/地址到坐标、目的地消歧、起点配置；按实际需要评估逆地理编码和坐标转换 | 明示坐标参考系、经纬度顺序、距离/时间单位和时区；对配置坐标按所选接口规范适配，覆盖偏移与重复转换问题。优先作为内部公共能力，是否另行暴露工具待设计 |

接口核对参考高德官方的 [POI 搜索](https://lbs.amap.com/api/webservice/guide/api-advanced/search)、[路径规划](https://lbs.amap.com/api/webservice/guide/api/direction) 与 [地理/逆地理编码](https://lbs.amap.com/api/webservice/guide/api/georegeo)。这些文档用于功能映射依据；实际开发前复核所选 API 版本、Web 服务 Key、接口权限、配额及返回字段，再确定最终 Schema，不在本次规划中锁死端点或声称已支持具体参数。

集成与兼容边界：

- 新工具由本项目提供，以独立的 API/工具身份区分高德来源，具体标识在设计时确定；不接管或伪装成 Tools for Assist 的 `llm_intents` API。沿用现有 `list_tools/describe_tool/check_tools/call_tool` 的发现、检查和调用链路，新增只读审核依据须独立评审。
- 高德提供本次复刻工具的目标地图数据源，由本项目管理可选配置与 Key，现有无地图密钥的桥接安装路径仍可用。高德查询不得依赖 Google Key，密钥、精确位置和完整查询按既有日志/输出约束处理。
- `llm_intents/find_places`、`llm_intents/get_route` 仍代表上游原版 Google 工具，作为旧白名单的兼容路径保留。迁移至高德时明确更新工具标识及授权，不能把旧请求静默转发到新供应商；现有 Google 契约证据不算作高德验证。
- 新工具继续要求明确启用、精确白名单和原始有效管理员 Context；保持原生参数校验、只读分类边界、固定错误、取消/超时和 16 KiB 输出预算。大 POI/路线响应必须保留有效数据，回归 v0.6.1 的裁剪问题。
- 高德地点和路线的实现、模拟契约及真实联网/EOAIC2 验收均为 1.0 前必需项。Home Control 继续排除，不因本次位置规划恢复设备控制、脚本、设备上下文或计时器。

## 剩余 0.x 工作与 1.0 门槛

v0.6 已为当前非 Home Control 工具家族补齐原版参数/调用契约与媒体参数发现，v0.6.1 修复通用大结果裁剪。后续新增高德地点位置工具，继续按小版本推进。下表版本号为拟定分期，**高德相关阶段均未启动开发**，不代表本次启动开发或承诺发布日期；实际启动以用户后续开发指令为准。

| 阶段 | 计划交付 | 进入后续阶段前的验收重点 |
| --- | --- | --- |
| v0.6.x 稳定维护 | 处理已发布功能的真实复测与必要修复 | v0.6.1 的真实大结果复测、既有查询/计算器/媒体及权限回归 |
| v0.7 高德地点与位置解析 | 高德可选配置、独立工具身份、地点/附近地点查询与必要的位置解析，接入现有发现/检查/调用接口 | 明确参数/字段映射，配置与权限边界、坐标/城市消歧、缺失字段、空结果、Key/配额失败与大结果的模拟契约；真实地点查询验收另记 |
| v0.8 高德路线 | 配置起点、目的地解析、路线距离/耗时、出行方式及时间参数适配，复用位置公共能力 | 逐种方式与时间能力核对、无法映射时的明确错误、单位/时区/坐标一致性、失败/取消/预算、原版行为参考与高德真实路线验收 |
| v0.9 联调与收口 | Google 直通到高德工具的明确迁移说明、EOAIC2 Functions 使用和授权指引、HACS 升级与完整真实验收 | 独立记录高德与旧 Google 路径、查询/计算器/媒体等家族的证据；完成全部 1.0 门槛 |
| 后续 0.x（按需） | 补齐未完成映射、修复验收问题与上游变化 | 任一必需项仍未完成时继续 0.x，不按版本号直接跳至 1.0 |

1.0 前仍需完成：

- [ ] 在真实 HA 中记录 1.11.0 或后续复核版本实际启用的四个 API、工具清单、参数和响应；查询、计算器、媒体分别验收，注明缺少的后端条件，不把类型就绪当作实际成功。
- [ ] 实际验证四种搜索后端及可选筛选参数，以及维基百科、YouTube、天气、单位换算和日期；接受计算器数值限制，验证原版结果及拒绝行为。地点与路线按下述高德门槛验收。
- [ ] 完成本项目高德地点查询、路线查询和必要位置解析的实现、配置及独立工具身份；逐项记录与 Tools for Assist 的参数/字段/出行方式/时间能力映射，所有差异明确处理，高德路径不依赖 Google Key。
- [ ] 高德工具具备发现/描述/不执行参数逻辑的就绪检查、原始管理员与精确白名单、参数/输出限制及错误处理的契约测试；覆盖坐标、同名地点、缺失字段、空结果、超时、配额/Key 失败和大结果，不以旧 Google 测试替代。
- [ ] 在真实 HA 与 EOAIC2 中分别验收高德地点和路线，记录所用 API、实际 Key 的接口权限、起终点/城市、坐标及单位/时间映射和有效结果；旧 Google 直通保留兼容回归，新增地点/路线的 1.0 验收以高德为准。
- [ ] 用适用物理播放器验证实体/区域/设备选择、单设备回退、独立副作用许可与不重试；确认上游下游 Context 限制及失败后的人工状态核对。
- [ ] 实际验证 EOAIC2 原始管理员 Context、`_function_result`、模型选工具和参数描述，并回归既有原生 HA 控制 Functions。
- [ ] 实际通过 HACS/Release 升级、重启及选项保持；原四个动作兼容，第五个参数描述动作可用。
- [ ] 复核发布时的上游变更、受支持 HA 版本、参数/输出预算及全部契约检查；当前非 Home Control 工具没有未记录的兼容缺口，CI 无遗漏或跳过。

模拟和契约测试不等于联网、物理设备、实际模型、Assist/TTS 或安装验收。用户尚未明确报告 v0.5 或 v0.6 实际验收通过；历史版本的总体验收也不补写逐项证据。各版本结果见 [TESTING.md](TESTING.md)。
