# 测试记录和手工验收

执行日期：**2026-10-09（Asia/Shanghai）**。测试使用独立虚拟环境，未连接或修改用户的 Home Assistant。

## 已执行的自动化检查

- Python 3.14.6，HA Core **2026.10.0**，`pytest-homeassistant-custom-component==0.13.371`。
- EOAIC2 契约测试使用提交 `b0274f752fc01495875522db9281c335af8cf484` 的原版脚本相关文件，经过 SHA-256 验证。
- 搜索后端返回、上游故障和超时均使用模拟工具；HA 服务、配置流、Context、LLM 注册/调度以及 Script 执行使用真实 HA 实现。
- pytest 禁止网络访问，不能把测试中的标题、摘要或链接当作真实搜索结果。

本地最终结果：**80 passed，0 skipped**。其中 **9 项**执行固定提交的原版 EOAIC2 ScriptFunction；其他测试覆盖桥接服务、参数/安全边界、生命周期及元数据。Ruff 静态检查及格式检查通过。安装 ZIP 已构建，并检查了内容清单及 SHA-256。

公开仓库已经发布：[qiqi20020612/eoai-tools-bridge](https://github.com/qiqi20020612/eoai-tools-bridge)。

提交 `6f45b4abe73b7e2d34234368437085b4650a171c` 的 [GitHub CI](https://github.com/qiqi20020612/eoai-tools-bridge/actions/runs/37908765239) 已通过三个任务：

- Ubuntu/Linux 上的全部 **80 项测试**、Ruff 检查、固定上游源码 SHA-256 校验和安装 ZIP 构建。
- Home Assistant 官方 **Hassfest** 集成校验。
- 官方 **HACS action** 的仓库校验（全部 9 项），包含许可证、描述、品牌、主题标签、manifest 和 hacs.json。

这些是自动化和仓库规范验证，**真实 HACS 安装/更新及真实 HA 对话验收仍未执行**。后续记录提交只更新测试说明和发布文件，不改变已验证的集成实现。

自动测试覆盖：

| 范围 | 覆盖内容 |
| --- | --- |
| 配置与生命周期 | UI flow 添加、单实例、无上游仍能加载、只注册一次、响应必需、卸载/重载/删除后的动作行为 |
| 输入边界 | 缺少 query、错误类型、空白、501 字符、500 字符合法、额外 API/工具/URL/Headers/动作/实体参数拒绝 |
| 调用边界 | 固定 API 与工具、原始 Context、配置语言、无伪造设备 ID、后端变化后重新获取实例 |
| 结果与失败 | 空结果字符串、旧式字典通过真实 HA 包装、ToolResult.error、正文 error、业务 success=false、未知结构、API/工具异常 |
| 运行控制 | API 获取和工具调用超时、调用取消传播 |
| 数据与隐私 | 不返回上游指令或 API prompt、不编造链接、异常和桥接日志不暴露敏感文本、URL 校验、Unicode JSON 大小/条数/文字限制 |
| EOAIC2 接线 | 原版 ScriptFunction 校验示例、执行动作并返回 _function_result、失败响应返回、数字和模板类字符串保持原样 |
| 文档与描述 | HA 运行时英文动作描述、中文键、README YAML 与交付示例一致 |

## 尚未执行的实际运行验收

以下项目需要真实 HA 2026.10.x、已配置搜索服务及 EOAIC2。**本地模拟测试通过不能替代以下验收。**

- [ ] 在真实 HA UI 中安装并添加集成，确认日志没有导入或依赖错误。
- [ ] 在真实 HACS 中添加公开仓库、安装、更新；确认第三方集成仍能独立更新。
- [ ] Tools for Assist 选择 Brave 或 Brave LLM Context 后，动作返回真实搜索结果。
- [ ] Tools for Assist 选择 SearXNG 后，动作返回真实搜索结果。
- [ ] 在真实 HA 上分别测试未安装 Tools for Assist、未加载、搜索未启用，确认对应失败提示。
- [ ] EOAIC2 聊天询问「搜索今天 AI 新闻」，核对函数调用、实际响应、最终答案及 TTS。
- [ ] EOAIC2 请求「打开卧室灯」，确认原有控制函数与设备动作正常。
- [ ] 单独使用 Codex Assist，确认其原生搜索和独立对话配置正常。
- [ ] 真实 HA 重启、桥接重载、Tools for Assist 更换后端及卸载后，动作状态正确且无重复注册。
- [ ] 真实后端无结果、网络故障或错误密钥时，EOAIC2 能友好回答且没有伪造搜索结果/引用。

建议填写验收证据时记录 HA、Tools for Assist、EOAIC2 的版本，测试输入、实际 error_code 或结果条数，以及是否存在真实来源 URL。保留必要截图/调用记录，并按原有隐私策略处理查询及日志。

## 可复现命令

```sh
uv sync --locked --group dev --python 3.14
uv run --no-sync python scripts/fetch_test_upstream.py
uv run --no-sync pytest -q --timeout=30
uv run --no-sync ruff check custom_components tests scripts
uv run --no-sync ruff format --check custom_components tests scripts
uv run --no-sync python scripts/build_release.py
```

生产集成不读取、修改 `.cache/upstream/`。上游源码下载只用于开发测试，安装 ZIP 排除 `.venv`、上游源码、测试文件和所有开发缓存。
