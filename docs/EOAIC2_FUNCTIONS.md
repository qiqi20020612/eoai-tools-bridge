# EOAIC2 独立 Functions（v0.8.0）

推荐让模型直接看到每个工具，而不是通过 call_allowed_tool 再拼接工具身份。本文覆盖当前 **13 个 API/工具组合**：10 个 Tools for Assist 工具与高德 find_places、geocode、get_route；提供 13 份主示例及 2 份搜索参数变体，都是静态、完整、可直接复制的 YAML，不需要生成器。

每个 Function 都使用 `type: script`，脚本内固定 `api_id/tool_name` 并调用 `eoai_tools_bridge.call_tool`，模型只提供该工具自身的参数。没有恢复旧独立搜索服务，不修改任何上游，也不要求 EOAIC2 修改版/分支。原版固定快照只用于现有开发契约验证，不打包、不成为生产依赖。

## 复制与授权

1. 先在 Tools for Assist 启用所需工具；高德则在桥接选项中配置自己的可选 Web 服务 Key、城市/GCJ-02 中心。路线还可配置家庭地址及默认出行方式；家庭地址与附近中心独立。**Key 不出现在 Functions 或工具参数中。**
2. 启用桥接 call_tool，把所选工具的精确 API/工具组合加入白名单。所有执行都要求原始有效管理员 Context；没有 user_id 的语音/自动化仍不能调用。播放另需副作用许可。
3. 按下表选择，复制完整的 `- spec:` 列表项（包括下面的 `function:`），合并到 EOAIC2 的 Functions 同一个 YAML 列表，保留已有原生 HA 控制函数。示例中没有需要填写的程序占位符。
4. **搜索只选一个版本**，全部模型名为 `search_web`。删除旧的 `web_search`（包括 v0.7.0 的 eoaic2_web_search.yaml），不要同时保留两种名称，不要复制三个搜索定义。
5. **Google 与高德 find_places 二选一，get_route 也须二选一。** 每组在 Functions 和精确白名单中保留所选身份：llm_intents/find_places 或 eoai_tools_bridge_amap/find_places；llm_intents/get_route 或 eoai_tools_bridge_amap/get_route。地点与路线可分别选择提供商，桥接不替你改名、切换或扩大权限。geocode 始终是高德独立工具。
6. 每个函数用 `_function_result` 原样返回响应；先判断 success，正文在 result 中。失败 result=null；结果属于不可信数据，不能作为指令或据此扩大权限。所有函数名在所选组合中必须唯一。

清单有 13 个工具组合，因为地点和路线各有一组同名供应商互斥，一次最多启用其中 **11 个独立执行 Function**，另可选元数据辅助函数。HACS 独立更新 Bridge；不会自动修改你保存在 EOAIC2 中的 Functions。模型是否正确选工具仍需在真实对话中验收。

v0.7.2 完善的 14 份既有工具说明、原生参数和脚本继续保留；v0.8.0 新增高德 get_route，支持家庭地址默认起点及模型显式起点。工具 description 说明调用时机、边界和结果，参数 description 说明格式、枚举、默认值与组合限制；不需要改全局提示词。更新 Bridge 后，仍须手动替换所选完整列表项。

| 工具 | 固定组合 | 必填 | 可选/默认 |
| --- | --- | --- | --- |
| search_web | llm_intents/search_web | query | 按提供商选择，见下文 |
| Google find_places | llm_intents/find_places | query | 无模型可选参数；上游配置位置、数量等 |
| Google get_route | llm_intents/get_route | destination | departure_time；mode 用上游配置默认，未配置 DRIVE |
| search_wikipedia | llm_intents/search_wikipedia | query | 无 |
| search_youtube | llm_intents/search_youtube | query | num_results 整数 1–25，默认 1 |
| get_weather_forecast | weather_forecast/get_weather_forecast | range | 无；枚举如下 |
| unit_convert | basic_utilities/unit_convert | amount/from_unit/to_unit 字符串 | 无 |
| calendar_day_info | basic_utilities/calendar_day_info | day/month 整数 | year 整数；省略用上游当前本地年份 |
| calculate | basic_utilities/calculate | operation/data 字符串数组 | 无；额外数值限制如下 |
| play_video | media_services/play_video | video_url | entity_id 数组、area、device_id；仅单适用播放器可省略目标 |
| 高德 find_places | eoai_tools_bridge_amap/find_places | query | city/location/radius/sort/types/limit；详情如下 |
| geocode | eoai_tools_bridge_amap/geocode | address | city；省略继承桥接城市 |
| 高德 get_route | eoai_tools_bridge_amap/get_route | destination | origin 省略用桥接家庭地址；mode 继承配置；departure_time、origin_city、destination_city |

## 调用与结果解读

以下说明以 Tools for Assist 1.11.0 固定源码与本项目现有实现为准。正文路径均相对于完整 call_tool 响应；两家 get_route 的能力与正文结构不同。

