# 上游源码核对

核对日期：**2026-10-09（Asia/Shanghai）**。开发依据以下实际源码快照，未修改任何上游源码或实际 HA 安装目录。

| 项目 | 基准 | 固定提交 |
| --- | --- | --- |
| HA Core | `2026.10.0` | `6a811d3359c7b2076dc9e1cf900843a129c044af` |
| Tools for Assist | `master` | `100e740b93a2a1a6d304329883937193a4571ac0` |
| EOAIC2 | `develop` | `b0274f752fc01495875522db9281c335af8cf484` |

## HA Core

[helpers/llm.py](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/homeassistant/helpers/llm.py) 确认：

- `async_get_api(hass, api_id, llm_context)` 返回 `APIInstance`，API 不存在时抛 `HomeAssistantError`。
- `LLMContext` 接受 `platform, context, language, assistant, device_id`。
- `ToolInput` 接受固定工具名称及参数字典；`APIInstance.async_call_tool` 返回 `ToolResult`。
- 第三方工具返回字典时，HA 2026.10 将其包装为 `ToolResult(data=...)` 并报告弃用，字典返回兼容截至 2027.11.0 的弃用期限。桥接处理 `ToolResult`，额外保留字典防御分支。
- 尽管该方法的 docstring 提及校验，当前实现直接调用工具，未替桥接完成查询长度/类型/白名单验证。因此桥接服务自己严格验证。

[core.py](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/homeassistant/core.py) 确认服务注册接受 `supports_response=SupportsResponse.ONLY`；调用必须请求响应，Python 调用还必须 blocking。参数 Schema 使用 `probatio`，而不是旧版 HA 示例中的 `voluptuous`。

[pyproject.toml](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/pyproject.toml) 要求 Python `>=3.14.2`、`probatio==0.13.0`。本项目运行时没有额外 pip 依赖。

v0.2 清单使用 `async_get_apis` 枚举注册表，先过滤固定 API 白名单，再通过 `async_get_api` 取得工具的公开 `name/title/description/parameters/annotations`。不读取工具配置、不导入第三方内部模块、不调用 `async_call_tool`。

[openai_conversation/entity.py](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/homeassistant/components/openai_conversation/entity.py) 使用 `probatio.to_openapi(..., custom_serializer=..., openapi_version="3.1.0")` 转换工具参数。本集成沿用公开接口，额外启用 `strict=True`，避免不支持的约束被放宽，并限制 Schema 结构、大小和输出字段。

[homeassistant/__init__.py](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/homeassistant/__init__.py) 在启动时调用 `probatio.compat.install_as_voluptuous()`。因此 Tools for Assist 的 `import voluptuous as vol` 在正常 HA 2026.10 进程中解析为 probatio 兼容层；不能根据包内仍存在 `voluptuous` 字样就断言其 Schema 不可转换，也不需要导入上游内部模块实现转换。

HA `ToolAnnotations` 的默认值为 `read_only=False, destructive=True`，代表未声明时保守处理。固定快照中的 Tools for Assist 搜索工具直接继承未声明状态；v0.2 仅对已经审核的 `llm_intents/search_web` 使用白名单依据，并在清单标记 `read_only_basis=audited_allowlist`。若上游给出独立声明，则必须同时为只读且无破坏性。`read_only=true` 不会自行扩大 API/工具白名单。

v0.3 `call_tool` 使用同一公开注册/调度接口，只在当前精确白名单和原始有效管理员授权通过后取得 API。HA 2026.10.0 的 `APIInstance.async_call_tool` 不调用工具的参数 Schema，因此桥接先执行工具公开的 probatio Schema，并再次检查结果是受限 JSON 对象，再交给原生调度。Schema/default 工厂运行一次，清单仍拒绝带默认值的 Schema；调用与发现采用不同的执行边界。HA 会在 LLM trace 中记录工具名和参数，桥接自身不记录正文。

[auth/models.py](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/homeassistant/auth/models.py) 提供用户的 `is_active` 和 `is_admin`；桥接通过 `hass.auth.async_get_user` 查询原始 Context 用户，不靠模型参数声明身份。缺少用户或非管理员明确拒绝。测试使用真实 HA 认证存储的用户。未声明只读的工具、写入或破坏性工具需要另外启用副作用选项；注释不作为 Python 沙箱。

[config_entries.py](https://github.com/home-assistant/core/blob/6a811d3359c7b2076dc9e1cf900843a129c044af/homeassistant/config_entries.py) 的公开 OptionsFlow 在初始化后提供 `config_entry`。桥接保留单实例配置流与版本 1，新增原生选项流；旧配置没有授权选项，通用调用默认关闭。运行时每次读取选项和已加载状态，无需维护 API 实例或额外重载缓存。

## Tools for Assist

[llm_functions.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/llm_functions.py) 中 `SearchAPI.id=llm_intents`。仅配置了相关工具的 API 才注册；即使搜索 API 注册，也可能只启用了维基百科等工具。桥接分别检查 API 注册与 `search_web` 可用性。

[base_web_search.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/base_web_search.py) 的工具名为 `search_web`，必填参数 `query`。正常结果为 `{"results": ...}`，空结果为字符串 `"No results found"`，业务失败为 `{"error": ...}`，部分成功响应附有 `instruction`。桥接规范化空结果、隐藏错误原文并丢弃指令字段。

实际结果格式：

- [brave_web_search.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/brave_web_search.py)：`title` 及 `content`，后者可为摘要列表。
- [brave_llm_context_search.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/brave_llm_context_search.py)：`content` 是摘要列表，JSON 摘要可能被解析为对象。
- [searxng_search.py](https://github.com/skye-harris/llm_intents/blob/100e740b93a2a1a6d304329883937193a4571ac0/custom_components/llm_intents/searxng_search.py)：`title` 及字符串 `content`。

以上三个后端当前都未向 LLM 返回 URL。桥接不会从标题猜测来源；若将来上游提供实际 `url`/`link`，会保留安全的原始链接。

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
