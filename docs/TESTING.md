# 测试记录和手工验收

初始记录日期：**2026-10-10（Asia/Shanghai）**；最新记录 **2026-10-20 / v0.7.2**。开发测试使用独立虚拟环境，未连接或修改用户的 Home Assistant。自动化、独立提供商联网验证与用户环境验收分别记录；下文旧版本记录保留当时状态。

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

安装 ZIP 已核对：34 个文件逐字节匹配工作区，项目、锁文件和 Manifest 均为 0.5.0，JSON 与 SHA-256 校验正确，不含测试、上游源码、开发环境、缓存或凭据。8 个新增动作示例均通过原版工具 Schema 校验。实现提交 `1691474db993b7ed8f2b1ca18361eb1dc7c05d22` 的 [v0.5.0 GitHub CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37962653112) 全部通过：Ubuntu 执行 **345 项测试**、Ruff、两套固定上游源码校验及安装包构建通过，官方 Hassfest 通过，HACS 的全部 **9 项**仓库检查通过。后续发布记录仅更新文档；最终提交、CI 和资产见 [v0.5.0 Release](https://github.com/qiqi20020612/eoai-tools-bridge/releases/tag/v0.5.0)。

模拟数据与原版契约不代表真实联网、用户的 HA、实际 Assist/模型/TTS、Recorder 或物理设备已验收。

## v0.5.0 尚待实际运行验收

以下是 v0.5 发布时的历史验收清单，未取得通过报告。v0.6 以后以当前兼容清单为准：Home Control 退出范围，计算器改用有限数值校验，不再要求副作用许可。

- [ ] 从 v0.4.0 经 HACS 或 Release ZIP 更新并重启；原有四个动作和已保存选项正常，既有搜索/设备控制 Functions 保持可用。
- [ ] 在 Tools for Assist 中逐项启用所需查询工具并完成其后端配置；在桥接中逐项加入确切组合并开启通用调用，副作用许可关闭时管理员能通过目录、检查和实际调用使用这些查询工具。
- [ ] 验证地点、路线、维基百科、YouTube、天气、单位换算、日期、实体历史的实际参数和响应；注明实际启用范围、环境缺项及版本，不能用工具类型就绪替代后端成功。
- [ ] YouTube 省略数量时默认 1，显式数量 1–25 生效，26 被拒绝；发现/检查不发起实际查询，默认工厂不在元数据发现时运行。
- [ ] 原始管理员限制、未加入白名单、关闭通用调用或撤销许可的拒绝正常；计算器、播放和未知工具仍按独立副作用许可处理。
- [ ] EOAIC2 使用现有清单和 `call_allowed_tool` 示例获取实际查询结果；分数字符串、整数日期、天气文本和历史数据通过 `_function_result` 返回，实际模型选择工具的行为另行记录。

v0.5 当时的后续计划包含计算器、媒体播放及 Home Control 动态工具；用户随后取消 Home Control。当前非 Home Control 的 1.0 门槛维护在 [TOOLS_COMPATIBILITY.md](TOOLS_COMPATIBILITY.md)，不再要求动态控制/脚本或计时器。

## 2026-10-19：上游 Tools for Assist 1.11.0 兼容核对

以下记录独立上游核对阶段，桥接当时仍为 **v0.5.0**，运行代码、Manifest、项目版本及依赖锁文件均未变更；不代表后续 v0.6 的发布状态。1.11.0 固定提交 `198e37885fe06e6452d2d6e26bc5e532b1686acc` 的 22 个原版文件独立缓存并验证 SHA-256，原 20 文件基线保留。

本地 **362 passed，0 skipped**（原 345 项及新增 **17 项**原版 Tavily/HA 契约），Ruff 静态和格式检查通过。测试使用固定 Python 3.14.6、HA Core 2026.10.0 和原锁定依赖；HTTP、缓存模拟，没有使用真实 Tavily 密钥或连接用户 HA。详细覆盖与结论见 [1.11.0 兼容核对](TOOLS_FOR_ASSIST_1_11_0.md)。

此次未发布兼容补丁或新的 Release，也未重新运行远程 CI。现有 v0.5.0 的历史 345 项 CI 与本次本地 362 项结果分别记录；v0.5.0/1.11.0 的真实集成验收仍待进行，未将用户先前的 v0.4.0 验收扩大到新组合。


## v0.6.0 已执行的自动化检查

范围依据用户本次决定更新：放弃 Home Control API，原生 HA 控制由 EOAIC2 承担。当前只声明四个非 Home Control API 的工具兼容，保留历史行为的回归测试供兼容；未因用户要求继续开发而记录 v0.5 实际验收通过。

本地完整结果：**443 passed，0 skipped**。其中 **28 项**执行原版 EOAIC2 ScriptFunction，**119 项**带 Tools for Assist 源码契约标记（两类重叠 **5 项**，不可直接相加）。使用 Python 3.14.6、HA Core 2026.10.0、probatio 0.13.0 与固定上游源码；新增开发依赖 SymPy 1.14.0 / mpmath 1.3.0，生产 Manifest 仍无新增 pip 依赖。Ruff 静态与格式检查通过。

| 范围 | 自动化证据与边界 |
| --- | --- |
| 全部当前工具入口 | 原版 1.11.0 的 SearchAPI、WeatherAPI、BasicUtilitiesAPI 和 MediaAPI 实际实例化；全启用工具恰好为 10 个确切组合，目录为 9 个已审核只读工具；全部 10 项参数描述成功，播放在关闭许可时就绪状态为 side_effects_blocked |
| 参数描述 | 原始有效管理员、启用和精确白名单；未开放播放许可也能查看参数，执行仍被拒绝；不运行工具、参数校验器或默认工厂；权限/身份/Schema/只读依据/序列化器变化、固定错误、10 秒异步超时、取消和不返回部分元数据 |
| 计算器 | 原版 API、选择器、SymPy 表达式与 min/max/avg；保留数值字符串与原始 Context；有限 AST/数字/指数/深度/节点/项目数检查，空输入、代码、非有限值和超出预算在原版方法前拒绝；结果由原版工具产生 |
| 媒体 | 真实 HA 注册表/状态和原版动态实体选择器；显式实体数组、区域、设备及单设备回退；动态枚举随实体删除刷新；非法参数不调度；歧义目标、服务失败和执行中超时最多调用一次，outcome_unknown=true，不重试 |
| EOAIC2 接线 | 原版 ScriptFunction 执行参数描述 YAML，以及原版计算器和播放工具通用调用；全 data 字典模板、原始 Context 和 _function_result 正常；播放只触发模拟 HA 服务 |
| 1.11.0 回归 | 固定旧 20 文件与新 22 文件的 SHA-256；包含 Tavily 17 项原版契约，HTTP/缓存模拟；原有搜索/查询、就绪、目录、配置及五个响应专用动作的生命周期通过 |

本地安装 ZIP 内容核对通过：41 个文件逐字节匹配工作区；项目、锁文件和 Manifest 均为 0.6.0，中英文 JSON、ZIP 完整性及 SHA-256 文件正确，未包含测试、上游源码、缓存或开发环境。EOAIC2 4 个、Tools for Assist 两套共 42 个固定文件的获取/校验流程通过。

实现提交 `9032523117ef7f0c1a3af0ea45e831f29b6c647c` 的 [v0.6.0 CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/39260447158) 全部通过：Ubuntu 执行 **443 项测试，0 skipped**，Ruff、固定源码验证及安装包构建通过；官方 Hassfest 通过，HACS 的全部 **9 项**仓库校验通过。后续发布记录及 EOAIC2 示例说明更新保持脚本接线不变；最终提交、CI 与资产见 [v0.6.0 Release](https://github.com/qiqi20020612/eoai-tools-bridge/releases/tag/v0.6.0)。

**媒体已知限制如实记录：**原版播放工具取得管理员 LLMContext，却未在下游播放服务调用中传入 Context。测试确认模拟服务 user_id 为空，未修补上游或 HA Core。入口权限仍由桥接检查；真实设备需单独确认这一行为。SymPy 与其他上游同步代码仍须正常返回，异步超时不构成同步 CPU 抢占。

## v0.6.0 尚待实际运行验收

- [ ] 经 HACS 或 Release ZIP 更新并重启，五个动作可见；原有选项、搜索及 EOAIC2 原生 HA 控制 Functions 正常。
- [ ] 在 Tools for Assist 1.11.0 中启用实际所需查询工具并配置后端，逐项验证当前范围工具，记录环境版本、清单、参数与结果；原版模拟契约不代替此项。
- [ ] 管理员明确允许 basic_utilities/calculate，副作用许可关闭时可以描述、检查及计算 expression/min/max/avg；数值限制外输入返回 invalid_args。
- [ ] 管理员明确允许 media_services/play_video；关闭执行许可时能描述动态参数但不能播放；许可开启后通过真实实体/区域/设备目标及单设备回退播放，记录上游 Context 限制；失败后先核对实际设备，不重复触发。
- [ ] EOAIC2 的 describe_allowed_tool 与 call_allowed_tool 在真实对话中传回 _function_result，模型按返回的参数和限制调用；未授权、非管理员和撤销权限仍拒绝。
- [ ] Home Control 不再列入本项目验收；实际回归 EOAIC2 原生设备控制路径。

当前只完成开发模拟/契约检查，未连接用户 HA、使用真实密钥或操作物理播放器。实际联网、模型、Assist/TTS、安装更新和重启均另行验收；1.0 门槛继续保留在兼容清单。


## 2026-10-19：当前 HA 基准升级到 2026.10.2

按用户要求升级开发、源码核对及 CI 基准。`pyproject.toml` 明确固定 `homeassistant==2026.10.2` 与 `pytest-homeassistant-custom-component==0.13.373`，`uv.lock` 同步更新；本地通过 `uv sync --locked --group dev --python 3.14` 安装，实际环境读出的版本与约束一致。CI 新增基准报告步骤，显示实际 HA 与测试插件版本。

锁定的 174 个包中，仅三个包升级：HA Core 2026.10.0 → 2026.10.2、配套测试插件 0.13.371 → 0.13.373、aiohttp 3.14.4 → 3.14.5。Python 3.14.6、probatio 0.13.0、EOAIC2 与 Tools for Assist 固定快照保持原基准。11 个相关 HA 源码文件逐项比对及公开接口结论见 [UPSTREAM.md](UPSTREAM.md)。

本地完整回归：**443 passed，0 skipped**，其中原版 EOAIC2 ScriptFunction 28 项、Tools for Assist 标记契约 119 项（重叠 5 项）。Ruff 静态与格式检查通过。既有五个动作、原始管理员、白名单、副作用许可、参数/结果边界、计算器与播放契约均通过原有检查。

本次是当前开发基准更新，已有 v0.6.0 发布记录继续记载最初使用的 HA 2026.10.0。HACS 的 `homeassistant` 字段仍表示最低安装版本 2026.10.0，依据已发布版本的兼容范围；当前自动化精确使用 2026.10.2。Home Control 的范围决定、真实环境验收状态及已发布标签/附件均按各自记录维护。

测试运行在项目隔离开发环境，HTTP、天气和 HA 播放服务模拟；没有修改用户实际 HA、EOAIC2 或 Tools for Assist 的安装文件，也没有连接用户 HA、真实联网搜索或操作物理播放器。HA 2026.10.2 的真实安装、对话、Assist/TTS 和设备行为尚待实际验收。


## v0.6.1：通用工具大结果裁剪修复

**用户提供的真实故障证据：**v0.6.0 固定 search_web 正常，call_tool 调用 llm_intents/search_web 带或不带 freshness 均返回 success=true、result={}、truncated=true。该报告不构成 v0.6.0 总体验收通过，也未提供本次修复后的实际复测结果。

根因在 payload.py 的最终总字节预算循环：先完成单项/文字/节点裁剪后，响应仍超 16 KiB 时直接对顶层对象调用 popitem；搜索正文在过滤 instruction 后常只剩 results，整个结果集因此被删掉，成功标记未变。旧 Unicode 预算测试只验证 success/truncated 和字节上限，没有验证仍有结果，漏检此故障。

修复保留顶层字段，递归处理较大的嵌套数据，先减少数组尾项，单项仍过大时继续裁短文本或必要的嵌套对象字段，不删除最后一个条目/字段来伪造空结果。文字保留原始前缀与省略号，按实际 UTF-8 JSON 大小计算引号与转义开销。顶层空对象（含敏感字段过滤后为空）及无法满足预算的负载返回固定 invalid_response 和 result=null；执行过的副作用调用仍按原契约设置 outcome_unknown。原始数据不被修改，合法空结果数组及零值/布尔值保持兼容。

在 HA Core **2026.10.2**、测试插件 **0.13.373**、Python 3.14.6 与原固定依赖上，本地完整回归 **473 passed，0 skipped**，比基线新增 **30 项**。原版 EOAIC2 ScriptFunction 标记 **32 项**，Tools for Assist 源码标记 **123 项**，两类重叠 **9 项**，不可直接相加。Ruff 静态与格式检查通过。

新增证据包括：ASCII/中文/Emoji/控制字符转义的大结果、单条长文本、多层结果对象、顶层数组与文本、嵌套大字段、严格字节边界与最大标识开销、顶层元数据保留、输入不变、空对象拒绝、无法保留数据时的副作用未知状态，以及小结果/真实空数组/零值/布尔值兼容。原有 Unicode 预算测试增加非空结果断言。未修复代码在首轮 25 项相关检查中复现 19 项失败、6 项通过；修复后完整检查通过。

原版 Tools for Assist 1.11.0 Brave LLM Context 的 HTTP 与缓存模拟，实际执行其查询方法、原生 freshness Schema、JSON 片段解析和 SearchWebTool 包装；同时走固定搜索、通用调用和原版 EOAIC2 YAML 三条路径。带/不带 freshness、纯文本/嵌套对象片段四种组合均保留首条标题和正文，完整 JSON <=16 KiB。三次显式请求各调度一次，参数按原生映射透传，权限与输出过滤回归通过。

### v0.6.1 实际验收状态

2026-10-19 用户明确报告“验收通过”，并要求继续 v0.7。记录为 v0.6.1 总体验收通过；以下清单保留原逐项待核对状态，用户未提供各项详细结果，不据总体验收补填环境、提供商或物理设备证据。

- [ ] 通过 HACS 或 Release ZIP 从 v0.6.0 更新到 v0.6.1 并重启 HA，原有选项和五个动作正常。
- [ ] 使用此前触发空对象的真实查询，确认固定 search_web 仍正常；管理员经 call_tool 调用同一工具，分别省略和传入 freshness，能得到非空的 result.results、有效标题/正文及真实 truncated 状态。
- [ ] EOAIC2 call_allowed_tool 的 _function_result 保留相同结果，模型据已返回数据回答，不推断被裁剪内容。
- [ ] 无结果查询仍保留原生空结果语义；撤销白名单、无管理员身份及关闭副作用许可的拒绝行为正常。

该版本自动化使用固定原版源码和模拟后端，未连接用户 HA 或使用真实搜索密钥；后续用户总体验收已报告通过，逐项结果未单独提供。Home Control 继续不在本项目范围内。

## v0.7.0：统一工具入口与高德地点/位置

### 本地自动化与契约

基于 HA Core **2026.10.2**、测试插件 **0.13.373**、Python **3.14.6** 与精确锁定的开发依赖，完整回归 **512 passed，0 skipped**；Ruff 静态、格式与 Git 空白检查通过。原版 EOAIC2 ScriptFunction 标记 **33 项**，Tools for Assist 源码标记 **120 项**，重叠 **9 项**，不可直接相加。pytest 禁止网络；测试 Key 没有进入 fixture 或 CI。

删除仅适用于旧独立搜索服务的测试与示例，并将仍有意义的搜索、Tavily 与原版 EOAIC2 契约迁到通用入口。旧版本测试数量不作机械累计。v0.6.1 的全部通用裁剪边界仍保留，payload.py 与修复发布提交 f6e13a02396df0905107a1b180119e6588a2e44a 逐字节相同；gateway.py 仅将共享 validate_query 从已删除的 search.py 改为 validation.py，policy.py、calculator.py 和参数/检查/描述实现没有改动。

| 回归范围 | 已执行的检查 |
| --- | --- |
| 删除与升级 | 仅注册四个响应服务；旧服务调用为 ServiceNotFound；启动清理旧注册；重复 setup、补注册及卸载/重载/删除；旧空选项不自动授权，既有授权与身份要求保留 |
| 通用搜索 | 原生 query 字符串/空白/Unicode/长度检查；原始管理员 Context；Brave freshness、Tavily topic/time_range；新 web_search 及 call_allowed_tool 原版脚本接线；字符串样式参数不被数值化 |
| 大结果 | 原版 Brave LLM Context 带/不带 freshness、纯文本/嵌套片段经通用动作和原版 EOAIC2 脚本，每条路径只派发一次；非空正文、保留顶层/首项、严格 UTF-8 16 KiB；高德大 POI 营业时间亦保留有效数据 |
| 高德配置/权限 | 可选 Key/城市/GCJ-02 中心；保存配置不授权；坏地图配置不影响旧搜索；原生 Amap API 不能绕过网关开关/精确白名单/原始管理员/停用/卸载；等待期间配置、权限或用户变动阻止 HTTP |
| 高德元数据 | 独立 API 身份、只读声明和参数；目录/描述不执行工具或原生校验器、不创建 HTTP 会话；就绪检查不调用序列化器；非管理员不发现额外地图工具 |
| 高德语义 | 关键词/附近端点、配置与显式覆盖、城市限制、排序/类型码、整数/坐标边界、空结果、缺失字符串数组、地址候选/歧义/匹配级别与数量限制；真实原版 EOAIC2 ScriptFunction 经 call_tool 接线（HTTP 模拟） |
| 高德失败 | Key/配额拒绝、HTTP/重定向、不重试、网络/超时/取消、256 KiB 流式预算、无效/过深 JSON、坏结构、公开字段回显 Key 脱敏；失败不返回空对象成功 |

### 高德真实 HTTP（独立进程）

2026-10-19 使用用户给出的测试 Key，经终端隐藏输入只留在进程内存，直接运行本项目 AmapClient，分别请求高德官方 HTTPS 端点。Key、完整请求 URL 和原始响应没有写入文件或日志，配置中也未持久保存本次测试 Key。

| 端点 | 本次公共地点请求 | 结果 |
| --- | --- | --- |
| /v5/place/text | 北京市，北京大学，limit=2 | 成功，返回 2 项，包含有效 GCJ-02 坐标 |
| /v5/place/around | 北京天安门公共坐标附近咖啡，半径 3000 米、distance、types=050000、limit=2 | 成功，返回 2 项，包含有效 GCJ-02 坐标 |
| /v3/geocode/geo | 北京市东城区天安门，city=北京市 | 成功，返回 1 个候选和有效 GCJ-02 坐标 |

真实 HTTP 只验证当次 Key 的接口可用性和三种请求，不声称错误/配额边界均经过真实消耗测试。相关错误边界用模拟响应验证。没有连接用户 HA、对话模型或物理设备，因此不算真实安装/EOAIC2 联调通过。

### v0.7 尚待用户环境验收

- [ ] 从 v0.6.1 经 HACS/Release 更新并重启 HA，四个保留服务正常、旧搜索服务不存在，选项保持原值。
- [ ] 将旧 Functions/自动化迁为 call_tool，并先判断 success、读取 result.results；原始管理员可搜索，无身份/非管理员被拒绝；不扩大白名单。
- [ ] 在真实 HA 配置自己的高德 Web 服务 Key，授权两工具；验证关键词/附近地点/城市与位置选择、缺失字段及地址候选消歧，再经真实 EOAIC2 模型调用。
- [ ] 回归既有查询、计算器、媒体和原生 HA 控制；记录物理设备行为，保留上游播放 Context 限制。

v0.8 高德路线与 v0.9 收口继续按 [兼容清单](TOOLS_COMPATIBILITY.md) 推进，不因模拟与 HTTP 验证通过直接发布 1.0。

## v0.7.1：12 个工具的独立 Functions

本次只修改文档、静态 examples、必要的示例验证测试和发布版本号；所有 Bridge Python 运行文件与 v0.7.0 逐字节相同，依赖锁定除项目自身版本外不变，未增加 YAML 生成器，也未修改 EOAIC2、任何分支或 Tools for Assist。生产仍通过 HA 公开接口，不新增上游代码依赖。已有固定原版快照只用于测试，仍逐文件验证哈希。

HA Core **2026.10.2**、配套测试插件 **0.13.373**、Python **3.14.6** 上完整回归 **601 passed，0 skipped**，新增 **89 项**示例验证；Ruff 静态/格式、锁文件离线检查、Git 空白检查通过。EOAIC2 ScriptFunction 标记 **95 项**，Tools for Assist 源码标记 **182 项**，重叠 **54 项**，不直接相加。

| 示例检查 | 证据 |
| --- | --- |
| 工具与身份 | 清单恰好覆盖原 10 个工具及高德 2 个组合；14 个静态文件包含两个额外搜索变体。所有独立 Function 的模型名为原工具名，只有原生参数，type=script、固定 API/工具并统一调用 call_tool |
| 原生参数 | 与固定原版 Schema 核对必填、可选、字段类型、固定枚举和数值/长度边界；使用现有 probatio JSON Schema 编解码检查模型参数，不增加测试依赖 |
| 原版脚本接线 | 在未修改的原版 ScriptFunction 上逐个执行最小及全可选参数，真实 HA 服务、管理员、白名单、原生 Schema 验证；只模拟最终提供商方法，逐次核对服务入参/原生 ToolInput 和原始 Context，只派发一次 |
| 类型与默认值 | 字符串样式查询、模板文字、分数、整数、字符串数组保持类型；YouTube num_results=1 与高德 limit=5 原生默认生效；year/mode/城市/中心未给时省略，不写死当前年份或配置默认值；错误类型及显式 null 不隐藏/强转 |
| 搜索四后端 | query-only 对四实现兼容；Brave LLM Context freshness 与 Tavily topic/time_range 枚举保持原版，Tavily 可选筛选字段独立省略；不向另一个后端暴露参数并集，过时提供商专用定义在后端切换后明确拒绝 |
| 播放可选目标 | entity_id 数组、area、device_id 分别与联合透传；省略 device_id 时不把 HA 内置 device_id() 当作参数，三种目标全部省略的模板也能正确返回字典。真实单设备回退语义仍由已有媒体契约验证 |
| 配置不冲突 | Google/高德地点二选一 × 三份搜索选一，共六种推荐组合的模型名均唯一；删除旧 web_search 文件，所有示例不调用已移除的搜索服务 |
| 权限与文档 | 独立搜索/播放示例保留原始管理员校验与副作用阻断；文档 14 个完整代码块与各静态 YAML 一致，README 搜索块也与交付文件一致 |

本次模拟验证不代表真实模型会正确选择全部工具，也不构成用户 HA、HACS 升级、搜索后端或播放器验收。本次未调用真实提供商或使用任何测试 Key，不把 v0.7.0 的三端点高德 HTTP 验证重记为 v0.7.1 新验收。v0.7.x 的用户安装/模型验收仍按既有待验清单记录。

建议在真实环境先替换旧 web_search、选择一个搜索参数版本和一个 find_places 提供商，再逐个验证模型原生参数、响应与权限。Functions 为用户手工配置，不会由 HACS 自动改写，Home Control 继续排除。

2026-10-20 用户报告 GitHub CI 服务恢复并通过；复核发布提交 `b411d5520a48189a99c39b592e7e282715c0f76e` 的 [v0.7.1 CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/39280582634)，test、hassfest、hacs 均为 success。v0.7.1 发布当时因服务故障跳过等待的记录仍保留；本次补记恢复后的结果，不改写成当时已通过，也不视为用户环境验收。

## v0.7.2：独立 Functions 描述优化

本次基于 v0.7.1，只完善 14 份独立 YAML 的模型可见描述、相关文档和验证测试，发布元数据升为 0.7.2。逐字节核对集成及构建/源码获取文件：除 manifest.version 外均保持原值，所有 Bridge Python 文件不变；pyproject/uv.lock 除项目版本外结构一致，无新依赖。未修改上游、EOAIC2 全局提示词或实际安装，未提前开发高德路线。

本地完整 **630 passed，0 skipped**；独立示例相关 **118 项**通过，其中新增 **29 项**。固定环境仍为 Python **3.14.6**、HA Core **2026.10.2**、测试插件 **0.13.373**。EOAIC2 ScriptFunction 标记 **95 项**，Tools for Assist 原版契约标记 **183 项**，重叠 **54 项**，不能直接相加。Ruff 静态与格式、锁文件离线、Git 空白及文档本地链接检查通过。

| 检查 | 结果与范围 |
| --- | --- |
| 非描述契约冻结 | 14 项对比 v0.7.1 固定提交的规范 JSON 摘要；递归移除 description 后，Function 名、API/tool、所有 Schema 关键字/默认值、完整 Jinja 与执行序列必须相同，不依赖 Git 历史或新增下载 |
| 描述完整与长度 | 14 项逐文件检查工具/所有参数有文本说明；工具最多 140 个英文词、单参数最多 130 个，避免扩成系统提示词。数值语法等长约束放参数描述 |
| 单位依据 | 1 项与未修改原版转换器逐组核对全部英文单位，含 dl，不添加伪造单位或 Schema 枚举 |
| 原版回归 | 既有最小/全可选、四搜索后端、独立可选筛选、字段类型/默认、原始管理员、白名单、副作用许可、Google/高德互斥组合、原版工具结果与 v0.6.1 大结果裁剪均完整回归；HTTP/设备使用模拟 |
| 代码块一致 | Functions 指南 14 个完整片段与 YAML 逐字相同（含描述及注释），README 搜索块与实际定义一致；没有新增 YAML 生成器 |

远端 CI 的具体提交、结果和安装包校验见 [v0.7.2 Release](https://github.com/qiqi20020612/eoai-tools-bridge/releases/tag/v0.7.2)。本地测试不等于远端 CI；不沿用上一补丁的故障跳过结论。

**真实联调状态：**用户提供了单位、英文维基百科、YouTube 数量、引用和地图等实际问题，作为本次描述修正依据；未提供新版逐项验收结果。本次没有调用真实提供商、使用测试 Key、连接用户 HA 或播放物理设备，也不把 v0.7.0 的联网结果重复记为本次证据。文字说明和自动化不能证明模型必然遵循或回答质量已提升。

替换所选 Functions 后，建议另行实际验收：

- [ ] 中文单位正确映射到英文标识、amount 保持字符串；中文百科问题使用英文主题检索并用中文回答。
- [ ] YouTube 按实际选项数请求，结果不足允许针对缺口补充；三份搜索保持提供商隔离，无链接时不编造来源或反复查相同内容。
- [ ] 仅启用一个 find_places；区分 Google 位置偏好和高德城市限制，附近搜索不用猜测位置，GCJ-02/经度顺序正确；地址多候选消歧、缺失字段及非穷尽条数说明准确。
- [ ] Google get_route 固定配置起点、默认 mode/时间和估算表述正确；计算、日期、天气的约束/默认/空结果被正确解读。
- [ ] 播放使用真实兼容目标，命令成功不声称已观察到播放；副作用未知状态不直接重试。HACS 更新及手动 Functions 替换各自正常，现有权限保持。

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