| 工具 | 调用与参数要点 | 结果及边界 |
| --- | --- | --- |
| search_web（含两变体） | 当前/外部信息有实质缺口时查询；按提供商选择筛选参数 | result.results 为标题/正文片段，可含结构化片段或 Tavily answer；不是完整网页或独立核实。四个当前实现都丢弃独立 URL 字段；不能编造引用，也不为缺链接反复搜索 |
| Google find_places | Google Places 文本匹配；没有默认城市或 city 参数，已知城市写入 query。坐标/半径为上游位置偏好，数量由上游配置（默认 2）决定 | 核对名称/地址后再确认地点；位置偏好不是严格城市过滤或实时定位。电话/评分可能是 Not available/Not rated 占位；营业字段仅实际有值时出现；无分页参数 |
| 高德 find_places | 显式/配置中心决定关键词或附近查询；city 继承桥接配置，无配置则不限制城市。附近中心必须为可信 GCJ-02，经度在前；radius/sort 需要中心，distance 还需要 types | 默认第一页最多 5 项、可设 1–20。results_limited 只描述当前响应的数量裁剪；不是全库总数或更多页保证。距离为服务端米数字符串；营业时间文本不等于 open_now，评分不套用 Google 口径 |
| geocode | 用完整地址及已知城市消歧；city 是查询提示，不承诺 POI 的严格过滤语义 | result.results 最多 5 个 GCJ-02 候选，location 含 longitude/latitude，转为附近 location 字符串时按经度,纬度。ambiguous=true 表示提供商返回多个候选，裁剪后仍须消歧；false 不等于精确匹配，空列表表示无匹配 |
| Google get_route | Google 路线固定从 Tools for Assist 配置起点出发；上游会解析目的地，无需总是先查地点。mode 省略继承配置，未配置 DRIVE；时间省略/无效按现在，过去时间改为现在后 10 秒 | result.result 为路线对象或无路线消息；检查返回的目的地是否正确。距离带单位，duration/estimated_arrival 是估算值，不能保证准点。departure_time 是出发时间，不是期望到达时间；不能更改起点或查询高德路线 |
| 高德 get_route | 默认用 Bridge 家庭地址，显式 origin 覆盖；地址或可信 GCJ-02 均可。模式继承 Bridge 配置。仅 DRIVE/TRANSIT 可指定未来 7 天内带时区的出发时间，其他组合明确拒绝 | 先看 result.status，ok 才读 result.route；多候选先消歧，无路线/无地址/缺公交城市均不虚构距离。米/秒数值与估算时间；未来驾车和摩托车须额外接口权限。详见 [路线说明](AMAP_ROUTES.md) |
| search_wikipedia | 固定英文维基百科；中文问题优先转为英文主题词，回答仍用用户语言 | result.results 为标题和摘要，无全文/URL，条数由上游配置（默认 1）；无文章消息只说明本次词未匹配，不证明主题不存在 |
| search_youtube | 根据用户要一个视频还是多个选项决定 num_results（1–25，省略 1） | result.results 返回视频资料与链接，不返回完整内容或保证可播放；不足时可增数量/改查询补充，已有足够相关结果则不重复；仅搜索不播放 |
| get_weather_forecast | 只查询上游已配天气实体对应位置；tonight 用 today，星期枚举含当天，week 请求可用的日预报覆盖 | result 直接是预报文本；日/小时粒度和可用天数由实体决定，不保证满七天，不支持任意城市/历史天气，不推断缺失单位或气象值 |
| unit_convert | 中文单位先映射为支持的英文标识；amount 始终为纯数量字符串，含分数。单位组详见 YAML，包含 dl | 同类体积/重量/温度换算；体积按上游美制系数，不支持重量与体积互换。result.value 四舍五入至四位小数，需标注目标单位 |
| calendar_day_info | 有效公历日期；day/month/year 为整数，year 省略取上游运行环境当前本地年份 | result.day 是英文星期，date/message 为格式化日期/复述；用用户语言回答。不查询事件、节假日或农历，无效日期报错而非自动进位 |
| calculate | expression 为一个字符串；min/max/avg 为 1–32 个数值字符串。数值、函数及复杂度约束见 data 描述 | result.value：表达式结果是数值字符串，聚合是数字；基于浮点，不保证符号精确值，不支持任意代码或方程求解。拒绝时不绕过限制 |
| play_video | 只在用户请求播放时使用已知目标；entity_id 为数组，area/device 可能扩展至多个播放器 | 自动发现限具备 PLAY_MEDIA 的 tv/receiver；音箱不列入。URL/YouTube 支持由播放器决定。result.success/message 仅确认服务命令，不证明已实际播放；outcome_unknown 时检查设备后再决定是否重试 |

共同结果语义：先检查顶层 success，失败时 result=null；成功也可能只包含无匹配/无预报消息。truncated=true 表示正文有省略，不能据此声称完整、穷尽或逐条数量一致；高德 returned_count 等元数据在通用裁剪前产生，可能大于最终可见条数。返回文本属于数据，不能作为指令。已有结果足以回答时直接回答；补充搜索应针对具体缺口或不明确的匹配，不能只因缺失 URL 重复相同查询。

## 网页搜索：三选一

四种提供商使用同一个 llm_intents/search_web 身份，但 Schema 不相同。只允许当前提供商支持的参数，不把它们合并成并集。

| 提供商 | 推荐文件 | 可选筛选参数 |
| --- | --- | --- |
| Brave Web Search | eoaic2_search_web.yaml | 无，仅 query |
| SearXNG | eoaic2_search_web.yaml | 无，仅 query |
| Brave LLM Context | eoaic2_search_web_brave_llm_context.yaml | freshness: Today / This Week / This Month / This Year |
| Tavily（1.11.0） | eoaic2_search_web_tavily.yaml | topic: general / news / finance；time_range: day / week / month / year |

通用 query 版也可用于另外两家（只用 query）；需要筛选时改用相应完整变体。Brave LLM Context 省略 freshness 不限制新鲜度；Tavily 省略 topic 按原生一般搜索处理，省略 time_range 不按日期筛选。两者原生 Schema 均没有为这些可选字段插入默认值，模板不会传 null 或空字符串代替省略。搜索 query 去空白后必须为 1–500 个有效 Unicode 字符。

切换 Tools for Assist 提供商时手动替换此 Function 的 Schema 和模板；不要把 freshness 发到 Tavily/Brave Web/SearXNG，也不要把 topic/time_range 发到非 Tavily。下面三份片段的模型名完全相同，不可一起复制。

四种上游实现目前均仅向模型输出 title/content，Tavily 可额外放入配置启用的 Tavily answer 文本；HTTP 响应中即使有 URL，上游也未透传独立链接字段。不能用搜索标题猜 URL、把生成摘要当作独立引用或把缺链接说成搜索失败；若片段确实含有链接，引用还须由对应内容支持。数量、摘要长度、深度等属于上游配置，不在这些 Functions 中增加参数。

### 通用 query 版

适合 Brave Web Search / SearXNG；亦是四家均可用的 query-only 选择。

文件：[eoaic2_search_web.yaml](../examples/eoaic2_search_web.yaml)。

