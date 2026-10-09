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
