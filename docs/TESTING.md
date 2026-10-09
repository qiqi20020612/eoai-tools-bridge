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

安装 ZIP 已检查：31 个文件与工作区逐字节一致，Manifest、项目及锁文件版本一致，JSON 元数据与 SHA-256 正确，无开发环境、测试源码、上游源码或缓存。

实现提交 `7fd8bcd46bce3ca763fef9cca3e03b3f6fd28819` 的 [v0.4.0 GitHub CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37957598006) 全部通过：Ubuntu 的 **274 项测试**、Ruff、固定上游源码验证及安装包构建通过，官方 Hassfest 及 HACS 全部 9 项检查通过。后续发布记录仅修改文档；最终发布提交、CI 与安装资产见 [v0.4.0 Release](https://github.com/qiqi20020612/eoai-tools-bridge/releases/tag/v0.4.0)。

## v0.4.0 真实验收记录

**用户报告通过。** 用户明确回复“验收通过。继续下一个版本，注意1.0版本之前要兼容 Tools for Assist 支持的所有工具。”据此接受 v0.4.0 总体验收结论；没有逐项证据，不补写具体后端、设备、TTS 或 HACS 更新的单项结果。最终发布提交 `db574ee4065652449ef71055abb908b0ca171fa2` 的 [CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37958021421) 已通过；标签与资产保留。

以下保留原定手工验收用例供追溯，不作为逐项通过证据：

- 通过 HACS 或 Release ZIP 从 v0.3.0 更新并重启 HA，四个动作可见；已有白名单、通用调用开关与副作用许可保持原值，三个既有动作及设备控制 Functions 正常。
- 管理员调用 `check_tools` 获得实际白名单的状态；关闭 `call_tool` 时返回 `gateway_disabled`，检查自身不启用任何许可，也不产生实际工具调用。
- 开启后，已配置搜索工具显示 `ready`；禁用上游工具或 API 后反映 `tool_unavailable` 或 `api_unavailable`，不使用旧实例。`ready` 与真实后端及参数验证区分清楚。
- 原始有效管理员限制正常；普通用户或无用户 Context 返回 `permission_denied`，错误入参被 HA 拒绝。
- 可选追加 `examples/eoaic2_check_tools.yaml` 后，管理员 Context 能读取 `_function_result`；模型依据各条目状态回答，不把顶层 success 当作全部可用，也不根据检查结果扩大授权。
- 卸载/重载后的拒绝及恢复正常；观察上游日志确认检查未触发搜索或副作用工具。

记录验收证据时可附 HA、Tools for Assist、EOAIC2 的版本、动作响应、实际函数调用及升级方式；按原有隐私策略处理查询和日志。


## v0.5.0 已执行的自动化检查

使用相同固定依赖：Python 3.14.6、HA Core 2026.10.0、`pytest-homeassistant-custom-component==0.13.371`，无新增生产或开发第三方依赖。锁文件仅更新项目版本为 0.5.0。

本地结果：**345 passed，0 skipped**。其中 **25 项**运行原版 EOAIC2 ScriptFunction，**46 项**带 Tools for Assist 源码契约标记（两类重叠 **2 项**，不能直接相加）；另有参数元数据视图与权限回归。Ruff 静态及格式检查通过。完整源码覆盖清单见 [TOOLS_COMPATIBILITY.md](TOOLS_COMPATIBILITY.md)。

Tools for Assist 使用固定提交 `100e740b93a2a1a6d304329883937193a4571ac0` 的 20 个原版文件，在导入前逐个验证 SHA-256。运行 11 个查询实现的原版参数 Schema 与方法，覆盖 9 个确切 API/工具组合。入口清单同时确认计算器、媒体播放及 Home Control 的动态聚合，未据 AST 盘点宣称这些剩余工具的实际调用通过。

| 范围 | 自动化证据 |
| --- | --- |
| 查询工具 | 三种网页搜索变体，以及地点、路线、维基百科、YouTube、天气、单位换算、日期和历史工具的 Schema、只读目录和就绪状态；错误参数阻止原版方法执行 |
| 原版执行 | 地点/路线/维基百科/YouTube 使用模拟 HTTP JSON，网页搜索数据、天气、Recorder 数据模拟；执行原版查询方法和结果处理。单位换算和日期执行原版计算代码 |
| 类型与数据 | 保存分数字符串及整数日期、路线嵌套结果、YouTube 链接、天气文本、历史统计/状态采样，丢弃原版工具追加的指令；2 项同时使用原版 EOAIC2 脚本和原版实用工具 |
| 默认值与约束 | 普通 Optional 默认值发现时不求值，原生调用求值一次；保留枚举、整数范围、Required、额外键策略、嵌套/分组约束；不重新编译自定义校验器，不修改原版 Schema |
| 拒绝与预算 | 必填/分组默认值和未知 Marker 子类拒绝发现且不求值，循环/深度/节点在转换前受限；9 个原版查询组合的完整目录和检查响应均在 16 KiB 内 |
| 授权回归 | 审核不自动授予访问权限，追加工具仍要求精确白名单和原始有效管理员；审核来源限定 Tools for Assist，上游显式危险声明不会被覆盖，未知控制工具仍需副作用许可 |
| 既有行为 | 原有搜索、受控调用、默认搜索清单和不执行参数逻辑的就绪检查保持通过；四个动作、选项、升级生命周期及中英文描述持续验证 |

安装 ZIP 已核对：34 个文件逐字节匹配工作区，项目、锁文件和 Manifest 均为 0.5.0，JSON 与 SHA-256 校验正确，不含测试、上游源码、开发环境、缓存或凭据。8 个新增动作示例均通过原版工具 Schema 校验。GitHub CI 和最终发行记录在实际完成后补充。

模拟数据与原版契约不代表真实联网、用户的 HA、实际 Assist/模型/TTS、Recorder 或物理设备已验收。

## v0.5.0 尚待实际运行验收

- [ ] 从 v0.4.0 经 HACS 或 Release ZIP 更新并重启；原有四个动作和已保存选项正常，既有搜索/设备控制 Functions 保持可用。
- [ ] 在 Tools for Assist 中逐项启用所需查询工具并完成其后端配置；在桥接中逐项加入确切组合并开启通用调用，副作用许可关闭时管理员能通过目录、检查和实际调用使用这些查询工具。
- [ ] 验证地点、路线、维基百科、YouTube、天气、单位换算、日期、实体历史的实际参数和响应；注明实际启用范围、环境缺项及版本，不能用工具类型就绪替代后端成功。
- [ ] YouTube 省略数量时默认 1，显式数量 1–25 生效，26 被拒绝；发现/检查不发起实际查询，默认工厂不在元数据发现时运行。
- [ ] 原始管理员限制、未加入白名单、关闭通用调用或撤销许可的拒绝正常；计算器、播放和未知工具仍按独立副作用许可处理。
- [ ] EOAIC2 使用现有清单和 `call_allowed_tool` 示例获取实际查询结果；分数字符串、整数日期、天气文本和历史数据通过 `_function_result` 返回，实际模型选择工具的行为另行记录。

1.0 前的全工具验收门槛单独维护在 [TOOLS_COMPATIBILITY.md](TOOLS_COMPATIBILITY.md)，未完成的计算器、媒体播放、动态控制/脚本与计时器继续通过后续 0.x 补齐。

## 可复现命令

```sh
uv sync --locked --group dev --python 3.14
uv run --no-sync python scripts/fetch_test_upstream.py
uv run --no-sync python scripts/fetch_tools_upstream.py
uv run --no-sync pytest -q --timeout=30
uv run --no-sync ruff check custom_components tests scripts
uv run --no-sync ruff format --check custom_components tests scripts
uv run --no-sync python scripts/build_release.py
```

生产集成不读取或修改 `.cache/upstream/`。上游源码下载只用于开发测试，安装 ZIP 排除 `.venv`、上游源码、测试文件和所有开发缓存。