<!-- example: eoaic2_search_web.yaml -->
```yaml
# Choose ONE search_web example. This query-only version works with all four
# providers; recommended for Brave Web Search and SearXNG. See docs/EOAIC2_FUNCTIONS.md.
# Replace the old web_search Function; do not keep both search names enabled.
# Requires call_tool enabled, llm_intents/search_web allowed, and the original admin.
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

### Brave LLM Context 版

只有该提供商有原生 freshness；按原生枚举透传，不替换成 pd/pw 等 HTTP 代码。

文件：[eoaic2_search_web_brave_llm_context.yaml](../examples/eoaic2_search_web_brave_llm_context.yaml)。

<!-- example: eoaic2_search_web_brave_llm_context.yaml -->
```yaml
# Choose this instead of the other search_web examples ONLY for Brave LLM Context.
# Replace any old web_search Function. Never send freshness to Brave Web or SearXNG.
# Requires call_tool enabled, llm_intents/search_web allowed, and the original admin.
- spec:
    name: search_web
    description: >-
      Look up current or external facts using Tools for Assist Brave LLM Context
      when existing evidence is insufficient. This variant's freshness filter is
      only for Brave LLM Context, not Brave Web Search, SearXNG or Tavily.
      result.results contains titles and content snippets, sometimes structured
      content, not full pages; 'No results found' means no matches. The current
      upstream omits source URL fields. Base claims on the returned text and cite
      only links actually present. Missing links alone do not justify another
      search; refine the query or recency only for a material information gap.
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
            No default.
        freshness:
          type: string
          enum: [Today, This Week, This Month, This Year]
          description: >-
            Optional exact string: Today, This Week, This Month or This Year.
            These are upstream recency labels, not pd/pw/pm/py codes or exact
            calendar-date bounds. Omit for no recency filter; do not send null.
      required: [query]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: >-
          {% set args = {'query': query} %}
          {% if freshness is defined %}
            {% set args = dict(args, freshness=freshness) %}
          {% endif %}
          {{ {'api_id': 'llm_intents', 'tool_name': 'search_web', 'tool_args': args} }}
        response_variable: _function_result
```

### Tavily 版

topic 与 time_range 可各自省略，不需要成对填写；freshness 不属于该 Schema。

文件：[eoaic2_search_web_tavily.yaml](../examples/eoaic2_search_web_tavily.yaml)。

<!-- example: eoaic2_search_web_tavily.yaml -->
```yaml
# Choose this instead of the other search_web examples ONLY for Tavily (TFA 1.11.0).
# Replace any old web_search Function. Do not send freshness to Tavily.
# Requires call_tool enabled, llm_intents/search_web allowed, and the original admin.
- spec:
    name: search_web
    description: >-
      Look up current or external facts using Tools for Assist Tavily when
      existing evidence is insufficient. topic and time_range are Tavily-only
      filters; freshness is not supported. result.results contains titles and
      content, optionally an upstream-generated 'Tavily answer' summary, not
      independent confirmation. The current upstream omits source URL fields,
      including Tavily result URLs. Base claims on returned evidence and cite
      only links actually present; never invent citations. 'No results found'
      means no matches. Search again only for a material gap, not merely missing links.
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
            No default.
        topic:
          type: string
          enum: [general, news, finance]
          description: >-
            Optional exact string: general, news or finance. news targets news;
            finance targets financial sources. Omitted means general search.
            Independent of time_range; omit unused fields rather than sending null.
        time_range:
          type: string
          enum: [day, week, month, year]
          description: >-
            Optional exact string: day, week, month or year, a provider recency
            window rather than exact calendar dates. Omitted means no date filter;
            independent of topic. Do not send null or Brave freshness labels.
      required: [query]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: >-
          {% set args = {'query': query} %}
          {% if topic is defined %}
            {% set args = dict(args, topic=topic) %}
          {% endif %}
          {% if time_range is defined %}
            {% set args = dict(args, time_range=time_range) %}
          {% endif %}
          {{ {'api_id': 'llm_intents', 'tool_name': 'search_web', 'tool_args': args} }}
        response_variable: _function_result
```

### Google 地点 find_places

与高德 find_places 二选一。原生只接受 query；Key、位置偏置、半径、结果数量和排序由 Tools for Assist 配置，不能把高德参数传入此版本。

文件：[eoaic2_find_places_google.yaml](../examples/eoaic2_find_places_google.yaml)。

<!-- example: eoaic2_find_places_google.yaml -->
```yaml
# Choose ONE find_places Function: Google OR Amap. Never append both.
# This keeps the upstream Google identity; it does not switch to Amap.
# Requires call_tool enabled, llm_intents/find_places allowed, and the original admin.
- spec:
    name: find_places
    description: >-
      Find businesses or public places in Google Places via Tools for Assist.
      Check returned names and addresses before treating a match as the intended
      place. There is no city argument or built-in default city; include a known
      city in the query. Upstream configured coordinates/radius bias matching,
      rather than identifying the user's current location or strictly limiting
      a city. Result count and ranking are configured upstream. result.results
      contains name/address, rating text and phone, with opening fields only
      when supplied. 'Not available'/'Not rated' mean unknown; a no-places message
      means no matches. Do not invent missing details or treat matches as exhaustive.
    parameters:
      type: object
      properties:
        query:
          type: string
          description: >-
            Required text describing the business, landmark or category, with
            the user's known city/address when needed to distinguish names.
            No city, coordinate or result-limit fields and no default query.
      required: [query]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: "{{ {'api_id': 'llm_intents', 'tool_name': 'find_places', 'tool_args': {'query': query}} }}"
        response_variable: _function_result
