# 进化库实现与验证（2026-10-23）

## 后续补充：是否使用总开关

按用户要求在进化库顶部加入“使用已确认经验”开关，默认开启。复用现有runtime配置及版本冲突校验持久化，runtime v7新增严格布尔字段`use_reviewed_experiences`。关闭后新快照不载入经验，已有原生检索工具派发时也检查当前开关并返回空结果、不写引用回执；任务上下文显示使用已关闭、可参考数为0。卡片、AI总结和原有映射发布不受影响。重新开启仍遵守旧任务快照边界，已进入上下文的内容无法撤回。

本次仅12项相关离线检查通过：`experience-usage-switch.xml`记录11项，`experience-usage-context.xml`记录1项；前端类型检查/生产构建通过（2504 modules）。合成内存API浏览器验证关闭、刷新后保持关闭和重新开启，截图`backend/tests/reports/experience-usage-switch-ui.png`。未使用真实模型/OCR，未跑全量，未启动或重启正式后端；临时4177预览在核对后关闭。下文runtime v6和27项结果保留为首次实现记录。

用户批准将抽象的“经验与规则”改成少填表、AI总结、可审核并供后续任务检索的进化库。实现已落入源码，未启动或重启正式后端；没有新建或修改真实账单，也没有修改既有不可变能力发布目录。

## 实际使用

账单详情点击“总结这次纠错”，或在进化库选择来源账单。用户只需可选补一句话，AI预填标题、实际问题、适用条件、处理方法、例外和检索词。来源账单、记账主体和revision由服务端绑定。卡片可编辑；勾选确认并入库后，后续同主体的新任务才可按需检索。缺主体的草稿不能启用。停用后不再返回该卡片，修改后回到待确认状态。

卡片显示来源和总结时实际选取的原文引用，以及哪些任务的工具实际返回过该经验。检索记录不能当作“已采纳”或“正确率提高”的证据。原有费用映射评测、发布和回滚保留在“执行规则”页签，参考经验不会自动成为可执行财务规则。

## 结构与官方能力复用

- `feedback-improvement 1.4.0`负责摘要投影、卡片契约、主体作用域与检索资格。沿用同一个业务Skill，没有新增模型运行器或业务知识服务。
- HTTP路由只提供存储与原生模型绑定；复用现有统一模型工厂、LangChain `with_structured_output`，不创建额外Agent循环。实际HTTP前的guard限制每次生成最多一次调用，关闭思考、输出最多1600token、配置超时45秒、无自动重试。成功输入复用；失败须明确重试，独立回执累计真实调用数及返回的token用量。
- 摘要只投影最近8次修订的末12项修改、前12行费用和最多10段原文，明确说明截取边界，不能声称完整复盘整单。
- 检索复用已安装的官方`BM25Retriever`及`rank-bm25==0.2.2`，只补中文双字/英文词切分、同主体过滤和无词重叠不返回。最多返回3条，原文参考限制每条2段、每段200字；无向量服务或额外模型开销。
- 新任务快照固定经验内容和版本；工具派发时再检查当前卡片仍启用且版本一致。已有任务不会自动获取后来新增的经验。停用不能撤销模型已收到的参考。
- 经验、生成作业、人工确认及实际检索回执复用现有通用仓储。审核人只记录真实本地工作区操作，未实现登录身份，不编造审核人姓名。

当前配置skills v32、agents v13、runtime v6；依赖已加入主声明、锁文件和Skill声明。官方文档MCP连接本轮未修复；方案依据此前已查阅的官方结构化输出/检索文档，并核对已安装SDK源码与实际离线调用，不把连接失败写成“官方没有”。

## 财务数据边界

经验只提供核对方法，不能把历史金额、币种、单号、付款方式或AR/AP填到当前单据。当前原件缺失仍留null；原件证据、金额、revision和导出校验照常执行。AI生成后始终是草稿，由用户确认才启用。生成失败不返回模板冒充AI成功。

## 本轮验证

仅运行以下定向离线检查：

```powershell
.\backend\python.cmd -m pytest backend/tests/test_experience_library.py backend/tests/test_improvement.py backend/tests/test_skill_versions.py backend/tests/test_host.py::test_real_model_http_requests_disable_thinking_and_share_task_budget backend/tests/test_host.py::test_request_with_thinking_enabled_never_reaches_transport backend/tests/test_configuration.py::test_role_prompt_files_are_resolved_and_frozen_in_task_snapshot -q --junitxml=backend/tests/reports/experience-library-focused.xml
```

结果 **27 passed，92 warnings，11.65秒**。警告来自现有LangChain MCP beta、community检索包弃用和LangSmith内部弃用API。覆盖同主体/状态过滤、无关查询不返回、缺主体禁止启用、真实来源绑定、重复成功复用、明确失败重试、原始账单不变、过期revision、原生HTTP结构化解析与一次调用计量、经验快照、停用/版本变更及检索去重回执，以及旧费用映射评测/发布门禁。原生模型HTTP测试使用`httpx.MockTransport`，未向模型服务发送请求。

Vue类型检查及生产构建通过，2504 modules；保留既有大分块提示，未扩大到无关打包重构。独立4177端口仅加载前端产物和内存模拟API，浏览器实际核对：选择合成账单、生成草稿、入库前确认限制、确认后状态、停用后状态、来源链接及“执行规则”页签。预览未读正式数据库，未产生真实模型/OCR调用，也不构成正式后端联调证明。

截图是**合成界面预览**：`backend/tests/reports/experience-library-ui-synthetic.png`。定向检查XML为`backend/tests/reports/experience-library-focused.xml`。预览脚本为`backend/tests/reports/experience-library-preview.cjs`，测试结束后关闭预览服务。

## 未验证及限制

未运行全量测试、真实模型/OCR、正式数据库新接口或线上新任务；未验证真实AI总结质量与准确率收益。源码和构建完成不代表正式服务已经加载。最终只读检查发现2024端口存在本轮前09:09启动的langgraph_cli进程（--no-reload），本轮未触碰该既有进程；新功能需在用户正常重启服务后使用。4177合成预览服务已关闭。

当前检索是文本相关性检索，近义词完全不重叠时可能无结果；不引入额外付费调用兜底。列表最多读取10000条记录，尚未实现规模化分页索引。硬终止进程可能使生成作业停留running；本轮未新增后台恢复机制。生成任务不支持实时取消，页面说明与回执以实际完成状态为准。
