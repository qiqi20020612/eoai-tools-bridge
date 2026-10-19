# EOAIC2 Tools Bridge

让 EOAIC2 通过 Home Assistant 公开 LLM API 使用 Tools for Assist 的搜索、天气、地点/路线、计算器、实用工具和媒体播放，并提供独立的高德地点、地址解析与路线工具。当前版本 **v0.8.0**，HA 自动化测试基准 **2026.10.2**，Tools for Assist 固定核对版本 **1.11.0**。

**v0.7.0 接口变更：独立的 `eoai_tools_bridge.search_web` 已移除，所有工具统一经 `call_tool` 执行。** Tools for Assist 的 `llm_intents/search_web` 继续支持。升级须替换旧搜索动作/Functions、明确授权搜索并改读 `result.results`，详见 [迁移说明](docs/MIGRATION_0_7.md)。既有白名单及副作用许可不会自动扩大。

本集成独立安装更新，不修改 EOAIC2、Tools for Assist、HA Core 或它们的安装文件。Home Control 由 EOAIC2 原生 HA 控制承担，不属于本项目范围。

## 安装与授权

1. 在 HACS 自定义仓库中添加 `qiqi20020612/eoai-tools-bridge`，类别选择 Integration，下载后重启 HA。也可从 [Releases](https://github.com/qiqi20020612/eoai-tools-bridge/releases) 下载 ZIP，将其中的 `custom_components/eoai_tools_bridge` 放入 HA 的 `config/custom_components/`，然后重启。
2. 在「设置 → 设备与服务 → 添加集成」添加 **EOAIC2 Tools Bridge**。安装不需要密钥，可先于 Tools for Assist 完成。
3. 使用上游工具时，另外安装配置 [Tools for Assist](https://github.com/skye-harris/llm_intents)。搜索支持 Brave、Brave LLM Context、Tavily 和 SearXNG；搜索 Key、提供商等仍由上游管理。
4. 打开桥接的「选项」，启用 `call_tool`，按需填写精确白名单，每行一项，最多 32 项，不支持通配符、URL 或模板。例如：

```text
llm_intents/search_web
eoai_tools_bridge_amap/find_places
eoai_tools_bridge_amap/geocode
```

**所有执行（包括搜索）均要求原始 Context 中存在 HA 认证存储里的有效管理员用户。** 缺失 `user_id`、普通/未知/停用用户会被拒绝，桥接不会补造身份。语音、定时自动化若没有管理员 Context，也不能执行工具。只读分类不授予访问权限；播放、写入或没有只读依据的工具还须单独开启副作用许可。保存选项立即生效，旧安装没有选项时仍默认关闭。

## 四个服务

所有服务仅返回响应，脚本/自动化须设置 `response_variable`，开发者动作须请求响应。

| 服务 | 用途 | 授权边界 |
| --- | --- | --- |
| `eoai_tools_bridge.list_tools` | 只读目录和公开参数；不执行工具、参数校验器或默认工厂 | 默认只发现上游搜索；管理员可发现明确授权的额外只读工具 |
| `eoai_tools_bridge.check_tools` | 无入参的配置工具状态与 Schema 类型检查 | 原始有效管理员；不执行工具、参数 Schema、默认工厂或序列化钩子 |
| `eoai_tools_bridge.describe_tool` | 查看一个已授权工具的公开参数，含动态播放选择器 | 原始有效管理员；无需先允许副作用；不执行工具或默认工厂 |
| `eoai_tools_bridge.call_tool` | 原生参数验证后执行一次 | 开关、精确白名单、原始有效管理员及必要的副作用许可 |

`check_tools` 的 `ready` 只表示类型/权限状态，不能证明密钥、网络、配额、参数值或设备正常。目录与参数描述采用 HA 的元数据转换接口；描述和返回正文均是不可信数据，不能扩大权限。元数据不会返回 API prompt、私有配置、Key、参数默认值或示例。上游参数描述可能调用其原生序列化器，与不执行该钩子的就绪检查有别。

## 推荐：每个工具独立的 EOAIC2 Function

推荐按需复制下面每个完整 YAML 列表项到 EOAIC2 的 **Functions**；模型直接看到 `search_web`、`calculate` 等工具名及各自原生参数。全部为 `type: script`，底层仍统一调用 `eoai_tools_bridge.call_tool`，脚本固定 API 与工具名，模型无需填写 `api_id/tool_name/tool_args`。v0.8.0 在既有描述与调用契约上新增高德路线，不改变 Google 路线或其他已有工具的参数/脚本，不新增生产依赖。

描述现已明确英文单位标识与字符串数量、英文维基百科、按需求选择 YouTube 条数、搜索链接缺失及补充查询条件、两种地图的位置/字段差异、地址候选消歧、固定起点的 Google 路线估算、天气覆盖和播放兼容性。详见 [逐工具调用与结果说明](docs/EOAIC2_FUNCTIONS.md#调用与结果解读)。**HACS 更新不会替换已保存的 Functions**；从 v0.7.1 升级后，手动替换所选 YAML 列表项才能使用新描述，不需要修改全局提示词。

**先做选择：**删除旧的 `web_search` Function，使用新的 **`search_web`**，三种搜索示例只选一份。**Google/高德的 find_places 二选一，get_route 也二选一**；Functions 和桥接白名单保留所选身份，不自动切换。当前覆盖 13 个 API/工具组合（共 15 份 YAML，含搜索变体），因地点和路线各有一组同名互斥，一次最多启用 11 个独立执行 Function。原生 HA 控制 Functions 保留。

| 工具 | 固定 API/工具组合 | 独立 YAML |
| --- | --- | --- |
| 网页搜索 `search_web` | `llm_intents/search_web` | [通用 query 版](examples/eoaic2_search_web.yaml) · [Brave LLM Context 版](examples/eoaic2_search_web_brave_llm_context.yaml) · [Tavily 版](examples/eoaic2_search_web_tavily.yaml)，三选一 |
| Google `find_places` | `llm_intents/find_places` | [Google 地点](examples/eoaic2_find_places_google.yaml)，与高德地点二选一 |
| Google `get_route` | `llm_intents/get_route` | [Google 路线](examples/eoaic2_get_route.yaml)，与高德路线二选一 |
| `search_wikipedia` | `llm_intents/search_wikipedia` | [维基百科](examples/eoaic2_search_wikipedia.yaml) |
| `search_youtube` | `llm_intents/search_youtube` | [YouTube 搜索](examples/eoaic2_search_youtube.yaml) |
| `get_weather_forecast` | `weather_forecast/get_weather_forecast` | [天气](examples/eoaic2_get_weather_forecast.yaml) |
| `unit_convert` | `basic_utilities/unit_convert` | [单位换算](examples/eoaic2_unit_convert.yaml) |
| `calendar_day_info` | `basic_utilities/calendar_day_info` | [日期](examples/eoaic2_calendar_day_info.yaml) |
| `calculate` | `basic_utilities/calculate` | [计算器](examples/eoaic2_calculate.yaml) |
| `play_video` | `media_services/play_video` | [视频播放](examples/eoaic2_play_video.yaml)，另需副作用许可 |
| 高德 `find_places` | `eoai_tools_bridge_amap/find_places` | [高德地点](examples/eoaic2_find_places_amap.yaml)，与 Google 地点二选一 |
| `geocode` | `eoai_tools_bridge_amap/geocode` | [高德地址解析](examples/eoaic2_geocode.yaml) |
| 高德 `get_route` | `eoai_tools_bridge_amap/get_route` | [高德路线](examples/eoaic2_get_route_amap.yaml)，与 Google 路线二选一 |

[完整 Functions 指南](docs/EOAIC2_FUNCTIONS.md) 包含以上所有可复制代码块、参数表、默认值与类型说明。网页搜索必须按实际提供商选择：

| Tools for Assist 提供商 | 模型可见参数 | 示例选择 |
| --- | --- | --- |
| Brave Web Search / SearXNG | 必填 `query`，没有搜索筛选参数 | 通用 query 版 |
| Brave LLM Context | 必填 `query`，可选 `freshness=Today/This Week/This Month/This Year` | Brave LLM Context 版，或只需 query 时使用通用版 |
| Tavily（1.11.0） | 必填 `query`，可选 `topic=general/news/finance`、`time_range=day/week/month/year` | Tavily 版，或只需 query 时使用通用版 |

不要合并这些筛选参数或传空值来表示省略；切换提供商时替换 Function 的 Schema 与模板，不同时保留多个 `search_web`。最简单的完整搜索 Function 如下：

```yaml
- spec:
    name: search_web
    description: >-
      Look up current or external facts not covered by the available evidence,
      using the configured Tools for Assist provider. This query-only Function
      works with Brave Web Search, SearXNG, Brave LLM Context or Tavily; optional
      provider filters are not exposed here. result.results contains titles and
      snippets, not full pages; 'No results found' means no matches. The current
      upstream implementations omit source URL fields. Base claims on returned
      text and cite only links actually present; never invent citations. Do not
      repeat a search just to obtain missing links; refine it for a material gap.
    parameters:
      type: object
      properties:
        query:
          type: string
          minLength: 1
          maxLength: 500
          description: >-
            Required focused search string, 1-500 valid Unicode characters after
            trimming; include the subject and any needed date or location context.
            No default; this variant accepts only query.
      required: [query]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: "{{ {'api_id': 'llm_intents', 'tool_name': 'search_web', 'tool_args': {'query': query}} }}"
        response_variable: _function_result
```

所有示例使用整体 `data` 模板，保持 `"123"` 等字符串、整数和数组的原类型；可选字段只有提供时才透传，上游负责应用默认值，不在模板中强制转换或填 `null`。播放的 `device_id` 同名 HA 模板函数已排除，省略目标时不会把函数对象当成设备 ID。具体限制及动态播放器枚举见指南。

[call_allowed_tool](examples/eoaic2_call_tool.yaml) 仅为**可选高级方案**，适用于需要动态选择受信任工具身份的场景；普通使用直接选择上述独立 Function，不需要经它嵌套调用。可选增加 [只读目录](examples/eoaic2_list_tools.yaml)、[就绪检查](examples/eoaic2_check_tools.yaml) 和 [参数描述](examples/eoaic2_describe_tool.yaml)。手动配置独立 Functions 不改变 HACS 独立更新、白名单、原始管理员 Context 或副作用许可，集成不会自动注入/改写 EOAIC2。

## 高德地点与位置解析

在桥接选项中填写自己的 **高德 Web 服务 API Key**（密码输入框），可选默认城市及附近中心。Key 由 HA 配置存储管理，不是文件级加密；不要放入 Functions、工具参数、版本库或发布包。没有 Key 不影响既有上游工具。只填 Key 不会启用网关或加入白名单。

高德 API 为 **`eoai_tools_bridge_amap`**，包含只读 `find_places`、`geocode` 与下文的 `get_route`。它们使用同一发现/检查/调用链路，均要求原始管理员与精确授权；直接选用原生 LLM API 也不能绕过桥接权限。

- `find_places`：`query` 必填（去空白后 1–80 字符）；可选 `city/location/radius/sort/types/limit`。未提供位置且无配置中心时按关键词查询；显式或配置中心则查询附近地点。坐标为 **GCJ-02 经度,纬度**，小数最多 6 位，不自动读取 HA 家庭/设备位置，也不猜测转换 WGS84/BD-09。城市用于严格限制检索范围。默认半径 5000 米、综合排序、前 5 项；最多 20 项，仅取第一页。
- `radius`（1–50000 米）和 `sort` 要求位置；`sort=distance` 还必须给 `types`（1–10 个六位 POI 类型码，以 `|` 分隔），因为高德仅关键词查询的距离排序不生效。参数组合不满足时拒绝请求，不静默改换语义。
- `geocode`：`address` 必填（1–500 字符），可选 `city`，继承配置城市。返回最多 5 个地址候选、坐标、匹配级别及 `ambiguous`；多候选须消歧，不能自动把首条当作目的地。返回坐标与附近查询采用相同顺序和参考系。
- 地点/地址解析结果包含 `source=amap`、`coordinate_system=GCJ-02` 及 `results`。名称/地址/坐标、电话、营业时间和评分仅在高德实际提供时保留，不计算“现在营业”，不承诺与 Google 字段或评分等价。合法空结果为 `results=[]`。

可直接使用 [高德动作示例](examples/amap_actions.yaml)。详细字段映射、错误与边界见 [高德说明](docs/AMAP.md)。上游 `llm_intents/find_places`、`llm_intents/get_route` 仍代表原 Google 工具，不会自动改为高德；迁移须更改身份与白名单。

## 高德路线：默认家庭地址或显式起点

v0.8.0 新增 `eoai_tools_bridge_amap/get_route`。在 Bridge 选项中可填**高德家庭地址**（或可信 GCJ-02 坐标）和**默认出行方式**。调用时 destination 必填；**省略 origin 用此家庭地址，显式 origin 覆盖它**，没有配置家庭地址也可通过 origin 查询两地之间的路线。家庭地址与附近搜索中心独立，不读取 Google 配置或 HA 实时位置。

- 支持驾车、步行、自行车、公交与摩托车的独立接口；地址先用高德解析，多候选时返回候选供消歧，不取第一项继续算路。
- 仅 DRIVE/TRANSIT 接受带明确时区、未来 7 天内的 departure_time；其他模式、历史/无效时间拒绝，不替换为当前路线。未来驾车及摩托车接口需要额外提供商权限，本次测试 Key 的请求被提供商拒绝，不降级为其他方式。
- 先判断顶层 success，再读 result.status；只有 ok 才有 result.route。距离/耗时为米/秒，并含可读文本；无匹配、缺公交城市、候选歧义或无路线不会编造零耗时。20 秒总预算内每次新 HTTP 前重查权限/配置，不重试或缓存。

按 [路线配置与迁移说明](docs/AMAP_ROUTES.md) 添加精确白名单并替换同名 Function；HACS 不会自动更新已保存的 Functions。公共坐标的驾车/步行/骑行/公交及未来公交已独立联网成功，真实 HA/模型/升级与额外权限端点的成功验收分开记录。

## 通用调用、安全与结果

入参 `api_id/tool_name/tool_args` 保持原契约。`tool_args` 为最多 **8 KiB** 的受限 JSON 对象；授权后才运行工具原生 probatio Schema 及其默认工厂，保留原生类型和枚举，不猜测工具名。API 获取和参数校验后再次检查身份、权限和工具定义。上游搜索的 `query` 仍严格验证为去空白后 1–500 字符的有效 Unicode 字符串。受信任的上游校验器/工具会执行自己的代码，桥接不是 Python 沙箱。

响应结构保持 v0.6.1 通用接口：

```json
{
  "success": true,
  "api_id": "llm_intents",
  "tool_name": "search_web",
  "result": {"results": [{"title": "示例", "content": "提供商正文"}]},
  "error_code": null,
  "error": null,
  "truncated": false,
  "outcome_unknown": false
}
```

`result` 保留上游通用 JSON 结构，某些搜索后端的无结果响应仍是 `{"results":"No results found"}`。失败时 `result=null`，返回固定错误，不能以空对象冒充成功。已知指令、请求头和凭据字段会被过滤，正文中的不可信指令仍须忽略。

v0.6.1 的裁剪逻辑保持原样：每段文本最多 2048 字符、每个容器前 32 项，深度/节点有界，完整 UTF-8 JSON（含转义）最多 **16 KiB**。超限优先递归裁剪嵌套数组尾项与文本，必要时删嵌套字段，保留顶层字段及有效数据。发生裁剪时 `truncated=true`，不据此推断被省略内容。空顶层对象、过滤后空对象或无法保留有效负载时返回 `invalid_response`；合法空数组、零与布尔值有效。

| 常见错误 | 处理方法 |
| --- | --- |
| `bridge_not_loaded` / `gateway_disabled` | 添加/启用集成，并在选项中明确启用调用 |
| `tool_not_allowed` / `permission_denied` | 核对精确白名单和原始有效管理员 Context |
| `api_unavailable` / `tool_unavailable` | 核对相应集成/API/工具是否启用 |
| `invalid_schema` / `invalid_args` | 重新读取参数描述，遵守原生 Schema 和桥接限制 |
| `side_effects_blocked` | 仅在确实要授权时为该白名单工具打开副作用许可 |
| `api_failed` / `upstream_error` / `call_failed` / `timeout` | 检查对应提供商或设备，勿自动重试可能的副作用 |
| `policy_changed` / `tool_changed` | 权限或工具已变化，重新检查后再决定调用 |
| `invalid_response` | 上游未返回可用 JSON，不能按成功回答 |

每次调用最多调度一次，整体异步超时 20 秒；`outcome_unknown=true` 表示副作用可能已发生，先核对实际状态，不自动重试。桥接不记录查询、完整正文、Key 或原始异常文本。HA 自身的 LLM trace 会记录工具名和调用参数，因此不能把 Key 放入参数。

## 计算器、媒体与兼容边界

当前非 Home Control 的上游清单为 4 个 API、10 个固定工具名、13 个实现，详见 [兼容清单及 1.0 门槛](docs/TOOLS_COMPATIBILITY.md)。只读审核与访问白名单分开；明确危险声明优先拒绝只读分类，旧 Home Control 历史分类仅保留兼容，不列入新支持承诺。

`basic_utilities/calculate` 继续使用原版计算器；桥接在派发前限制数值表达式语法、长度、节点、深度、中间数值与幂指数。目录/描述包含 `bridge_constraints`，详见兼容清单。不能把任意 SymPy/Python 代码当作表达式。生产集成无 SymPy 依赖。

`media_services/play_video` 继续要求副作用许可、上游启用 YouTube 及适用视频播放器；先用 `describe_tool` 读取当前动态参数，再选择实体/区域/设备。上游未把用户 Context 传给下游 HA 播放服务的已知限制保留，不能宣称身份贯穿下游。示例：[查询](examples/query_tools_actions.yaml)、[计算器](examples/calculator_action.yaml)、[播放](examples/play_video_action.yaml)。

## 开发与验证

```sh
uv sync --locked --group dev --python 3.14
uv run --no-sync python scripts/fetch_test_upstream.py
uv run --no-sync python scripts/fetch_tools_upstream.py
uv run --no-sync ruff check custom_components tests scripts
uv run --no-sync ruff format --check custom_components tests scripts
uv run --no-sync pytest -q --timeout=30
uv run --no-sync python scripts/build_release.py
```

开发/CI 固定 HA Core 2026.10.2、配套测试插件 0.13.373。测试下载并校验固定 SHA-256 的 EOAIC2 4 个文件与 Tools for Assist 两套 20/22 个文件，仅在忽略缓存中使用，不打包。pytest 禁止网络，使用真实 HA 注册/认证/Schema/Script 及未修改的原版工具代码，提供商与设备使用模拟后端。源码依据见 [UPSTREAM.md](docs/UPSTREAM.md)。

用户报告 v0.7.2 总体验收通过，未补写逐项提供商或物理设备证据。各版本自动化、独立高德 HTTP 验证与真实用户环境验收分开记录在 [TESTING.md](docs/TESTING.md)。v0.8.0 交付高德路线，后续真实联调、额外接口权限和未完成门槛继续按既定 0.x 路线推进，不直接跳至 1.0。

[版本记录](docs/CHANGELOG.md) · [v0.7 迁移](docs/MIGRATION_0_7.md) · [许可](LICENSE)