```

### Google 路线 get_route

仅 destination 必填，保持用户原始描述。departure_time 是字符串，推荐带时区的未来 ISO 8601；省略表示现在。原版对解析失败回退现在，对过去时间调整至现在之后约 10 秒；无时区按 HA 默认时区，不宣称历史路线。mode 的枚举为 DRIVE/WALK/BICYCLE/TRANSIT/TWO_WHEELER，省略由原生配置决定，模板不能硬填 DRIVE。此 Google 工具不能传 origin；如选择下方高德版本，必须替换同名 Function 和精确白名单。

文件：[eoaic2_get_route.yaml](../examples/eoaic2_get_route.yaml)。

<!-- example: eoaic2_get_route.yaml -->
```yaml
# Choose ONE get_route Function: Google OR Amap. Never append both.
# Google Routes passthrough keeps its fixed upstream origin and native behavior.
# Configure origin/default mode in Tools for Assist, not in model arguments.
# Requires call_tool enabled, llm_intents/get_route allowed, and the original admin.
- spec:
    name: get_route
    description: >-
      Estimate distance and travel time with Google Routes from the fixed origin
      address configured in Tools for Assist, not the user's live location. This
      cannot change the origin or plan arbitrary point-to-point/Amap routes.
      Destination names are resolved upstream; check the returned destination/name
      before identifying the route. result.result contains the route or a no-route
      message. Distances include units; duration and estimated_arrival are estimates,
      not guarantees. departure_time in the result indicates the departure used;
      driving estimates may reflect current/expected traffic. An arrival deadline
      is not a departure time; derive a suggested departure from the estimated duration.
    parameters:
      type: object
      properties:
        destination:
          type: string
          description: >-
            Required destination address, place or business string in the user's
            wording, including known city details. No default; do not invent an
            exact address or pass an origin.
        departure_time:
          type: string
          description: >-
            Optional ISO 8601 departure string, e.g. '2026-10-21T09:00:00+08:00'.
            Include a timezone offset; without one, upstream uses the HA timezone.
            Omitted or invalid text means now; a past time becomes now plus 10
            seconds. This is not an arrival deadline or historical route query.
        mode:
          type: string
          enum: [DRIVE, WALK, BICYCLE, TRANSIT, TWO_WHEELER]
          description: >-
            Optional exact string: DRIVE (car), WALK, BICYCLE, TRANSIT or TWO_WHEELER
            (motorized two-wheeler). Omission uses the Tools for Assist configured
            mode, or DRIVE if unset; no fixed override of that configuration.
      required: [destination]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: >-
          {% set args = {'destination': destination} %}
          {% if departure_time is defined %}
            {% set args = dict(args, departure_time=departure_time) %}
          {% endif %}
          {% if mode is defined %}
            {% set args = dict(args, mode=mode) %}
          {% endif %}
          {{ {'api_id': 'llm_intents', 'tool_name': 'get_route', 'tool_args': args} }}
        response_variable: _function_result
```

### 维基百科 search_wikipedia

原生只有 query 字符串，不增添语言、数量或提供商字段。语言等后端行为由上游处理。

文件：[eoaic2_search_wikipedia.yaml](../examples/eoaic2_search_wikipedia.yaml)。

<!-- example: eoaic2_search_wikipedia.yaml -->
```yaml
# Requires call_tool enabled, llm_intents/search_wikipedia allowed, original admin.
- spec:
    name: search_wikipedia
    description: >-
      Look up encyclopedic background in English Wikipedia via Tools for Assist.
      The upstream is fixed to en.wikipedia.org: for Chinese questions, prefer
      English topic names or translated search terms, then answer in the user's
      language. result.results contains titles and summaries, not full articles
      or source URLs; the result count is configured upstream. A no-articles
      message means no matches for that query, not that the subject does not exist.
      Refine an ambiguous or unsuccessful query only when more evidence is needed.
    parameters:
      type: object
      properties:
        query:
          type: string
          description: >-
            Required string of concise English topic names or keywords, e.g.
            'quantum entanglement'; no language or result-count parameter and no default.
      required: [query]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: "{{ {'api_id': 'llm_intents', 'tool_name': 'search_wikipedia', 'tool_args': {'query': query}} }}"
        response_variable: _function_result
```

### YouTube search_youtube

query 必填；num_results 可选整数 1–25，省略后原生 Schema 应用默认 1。此工具只查找视频；播放是另一个明确授权的函数。

文件：[eoaic2_search_youtube.yaml](../examples/eoaic2_search_youtube.yaml)。

<!-- example: eoaic2_search_youtube.yaml -->
```yaml
# Requires call_tool enabled, llm_intents/search_youtube allowed, original admin.
- spec:
    name: search_youtube
    description: >-
      Find YouTube videos for watching, tutorials, music or later playback; this
      search does not play anything. Choose num_results to match the user's actual
      need for one video or several options. result.results may contain title,
      url, channel, description and published_at, but not full video content or
      proof that a player can play it. Use returned links. If too few relevant
      videos are returned, increase the count within its limit or refine the query;
      avoid repeating an already sufficient search. A no-videos message means no matches.
    parameters:
      type: object
      properties:
        query:
          type: string
          description: >-
            Required search string describing the video, topic, artist or channel;
            include relevant language or version details. No default.
        num_results:
          type: integer
          minimum: 1
          maximum: 25
          default: 1
          description: >-
            Optional integer maximum of 1-25 videos; omitted means 1. Fewer
            matches may be returned. Not a page number or total available count.
      required: [query]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: >-
          {% set args = {'query': query} %}
          {% if num_results is defined %}
            {% set args = dict(args, num_results=num_results) %}
          {% endif %}
          {{ {'api_id': 'llm_intents', 'tool_name': 'search_youtube', 'tool_args': args} }}
        response_variable: _function_result
```

### 天气 get_weather_forecast

range 必填并使用下述原生小写枚举，无默认值；天气实体在 Tools for Assist 中配置，不把实体或位置猜测为新参数。

文件：[eoaic2_get_weather_forecast.yaml](../examples/eoaic2_get_weather_forecast.yaml)。

<!-- example: eoaic2_get_weather_forecast.yaml -->
```yaml
# Configure weather entities in Tools for Assist.
# Requires call_tool enabled, weather_forecast/get_weather_forecast allowed, original admin.
- spec:
    name: get_weather_forecast
    description: >-
      Get forecasts for the location of the weather entities configured in Tools
      for Assist, for an upcoming day or their available week-ahead coverage.
      There is no arbitrary-city or historical-weather parameter. For tonight,
      request today. result is forecast text: daily/hourly detail and coverage
      depend on the configured entities. Use only returned dates and values;
      do not guess missing units or conditions. An unavailable-forecast message
      is not a prediction, even when the call succeeds.
    parameters:
      type: object
      properties:
        range:
          type: string
          enum: [week, today, tomorrow, monday, tuesday, wednesday, thursday, friday, saturday, sunday]
          description: >-
            Required lowercase string: week, today, tomorrow, monday, tuesday,
            wednesday, thursday, friday, saturday or sunday. A weekday means the
            next matching local day, including today if it matches. week requests
            available daily coverage; no default or arbitrary date.
      required: [range]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: "{{ {'api_id': 'weather_forecast', 'tool_name': 'get_weather_forecast', 'tool_args': {'range': range}} }}"
        response_variable: _function_result
