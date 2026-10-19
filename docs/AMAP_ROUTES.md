# 高德路线查询（v0.8.1）

新工具为 **`eoai_tools_bridge_amap/get_route`**，与原 Google `llm_intents/get_route` 保持独立身份。通过现有 `call_tool` 执行，只读但仍要求精确白名单、网关开启和原始有效管理员 Context；不会自动授权、读上游私有配置或接管原 Google 工具。

## 家庭地址与显式起点

在 Bridge 选项配置 `amap_home_address`（高德家庭地址或已经是 GCJ-02 的经度,纬度）及 `amap_route_mode`（默认出行方式，初始 DRIVE）。家庭地址可选：

- **省略 origin**：使用此配置的家庭地址；没有配置则失败，要求提供 origin 或设置家庭地址。
- **提供 origin**：模型传入的明确起点覆盖家庭地址；即使没有配置家庭地址也可查询任意两个已知地点之间的路线。
- `amap_location` 仍只是附近地点搜索中心，不会成为路线家庭地址。不会读取 HA 家庭坐标、设备/人员实时位置，也不会把 Google 坐标自动转换为 GCJ-02。

家庭地址可填与 Tools for Assist 相同的实际地址，但这是 Bridge 自己的配置，不自动读取/迁移 Google Routes 的设置。保存/清空家庭地址、调整默认出行方式均不改变已有白名单、网关和副作用许可。旧配置项版本仍为 1，无需删除重建；新增工具必须另行明确授权。

v0.8.1 删除高德摩托车及未来驾车功能。旧版保存的 TWO_WHEELER 默认模式在加载时仅改为 DRIVE，家庭地址、附近中心、Key、城市和全部权限原样保留。显式 mode=TWO_WHEELER 或非 TRANSIT 的 departure_time 会失败，不发送 HTTP。升级后手动替换高德路线 YAML；Google 工具及其参数行为不变。

```text
eoai_tools_bridge_amap/get_route
```

模型 Function 仍名为 `get_route`；[高德 YAML](../examples/eoaic2_get_route_amap.yaml) 与 [Google YAML](../examples/eoaic2_get_route.yaml) **二选一**，Functions 和精确白名单保留所选身份，禁止同时追加同名定义。不自动切换提供商。地点 find_places 的 Google/高德选择独立进行；13 个工具组合减去两组同名互斥，最多仍为 11 个独立执行 Function。

## 参数

| 参数 | 格式及默认 |
| --- | --- |
| destination | 必填，去首尾空白后 1–500 个有效 Unicode 字符：地址/地标名，或可信 GCJ-02 `经度,纬度` |
| origin | 可选，同 destination 格式；省略用已配置家庭地址，显式值优先。空值/null/“这里、我家、home”等相对词不等于省略 |
| mode | 可选，DRIVE/WALK/BICYCLE/TRANSIT；省略用 Bridge 配置，未配则 DRIVE，不写死覆盖用户配置 |
| departure_time | 可选，带明确时区的 ISO 8601 出发时间，必须在当前之后、7 天以内；仅 TRANSIT 支持。省略即当前出发；不接受历史时间、无时区或无效文本 |
| origin_city | 可选，1–80 字符的起点城市名/citycode，用于地址解析提示；未给时继承 Bridge 默认城市。TRANSIT 需要解析得到的城市或明确提示值 |
| destination_city | 可选，目的地城市名/citycode，格式/默认同上；跨城时单独指定，不能猜为起点城市 |

GCJ-02 坐标必须经度在前、英文逗号分隔、内部无空格、小数最多 6 位，经度范围 ±180、纬度 ±90。不猜测或隐式转换 WGS84、BD-09。地址用现有高德 geocode 解析；含糊的名字可能得到行政区级结果，不能因为只有一个候选就保证具体建筑或入口准确。

同一调用最多解析两个地址再请求一次路线；坐标端点不多做地址解析。可直接将经过用户确认的 geocode 候选 location.longitude/location.latitude 按顺序拼成坐标使用。地址多候选或无匹配时停止，不取第一项继续算路，也不改用 Google。

公交使用 v3 接口的城市名或 3–4 位 citycode，支持分别传起终城市；不能把 6 位 adcode 当作公交 citycode。地址结果中的城市优先于解析提示；坐标缺少必要城市时返回 city_required，不调用逆地理编码猜城市。

端点中的 city 仅来自地址解析结果；city_hint 表示参数或配置提供的提示，不能当作对坐标所属城市的反向核实。

## 出行方式与时间映射

