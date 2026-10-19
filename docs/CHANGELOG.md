# 版本记录

## 0.7.2 — 2026-10-20

- 完善全部 12 个工具组合及两份搜索参数变体的模型可见 description；按“何时调用、怎样传参、限制、返回含义”核对，工具描述放用途/结果，参数描述放类型、格式、枚举、默认值与组合限制，不改全局提示词。
- 单位换算明确中文单位先映射到实际支持的英文标识（含 dl），amount 始终字符串、同类换算及四位小数结果；维基百科固定英文源、优先英文搜索词并用用户语言回答；YouTube 按实际需求选条数，相关结果不足时可补充。
- 三份 search_web 分别说明提供商参数边界、片段/Tavily answer 的含义和当前上游丢弃来源 URL 的事实；引用须有返回证据，缺链接本身不要求重复搜索。Google/高德地点分别解释匹配、默认位置/城市、数量、缺失字段与评分/营业语义；高德真实 GCJ-02、经度在前、附近组合限制和地址 ambiguous 候选消歧明确。
- Google get_route 明确固定配置起点、mode/出发时间默认及估算结果；补足天气覆盖、计算数值/结果类型、公历年份与播放目标/URL 兼容性、命令成功与真实播放的区别。高德路线不在本补丁中，按既定路线留到 v0.8.0。
- Function 名、API/tool 身份、Schema 约束/默认、Jinja 模板/执行序列、Bridge 运行代码、权限、白名单、返回格式、依赖及 HACS 更新机制保持 v0.7.1 不变，仅更新发布版本元数据。Google/高德 find_places 二选一与搜索三选一继续保留；已有 Functions 须手动替换，HACS 不会自动改写。
- 同步 README、完整代码块、迁移与来源说明；新增 29 项非描述结构冻结、描述覆盖/长度与原版英文单位组验证，文档代码块与 YAML 逐字核对。完整 **630 passed、0 skipped**，Ruff 与锁文件检查通过。真实模型对话、用户 HA 和物理设备效果仍须单独验收。

## 0.7.1 — 2026-10-19

- 补齐当前 12 个 API/工具组合的独立 EOAIC2 Functions：原 10 个 Tools for Assist 工具与高德 find_places、geocode。提供 12 份主静态 YAML 及 2 份搜索筛选参数变体，全部 type: script，脚本固定身份并调用 eoai_tools_bridge.call_tool，模型只填写各工具原生参数。
- 推荐独立 Functions，call_allowed_tool 改为可选高级方案。统一推荐模型名 search_web，删除旧 eoaic2_web_search.yaml，并要求手动替换旧 web_search，避免重复；未恢复已删除的独立搜索服务。
- 按提供商区分 query-only、Brave LLM Context freshness、Tavily topic/time_range，三份 search_web 只选一份。Google 与高德 find_places 同名且在 Functions/精确白名单中二选一，保留原 API 身份，不自动切换。
- 原生必填/可选、枚举、默认值及桥接限制逐项映射；整体 data 模板保留字符串、整数、数组和参数省略，播放 device_id 排除 HA 同名内置函数，动态实体枚举仍由当前原生选择器校验。原始管理员、白名单、副作用许可和 HACS 独立更新不变。
- 新增 [完整 Functions 指南](EOAIC2_FUNCTIONS.md)，包含全部可复制片段，更新 README、迁移说明和过时辅助示例；文档代码块与静态文件一致性受测试验证，不增加 YAML 生成器或上游修改分支依赖。
- 新增 89 项示例验证；完整 **601 passed、0 skipped**。使用现有未修改的原版 EOAIC2 ScriptFunction、Tools for Assist 1.11.0 Schema 及真实 HA 服务/权限链，提供商执行模拟。Bridge Python 运行文件、依赖和上游源文件保持不变，仅更新 0.7.1 发布元数据；本次没有新增真实联网、安装或模型验收证据。

## 0.7.0 — 2026-10-19

