# Tools for Assist 1.11.1 与 HA 2026.10.4 兼容核对

核对日期：**2026-10-29（Asia/Shanghai）**。本次适配版本为 **Bridge v0.8.2**。源码读取、隔离测试和用户真实环境验收分别记录；不修改任何上游或实际安装。

## 上游事实与固定范围

- [Tools for Assist 1.11.1](https://github.com/skye-harris/llm_intents/releases/tag/1.11.1) 发布于 2026-10-21，固定提交 `5d2e76d72564fe378f32870bd311ca9460956281`。相对原 1.11.0 基准，包含功能合并 `2c3f71f7aa8d140452931b9fc5349410c6562f25` 和版本提交。
- 主分支截至核对时为 `112aed155c90bdc5f9255bf1ffdd696b741a0d48`；[发布后增量](https://github.com/skye-harris/llm_intents/compare/5d2e76d72564fe378f32870bd311ca9460956281...112aed155c90bdc5f9255bf1ffdd696b741a0d48) 只修正 README 安装路径拼写，运行文件与 1.11.1 相同。不以主分支名替代固定源码。
- [HA Core 2026.10.4](https://github.com/home-assistant/core/releases/tag/2026.10.4) 是核对时的最新正式版，固定提交 `357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b`，UTC 2026-10-24 发布（北京时间 10-25）。开发/CI 固定同版 HA 及 [测试插件 0.13.375](https://pypi.org/project/pytest-homeassistant-custom-component/0.13.375/)，不使用预发布版。

Tools for Assist 仍为四个非 Home Control API、10 个工具名、13 个实现；没有新增需暴露的工具。旧基线 20 文件与 1.11.0/1.11.1 各 22 文件分别缓存、固定 SHA-256；只用于开发测试，不加入发布包。当前分支的 Home Control 仍在范围外。

## 逐项变化与 Bridge 处理

| 上游变化 | 实际影响与适配 |
| --- | --- |
| [计算器 AST](https://github.com/skye-harris/llm_intents/blob/5d2e76d72564fe378f32870bd311ca9460956281/custom_components/llm_intents/calculator.py) 替换 SymPy，表达式在执行器线程运行 | 原生 operation/data 和 value 类型不变，支持数字、+ - * / % **、正负号及括号。Bridge 统一使用新旧两版共有语法，拒绝函数、pi/E、^、//，保留原有数值/节点/深度预算并对齐大底数幂限制；不改写输入或重算输出 |
| [媒体工具](https://github.com/skye-harris/llm_intents/blob/5d2e76d72564fe378f32870bd311ca9460956281/custom_components/llm_intents/play_media.py) 改为每个实例构造参数，接收 LLMContext | 1.11.1 只发现暴露给当前 assistant 的、有 PLAY_MEDIA 的 tv/receiver；entity_id、区域和单播放器回退均受该集合限制。device_id 从原生 Schema/执行路径移除；静态 Function 同步移除，旧版原生设备直通保持兼容 |
| [API 实例构造](https://github.com/skye-harris/llm_intents/blob/5d2e76d72564fe378f32870bd311ca9460956281/custom_components/llm_intents/llm_functions.py) 将 LLMContext 交给工具 | Bridge 原有公开 API 获取方式适用，管理员 Context 和 conversation assistant 不变；不导入上游私有实现，也不缓存工具实例 |
| [SearXNG 编码](https://github.com/skye-harris/llm_intents/blob/5d2e76d72564fe378f32870bd311ca9460956281/custom_components/llm_intents/searxng_search.py) 使用独立 HTTP params | 中文、空格、&、+、?、#、% 等保持为一个 q 参数；Bridge 保持原查询透传，不双重编码；四种搜索及筛选字段身份不变 |
| [缓存](https://github.com/skye-harris/llm_intents/blob/5d2e76d72564fe378f32870bd311ca9460956281/custom_components/llm_intents/cache.py) 从 SQLite 改为共享内存 | 上游默认 TTL 仍为 7200 秒，按工具和参数区分，进程重启后清空；Bridge 不访问其私有缓存、不新增缓存。每次调用仍检查当前权限，已有缓存不能绕过禁用/白名单 |
| [HA HTTP 客户端](https://github.com/home-assistant/core/blob/357cae5c598dfcd7a0ea7dc5b1facccd4ec6037b/homeassistant/helpers/aiohttp_client.py) 默认响应行/字段上限增至 64 KiB | Bridge 高德客户端通过公开 async_get_clientsession 自动使用新行为；原有单请求 10 秒、响应体 256 KiB、结果 16 KiB 等预算不变 |

HA 2026.10.2 → 2026.10.4 的 14 个相关固定源码文件逐字节比对：LLM、服务核心、配置项、用户/认证、脚本、选择器、服务、翻译、初始化、OpenAI 转换及 Home Assistant 的 LLM/暴露管理共 13 文件一致；只有 aiohttp_client 增加响应头限制设置。LLM ToolResult、原始管理员和 probatio 转换契约不变，无需修改网关、服务注册、权限、Schema 或 payload。

## 迁移与兼容边界

1. 通过各自更新机制更新 Bridge、Tools for Assist 和 HA；本项目不会修改用户安装或替其他集成升级。
2. 手动替换 EOAIC2 中 [calculate](../examples/eoaic2_calculate.yaml) 和 [play_video](../examples/eoaic2_play_video.yaml) 的完整列表项，不能追加同名 Function；HACS 不自动改写 Functions。
3. 表达式中的幂改用 **，函数/常量和 // 不再属于 Bridge 语法；需要表达式外的 min/max/avg 时使用对应 operation。保留数字字符串、原生返回和全部既有预算。此共同语法同样适用于旧 1.11.0，不能靠旧提供商放宽限制。
4. 1.11.1 播放目标改用 entity_id 数组或 area，在 HA 的 Assist 设置中明确暴露设备；通过 describe_tool 查看当前动态实体。无设备占位值不是可播放实体。1.11.0 不具备同等暴露过滤，本项目不替旧上游添加该能力；其旧 device_id 只保留原生通用调用回归，新独立 Function 不暴露。

仍要求原始有效管理员、网关开启、精确白名单及播放单独副作用许可；管理员不会自动获得被新上游隐藏的播放器。原生播放器下游调用仍未传递原始服务 Context，不宣称身份贯穿播放服务。命令成功不证明实际播放，outcome_unknown=true 时不自动重试。

高德、Google 直通、其他工具与四服务保持原样；高德摩托车和未来驾车继续排除，仅公交可用未来时间。不新增 Home Control、工具生成器、生产依赖或上游修改分支。

## 验证记录

新旧发布版本分别执行原版 API/Schema/方法与原版 EOAIC2 ScriptFunction，提供商 HTTP 与媒体播放均模拟。新增验证特殊字符编码、真实上游内存缓存及权限、缓存 TTL/参数隔离、执行器只计算一次、无浮点结果重算、未暴露播放器的实体/区域/默认路径拒绝及新旧设备参数差异。原有大结果裁剪和管理员/白名单/副作用回归保留。完整结果与 CI 见 [TESTING.md](TESTING.md) 及 [v0.8.2 Release](https://github.com/qiqi20020612/eoai-tools-bridge/releases/tag/v0.8.2)。

本次没有新增真实提供商调用、用户 HA/模型/物理播放器或 HACS 安装验收。固定源兼容测试不能替代这些证据，继续按 [0.x 路线](TOOLS_COMPATIBILITY.md#剩余-0x-工作与-10-门槛) 推进。
