# 测试记录和手工验收

记录日期：**2026-10-09（Asia/Shanghai）**。开发测试使用独立虚拟环境，未连接或修改用户的 Home Assistant。用户报告的真实验收与开发者执行的自动化检查分别记录。

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

## v0.3.0 尚待实际运行验收

以下需要在实际 HA 2026.10.x、Tools for Assist 和 EOAIC2 环境执行。v0.2.0 的用户验收不覆盖新接口，模拟测试和仓库校验不替代真实验收。

- [ ] 从 v0.2.0 更新并重启 HA，已有配置项加载、三个动作可见，`search_web`、`list_tools` 和原有设备控制 Functions 正常。
- [ ] 升级后 `call_tool` 返回 `gateway_disabled`；管理员在集成选项中启用 `llm_intents/search_web` 后，开发者动作返回真实正文；关闭开关或删除白名单立即阻止后续调用。
- [ ] 非管理员或没有用户身份的自动化/语音 Context 返回 `permission_denied`，白名单外工具返回 `tool_not_allowed`，错误参数不能执行上游工具。
- [ ] 对实际所需的其他只读工具验证原生参数及响应；未声明或写入工具在未开副作用许可时被拒绝。若需要副作用验收，选用可恢复操作并核对实际状态和调用次数。
- [ ] 可选追加 `examples/eoaic2_call_tool.yaml` 后，有管理员 Context 的 EOAIC2 调用能读取 `_function_result`；无用户 Context 时明确失败，原有搜索可独立使用。
- [ ] 卸载和重载后的拒绝/恢复正常，没有重复注册；实际出现 `outcome_unknown=true` 时先核对状态，避免重复操作。

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
