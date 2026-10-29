# 上游源码核对

初次核对：**2026-10-10**；最近增量核对：**2026-10-29（Asia/Shanghai）**。开发依据以下实际源码快照，未修改任何上游源码或实际 HA 安装目录。下文旧版本分析保留原始提交，当前变更见 v0.8.2 增量记录。

| 项目 | 基准 | 固定提交 |
| --- | --- | --- |
| HA Core（当前基准） | `2026.10.4` | `357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b` |
| HA Core（v0.6.1–v0.8.1 基准） | `2026.10.2` | `8d7fd8b68677c2585be36ec86043308f403875b8` |
| HA Core（原基准） | `2026.10.0` | `6a811d3359c7b2076dc9e1cf900843a129c044af` |
| Tools for Assist（原基线） | `master` | `100e740b93a2a1a6d304329883937193a4571ac0` |
| Tools for Assist（旧发布回归） | `1.11.0` | `198e37885fe06e6452d2d6e26bc5e532b1686acc` |
| Tools for Assist（当前发布基准） | `1.11.1` | `5d2e76d72564fe378f32870bd311ca9460956281` |
| Tools for Assist（主分支增量核对） | `master`，仅 README 拼写变化 | `112aed155c90bdc5f9255bf1ffdd696b741a0d48` |
| EOAIC2 | `develop` | `b0274f752fc01495875522db9281c335af8cf484` |

## HA Core

本节公开接口在 v0.8.2 使用 2026.10.4 固定源码再次逐文件确认；旧链接用于保留最初依据，HTTP 客户端增量另记如下。

[helpers/llm.py](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/helpers/llm.py) 确认：

- `async_get_api(hass, api_id, llm_context)` 返回 `APIInstance`，API 不存在时抛 `HomeAssistantError`。
- `LLMContext` 接受 `platform, context, language, assistant, device_id`。
- `ToolInput` 接受固定工具名称及参数字典；`APIInstance.async_call_tool` 返回 `ToolResult`。
- 第三方工具返回字典时，HA 2026.10 将其包装为 `ToolResult(data=...)` 并报告弃用，字典返回兼容截至 2027.11.0 的弃用期限。桥接处理 `ToolResult`，额外保留字典防御分支。
- 尽管该方法的 docstring 提及校验，当前实现直接调用工具，未替桥接完成查询长度/类型/白名单验证。因此桥接服务自己严格验证。

[core.py](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/core.py) 确认服务注册接受 `supports_response=SupportsResponse.ONLY`；调用必须请求响应，Python 调用还必须 blocking。参数 Schema 使用 `probatio`，而不是旧版 HA 示例中的 `voluptuous`。

[pyproject.toml](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/pyproject.toml) 要求 Python `>=3.14.2`、`probatio==0.13.0`。本项目运行时没有额外 pip 依赖。

v0.2 清单使用 `async_get_apis` 枚举注册表，先过滤固定 API 白名单，再通过 `async_get_api` 取得工具的公开 `name/title/description/parameters/annotations`。不读取工具配置、不导入第三方内部模块、不调用 `async_call_tool`。

[openai_conversation/entity.py](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/components/openai_conversation/entity.py) 使用 `probatio.to_openapi(..., custom_serializer=..., openapi_version="3.1.0")` 转换工具参数。本集成沿用公开接口，额外启用 `strict=True`，避免不支持的约束被放宽，并限制 Schema 结构、大小和输出字段。

[homeassistant/__init__.py](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/__init__.py) 在启动时调用 `probatio.compat.install_as_voluptuous()`。因此 Tools for Assist 的 `import voluptuous as vol` 在正常 HA 2026.10 进程中解析为 probatio 兼容层；不能根据包内仍存在 `voluptuous` 字样就断言其 Schema 不可转换，也不需要导入上游内部模块实现转换。

