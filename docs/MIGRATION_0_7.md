# v0.7.x 升级与接口迁移

v0.7.0 基于 v0.6.1，**删除独立 `eoai_tools_bridge.search_web` 服务**。Tools for Assist 的 `llm_intents/search_web` 工具继续支持；所有执行经 `eoai_tools_bridge.call_tool`。`list_tools`、`check_tools`、`describe_tool` 和 `call_tool` 保留既有契约与安全限制，v0.6.1 的通用结果裁剪不变。没有旧服务别名、自动授权或身份回退。

## 更新步骤

1. 备份现有桥接选项和 EOAIC2 Functions。通过 HACS 更新，或从 Release 替换桥接自己的集成目录，然后**重启 HA**。无需删除/重建配置项；只重载集成不等于更新 Python 代码。
2. 原有通用调用白名单、开关及副作用许可保持原值。此前只用固定搜索、尚未设置通用调用的安装仍保持关闭。在桥接选项中明确启用 `call_tool`，加入 `llm_intents/search_web`，无需为搜索开启副作用许可。
3. 确保调用链保留**原始有效管理员 Context**。无 `user_id` 的语音/自动化、普通用户、未知或停用用户不能搜索；不能填入管理员 ID、伪造 Context 或绕过身份检查来迁移。
4. 将自动化、脚本、开发者动作和 Functions 中的旧搜索调用改用下面的统一入口；所有调用须接收响应。v0.7.1 推荐模型端直接使用 `search_web`，删除旧 `web_search`，避免两者重复；各工具采用独立 Function。
5. 把旧的顶层 `results` 读取改为 **`result.results`**，并先检查 `success`。失败时 `result=null`；上游某些后端无结果时可能返回 `result.results="No results found"`，不再使用专用搜索规范化器转换为空数组。
6. 核对四个服务可用、旧服务不存在；先用原始管理员执行搜索，再检查无身份/非管理员被拒绝。实际 HACS/HA/EOAIC2 升级验收另记，不能由本地契约测试代替。

## 新调用

```yaml
action: eoai_tools_bridge.call_tool
data:
  api_id: llm_intents
  tool_name: search_web
  tool_args:
    query: 今天的 AI 新闻
response_variable: search_response
```

入参 `query` 移入 `tool_args`，仍要求去首尾空白后 1–500 个有效 Unicode 字符。原生 Schema 校验、审核只读分类、精确白名单和可选 `freshness` / `topic` / `time_range` 保留；仅传实际提供商支持的参数。

EOAIC2 推荐采用 [独立 search_web](../examples/eoaic2_search_web.yaml)，或按提供商选 [Brave LLM Context](../examples/eoaic2_search_web_brave_llm_context.yaml) / [Tavily](../examples/eoaic2_search_web_tavily.yaml) 完整版本，只选一份。各工具均有 [独立 Functions](EOAIC2_FUNCTIONS.md)，模型只填写原生参数；[call_allowed_tool](../examples/eoaic2_call_tool.yaml) 降为可选高级方案。v0.7.0 的 `examples/eoaic2_web_search.yaml`（模型名 web_search）现已删除；更早的专用搜索示例也已删除。先删除/替换旧 Function，再追加选中的完整列表项，不要保留 web_search 与 search_web 两个入口。保留原生 HA 控制 Functions。整体 data 模板保持字符串、整数及数组，不把字符串样式参数转为数值或再次解析模板。

## 响应与失败

| 项目 | v0.7.0 行为 |
| --- | --- |
| 返回正文 | `result` 包含上游通用 JSON，搜索项通常在 `result.results` |
| 失败 | `success=false`、`result=null` 及现有固定 `error_code/error` |
| 内容裁剪 | 沿用 v0.6.1，递归缩减嵌套项/文本并保留有效数据，完整 JSON ≤16 KiB |
| 空对象 | 不以 `{}` 冒充成功，空顶层对象返回 `invalid_response` |
| 合法空值 | 空数组、零和布尔值保持有效 |
| 旧服务调用 | HA 报服务不存在，不会降级到另一条执行链路 |

旧专用搜索结果可能带有 URL 归一化等行为；迁移后遵循既有通用正文契约，不保证所有提供商有相同字段。仅引用提供商实际返回的来源链接，不编造 URL 或省略内容。

## 高德工具迁移独立授权

新高德工具为 `eoai_tools_bridge_amap/find_places`、`eoai_tools_bridge_amap/geocode`；Key 填桥接选项的密码框。现有 `llm_intents/find_places` 和 `llm_intents/get_route` 仍为上游 Google 工具，不会静默切换数据源。高德地点迁移需改用新身份、明确加入白名单，并按 [高德参数与字段说明](AMAP.md) 调整参数；v0.7 尚无高德路线工具。

## 从 v0.7.0 更新至 v0.7.1

