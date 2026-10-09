# 测试记录和手工验收

记录日期：**2026-10-09（Asia/Shanghai）**。开发测试使用独立虚拟环境，未连接或修改用户的 Home Assistant。用户报告的真实验收与开发者执行的自动化检查分别记录。

## v0.1.0 验收记录

**真实验收：用户报告通过。** 用户在当前开发对话中明确回复“验收通过。继续下一个版本”。本记录据此接受 v0.1.0 的验收结论；用户未提供环境版本或逐项证据，不补写具体 Brave/SearXNG、TTS 或 HACS 更新的单项结果。

**历史自动化结果：80 passed，0 skipped**，包含 **9 项**固定提交的原版 EOAIC2 ScriptFunction 契约测试。Ruff、安装 ZIP 检查通过；[v0.1.0 最终提交的 GitHub CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37909206602) 通过 Ubuntu 测试、Home Assistant 官方 Hassfest 和官方 HACS action（全部 9 项仓库检查）。

发布版本：[v0.1.0](https://github.com/qiqi20020612/eoai-tools-bridge/releases/tag/v0.1.0)，提交 `01a18464f66cc386f1372978593c3b14a741fe3b`。该版本的标签和安装包保留不变。

## v0.2.0 已执行的自动化检查

- Python **3.14.6**，HA Core **2026.10.0**，`pytest-homeassistant-custom-component==0.13.371`。
- EOAIC2 契约测试使用提交 `b0274f752fc01495875522db9281c335af8cf484` 的原版脚本相关文件，经过 SHA-256 验证。
- 搜索返回、API 元数据、故障和超时使用模拟对象；HA 服务、配置流、Context、LLM 注册/调度、probatio Schema 转换及 Script 执行使用真实实现。
- pytest 禁止网络访问，不能把测试中的元数据、标题、摘要或链接当作真实环境数据。

本地结果：**124 passed，0 skipped**，其中 **11 项**执行原版 EOAIC2 ScriptFunction（原有 9 项搜索测试及 2 项可选清单 YAML 测试）。Ruff 静态检查与格式检查通过；`uv.lock` 只更新本项目版本，第三方依赖版本保持原样。

提交 `469e3ea45f2fde2a03e0764ce52bd70784666d58` 的 [首次 v0.2.0 CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37945161517) 中，Ubuntu 的 **124 项测试**、Ruff、固定上游源码校验及 ZIP 构建通过，官方 Hassfest 通过。Hassfest 提示缺少 CONFIG_SCHEMA，现已补充 HA 的公开 `config_entry_only_config_schema` 声明，并重新通过本地全部测试。

首次 HACS 校验 **7/9 项通过、2 项失败**：仓库当前为私有，匿名读取 hacs.json 和 manifest 均为 404，校验器因此取得空内容。固定提交的文件可通过已认证 GitHub API 正常读取；这不是跳过或通过 HACS 校验的依据。[HACS 不支持私有仓库](https://www.hacs.xyz/docs/faq/private_repositories/)。发布方式确认后将补充最终状态，v0.1.0 的历史 CI 不用作 v0.2.0 的通过依据。

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

## v0.2.0 尚待实际运行验收

v0.1.0 的验收不覆盖本次新增动作。以下需要在实际 HA 2026.10.x、Tools for Assist 和 EOAIC2 环境执行；模拟测试与仓库校验不替代真实升级验收。

- [ ] 从 v0.1.0 通过 HACS 更新到 v0.2.0 并重启 HA；原有配置项能加载，两个动作可见，没有导入或重复注册错误。
- [ ] 启用网页搜索时，`eoai_tools_bridge.list_tools` 返回 `llm_intents/search_web` 的实际描述及 query Schema；清单动作本身不产生搜索调用。
- [ ] 禁用搜索或移除搜索 API 后，清单返回成功的空列表；按 Tools for Assist 要求重载/更换后端后，下次调用反映新参数。
- [ ] 可选追加 `examples/eoaic2_list_tools.yaml` 后，EOAIC2 调用 `list_search_tools` 能读取真实清单；原有 `web_search` 仍能搜索，设备控制 Functions 保持正常。
- [ ] 清单动作的额外参数被拒绝；卸载桥接后返回 `bridge_not_loaded`，重新启用/重载后恢复，无重复注册。

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