当前实现使用 [高德路径规划 2.0](https://lbs.amap.com/api/webservice/guide/api/newroute) 和 [公交 v3](https://lbs.amap.com/api/webservice/guide/api/direction)，映射如下：

| 模型 mode/时间 | 实际固定端点 | 说明 |
| --- | --- | --- |
| DRIVE，当前出发 | /v5/direction/driving | 推荐策略 32，show_fields=cost，使用服务返回耗时；传 departure_time 明确失败 |
| WALK | /v5/direction/walking | 无指定时间能力；传 departure_time 明确失败 |
| BICYCLE | /v5/direction/bicycling | 无指定时间能力；兼容真实 path.duration 和文档 cost.duration 结构 |
| TRANSIT，当前/未来 | /v3/direction/transit/integrated | 分别传 city/cityd；指定时间转换为 Asia/Shanghai 日期和小时:分钟，7 天为本桥接限制 |

Google 的 mode 名称保留方便理解，但每种语义按高德实际接口处理，不能认为提供商能力完全等价。未实现电动车、途经点、任意策略、实时定位或导航逐步指令。参数/接口错误、无权限、配额和网络失败不会触发另一提供商、模式或时间的回退。

与 Google 不同，高德无效、无时区或过去的显式时间会失败，不能悄悄变成“现在”；即刻出发应省略该字段。指定时间仅限公交，精确到整分钟；返回的 departure_time 是实际用于请求的 UTC ISO 时间，estimated_arrival 也是带 UTC 偏移的估算值。公交时间按中国时区发给接口，与用户所在 HA 时区无关。超时或等待地址解析导致已过出发时间时也会拒绝。

## 返回语义

仍使用通用服务原有信封：先检查顶层 success，失败时 result=null；成功后检查 `result.status`，不能只凭 success 宣称有路线。

| result.status | 含义 |
| --- | --- |
| ok | result.route 包含首条路线估算；origin/destination 含实际使用的地址/坐标信息 |
| needs_clarification | 地址存在多候选；endpoint 指明 origin/destination，candidates 最多 5 项。用户确认后使用明确地址/坐标重新调用 |
| no_match | 指定端点地址没有匹配；route=null，修正地址而非宣称路线不存在 |
| city_required | 公交端点缺少可用城市；route=null，补充对应城市参数 |
| no_route | 服务有效返回无路线；route=null，不生成零距离/零耗时 |

ok 示例正文（外层仍为原 call_tool 信封）：

```json
{
  "source": "amap",
  "coordinate_system": "GCJ-02",
  "status": "ok",
  "origin_source": "argument",
  "travel_mode": "DRIVE",
  "route": {
    "distance_meters": 4264,
    "duration_seconds": 805,
    "distance": "4.3 km",
    "duration": "13 min 25 sec"
  },
  "alternatives_available": false,
  "time_basis": "current_traffic_estimate"
}
```

示例省略端点信息，仅展示字段含义；不能把当次测试数值当作当前路线。origin_source 是 configured_home 或 argument。数值距离/耗时始终为米/秒，格式化距离为米/千米，不继承 Google 的英制输出。只选择提供商首条路线，alternatives_available 仅表示本次响应是否还有其他条目，不代表已比较最优。

time_basis 分别为 current_traffic_estimate、timetable 或 untimed_estimate；不输出虚构的无拥堵时间、营业状态或准点保证。返回不含原始响应、导航指令、Key 或上游错误原文。沿用 v0.6.1 的预算/嵌套裁剪，truncated=true 时仍需按可见内容解释。

## 权限、预算与验证

每个新 HTTP 请求前及返回前重新核对原始管理员、白名单/网关和配置快照；解析期间撤权或改 Key/家庭地址后，不继续请求或交付旧结果。原生 API 直接调用同样受保护。整个路线工具有 20 秒异步总预算，每个 HTTP 仍为 10 秒、原始响应 256 KiB、禁止重定向/重试/缓存；只允许固定 restapi.amap.com 端点，不接受模型 URL/Headers/Key。获取 Schema、目录或就绪检查不请求后端，不验证接口权限或密钥。

自动化使用真实 HA 与原版 EOAIC2 ScriptFunction、模拟 HTTP，覆盖起点优先级、独立默认、四种模式/公交时间/单位、地址消歧、错误/取消/预算、权限中途变化及旧配置升级。v0.8.0 的独立公共坐标联网验证中，当前驾车、步行、骑行、公交及未来公交返回有效距离/耗时；v0.8.1 未新增联网验证。已移除能力不再列入后续验收门槛，历史结果仍按原版本记录。

真实 HTTP 不等于用户 HA 安装、默认家庭地址、实际模型调用、HACS 升级或全部模式验收。完整证据与后续门槛见 [TESTING.md](TESTING.md) 和 [兼容清单](TOOLS_COMPATIBILITY.md)。