- **接口变更：删除独立 eoai_tools_bridge.search_web 服务。** 移除专用注册、search.py 执行/规范化链路、旧 Schema/常量、旧示例及专用测试；仅保留 list_tools、check_tools、describe_tool、call_tool。启动清理残留旧注册，旧服务调用不再有执行回退。
- **迁移：**在桥接选项启用 call_tool，明确允许 llm_intents/search_web；搜索同样要求原始有效管理员 Context。把 query 放入 tool_args，改读 result.results，先检查 success。新 examples/eoaic2_web_search.yaml 保留模型函数名 web_search，但底层统一调用 call_tool；替换旧 Functions，不重复追加同名函数。完整步骤见 [迁移说明](MIGRATION_0_7.md)。
- 保留 Tools for Assist 搜索工具、原生 freshness/topic/time_range 参数、只读审核和精确白名单。共享 validate_query 移至 validation.py，500 字符/空白/有效 Unicode 校验保留；既有权限、计算器、副作用、取消/超时机制及 v0.6.1 的 payload.py 裁剪不变。升级不自动授权，不补造管理员身份。
- 新增本项目独立的 eoai_tools_bridge_amap/find_places 与 geocode，只读高德关键词/附近地点和地址候选解析。增加可选 Web 服务 Key、默认城市和 GCJ-02 经度,纬度中心配置；密钥不进入模型参数、日志、缓存、源码或发布包。Google 原工具仍保留原身份，不静默切换数据源。
- 高德沿用统一发现/检查/描述/执行入口，原生 API 亦检查桥接策略。固定 HTTPS 端点、无重定向/重试/缓存、10 秒请求与 256 KiB 响应上限；字段按实际返回保留，地址歧义不自动选第一项，错误不伪装成空成功。参数、排序限制与字段差异见 [高德说明](AMAP.md)。
- 本地 512 项模拟/契约测试通过，0 skipped，含原版 EOAIC2 和 Tools for Assist 契约。另用内存中的测试 Key 真实验证三个高德端点：关键词/附近各 2 项、地址解析 1 个候选，均有有效 GCJ-02 坐标。真实 HA/EOAIC2/升级验收另行记录，未开发高德路线，继续 0.x。
- 用户报告 v0.6.1 总体验收通过，不据此补写逐后端或设备证据。

## 0.6.1 — 2026-10-19

- 修复通用 call_tool 大结果超过 16 KiB 后直接 popitem 删除顶层 results 的问题；保留顶层字段，递归裁剪嵌套数组尾项、文本及必要的嵌套对象字段，保持有效数据与首条结果。
- 按实际 UTF-8 JSON 大小计入转义字符和省略号；顶层空对象、过滤后空对象或无法缩减到预算的结果使用现有 invalid_response 返回失败，副作用调用仍正确标记 outcome_unknown；合法空数组、零值和布尔值保持兼容。
- 新增 30 项大结果与边界回归；原版 Tools for Assist Brave LLM Context、HA 服务和原版 EOAIC2 ScriptFunction 验证固定搜索与带/不带 freshness 的通用搜索。完整 473 passed、0 skipped；接口、白名单、原始管理员、原生参数验证和副作用许可保持原契约。
- 按用户要求，将 HA Core 源码与开发/CI 基准升级为 2026.10.2，精确固定配套测试插件 0.13.373，并同步升级 aiohttp 至 3.14.5；CI 显示实际测试版本。

## 0.6.0 — 2026-10-19

- 按用户决定取消 Home Control API 后续实现与 1.0 验收要求，HA 原生控制继续由 EOAIC2 承担；保留 v0.5 历史分类和已有手工白名单兼容，不新增动态控制、脚本、设备上下文或计时器。
- 新增管理员 `describe_tool`，一次读取一个明确授权工具的当前原生参数；可先查看播放动态选择器再决定执行许可，不执行工具/参数校验器/默认工厂，不扩大权限。只读目录及不执行参数逻辑的就绪检查保持原契约。
- 补齐原版计算器/API 与有限数值输入校验，支持 expression/min/max/avg；通过校验的计算器不再需要副作用许可，约束随目录和描述返回。原版 SymPy 产生结果，生产无新增 pip 依赖；超出边界不调度。
- 补齐原版 MediaAPI、动态实体数组选择器、区域/设备及单设备回退的调用契约，播放仍要求独立副作用许可；失败/超时不重试。上游未向下游 HA 播放服务转交用户 Context 的已知限制已记录。
- 纳入 Tools for Assist 1.11.0 / Tavily 的固定快照和 17 项模拟契约，保留原搜索/查询契约；当前四个非 Home Control API 共 10 个固定工具、13 个实现的源码清单及开发契约齐全，真实验收仍待完成。
- 443 项模拟/契约测试通过，0 skipped；其中 28 项执行原版 EOAIC2 脚本、119 项带 Tools for Assist 源码标记（重叠 5 项）。补充中英文动作、参数描述及计算/播放示例；真实用户环境验收见 [TESTING.md](TESTING.md)，继续迭代 0.x。

