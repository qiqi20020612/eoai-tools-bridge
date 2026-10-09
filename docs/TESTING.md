# 测试记录和手工验收

记录日期：**2026-10-10（Asia/Shanghai）**。开发测试使用独立虚拟环境，未连接或修改用户的 Home Assistant。用户报告的真实验收与开发者执行的自动化检查分别记录。

## v0.1.0 验收记录

**真实验收：用户报告通过。** 用户在当前开发对话中明确回复“验收通过。继续下一个版本”。本记录据此接受 v0.1.0 的验收结论；用户未提供环境版本或逐项证据，不补写具体 Brave/SearXNG、TTS 或 HACS 更新的单项结果。

**历史自动化结果：80 passed，0 skipped**，包含 **9 项**固定提交的原版 EOAIC2 ScriptFunction 契约测试。Ruff、安装 ZIP 检查通过；[v0.1.0 最终提交的 GitHub CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37909206602) 通过 Ubuntu 测试、Home Assistant 官方 Hassfest 和官方 HACS action（全部 9 项仓库检查）。

发布版本：[v0.1.0](https://github.com/qiqi20020612/eoai-tools-bridge/releases/tag/v0.1.0)，提交 `01a18464f66cc386f1372978593c3b14a741fe3b`。该版本的标签和安装包保留不变。

## v0.2.0 验收记录与自动化检查

**真实验收：用户报告通过。** 用户明确回复“仓库公开了。验收通过。继续下一个版本”。据此接受 v0.2.0 的验收结论；未提供逐项证据，不补写具体搜索后端、TTS 或 HACS 安装更新的单项结果。

- Python **3.14.6**，HA Core **2026.10.0**，`pytest-homeassistant-custom-component==0.13.371`。
- EOAIC2 契约测试使用提交 `b0274f752fc01495875522db9281c335af8cf484` 的原版脚本相关文件，经过 SHA-256 验证。
- 搜索返回、API 元数据、故障和超时使用模拟对象；HA 服务、配置流、Context、LLM 注册/调度、probatio Schema 转换及 Script 执行使用真实实现。
- pytest 禁止网络访问，不能把测试中的元数据、标题、摘要或链接当作真实环境数据。

本地结果：**124 passed，0 skipped**，其中 **11 项**执行原版 EOAIC2 ScriptFunction（原有 9 项搜索测试及 2 项可选清单 YAML 测试）。Ruff 静态检查与格式检查通过；`uv.lock` 只更新本项目版本，第三方依赖版本保持原样。

提交 `469e3ea45f2fde2a03e0764ce52bd70784666d58` 的 [首次 v0.2.0 CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37945161517) 中，Ubuntu 的 **124 项测试**、Ruff、固定上游源码校验及 ZIP 构建通过，官方 Hassfest 通过。Hassfest 提示缺少 CONFIG_SCHEMA，现已补充 HA 的公开 `config_entry_only_config_schema` 声明，并重新通过本地全部测试。

补齐 CONFIG_SCHEMA 后，提交 `e4d9ff59b57cdffe452476f65145cb4d1a6ee2c1` 的 [CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37946199193) 再次通过 Ubuntu 测试和官方 Hassfest。后续发布记录仅修改文档，不改变已验证的集成或测试代码。

v0.2.0 发布时仓库为私有，HACS 校验历史结果为 **7/9 项通过、2 项失败**，原因是匿名读取 hacs.json 和 manifest 得到 404。当时按用户要求保留标准 GitHub Release、安装 ZIP 和 HACS 校验流程。[HACS 不支持私有仓库](https://www.hacs.xyz/docs/faq/private_repositories/)。

开发 v0.3.0 前已通过 GitHub API 确认仓库公开，并重新运行 v0.2.0 最终提交 `33fcd972991bdbd208f05c66b2397468483d83c5` 的失败任务。[最终提交的 CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37947283190) 现已全部通过：原有 Ubuntu 测试和 Hassfest 通过，HACS 在仓库公开后的重跑中通过。发布版本为 [v0.2.0](https://github.com/qiqi20020612/eoai-tools-bridge/releases/tag/v0.2.0)，标签与资产保留不变。

| 范围 | 自动化覆盖 |
| --- | --- |
| 原有搜索回归 | 原有输入边界、固定调用、搜索结果和错误处理、Context、取消/超时、输出限制及脚本 YAML 持续通过 |
| 清单调用边界 | 无入参、必须接收响应、不打开白名单外的 API、不执行任何工具、保留原始 Context 和语言 |
| 只读限制 | 固定 API/工具白名单、未声明搜索工具的审核依据、显式不安全声明排除、只读声明不扩大白名单、重复名称遵循 HA 的首项匹配 |
| 动态发现 | API 注册/注销、工具启用/禁用、提供商参数变化和可选 freshness，不使用旧实例缓存 |
| Schema 与隐私 | 公开转换器与自定义序列化钩子、严格拒绝无法表示的校验器、默认值工厂不执行、去除默认值/示例/扩展字段、不返回 API prompt 或配置 |
| 数据限制与故障 | 非 JSON 值、无效 Unicode、非对象 Schema、深度/节点/字节限制、描述截断、API 故障/超时及取消传播、异常原文不进入响应或桥接日志 |
| 生命周期与接线 | 两个动作均只注册一次，缺失动作单独补注册，卸载/重载/删除后的清单行为，原版 EOAIC2 ScriptFunction 返回清单 _function_result |
| 元数据 | HA 运行时英文和中文动作描述、服务响应要求、交付 YAML 与 README 搜索示例一致 |

## v0.3.0 已执行的自动化检查

使用与 v0.2.0 相同的固定依赖、HA 2026.10.0 和原版 EOAIC2 源码快照。本地结果：**225 passed，0 skipped**，其中 **19 项**执行原版 EOAIC2 ScriptFunction：原有 11 项搜索/清单契约测试及 8 项受控调用的类型、身份和失败响应测试。Ruff 静态与格式检查通过，第三方依赖版本未变。

HA 的配置项、选项流、认证存储中的真实用户、服务 Schema、Context、LLM 注册/调度和 Script 使用真实实现；工具正文、实际改变、网络、故障和超时为模拟对象。未连接用户的 HA 或修改任何上游安装目录。

| 范围 | 自动化覆盖 |
| --- | --- |
| 升级与授权 | 升级后默认关闭、空白名单不授予权限、32 项精确 API/工具组合、拒绝通配符/模板/无效标识，损坏的存储选项关闭调用 |
| 原始身份 | 认证存储的有效管理员、拒绝缺失/伪造/普通/停用用户，保留原始 Context，禁止请求传入权限字段，API 不能替换管理员身份 |
| 副作用许可 | 未声明、写入或破坏性工具要求独立许可，许可仍受逐项白名单限制，只读声明不扩大授权，重复名称遵循 HA 首项匹配 |
| 原生参数 | probatio Schema、枚举与额外字段、默认值工厂仅在授权后运行一次、无参工具、校验后的 JSON 对象检查、搜索长度与可选 freshness；执行前工具、Schema 或只读依据变化时拒绝派发 |
| 撤销与生命周期 | API 获取后及参数校验后再次检查管理员和权限快照，撤销/停用/卸载阻止执行，保存选项立即生效，三个动作独立补注册、不缓存 API |
| 执行失败 | 取得 API 或执行超时、业务错误、异常结构、取消传播；最多执行一次，副作用工具派发后的失败标记 outcome_unknown |
| 输入与输出 | JSON 类型、有限数值、Unicode、8 KiB 入参、深度/节点限制、16 KiB 响应、容器与文本截断、递归去除已知指令与凭据字段，不输出异常原文 |
| 清单与兼容 | 默认搜索清单兼容；仅管理员可发现明确启用的额外只读工具，异步获取后重查权限，副作用许可不使写入工具进入清单；原有搜索回归持续通过 |
| EOAIC2 与元数据 | 三个完整 YAML 的原版脚本执行、字面模板字符串与参数类型、管理员 Context、无用户语音 Context 的明确拒绝、中英文动作描述与 UI 选择器 |

安装 ZIP 已检查：28 个文件与工作区源文件逐字节一致，版本与项目/锁文件一致，JSON 元数据和 SHA-256 正确，无开发环境、测试、上游源码或缓存。

实现提交 `0765342c3a2704e005be507ed901db1039d1c3b0` 的 [v0.3.0 GitHub CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37953250305) 全部通过：Ubuntu 执行 **225 项测试**、Ruff、上游源码校验及安装包构建通过，官方 Hassfest 和 HACS action 通过。后续发布记录只修改文档，不改变集成或测试代码；最终发布提交与 CI 见 [v0.3.0 Release](https://github.com/qiqi20020612/eoai-tools-bridge/releases/tag/v0.3.0)。

## v0.3.0 真实验收记录

**用户报告通过。** 用户明确回复“验收通过。继续下一个版本，注意继续小版本迭代，不能直接开发1.0。”据此接受 v0.3.0 的验收结论。没有环境版本或逐项证据，不补写具体后端、副作用操作、TTS 或 HACS 更新的单项通过记录。v0.3.0 标签和发行资产保持不变。

## v0.4.0 已执行的自动化检查

使用原有固定依赖：Python 3.14.6、HA Core 2026.10.0、`pytest-homeassistant-custom-component==0.13.371`。本地结果：**274 passed，0 skipped**，其中 **23 项**执行固定提交的原版 EOAIC2 ScriptFunction。新增 4 项检查 YAML 契约测试，覆盖管理员/无用户 Context 与通用调用开关的组合；原有 19 项契约测试继续通过。Ruff 静态及格式检查通过，锁文件只更新本项目版本。

HA 服务注册/校验、配置项、认证用户、Context、LLM 注册表/APIInstance 和 Script 使用真实实现；API 元数据、工具执行、副作用、网络和故障使用模拟对象。没有连接用户的 HA 或修改任何上游安装目录。

| 范围 | 自动化覆盖 |
| --- | --- |
| 管理员边界 | 拒绝无身份/未知/普通/停用用户，不暴露选项或白名单，不读取对应 API；原始 Context、语言与无伪造设备身份 |
| 检查范围 | 无入参、必须接收响应、仅检查确切白名单；关闭通用调用仅查询注册表，空白名单不授予权限；每 API 获取一次，不读取未批准 API |
| 不执行 | 原生工具调度、参数校验器、默认值工厂、自定义序列化钩子及 probatio 转换器均未调用，选项保持原值 |
| 状态与安全 | 当前注册/工具/Schema 类型、副作用许可、未声明/写入/破坏性工具、审核搜索依据、重复名称遵循首项匹配 |
| 故障与撤销 | 单个 API 故障不阻断其他 API 的状态，原始身份变化、停用、撤销、卸载和元数据读取时撤权丢弃结果；总体超时丢弃部分结果，取消传播 |
| 隐私与预算 | 不输出标题/描述/API prompt/私有配置/异常原文，完整 32 项最长标识仍在 16 KiB 内；预算不足时省略完整条目，不截断标识 |
| 升级与接线 | 原有测试持续通过，四个动作只注册一次、单个缺失动作单独补注册，卸载/重载/删除和动态元数据变化不缓存；原版 EOAIC2 检查 YAML 及中英文动作描述 |

安装 ZIP 已检查：31 个文件与工作区逐字节一致，Manifest、项目及锁文件版本一致，JSON 元数据与 SHA-256 正确，无开发环境、测试源码、上游源码或缓存。本版本 GitHub CI 尚待提交后运行；不沿用 v0.3.0 的结果作为 v0.4.0 的通过依据。

## v0.4.0 尚待实际运行验收

- [ ] 通过 HACS 或 Release ZIP 从 v0.3.0 更新并重启 HA，四个动作可见；已有白名单、通用调用开关与副作用许可保持原值，三个既有动作及设备控制 Functions 正常。
- [ ] 管理员调用 `check_tools` 获得实际白名单的状态；关闭 `call_tool` 时返回 `gateway_disabled`，检查自身不启用任何许可，也不产生实际工具调用。
- [ ] 开启后，已配置搜索工具显示 `ready`；禁用上游工具或 API 后反映 `tool_unavailable` 或 `api_unavailable`，不使用旧实例。`ready` 与真实后端及参数验证区分清楚。
- [ ] 原始有效管理员限制正常；普通用户或无用户 Context 返回 `permission_denied`，错误入参被 HA 拒绝。
- [ ] 可选追加 `examples/eoaic2_check_tools.yaml` 后，管理员 Context 能读取 `_function_result`；模型依据各条目状态回答，不把顶层 success 当作全部可用，也不根据检查结果扩大授权。
- [ ] 卸载/重载后的拒绝及恢复正常；观察上游日志确认检查未触发搜索或副作用工具。

记录验收证据时可附 HA、Tools for Assist、EOAIC2 的版本、动作响应、实际函数调用及升级方式；按原有隐私策略处理查询和日志。

## 可复现命令

```sh
uv sync --locked --group dev --python 3.14
uv run --no-sync python scripts/fetch_test_upstream.py
uv run --no-sync pytest -q --timeout=30
uv run --no-sync ruff check custom_components tests scripts
uv run --no-sync ruff format --check custom_components tests scripts
uv run --no-sync python scripts/build_release.py
```

生产集成不读取或修改 `.cache/upstream/`。上游源码下载只用于开发测试，安装 ZIP 排除 `.venv`、上游源码、测试文件和所有开发缓存。