HA `ToolAnnotations` 的默认值为 `read_only=False, destructive=True`，代表未声明时保守处理。固定快照中的 Tools for Assist 搜索工具直接继承未声明状态；v0.2 仅对已经审核的 `llm_intents/search_web` 使用白名单依据，并在清单标记 `read_only_basis=audited_allowlist`。若上游给出独立声明，则必须同时为只读且无破坏性。`read_only=true` 不会自行扩大 API/工具白名单。

v0.3 `call_tool` 使用同一公开注册/调度接口，只在当前精确白名单和原始有效管理员授权通过后取得 API。HA 2026.10.2 的 `APIInstance.async_call_tool` 仍不调用工具的参数 Schema，因此桥接先执行工具公开的 probatio Schema，并再次检查结果是受限 JSON 对象，再交给原生调度。Schema/default 工厂运行一次；v0.3 当时的清单仍拒绝带默认值的 Schema；调用与发现采用不同的执行边界。HA 会在 LLM trace 中记录工具名和参数，桥接自身不记录正文。

[auth/models.py](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/auth/models.py) 提供用户的 `is_active` 和 `is_admin`；桥接通过 `hass.auth.async_get_user` 查询原始 Context 用户，不靠模型参数声明身份。缺少用户或非管理员明确拒绝。测试使用真实 HA 认证存储的用户。未声明只读的工具、写入或破坏性工具需要另外启用副作用选项；注释不作为 Python 沙箱。