## 0.5.0 — 2026-10-10

- 延续 0.x 小版本迭代，明确将 Tools for Assist 全部工具家族的兼容与实际验收作为 1.0 发布门槛；提供完整固定工具/动态 Home Control 工具清单及后续版本计划。
- 对明确配置且由原始管理员调用的 9 个 Tools for Assist 查询组合补齐审核只读依据，覆盖三个网页搜索实现及地点、路线、维基百科、YouTube、天气、单位换算、日期和实体历史；无需开启副作用许可，不自动扩大访问白名单。
- 只读目录支持普通 Optional 默认值，通过有预算、不编译的元数据视图省略默认工厂，保留原生参数约束。原生调用仍执行未修改的 Schema 和默认值一次；必填/分组默认值及无法忠实表达的参数继续拒绝发现。
- 新增 SHA-256 固定的原版 Tools for Assist 契约测试与 CI 获取流程、查询动作示例和中英文说明。345 项模拟/契约测试通过，含 25 项原版 EOAIC2 脚本测试、46 项 Tools for Assist 标记的源码契约测试（其中 2 项同时属于两类）；实际验收另见 [TESTING.md](TESTING.md)。
- 计算器、媒体播放、Home Control 动态控制/脚本与设备相关计时器的完整发现、参数和调用验收继续列入后续 0.x，不据当前模拟查询测试宣称已全工具验收。
- 用户报告 v0.4.0 实际验收通过；四个已有动作及升级后的明确授权选项保持兼容。

## 0.4.0 — 2026-10-10

- 本次仅增加白名单工具就绪检查，继续 0.x 小版本迭代。
- 新增无入参、仅返回响应的 `eoai_tools_bridge.check_tools`，要求原始有效管理员身份，检查确切白名单工具的 API 注册、工具可用性、Schema 类型及副作用许可。
- 通用调用关闭时仅查询注册表，不取得 APIInstance；开启后每个 API 在一次检查中读取一次。始终不执行工具、参数 Schema、默认值工厂或序列化钩子。
- 每个工具返回独立状态；检查期间权限/身份变化或总体超时会丢弃结果，不泄露过期权限快照、私有配置或异常原文。
- 提供中英文动作说明、开发者动作示例及可选 EOAIC2 `check_enabled_tools` YAML。`ready` 不验证真实后端、密钥或具体参数，不授予新权限。
- 旧动作及 v0.3.0 的白名单和许可保持兼容；274 项模拟/契约测试通过，含 23 项原版 EOAIC2 脚本测试。实际 v0.4.0 验收另见 [TESTING.md](TESTING.md)。
- 用户报告 v0.3.0 实际验收通过，并要求继续小版本迭代。

## 0.3.0 — 2026-10-09

- 新增默认关闭的 `eoai_tools_bridge.call_tool`，通过集成选项逐项启用 API/工具组合，最多 32 项；保存后立即生效。
- 所有通用调用要求原始有效管理员 Context；写入、破坏性及未声明只读的工具还需要独立副作用许可。API 获取后及原生参数校验后再次检查权限，撤销或身份改变阻止执行。
- 使用上游 probatio Schema 校验参数，支持枚举、默认值和无参工具；JSON 入参限 8 KiB，结果限 16 KiB，隐藏已知指令/凭据字段及异常原文。
- 工具最多执行一次；副作用工具执行后的失败标记 `outcome_unknown`，提示状态可能已改变，不自动重试。
- 提供中英文白名单选项、动作说明、动作示例及可选 EOAIC2 `call_allowed_tool` YAML；额外只读清单仅向原始管理员开放，副作用工具仍不出现在清单中。
- 原有 `search_web`、默认清单和已安装配置保持兼容。225 项模拟/契约测试通过，含 19 项原版 EOAIC2 脚本测试；实际 v0.3.0 验收另见 [TESTING.md](TESTING.md)。
- v0.2.0 的真实验收由用户报告通过；仓库公开后重跑 v0.2.0 HACS 校验通过。

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