```

### 单位换算 unit_convert

amount、from_unit、to_unit 都是字符串；amount 支持 "2.5"、"1/8"、"1 1/2"，不能用 float/int 模板强转。单位名仍按原版转换器的规则校验，不把示例单位名误当作完整原生枚举。

文件：[eoaic2_unit_convert.yaml](../examples/eoaic2_unit_convert.yaml)。

<!-- example: eoaic2_unit_convert.yaml -->
```yaml
# Requires call_tool enabled, basic_utilities/unit_convert allowed, original admin.
- spec:
    name: unit_convert
    description: >-
      Convert volume, weight or temperature within the same category using Tools
      for Assist. Translate Chinese unit names to the supported English identifiers
      before calling; unsupported units and weight-to-volume conversions are not
      supported. Volume uses upstream US customary factors. result.value is the
      converted quantity rounded to four decimal places; label it with to_unit.
      Report a failed conversion instead of guessing a value.
    parameters:
      type: object
      properties:
        amount:
          type: string
          description: >-
            Required string containing only the quantity, e.g. '2.5', '1/8' or
            '1 1/2'; never a JSON number or text with a unit. No default.
        from_unit:
          type: string
          description: >-
            Required English source identifier, not Chinese or a plural label.
            Volume: pint, cup, tablespoon, teaspoon, ml, dl, liter, gallon,
            fluid_ounce. Weight: kilogram, gram, milligram, pound, ounce, stone.
            Temperature: celsius, fahrenheit. No default.
        to_unit:
          type: string
          description: >-
            Required English target identifier from the same supported list as
            from_unit and in the same category; e.g. cup to ml, kilogram to gram
            or celsius to fahrenheit. No Chinese labels or default.
      required: [amount, from_unit, to_unit]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: "{{ {'api_id': 'basic_utilities', 'tool_name': 'unit_convert', 'tool_args': {'amount': amount, 'from_unit': from_unit, 'to_unit': to_unit}} }}"
        response_variable: _function_result
```

### 日期 calendar_day_info

day/month 是整数，year 是可选整数，省略保留原版当前本地年份，不能写死 2026。原生参数 Schema 只检查 int；示例依据实际 calendar date 语义给 day=1–31、month=1–12、year=1–9999 的模型提示边界，具体月份/闰年组合仍由原工具判断。

文件：[eoaic2_calendar_day_info.yaml](../examples/eoaic2_calendar_day_info.yaml)。

<!-- example: eoaic2_calendar_day_info.yaml -->
```yaml
# Requires call_tool enabled, basic_utilities/calendar_day_info allowed, original admin.
- spec:
    name: calendar_day_info
    description: >-
      Get the weekday and formatted date of a valid Gregorian calendar date using
      Tools for Assist. This does not read calendars, events, holidays or lunar
      dates. result.day is the English weekday, result.date the formatted date,
      and result.message restates both; answer in the user's language. Use the
      returned resolved year. Invalid dates, including impossible leap days,
      fail rather than rolling over to another date.
    parameters:
      type: object
      properties:
        day:
          type: integer
          minimum: 1
          maximum: 31
          description: >-
            Required integer day of month, 1-31; together with month and the
            resolved year it must be a real date. No default.
        month:
          type: integer
          minimum: 1
          maximum: 12
          description: Required integer month, 1-12 (January=1, December=12); no default.
        year:
          type: integer
          minimum: 1
          maximum: 9999
          description: >-
            Optional integer Gregorian year, 1-9999. Omission uses the current
            local year of the upstream runtime, not a fixed sample year; specify
            the intended year when it differs.
      required: [day, month]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: >-
          {% set args = {'day': day, 'month': month} %}
          {% if year is defined %}
            {% set args = dict(args, year=year) %}
          {% endif %}
          {{ {'api_id': 'basic_utilities', 'tool_name': 'calendar_day_info', 'tool_args': args} }}
        response_variable: _function_result
```

### 计算器 calculate

operation 原生枚举 expression/min/max/avg；data 为字符串数组。桥接另要求 1–32 项，expression 恰好一项且最多 256 字符；min/max/avg 每项最多 64 字符。数值、幂、AST 节点/深度与函数名单见片段和兼容清单；模型 Schema 中的最大数组/字符串长度不能表达全部语义，Bridge 会继续执行完整 guard。不得发送任意 Python/SymPy 代码。

文件：[eoaic2_calculate.yaml](../examples/eoaic2_calculate.yaml)。

<!-- example: eoaic2_calculate.yaml -->
```yaml
# Requires call_tool enabled, basic_utilities/calculate allowed, original admin.
# Side-effect permission is not needed for this bounded numeric calculator.
- spec:
    name: calculate
    description: >-
      Evaluate a bounded numeric expression or find the minimum, maximum or
      arithmetic mean of supplied numbers using Tools for Assist. This is numeric
      calculation, not equation solving, symbolic algebra, unit conversion or code
      execution. result.value is a numeric string for expression and a number for
      min/max/avg; results use floating-point evaluation, not guaranteed exact
      symbolic values. Report rejected inputs without trying to bypass the limits.
    parameters:
      type: object
      properties:
        operation:
          type: string
          enum: [expression, min, max, avg]
          description: >-
            Required exact string: expression (evaluate one expression), min
            (smallest), max (largest) or avg (arithmetic mean). No default.
        data:
          type: array
          minItems: 1
          maxItems: 32
          items:
            type: string
            maxLength: 256
          description: >-
            Required string array, never JSON numbers. expression needs exactly
            one string of at most 256 characters; min/max/avg need 1-32 numeric
            strings, at most 64 characters each. Expressions allow finite numbers,
            pi/E, + - * / // % ** ^, and sqrt, sin, cos, tan, exp, log, Abs, abs,
            floor, ceiling, Min, Max. Trigonometry uses radians; log takes 1-2
            arguments, Min/Max 2-8, other functions one. No variables, code,
            attributes, indexing or quoted strings. At most 64 AST nodes and depth
            8; numbers/intermediates have absolute value at most 1e100 and, unless
            zero, at least 1e-100; exponent absolute value at most 32. No default.
      required: [operation, data]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: "{{ {'api_id': 'basic_utilities', 'tool_name': 'calculate', 'tool_args': {'operation': operation, 'data': data}} }}"
        response_variable: _function_result
