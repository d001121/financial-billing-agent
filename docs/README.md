# 文档导航与实际状态

2026-10-21 最新智能体行为已改为Codex式自主阅读/按需核验，详见[本轮实现与验收](research/codex-style-extraction.md)。旧的九块覆盖、固定复核和评分中断不再适用于新任务；下文版本、分流及测试成绩保留历史身份。

更新：2026-10-21。后端职责重构、Office原文复核及无模板海外提取/v2融合已有实现；前端现已按业务用户拆分总览、大屏、业务操作、待办及管理页面，类型检查和生产构建通过（2408 modules，Vite 1.71秒）。新版浏览器主要路径、390×844布局和测试标签API阻断/恢复通过，完整键盘、长表、视口与断线矩阵仍待验。本轮优先完成需求，不制作、更新或迁移交付包。

| 文档 | 用途 |
| --- | --- |
| [根 README](../README.md) | 启动、示例、目录与外部条件 |
| [AGENT.md](../AGENT.md) | 唯一开发约定正文，开始工作先读 |
| [最终开发计划](superpowers/plans/2026-10-21-final-development-plan.md) | T01–T33 要求、实施状态和当前重构范围 |
| [implementation.md](implementation.md) | 设计基线、实际职责树及实现差异 |
| [skills-and-hooks.md](skills-and-hooks.md) | 八个 Skill、十一类 Hook、官方加载/执行 |
| [acceptance.md](acceptance.md) | 本轮重构验证、历史回归与在线结果 |
| [recovery.md](recovery.md) | 持久化分工、历史重启证据及限制 |
| [performance.md](performance.md) | 历史实测时延及未完成的性能验收 |
| [insights.md](insights.md) | 题目要求的补充思考 |
| [ui-design.md](ui-design.md) | 业务页面/Hash导航、官方Vue协议、当前实施与历史浏览器联调 |
| [portable-environment.md](portable-environment.md) | 私有 Python、依赖和运行时来源 |
| [portability.md](portability.md) | 既有交付方式与历史迁移记录，本轮暂停 |
| [sample-inventory.md](sample-inventory.md) | 原题材料、附件关系及金标状态 |
| [development-tools.md](development-tools.md) | 插件/MCP与先查官方的纪律 |
| [实现依据增补](research/implementation-evidence.md) | 原验收版本的研究证据及本轮追加的职责重构依据 |
| [海外提取与融合研究](research/global-extraction-confidence.md) | 文章取舍、全球数字/币种歧义、三组支持度及合成差分边界 |

`backend/` 本身作为 Python 包，按 `agents/`、`middleware/`、`tools/`、`hooks/`、`mcp/`、`extensions/`、`harness/`、`api/`、`infrastructure/`、`config/` 分责；八个业务包仍在 `skills/`。Vue 位于 `frontend/`，`src/pages/`为总览/大屏/业务列表/管理页面，`components/`提供材料、账单详情及原生Agent交互，`utils/taskPresentation.ts`统一摘要展示。官方入口为 `backend.agents:make_graph` 与 `backend.api:app`，内部使用实际职责模块，不保留旧平铺模块别名。

前端默认打开工作总览；`#/tasks`为账单业务中心，`#/review`集中待办，`#/new`独立提交材料，`#/screen`进入大屏，`#/management`进入能力与经验管理。Hash导航支持刷新和浏览器返回；列表在同次页面会话内保留筛选与分页。默认只同步任务摘要与health，详情才读取费用与资产；技术日志按需展开，原生人工中断保持可见。新版已实际打开全部页面及管理子页，验证搜索`european`进入详情后返回仍保留筛选、复核清筛不跳页、EUR金额定位邮件内容块，以及日志折叠时历史人工请求可见。100分结果展示确认入口，未审批版本禁用正式导出；本轮未点击确认、回复中断或提交材料。390×844下总览、列表与详情无页面横向溢出，移动菜单Esc关闭并回归焦点；测试标签临时阻断`/api/*`后保留16项旧快照，解除并重试后恢复，未关闭后端。报告及实际截图清单见[新版工作空间验收](../backend/tests/reports/user-workspace-ui.json)，旧UI截图与历史联调不代验新版。

当前skills经CAS发布v6，能力快照 `0dd7d9b036a29571747e`，最终全量 **353 passed、43 warnings、4 subtests passed，220.45秒**。报告为 `backend/tests/reports/global-confidence-publication.json`、`global-confidence-pytest.txt`、`global-confidence-pytest.xml`；历史任务未迁移。置信度阶段的前端类型/生产构建及SSR兼容验证已有记录，其在线任务与旧UI结果以当时实际验收报告为准；[新版页面验收](../backend/tests/reports/user-workspace-ui.json)单独记录，不替代后端回归、长材料性能或新增审批流程验收。

此前职责重构全量回归163项通过（43 warnings、4 subtests、68.90秒），后续配置修复40项通过（28.73秒），项目外运行时与pip check通过；官方服务四HTTP全200。三个历史任务的检查点、19/9/17条消息、原中断和revision保留，1166个skills/releases文件及.env哈希不变，该批次未新建或恢复Agent运行；原有GET导出核验更新last_export和审计回执。证据为 `backend/tests/reports/responsibility-tests.txt`、`responsibility-configuration-tests.txt`、`responsibility-runtime.json` 和 `responsibility-after.json`。旧161项回归和ZIP迁移保留原版本身份。

此前真实 Qwen、GaussDB、Redis、官方 Server 和 Vue 已联调，合成 Excel 完成审批导出；已授权 OBS 和指定 OCR 的原题基础接入验证保留在原始报告。历史 EML 的正文 `$50` 缺币种及收费双方，原生等待输入，正式导出422、未批准。在线结果保留各自验收范围；旧Office/v5记录见[历史验收](acceptance.md#历史officev5置信度与原文复核2026-10-21)，不由本轮离线回归推断在线成功。

研究目录保留当时的 commit、版本、路径和历史探针，不因当前重构回写。Office 转换器移机、长材料在线性能、独立真实金标、完整故障/负载矩阵和生产强恢复仍有未验证项，详情见验收记录。