本次为文档/示例补丁；除发布版本号元数据外，Bridge 运行文件和依赖不变。HACS 更新仍独立进行，Functions 是用户在 EOAIC2 中保存的配置，**不会随着 HACS 下载自动替换**。按完整指南选择工具、复制 YAML，并更新各自精确白名单即可，无需 EOAIC2 修改版、任何分支或 YAML 生成器。

- 搜索 Function 统一改名 `search_web`，删除旧 `web_search`；三个搜索示例只选一份，不能向不支持的提供商发送 freshness/topic/time_range。
- Google 与高德 `find_places` 保持相同模型名，**只启用一个**；Functions 和白名单均只保留所选 API/工具组合。迁移时由管理员明确更改身份与配置，不自动切换供应商。
- 可选参数未提供时省略，保留 YouTube num_results=1、高德 limit=5、原生配置路线 mode/城市/中心及当前年份等默认语义。不传空字符串、null 或伪造固定年份充当省略。
- 播放 entity_id 为字符串数组，area 是区域名/ID，device_id 是设备 ID；实际 entity_id 枚举由 HA 动态产生，参考当前 describe_tool，不在通用 YAML 中写虚假设备。仍需副作用许可，失败后 outcome_unknown 语义不变。
- 配置建议的互斥选择属于 Functions 管理约定，不新增 Bridge 的提供商切换或冲突检查运行逻辑。原有网关、管理员与副作用授权逐次检查仍负责执行边界。

## 从 v0.7.1 更新至 v0.7.2

这是模型可见描述补丁：14 份独立 YAML（12 个工具组合与两个搜索参数变体）只修改 spec.description 及各参数 description。身份、名称、Schema 的类型/枚举/必填/默认值、整体 data 模板、执行序列、返回格式、白名单、原始管理员和副作用许可均保持 v0.7.1 原值；无需配置迁移、修改全局提示词或上游源码。

通过 HACS/Release 更新 Bridge 后，到 EOAIC2 Functions **替换已有的所选完整 YAML 列表项**。HACS 不自动改写这些配置；不要在旧列表后重复追加同名 Function。仍只选一份 search_web 和一份 Google/高德 find_places，不因优化描述改换提供商、添加参数或扩大白名单。仍使用高级 call_allowed_tool 的用户不会自动获得这些独立工具描述，可按需选择独立方案。

新版说明覆盖英文单位/英文维基词条、YouTube 数量和补充查询、来源链接缺失、地图候选/真实坐标、路线和天气估算范围、计算数值与日期结果、播放器兼容性。建议用原本出现问题的对话重新验收；没有实质信息缺口时不要求模型反复搜索，返回成功也不等于有匹配数据或设备已播放。完整差异见 [Functions 指南](EOAIC2_FUNCTIONS.md#调用与结果解读)。高德路线不在本补丁中，按规划留到 v0.8.0。

## 从 v0.7.2 更新至 v0.8.0

既有四个服务、白名单/管理员与副作用许可、v0.6.1 裁剪、Google get_route 和其他上游工具继续保留。新增高德 get_route 需要手动选择 [高德路线 Function](../examples/eoaic2_get_route_amap.yaml)，删除/替换同名 Google Function，并在精确白名单选择 eoai_tools_bridge_amap/get_route；不自动改提供商或复制 Google 的家庭地址配置。

在 Bridge 选项设置可选家庭地址及默认出行方式。origin 省略时用该地址，显式 origin 优先；家庭地址空缺时必须提供起点，不复用附近中心或 HA 设备位置。更新无需重建配置项，已有权限/选项仍保持原值，新增工具不会自动获权。HACS 仍只更新 Bridge，Functions 手工替换且不能重复同名。

高德时间严格校验，不能套用 Google 无效/过去时间的回退行为；返回也需改为先看 result.status、ok 时读 result.route，而非 Google 的 result.result。多候选须消歧、公交坐标须有城市，失败不降级。当前支持范围以 [高德路线说明](AMAP_ROUTES.md) 为准，v0.8.0 的原始范围与测试保留在历史记录中。

## 从 v0.8.0 更新至 v0.8.1

高德路线删除 TWO_WHEELER 摩托车及 DRIVE + departure_time 未来驾车的实际接口、解析和配置选项；仅保留即时 DRIVE、WALK、BICYCLE、TRANSIT，以及 TRANSIT + departure_time。旧版保存的 TWO_WHEELER 默认模式在集成加载时自动改为 DRIVE，只更新该项，家庭地址、附近中心、Key、默认城市、白名单、网关及副作用许可原样保留，无需重建配置项。

更新并重新加载/重启后，手动替换已保存的 [高德路线 YAML](../examples/eoaic2_get_route_amap.yaml)，不要重复追加同名 get_route；HACS 不自动改写 Functions。模型或旧脚本显式传入 TWO_WHEELER 会被参数校验拒绝，非公交传入 departure_time 也失败且不发 HTTP，不会忽略时间退回即时路线。需要驾车时省略时间；需要未来公交时使用 TRANSIT。Google get_route、其他工具、四服务及既有权限/返回格式保持不变。