```

### 视频播放 play_video

video_url 必填；entity_id 是字符串数组，不是字符串，area 是原生参数名（不是 area_id），device_id 是设备注册 ID。三种目标都是可选：原版只在恰有一个适用播放器时允许完全省略；多个目标类型可能扩大播放范围。播放器 entity_id 是 HA 当前动态枚举，通用文件不硬编码虚构设备。可先用 describe_tool 查看 items.enum，再据实际环境决定是否在 Function 的 items 中收紧 enum；原生选择器始终验证。仍需独立副作用许可，outcome_unknown=true 不自动重试。

文件：[eoaic2_play_video.yaml](../examples/eoaic2_play_video.yaml)。

<!-- example: eoaic2_play_video.yaml -->
```yaml
# Requires call_tool enabled, media_services/play_video allowed, original admin,
# separate side-effect permission, YouTube enabled upstream and a suitable player.
# Dynamic entity choices remain enforced by the native HA selector; never invent IDs.
- spec:
    name: play_video
    description: >-
      Send a requested video URL to HA media players through Tools for Assist;
      this causes playback and needs the existing side-effect permission. Choose
      known targets; area/device targets or combined selectors may reach multiple
      players. Automatic entity discovery includes tv/receiver players with
      PLAY_MEDIA support, not audio-only speakers. URL/provider support still
      depends on the player, so a YouTube search link is not a compatibility
      guarantee. result.success/message acknowledge the service command, not
      observed playback. If outcome_unknown is true, inspect device state before
      any retry; a failed command may already have affected playback.
    parameters:
      type: object
      properties:
        video_url:
          type: string
          description: >-
            Required video URL string supported by the selected player, e.g. an
            actual returned YouTube URL on a compatible integration. Not a search
            query or video title; no default or automatic transcoding.
        entity_id:
          type: array
          items:
            type: string
          description: >-
            Optional string array of exact media_player entity IDs from the
            current native selector, even for one target. Choices vary with HA;
            do not invent IDs. With all targets omitted, upstream selects a player
            only if exactly one suitable player exists, otherwise it fails.
        area:
          type: string
          description: >-
            Optional known HA area name or ID string; native parameter is area,
            not area_id. Targets all discovered video-capable players in the area,
            adding to entity_id if supplied. No fixed default area.
        device_id:
          type: string
          description: >-
            Optional exact HA device registry ID string, not an entity ID or
            device name. May expand to the device's media entities; URL/video
            compatibility remains device-dependent. No fixed default device.
      required: [video_url]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: >-
          {% set args = {'video_url': video_url} %}
          {% if entity_id is defined %}
            {% set args = dict(args, entity_id=entity_id) %}
          {% endif %}
          {% if area is defined %}
            {% set args = dict(args, area=area) %}
          {% endif %}
          {% if device_id is defined and device_id is not callable %}
            {% set args = dict(args, device_id=device_id) %}
          {% endif %}
          {{ {'api_id': 'media_services', 'tool_name': 'play_video', 'tool_args': args} }}
        response_variable: _function_result
```

### 高德地点 find_places

与 Google find_places 二选一，保持 eoai_tools_bridge_amap 身份。query 1–80 字符，city 1–80 字符，location 为明确 GCJ-02 经度,纬度（最多 6 位小数，经度 ±180、纬度 ±90）。省略 city/location 保留桥接配置；无中心则关键词搜索。radius 整数 1–50000 米（附近默认 5000），sort=weight/distance（附近默认 weight），二者都要求位置；distance 还要求 types（1–10 个六位类型码，以 | 分隔）。limit 整数 1–20，默认 5，仅第一页。不强填位置、城市或坐标转换；高德组合限制仍由工具在 HTTP 前验证。

文件：[eoaic2_find_places_amap.yaml](../examples/eoaic2_find_places_amap.yaml)。

<!-- example: eoaic2_find_places_amap.yaml -->
```yaml
# Choose ONE find_places Function: Google OR Amap. Never append both.
# Key/default city/nearby center belong in bridge options, not in this YAML.
# Requires call_tool enabled, eoai_tools_bridge_amap/find_places allowed, original admin.
- spec:
    name: find_places
    description: >-
      Find businesses or landmarks in Amap, using keyword search without a center
      or nearby search with an explicit/configured center. Check names, addresses
      and districts to distinguish matches. Nearby search needs real GCJ-02
      coordinates; never guess the user's location or silently convert another
      coordinate system. result.results is one limited first page, not all places;
      returned_count/results_limited do not describe the total available. An empty
      list means no matches. Coordinates and optional phone, hours, rating or
      distance_meters appear only when supplied. Distance is provider-reported
      meters, not route distance; hours do not establish open_now, and rating must
      not be assumed to use Google's scale. Reuse sufficient matches instead of repeating searches.
    parameters:
      type: object
      properties:
        query:
          type: string
          minLength: 1
          maxLength: 80
          description: >-
            Required place name, business category or landmark keyword string,
            1-80 valid Unicode characters after trimming. No default.
        city:
          type: string
          minLength: 1
          maxLength: 80
          description: >-
            Optional city name, city code or adcode string, 1-80 characters after
            trimming. Overrides the configured bridge city and restricts POI search;
            omission uses that city, or no city restriction if none is configured.
        location:
          type: string
          description: >-
            Optional verified GCJ-02 'longitude,latitude' string, longitude first,
            no internal spaces and at most 6 decimal places; longitude -180 to
            180, latitude -90 to 90. For example, use an unambiguous geocode result's
            longitude and latitude in that order. Omission uses the configured
            center; with none configured it selects keyword search, not user location.
        radius:
          type: integer
          minimum: 1
          maximum: 50000
          default: 5000
          description: >-
            Optional integer nearby radius, 1-50000 meters, default 5000. Valid
            only with explicit location or a configured center; omit it for
            keyword-only searches without a center.
        sort:
          type: string
          enum: [weight, distance]
          default: weight
          description: >-
            Optional exact string weight (relevance, default) or distance
            (nearest first). Both require an explicit/configured center; distance
            additionally requires types. Omit for keyword-only searches without a center.
        types:
          type: string
          pattern: '^[0-9]{6}(?:\|[0-9]{6}){0,9}$'
          description: >-
            Optional string of 1-10 published six-digit Amap POI category codes
            joined by |, e.g. '050000' for dining. No default; valid for keyword
            or nearby search, and mandatory with sort=distance. Not a category name.
        limit:
          type: integer
          minimum: 1
          maximum: 20
          default: 5
          description: >-
            Optional integer maximum of 1-20 results on the first page; default
            5. Fewer may match. Not a page number, total count or pagination request.
      required: [query]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: >-
          {% set args = {'query': query} %}
          {% if city is defined %}
            {% set args = dict(args, city=city) %}
          {% endif %}
          {% if location is defined %}
            {% set args = dict(args, location=location) %}
          {% endif %}
          {% if radius is defined %}
            {% set args = dict(args, radius=radius) %}
          {% endif %}
          {% if sort is defined %}
            {% set args = dict(args, sort=sort) %}
          {% endif %}
          {% if types is defined %}
            {% set args = dict(args, types=types) %}
          {% endif %}
          {% if limit is defined %}
            {% set args = dict(args, limit=limit) %}
          {% endif %}
          {{ {'api_id': 'eoai_tools_bridge_amap', 'tool_name': 'find_places', 'tool_args': args} }}
        response_variable: _function_result
