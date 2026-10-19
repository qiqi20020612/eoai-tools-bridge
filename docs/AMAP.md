# 高德地点与位置解析（v0.7）

高德实现由本项目维护，通过 HA 公开 LLM API 注册为 **`eoai_tools_bridge_amap`**，不会接管 Tools for Assist 的 `llm_intents`。功能参考其 1.11.0 的 `google_places.py`；新增地址解析为当前位置查询与后续路线开发提供独立公共能力。高德路线在 v0.8，逆地理编码、自动定位与坐标转换尚未实现。

## 配置与权限

桥接选项增加可选的 `amap_api_key`（Web 服务 Key，密码输入）、`amap_city`（默认城市）及 `amap_location`（附近中心）。留空 Key 清除已保存值；不填地图配置可继续使用原上游工具。Key 存入 HA 配置项选项，不写入仓库、Functions、fixture、日志、缓存或 Release；密码输入不是文件级加密。测试 Key 只经隐藏输入留在验收进程内存。

地图配置本身不启用网关、不增加白名单。按需授权：

```text
eoai_tools_bridge_amap/find_places
eoai_tools_bridge_amap/geocode
```

两工具以 `ToolAnnotations(read_only=True, destructive=False)` 提供只读依据，返回 `read_only_basis=annotation`；没有加入 Tools for Assist 的固定审核表。仍要求启用网关、原始有效管理员与精确组合，副作用许可可关闭。直接选择原生 Amap LLM API 也会检查同一桥接策略，原生调用不会成为旁路。派发前再次核对管理员、权限和地图配置快照；卸载会注销 API，保存选项立即生效。

`list_tools`、`describe_tool` 和 `check_tools` 都不进行 HTTP、密钥验证或工具调用；就绪检查也不调用参数 Schema、默认工厂或序列化钩子。没有 Key 时依然可能 `ready`，因为这只是类型/权限检查。

## 参数

`find_places` 支持：

| 参数 | 约束与语义 |
| --- | --- |
| `query` | 必填，去空白后 1–80 字符，关键词语义与原版相同 |
| `city` | 可选，1–80 字符，覆盖默认城市；向 POI 服务发送 `region` 和 `city_limit=true`，限制城市 |
| `location` | 可选，覆盖配置中心，**GCJ-02 经度,纬度** 字符串，小数最多 6 位，经度 ±180、纬度 ±90 |
| `radius` | 可选，整数 1–50000 米，默认 5000；要求显式或配置位置 |
| `sort` | 可选，`weight`（默认）或 `distance`；要求位置；距离排序还要求 `types` |
| `types` | 可选，1–10 个高德六位 POI 类型码，以 `\|` 分隔，例如餐饮 `050000` |
| `limit` | 可选，整数 1–20，默认 5；只取第一页，不能当作全量数据 |