[config_entries.py](https://github.com/home-assistant/core/blob/8d7fd8b68677c2585be36ec86043308f403875b8/homeassistant/config_entries.py) 的公开 OptionsFlow 在初始化后提供 `config_entry`。桥接保留单实例配置流与版本 1，新增原生选项流；旧配置没有授权选项，通用调用默认关闭。运行时每次读取选项和已加载状态，无需维护 API 实例或额外重载缓存。

v0.4 增量复核日期为 **2026-10-10**，当时采用原基准 HA 2026.10.0。`check_tools` 仅使用 `async_get_apis`、逐项授权 API 的 `async_get_api` 和工具公开的 `name/annotations/parameters`。Schema 只做 probatio 类型检查，既不执行校验，也不调用 `to_openapi` 或自定义序列化器；因此可检查带默认值的工具而不求值默认工厂。`ready` 只描述权限及元数据的当前状态，不能替代真实工具调用或参数校验。禁用通用调用时只读注册表，不取得 APIInstance；不修改配置、扩大权限或使用缺失用户的替代身份。


### 2026-10-19：基准升级到 HA Core 2026.10.2

按用户要求，将当前源码和开发/CI 基准升级到 [HA Core 2026.10.2](https://github.com/home-assistant/core/releases/tag/2026.10.2)，固定提交 `8d7fd8b68677c2585be36ec86043308f403875b8`。开发依赖明确固定 `homeassistant==2026.10.2` 和 `pytest-homeassistant-custom-component==0.13.373`；后者的 PyPI 元数据也要求同版 HA。锁文件仅升级 HA、配套测试插件及其要求的 `aiohttp` 3.14.4 → 3.14.5；Python 仍要求 >=3.14.2，probatio 仍为 0.13.0。

对比两版已安装的官方发行包中 11 个相关源码文件：LLM、服务核心、配置项、用户模型、脚本、选择器、服务描述、翻译、初始化及 OpenAI 参数转换的 10 个文件逐字节一致；`auth/__init__.py` 增加删除用户时撤销其刷新令牌的处理。桥接使用的公开接口与原始有效管理员检查约定保持适用，无需修改桥接运行代码。GitHub compare 的文件列表达到 300 项上限，因此逐文件比对发行包，不以列表中缺少某文件推断它未变。

在新基准下运行完整 **443 项**回归，**0 skipped**，覆盖真实 HA 服务/认证/配置/Schema、原版 EOAIC2 ScriptFunction 及 Tools for Assist 原版契约。Ruff 静态与格式检查通过；网络和播放后端仍模拟，实际用户环境验收另计。完整结果及 CI 证据见 [TESTING.md](TESTING.md)。

## Tools for Assist

[llm_functions.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/llm_functions.py) 中 `SearchAPI.id=llm_intents`。仅配置了相关工具的 API 才注册；即使搜索 API 注册，也可能只启用了维基百科等工具。桥接分别检查 API 注册与 `search_web` 可用性。

[base_web_search.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/base_web_search.py) 的工具名为 `search_web`，必填参数 `query`。正常结果为 `{"results": ...}`，空结果为字符串 `"No results found"`，业务失败为 `{"error": ...}`，部分成功响应附有 `instruction`。旧专用搜索链路曾规范化空结果；v0.7 统一使用 call_tool，保留原生 results 字符串，继续隐藏错误原文并丢弃指令字段。

实际结果格式：

- [brave_web_search.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/brave_web_search.py)：`title` 及 `content`，后者可为摘要列表。
- [brave_llm_context_search.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/brave_llm_context_search.py)：`content` 是摘要列表，JSON 摘要可能被解析为对象。
- [searxng_search.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/searxng_search.py)：`title` 及字符串 `content`。

以上三个后端当前都未向 LLM 返回 URL。桥接不会从标题猜测来源；若将来上游提供实际 `url`/`link`，会保留安全的原始链接。

v0.5 按上述同一固定提交核对所有工具入口。API 标识为 `llm_intents`、`weather_forecast`、`media_services`、`basic_utilities` 和区分大小写的 `HomeControl`。完整的固定工具、三个网页搜索变体、HA 原生动态平台/脚本和设备相关计时器见 [TOOLS_COMPATIBILITY.md](TOOLS_COMPATIBILITY.md)。Home Control 聚合 HA Assist 平台工具，并按 Tools for Assist 的禁用列表过滤；完整范围随实际加载平台与实体暴露变化。

v0.5 的开发测试通过 `scripts/fetch_tools_upstream.py` 获取 SHA-256 固定的 20 个原版工具/依赖/入口文件到忽略的缓存。namespace 仅用于测试，绕过完整集成初始化，不修改源码。只读查询测试执行原版工具参数和方法；网络、天气和 Recorder 数据获取被模拟，单位换算及日期使用原版计算代码。v0.5 当时只盘点计算器和媒体播放入口，未声称其原版调用已测试；后续 v0.6 证据见下节。

新增查询审核集合与默认访问白名单分开。只有用户明确配置的额外组合、启用通用调用、原始有效管理员身份，以及公开 `integration=llm_intents` 才能使用新增审核依据。独立的非只读/破坏性声明优先拒绝只读分类。集合不自动加入配置；默认网页搜索契约保留。

参数目录对普通 Optional 默认值建立不编译的元数据视图，保留 Required、额外键策略、枚举、范围和嵌套约束，省略工厂。调用继续使用未修改的原生 Schema，因此 YouTube 的默认数量 1 和范围 1–25 只在授权参数校验时生效。Required/分组默认值及不支持的结构仍拒绝发现；不会为兼容而放宽约束。`check_tools` 继续只检查 Schema 类型，不做转换。

## EOAIC2 和 YAML 调整

[functions/script.py](https://github.com/outsharked/extended-openai-conversation-2/blob/b0274f752fc01495875522db9281c335af8cf484/custom_components/extended_openai_conversation/functions/script.py) 使用 HA `Script`，以模型参数为 `run_variables`，传递原始 Context，返回运行结果变量 `_function_result`。

执行原版脚本契约测试后，任务书建议的服务动作与 `response_variable: _function_result` 均可运行。有一处兼容调整：

```yaml
# 任务书建议：单字段模板，字符串 "123" 会被 HA 解析为数字。
data:
  query: "{{ query }}"

# 交付版本：整个字典作为模板返回，保留 query 的字符串类型。
data: "{{ {'query': query} }}"
```

契约测试用固定提交的原版 `ScriptFunction`、`Function`、常量和异常文件，通过隔离的 Python namespace 加载这些文件。测试不运行上游完整集成初始化，也不加载其其他函数，更不修改其源码。它验证脚本接线，不验证模型决策、实际聊天、API Key、联网搜索或 TTS。

## 服务生命周期与 HACS

遵循 [HA 服务注册规范](https://developers.home-assistant.io/docs/dev_101_services/)，服务注册放在 `async_setup`；卸载后以配置项状态阻止搜索，保留服务使引用它的脚本仍可编辑。重载不重新注册。

按 [HACS 集成要求](https://www.hacs.xyz/docs/publish/integration/) 提供单一 `custom_components` 集成、Manifest、版本、HACS 元数据、许可证和本地图标。HA 2026.10 支持 [集成目录内的 brand 图片](https://developers.home-assistant.io/docs/creating_integration_file_structure/)。[HACS 不支持私有仓库](https://www.hacs.xyz/docs/faq/private_repositories/)；公开发布和实际 HACS 安装验收须与本地测试区分。

## 2026-10-19：Tools for Assist 1.11.0

核对固定发布提交 `198e37885fe06e6452d2d6e26bc5e532b1686acc`。与原基线相比，旧工具的 18 个实现/公共依赖文件未变；新增 Tavily 搜索类及其配置、常量和映射，原 API 标识、工具名及结果结构保留。桥接运行代码无需调整，新增的 topic/time_range 原生枚举可直接通过既有通用调用。该增量核对时固定搜索仍只接受 query；v0.7 已删除该独立服务，当前搜索 Functions 须按迁移说明改为 call_tool。

本地 17 项新增原版 Tavily 契约与完整 362 项回归通过（0 skipped），HTTP 和缓存模拟；真实联网与用户环境另行验收。原有 20 文件快照保留，另存固定发布的 22 文件快照用于回归。详见 [TOOLS_FOR_ASSIST_1_11_0.md](TOOLS_FOR_ASSIST_1_11_0.md)。


## v0.6：参数描述与原版计算/播放历史依据

用户已明确取消 Home Control API，EOAIC2 继续承担原生 HA 控制。Home Control 的动态工具/脚本、设备上下文和计时器从后续开发与 1.0 门槛移除；保留 v0.5 历史分类与手工配置行为供兼容，不据此新增 Home Control 支持声明。

1.11.0 的四个非 Home Control API 为 SearchAPI、WeatherAPI、BasicUtilitiesAPI、MediaAPI，共 10 个固定工具、13 个实现。测试通过原版 `llm_functions.py` 实例化并核对全部启用工具，不运行 Tools for Assist 的完整集成初始化，不取得或调用 Home Control API。生产桥接仍只用 HA 公开 API，依赖清单不变。

[calculator.py](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/calculator.py) 的 `calculate` 原生参数为 operation 选择器和字符串数组 data；expression 用 SymPy `sympify`，聚合使用 float/min/max/avg。[SymPy 官方说明](https://docs.sympy.org/latest/modules/core.html#sympy.core.sympify.sympify) 指出 sympify 内部使用 eval，不应传入未经处理的输入。桥接在原生 Schema 校验后增加有限数值 AST 检查和复杂度预算，再把未改写的参数交给原版工具；不导入 SymPy 作为生产依赖。开发测试固定 `sympy==1.14.0` 与其 `mpmath==1.3.0` 依赖，仅用于原版计算器运行。具体限制见 [计算器边界](TOOLS_COMPATIBILITY.md#计算器边界)。

[play_media.py](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/play_media.py) 的 `play_video` 根据 HA 状态与实体/设备/区域注册表构造视频播放器动态选择器，实体参数为多选数组；还接受区域和设备标识。MediaAPI 在读取 API 时更新选择器，不能缓存旧枚举。单个适用播放器可自动选择，多个且未指定目标时返回业务错误。原版工具调用 `media_player.play_media`，失败由桥接按副作用未知结果处理，不自动重试。

**上游 Context 限制：**桥接原样把管理员 Context 交给 API/工具；PlayVideoTool 发起下游播放服务时没有传入 context，因此服务端 user_id 为空。原版方法与模拟 HA 服务测试分别验证这两层行为；不能宣称用户身份完整穿透到设备服务。不修改第三方或 HA Core 来补写 Context；真实播放验收需检查该已知行为。

新增 `describe_tool` 允许管理员先读取一个精确授权工具的公开 Schema，即使播放执行许可尚未开启。它沿用严格、受预算的元数据视图，不执行工具、原生参数校验器或默认工厂；转换可调用原生序列化器。`list_tools` 保持只读目录，`check_tools` 保持不执行 Schema/默认值/序列化钩子的类型与状态检查，两者原有契约不变。原版 EOAIC2 ScriptFunction 新增描述、计算与播放接线测试；真实模型、联网和设备验收另计。

## v0.7：统一执行入口与独立高德 API

删除专用 search.py 和服务注册；共享 validate_query 迁至 validation.py，gateway.py 仅更改该导入。list_tools/check_tools/describe_tool/call_tool 及其权限逻辑保留，payload.py 与 v0.6.1 修复提交保持逐字节一致。HA 对旧服务调用报告 ServiceNotFound；启动时也移除可能残留的旧注册，不提供执行回退或自动授权。

高德 API `eoai_tools_bridge_amap` 使用 HA 公开 async_register_api，并在配置项卸载时注销。metadata 返回已创建的原生 Schema，获取 API 不创建 HTTP 会话；就绪检查不调用参数逻辑。原生 APIInstance 的调度本身不验证参数/桥接权限，因此新工具内部再次执行自身的受限原生参数和桥接策略检查，防止原生 API 成为旁路；不改变外部上游工具既有调用机制。

官方接口复核于 2026-10-19：[POI 2.0](https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch)（页面更新 2026-07-15）使用 /v5/place/text 和 /v5/place/around；[地理编码](https://lbs.amap.com/api/webservice/guide/api/georegeo)（页面更新 2026-02-02）使用 /v3/geocode/geo。文档的关键词 80 字符、页大小、城市限制、周边半径/排序、business 字段和缺失字符串数组语义已分别映射到本项目约束。未宣称 Google 与高德字段或位置参考系等价；[具体映射与边界](AMAP.md) 独立维护。

Key 为可选可信配置，不在模型参数中出现；仅固定 HTTPS 端点，无重定向/缓存/重试，单请求 10 秒、原始响应 256 KiB。三端点真实 HTTP 验证与模拟契约分别记入 TESTING；该验证不属于真实 HA/EOAIC2 或物理设备验收。

## v0.7.1：静态独立 Functions 的原生参数核对

以当前已固定的 1.11.0 原版工具公开 Schema 和现有 EOAIC2 ScriptFunction 测试快照核对 12 个工具组合，不修改、引入修改分支或新增上游生产依赖。Bridge Python 文件保持 v0.7.0 原字节，只有发布版本元数据更新。文档提供静态 YAML，不增加生成器。

网页搜索四实现共用同一工具名：Brave Web/SearXNG 只接受 query；Brave LLM Context 另有 freshness 的四项原生枚举；Tavily 另有 topic/time_range。独立 search_web 通过不同互斥示例保留差异，query-only 可用于四家，不用 Schema 并集。路线 mode 省略保留原版配置默认，year 省略保留原版当前本地年份；YouTube num_results=1、高德 limit=5 的 Schema 默认由原工具应用。

原版媒体的 entity_id 选择器为当前设备列表构成的字符串数组枚举，不能在可复制的通用模板中伪造固定值；示例准确保留数组、area 和 device_id，动态取值仍由原生选择器验证。原版 HA 模板环境有同名 device_id() 函数，示例在该可选字段不存在时排除可调用内置对象，避免参数渲染成非字典。完整参数与已知语义见 [Functions 指南](EOAIC2_FUNCTIONS.md)。

## v0.7.2：模型可见描述的行为核对

2026-10-20 重新阅读同一 Tools for Assist 1.11.0 固定快照的所有非 Home Control 工具实现，以及本项目现有 amap/amap_client/calculator/payload；不升级源快照、改动 Schema 或派发逻辑，不修改任何上游/安装文件。描述分工为：工具说明调用时机、限制与结果，参数说明格式、枚举、默认和组合约束。全部 14 份示例除 description 外与 v0.7.1 的结构相同，自动化保存其规范 JSON 的 SHA-256，CI 无需下载旧版或读取 Git 历史。

- [单位换算](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/unit_converter.py)：实际常量支持 9 个体积、6 个重量和 2 个温度英文标识，含原描述漏掉的 dl；只小写化标识，不翻译中文或自动识别复数。amount 是字符串，返回 value 四舍五入到四位小数，不同类别拒绝。
- [维基百科](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/wikipedia.py)：请求与摘要地址固定 en.wikipedia.org，无语言参数；输出 title/summary、不输出 URL。英文查询与用户语言回答是新版 Function 的模型指导，不是新增翻译执行链路。
- [YouTube](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/youtube.py)：num_results 为 1–25 的最大请求数，省略 1，实际可能不足；输出标题、链接、频道、描述、发布时间，搜索不触发播放。根据需求选数量/缺口时补充，是模型指导而非自动重试代码。
- 搜索四实现均把返回项重建为 title/content，包括 [Tavily](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/tavily_search.py)，因此 HTTP 自带 URL 也不会成为独立来源字段。Tavily answer 是配置可选的生成摘要，不是另一来源；Brave LLM Context 的 content 还可能含解析后的对象。现有 query/freshness/topic/time_range 的提供商隔离不变。
- [Google Places](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/google_places.py) 只有 query，无默认城市；配置坐标/radius 构成 locationBias，不是严格城市边界。数量配置默认 2，缺电话/评分有占位文本；高德 city 则传 region/city_limit。高德附近必须有真实 GCJ-02 中心，radius/sort、distance/types 的桥接组合限制维持原值；客户端元数据先于通用裁剪产生。
- [Google Routes](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/google_routes.py)：固定配置起点；先用 Places 解析目的地再查路线。mode 取配置或 DRIVE；时间缺失/无法解析为现在，朴素时间取 HA 时区，过去时间改为当前后 10 秒。结果是嵌套 result 中的格式化距离/时长及可选估算时间，不是任意起点或高德路线。
- [天气](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/weather.py)、[日期](https://github.com/skye-harris/llm_intents/blob/198e37885fe06e6452d2d6e26bc5e532b1686acc/custom_components/llm_intents/date_info.py)、前述计算与媒体实现：天气直接返回可用预报文本；日期为公历日期与英文星期；计算表达式 value 是字符串、聚合是数字且受既有数值限制；播放器自动发现检查 tv/receiver 与 PLAY_MEDIA，成功仅证明服务方法返回，URL 支持和实际播放仍需设备验收。

另核对 [高德 POI 2.0](https://lbs.amap.com/api/webservice/guide/api/newpoisearch) 的城市/坐标说明与 [地理编码](https://lbs.amap.com/api/webservice/guide/api/georegeo) 的 city、经度/纬度和匹配级别说明；只映射本项目已实现参数，未暴露官方接口的其他能力。geocode ambiguous 按原始候选数判断，不代表置信度。高德路线仍在 v0.8.0 单独开发，本次不改 Google get_route 或新增路线能力。

## v0.8.0：高德路线、家庭地址与显式起点

以下接口核对和联网结果为 v0.8.0 的历史记录；v0.8.1 按用户要求删除摩托车及未来驾车，不再暴露或作为验收门槛。当前四种模式和仅公交的未来时间映射见 [AMAP_ROUTES.md](AMAP_ROUTES.md)。

2026-10-20 按既定路线新增本项目自己的 get_route，不修改 Tools for Assist、EOAIC2 或 HA Core。Google 原生起点行为继续由原工具保留；高德使用 Bridge 的可选家庭地址与默认出行方式，显式 origin 优先。起点不是现有附近中心，也不读取上游私有配置或 HA 设备位置。

主要接口依据为 [路径规划 2.0](https://lbs.amap.com/api/webservice/guide/api/newroute)、[公交 v3](https://lbs.amap.com/api/webservice/guide/api/direction)、[未来驾车 ETD](https://lbs.amap.com/api/webservice/guide/api-advanced/advanced-path) 和 [摩托车](https://lbs.amap.com/api/logistic-service/guide/cycling-service/direction-motor)。使用国内 restapi.amap.com 的固定端点，不混用海外服务、SDK 或电动自行车来替代摩托车。具体映射、单位、时间与未实现参数见 [AMAP_ROUTES.md](AMAP_ROUTES.md)。

公交选择已公开支持城市名和出发日期/时间的 v3 接口；按中国时区分钟发送，避免把 v5 citycode 误当 adcode 或混用时间格式。未来驾车走 v4 ETD 单时间点，读取其 errcode 成功状态，验证返回毫秒时间点与请求秒时间戳、路线 pathindex，并将分钟转换为秒。WALK/BICYCLE/TWO_WHEELER 不接受显式出发时间；没有可映射能力时明确失败，不改为当前驾车。

独立公共坐标 HTTP 验证发现 v5 自行车实际返回 path.duration（秒），即使请求 show_fields=cost；实现同时兼容这一形状及文档中的 cost.duration，并分别回归。当前驾车、步行、骑行、公交与未来公交取得有效数值。摩托车和未来驾车被当前 Key 的提供商请求拒绝：仅记录固定类别，不保存原文或归因到具体权限/配额，真实成功未验证。模拟的成功响应只依据接口文档构造，不能代替额外权限端点验收。

地址解析复用既有 geocode 的候选与 GCJ-02 字段，多候选不选第一项；先回传状态/候选供消歧，零结果明确 no_match。一次路线最多两个地址解析与一个路线请求，整个工具限时 20 秒；每次新 HTTP 及返回前重查原始身份、策略和配置快照。元数据不会取得会话、运行校验器或检测 Key/接口权限。通用网关、四服务、v0.6.1 payload、计算器及上游源快照未变；独立静态示例新增一份并继续使用原版 ScriptFunction 验证。

## 2026-10-29：v0.8.2 正式上游兼容

Tools for Assist 1.11.1 固定到 5d2e76d72564fe378f32870bd311ca9460956281，主分支另一个 README 拼写提交已核对，没有运行增量。保留旧基线与 1.11.0，并对两个发布版分别运行原版契约。计算器改为 AST/执行器、播放新增 Assist 暴露过滤并移除 device_id；SearXNG 参数编码与内存缓存变化由原生实现处理，Bridge 不复制其执行代码。静态计算器/播放示例及共同表达式边界同步适配，原始管理员与权限、四服务和 payload 不变。

HA 最新正式版 2026.10.4 固定到 357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b，匹配测试插件 0.13.375。14 个相关固定源码比对中，13 个公开契约相关文件一致，只有 aiohttp_client 增加 64 KiB 响应头上限。依赖锁定只升级项目版本、HA、匹配测试插件及 HA 要求的 uv；旧测试和验收保留原版本。完整逐项来源、迁移和验证限制见 [1.11.1 记录](TOOLS_FOR_ASSIST_1_11_1.md)。