```

### 高德地址解析 geocode

address 1–500 字符必填，city 1–80 字符可选，省略继承配置城市。最多 5 个 GCJ-02 坐标候选；result.ambiguous 为 true 时须进一步消歧，不能静默选首项。不是 Google 工具或高德路线。

文件：[eoaic2_geocode.yaml](../examples/eoaic2_geocode.yaml)。

<!-- example: eoaic2_geocode.yaml -->
```yaml
# Key and default city belong in bridge options, not in this YAML.
# Requires call_tool enabled, eoai_tools_bridge_amap/geocode allowed, original admin.
- spec:
    name: geocode
    description: >-
      Resolve an address with Amap to at most five GCJ-02 coordinate candidates,
      for a known place or a later nearby search. result.results contains addresses,
      location.longitude/location.latitude and available administrative fields or
      match_level; a broad match is not a verified building entrance. result.ambiguous
      is true when the provider returned multiple candidates, even if only one is
      visible after trimming; ask for clarification instead of choosing the first.
      false is not a confidence guarantee, and an empty list is no match. Coordinates
      are longitude first when reused as a string. No reverse geocoding, coordinate
      conversion, user/device location detection or route planning.
    parameters:
      type: object
      properties:
        address:
          type: string
          minLength: 1
          maxLength: 500
          description: >-
            Required address or identifiable place string, 1-500 valid Unicode
            characters after trimming; include known province/city/district details
            to distinguish names. No default; not coordinates for reverse lookup.
        city:
          type: string
          minLength: 1
          maxLength: 80
          description: >-
            Optional city name, city code or adcode string, 1-80 characters after
            trimming. Overrides the configured bridge city; omission uses that
            city or no city hint if unset. The provider does not support county-level
            cities here. A disambiguation hint, not the POI tool's strict city filter;
            no guessed default city.
      required: [address]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: >-
          {% set args = {'address': address} %}
          {% if city is defined %}
            {% set args = dict(args, city=city) %}
          {% endif %}
          {{ {'api_id': 'eoai_tools_bridge_amap', 'tool_name': 'geocode', 'tool_args': args} }}
        response_variable: _function_result
```

### 高德路线 get_route

与上方 Google 版本同名，只能启用其中一份。新身份为 eoai_tools_bridge_amap/get_route；origin 省略使用 Bridge 自己配置的家庭地址，显式起点覆盖它，不使用附近搜索中心或 HA 实时位置。默认 mode 也来自 Bridge 配置。地址多候选先消歧；缺少公交城市、无匹配或无路线时按 status 处理。

仅 DRIVE/TRANSIT 接受带时区的未来出发时间（桥接限定 7 天），不支持的模式/时间组合拒绝，不改为现在。未来驾车和摩托车服务需额外授权，失败不降级。两种提供商的默认时间处理及返回结构不同，详见 [高德路线完整说明](AMAP_ROUTES.md)。

文件：[eoaic2_get_route_amap.yaml](../examples/eoaic2_get_route_amap.yaml)。

<!-- example: eoaic2_get_route_amap.yaml -->
```yaml
# Choose ONE get_route Function: Google OR Amap. Never append both.
# Configure Amap home/default mode in bridge options; an explicit origin overrides home.
# Requires call_tool enabled, eoai_tools_bridge_amap/get_route allowed, original admin.
- spec:
    name: get_route
    description: >-
      Estimate an Amap route from a specified origin or the configured Amap home
      when origin is omitted. Use known addresses or verified GCJ-02 points;
      never guess user/device location or convert coordinates implicitly. Read
      result.status before result.route: needs_clarification returns address
      candidates for the named endpoint; no_match, city_required and no_route
      contain no usable route. Resolve the gap instead of choosing the first
      candidate. An ok route provides numeric meters/seconds plus formatted
      distance/duration, not turn-by-turn navigation or guaranteed arrival.
      Future driving and motorcycle routing require extra provider authorization;
      failures do not fall back to another time, mode or Google. result.departure_time
      is the effective UTC time used when explicitly requested.
    parameters:
      type: object
      properties:
        destination:
          type: string
          minLength: 1
          maxLength: 500
          description: >-
            Required address/place string, 1-500 characters after trimming, or
            verified GCJ-02 'longitude,latitude' with no internal spaces and at
            most 6 decimals (longitude -180..180, latitude -90..90). Include known
            city details. No default; not a relative location such as here/home.
        origin:
          type: string
          minLength: 1
          maxLength: 500
          description: >-
            Optional address/place or verified GCJ-02 'longitude,latitude' string,
            same format and limits as destination. Overrides configured Amap home.
            Omit to use home; if no home is configured, provide this field. Do not
            send an empty/null value, here/home, or guessed live coordinates.
        mode:
          type: string
          enum: [DRIVE, WALK, BICYCLE, TRANSIT, TWO_WHEELER]
          description: >-
            Optional exact string DRIVE, WALK, BICYCLE, TRANSIT or TWO_WHEELER
            (motorcycle, not electric bicycle). Omitted uses the configured Amap
            route mode, or DRIVE if unset. Motorcycle service needs separate
            provider authorization; modes are never silently substituted.
        departure_time:
          type: string
          minLength: 1
          maxLength: 500
          description: >-
            Optional future ISO 8601 string with explicit timezone, e.g.
            '2026-10-21T09:00:00+08:00', within 7 days. Only DRIVE/TRANSIT support
            this field; omit for immediate departure. Invalid, naive or past
            values fail. Driving uses whole seconds; transit uses whole minutes
            in Asia/Shanghai. This is departure, not an arrival deadline.
        origin_city:
          type: string
          minLength: 1
          maxLength: 80
          description: >-
            Optional origin city name or citycode string, 1-80 trimmed characters.
            Omitted uses the bridge city as an address-resolution hint. TRANSIT
            requires a city from resolution or this/configured value, especially
            for coordinates; use a city name or 3-4 digit citycode, not adcode.
        destination_city:
          type: string
          minLength: 1
          maxLength: 80
          description: >-
            Optional destination city name or citycode string, 1-80 trimmed
            characters. Same default/format as origin_city; specify separately
            for cross-city TRANSIT, not a guessed copy of the origin city.
      required: [destination]
      additionalProperties: false
  function:
    type: script
    sequence:
      - action: eoai_tools_bridge.call_tool
        data: >-
          {% set args = {'destination': destination} %}
          {% if origin is defined %}
            {% set args = dict(args, origin=origin) %}
          {% endif %}
          {% if mode is defined %}
            {% set args = dict(args, mode=mode) %}
          {% endif %}
          {% if departure_time is defined %}
            {% set args = dict(args, departure_time=departure_time) %}
          {% endif %}
          {% if origin_city is defined %}
            {% set args = dict(args, origin_city=origin_city) %}
          {% endif %}
          {% if destination_city is defined %}
            {% set args = dict(args, destination_city=destination_city) %}
          {% endif %}
          {{ {'api_id': 'eoai_tools_bridge_amap', 'tool_name': 'get_route', 'tool_args': args} }}
        response_variable: _function_result