无位置时使用 v5 关键词搜索；有位置时使用 v5 周边搜索。依据 [高德 POI 2.0 文档](https://lbs.amap.com/api/webservice/guide/api-advanced/newpoisearch)（页面更新 2026-07-15），仅提供关键词时距离排序不生效，所以本实现对无 `types` 的 `sort=distance` 明确拒绝，避免悄悄返回另一种排序。布尔值不能充当整数；未知字段、超长查询、错误类型或越界坐标在原生 Schema 阶段拒绝。`radius/sort` 缺少位置或距离排序缺少类型码的组合在 HTTP 前拒绝。

`geocode` 的必填 `address` 为去空白后 1–500 字符；可选 `city` 为 1–80 字符，覆盖配置城市。依据 [高德地理编码文档](https://lbs.amap.com/api/webservice/guide/api/georegeo)（页面更新 2026-02-02）访问 `/v3/geocode/geo`。保留最多 5 个候选和匹配级别，`ambiguous=true` 时需进一步选择，不把第一项自动用作路线目的地。空结果为 `results=[]`。

不读取 HA 家庭坐标、人员或设备位置，不推断“我家/这里”，不把 WGS84 或 BD-09 当作 GCJ-02，不自动转换或重复转换。用户须从明确的 GCJ-02 来源提供坐标；输入与输出均经度在前。`city` 在 POI 服务中是城市限制，在地理编码中按官方城市查询参数传递，不承诺相同的严格过滤语义。

## 结果映射

通用响应的 `result` 含 `source=amap`、`coordinate_system=GCJ-02`、`results`、`returned_count` 和 `results_limited`。`returned_count` 为当前返回条数；`results_limited` 仅说明客户端因数量上限省略了本次响应里的行，不表示高德全库总量，也不保证更多页存在。`geocode` 另有 `ambiguous`，以服务实际返回的候选数判断。

| 高德字段 | 桥接结果字段 | 与原版 Google 工具的差异 |
| --- | --- | --- |
| `name/address/id` | `name/address/id` | 名称、地址及 POI ID，仅实际存在时保留 |
| `location` | `location.longitude/latitude` | GCJ-02，不能直接当作 Google 坐标 |
| `cityname/adname/adcode` | `city/district/adcode` | 提供行政区信息用于区分同名地点 |
| `business.tel` | `phone` | 缺失时省略，不写“有电话”或虚构号码 |
| `business.opentime_today/opentime_week` | `opening_hours_today/regular_open_hours` | 原始时间描述，不推导 `open_now/next_opens_at/next_closes_at` |
| `business.rating` | `rating` | 保留提供商评分文本，不附加 Google “out of 5” 假设 |
| `distance` | `distance_meters` | 周边搜索实际返回的米数字符串，不自行重算 |
| 地理编码 `formatted_address/level` | `address/match_level` | 地址候选与解析匹配级别，不等于地点检索排名 |

POI 请求只选择 `business` 扩展，避免请求不需要的照片等字段；不返回未知字段或上游指令。高德部分缺失字符串会以 `[]` 返回，归一化为缺失，不伪造数据。非空 POI 响应必须有有效名称；地理编码候选必须有地址和有效坐标。结构错误返回失败，不能转换成空成功。已知 Key 即便被提供商回显到公开字段也会脱敏。

## 请求、失败与预算

生产仅允许 `https://restapi.amap.com` 的三个固定端点：`/v5/place/text`、`/v5/place/around`、`/v3/geocode/geo`。Key 仅由可信配置填入请求，不接受模型提供 URL、Headers 或 Key。不跟随重定向，不重试、不缓存响应；单次 HTTP 总超时 10 秒，响应解码前按流限制 **256 KiB**。工具调用仍受既有 20 秒通用异步超时及 16 KiB 结果预算约束，沿用 v0.6.1 嵌套裁剪。

缺少/未授权 Key、配额不足、HTTP 错误、网络超时、超大/无效 JSON 或缺失必要字段均使用固定错误，原始 URL、响应和异常文本不会进入桥接日志/结果。`call_tool` 保留既有错误契约：原生字段验证失败为 `invalid_args`；提供商、缺 Key 或工具内部组合检查失败为 `upstream_error`，`result=null`、`outcome_unknown=false`。原生工具内部仅返回固定类别，不回显服务端 `info`。取消直接传播，不转为成功或重试。

## 验证状态

自动化使用模拟 HTTP 和真实 HA 注册/权限/Schema/生命周期及原版 EOAIC2 ScriptFunction。2026-10-19 另用测试 Key 在独立进程中真实请求上述三个端点：关键词与附近查询各返回 2 项，地理编码返回 1 个候选，均有有效 GCJ-02 坐标。Key 未保存，原始响应与完整请求 URL 未落盘。

此证据只证明本次官方端点与该 Key 的三种请求成功；真实 HA 安装、Functions/模型调用、管理员身份贯穿和 HACS 升级仍须单独验收。完整记录见 [TESTING.md](TESTING.md)。