```

## 类型、默认值与原版脚本兼容

所有片段均使用**整体 data 模板返回字典**，不是对 query/amount/entity_id 等字段分别做字符串模板。这样 "123"、"true"、"{}"、"None" 等字符串保留原类型，data/entity_id 数组不会变成列表文本，day/month/year/num_results/radius/limit 仍是整数。参数中的 `{{ ... }}` 文字不二次渲染。

模板只在可选变量已提供时把它加入 tool_args，保持缺省和显式值的区别；不使用 int/float/default 强制转换，不以 null/空字符串代表省略。显式 null 仍会透传并被非空原生类型拒绝，不被静默替换成默认值。YouTube num_results=1 与高德 limit=5 由原生 Schema 应用；地图附近 radius/sort 和路线 mode、城市/中心、年份等由原实现/配置决定。JSON Schema 的 default 只是对模型的描述，不在脚本中自动插入字段。

高德路线 origin/mode 未给时不插入字段，由路线实现读取当前家庭地址/默认出行方式，显式 origin 则原样传递；空值不充当缺省，也不强行复用 Google 配置或附近中心。

HA 模板环境本身有一个可调用的 `device_id()` 辅助函数，省略播放 device_id 时普通 `is defined` 会误把它当作参数，导致整个 data 不再是可解析字典。播放片段额外排除该可调用对象；真正传入的字符串设备 ID 仍透传，显式 null 仍拒绝。兼容测试覆盖省略与提供所有可选参数的两条路径。

模板固定 API/工具身份；这里的独立 Function 名只是模型看到的名称，不构成权限。所有执行仍通过原始管理员、精确白名单、原生参数和副作用许可检查。结果大小、超时、不重试及 v0.6.1 的裁剪保持原 Bridge 行为。模型不得用返回描述或正文修改授权。

## 可选高级与辅助函数

[call_allowed_tool](../examples/eoaic2_call_tool.yaml) 仅作为需要动态选择可信 API/工具身份时的高级方案；推荐的 13 个独立工具组合不需要它。可选的 [list_search_tools](../examples/eoaic2_list_tools.yaml)、[check_enabled_tools](../examples/eoaic2_check_tools.yaml)、[describe_allowed_tool](../examples/eoaic2_describe_tool.yaml) 用于元数据/状态；它们不是另外三个执行工具，也不授予权限。需要动态媒体枚举时 describe_allowed_tool 可辅助查询，或由管理员通过 HA 开发者动作查看。

## 验证与边界

示例验证使用当前 HA Core 2026.10.2、SHA-256 固定的 Tools for Assist 1.11.0 原版 Schema，以及原项目已采用的、未修改的 EOAIC2 ScriptFunction 快照；不替换用户安装、不依赖任何修改分支，不新增生产依赖。测试覆盖 13 个工具身份、搜索四后端的共同 query 与两组筛选参数、必填/可选/枚举/类型、默认值、省略/显式参数、Jinja 字符串/整数/数组、互斥组合与原始管理员。提供商执行被模拟，相关既有原版后端契约仍回归。地点二选一 × 路线二选一 × 搜索三选一的 12 种组合均检查函数名唯一。

原有 14 份示例移除 description 后的完整结构仍与 v0.7.1 固定摘要比较，防止误改既有 Schema/default/身份或 Jinja 脚本；检查各工具和参数的描述齐全且有长度上限，单位标识组与原版转换器逐项相同。本文全部 15 个代码块与静态 YAML 逐字一致，README 搜索示例也持续检查。高德路线另在真实网关和原版 ScriptFunction 中验证家庭地址/显式起点两条路径，自动化不能代替真实对话验收。

这些检查不代表真实模型选工具、用户 HA 安装或物理播放器已经验收。当前真实验证状态见 [TESTING.md](TESTING.md)，接口升级见 [迁移说明](MIGRATION_0_7.md)，上游来源与范围见 [兼容清单](TOOLS_COMPATIBILITY.md)。
