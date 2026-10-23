# 账单材料包与用户/管理端分离

日期：2026-10-21。本轮对应用户的三点纠正：用户端按账单组织，控制台单独管理能力与追踪，EML 全部材料共同参考。

## 实现边界

- 一次提交是一份账单材料包，一项费用仍是一条题面输出记录。用户列表不展示原生 todos 或内部调用步骤。独立提交不按文件名、单号自动合并；多次提交的业务意图不能从相似名称推断。
- `/api/bills` 是已保存事实的只读展示投影：单号、交易方、各条费用原值、材料父子关系与具体问题。没有另算置信度、币种汇率、财务合计或操作裁决。列表不传 OCR 正文与执行产物。数据库状态可能滞后于原生中断，所以批量读取官方 `threads.search(ids, select=[thread_id,status,interrupts])`，投影真实待补充问题；线程 idle 不代表财务审批通过。列表不保存或迁移历史任务。
- 用户端右上角进入管理员控制台，控制台导航只提供 Skill/工具、经验规则和 Trace；用户端保留总览、大屏、账单、待办和提交。这里是界面职责划分，不声明新增了账号/RBAC。
- 账单详情先展示原生人工补充表单与问题收件箱，逐项提供原件定位、费用修改或补充主体。费用表和全部业务字段表默认可读，无需阅读 JSON。高支持度结果仍可直接显式确认；修改、确认与正式导出的原有 revision 和校验门禁保留。
- EML 主材料、全部附件与嵌入图片共同属于这次提交。`document-extraction` 1.4.0 提供材料清单、父来源、各来源 chunk IDs、共享邮件原文与明确截断信息；每批工具结果都带相同材料包上下文。共享邮件片段最多 6000 字符，各块最多 1600，其余通过完整 chunks 读取，没有丢弃费用范围。独立附件的 document_id、owned_range、币种和原文总额作用域保持原身份。
- 跨来源补充需要明确业务联系及真实两处引用；重复表述不是新费用，原件空 OCR chargeList 不能证明没有费用。最终完成结论必须等待全部来源覆盖。没有新建 Agent 循环、上下文摘要器、Skill 执行器或拆页工作流。

## MCP 查证与最小业务缺口

| 操作 | 本轮 Docs MCP | 本轮 API Reference MCP | 实际组合/缺口 |
| --- | --- | --- | --- |
| 多材料上下文 | `/oss/python/deepagents/context-engineering`、`/oss/python/langchain/context-engineering` | `langchain_core.documents.base.Document` | 复用原生工具结果、Document 和现有 splitter；框架没有航运账单与邮件附件的领域关联规则，只在所属 Skill 中增加材料包清单与原文引用投影 |
| 列表发现人工中断 | Agent Server OpenAPI 的 ThreadSearchRequest/Thread.status/interrupts | `langgraph_sdk._async.threads.ThreadsClient.search` | `ids` 精确过滤，`select` 排除消息/正文，批量投影线程状态；不另建状态订阅服务 |
| 查看 Agent 路径 | `/langsmith/observability-concepts` 与 Agent Server OpenAPI | `langgraph_sdk._async.threads.ThreadsClient.get_state` | 原生 `subgraphs=True` 检查点投影 + 官方 Vue useStream；工具耗时取已有 DispatchPolicy 回执，不重建 tracing runner |
| 识别质量 | `/langsmith/evaluation-concepts` | 使用已有 LangSmith 评测合同，无新增模型评分器 | 生产任务尚未关联独立金标，准确率/误识率/漏识率为 null，页面显示未评测；不以置信度或修订率替代 |
| Skill 新版发布 | `/oss/python/deepagents/skills` 的 include_tools/pin/reload | `deepagents.middleware.skills.SkillsMiddleware` | 复用原生发现/渐进披露；本项目 CAS 配置与不可变快照固定新任务能力，历史不迁移 |

安装组合延续 Python 3.13.16、LangChain 1.4.6、LangGraph 1.2.16、Deep Agents 0.7.29、langchain-text-splitters 1.1.3、官方 Vue adapter 1.2.5；没有新增框架依赖。发布与验收结果见本文后续记录和 `docs/acceptance.md`。

## Trace 统计口径

`/api/traces` 最多展示当前最近 100 份提交，页面明确分母和数量。活跃时间来自已有去重计时器，包含模型/工具重叠时段的一次计量，不包含人工等待；单工具耗时来自完成回执，按完成时间排序，不把并行耗时相加为端到端时长。

人工修订比例为有 `human_revision` 审计事件的提交数 / 当前列出的提交数。当前等待补充、发生常规确认的提交数单列；这一口径不声称统计了历史所有人工回复，页面展示定义。完整事件计数由数据库聚合，Trace 详情只展示最近 1000 个事件的必要字段并显式标记截断。

调用路径展示官方当前检查点能读取的工具调用及子图任务身份。已完成专家内部调用可能不留在父检查点，不能伪造完整 span 树；已有工具回执仍独立展示。未擅自启用云端 LangSmith tracing 或上传业务材料。

## 本轮验证

新增离线测试覆盖材料包原文/附件关系、跨真实单据不串邻接上下文、共享上下文容量及未读完整范围、非 authoritative 预览排除、只读账单投影、跨币种不求和、原生路径不伪造 span、人工修订与常规确认分开、真实中断对列表状态的覆盖、idle 不审批、历史线程缺失显式可见。构建、回归和浏览器最终结果以验收记录为准，测试通过不当作真实无模板提取准确率。

发布结果：skills配置v7、agents配置v2，能力摘要 `347e46bf7361cfe776d0`；document-extraction为1.4.0。历史提交的id/revision/status/updated_at在发布前后相同，不迁移既有线程与Skill快照。开发源与当前发布包相符；此后修改包内容须新建版本。

全量回归361 passed、43 warnings、4 subtests passed，126.29秒，见 `backend/tests/reports/bill-workspace-pytest.txt`及XML。之后增加宿主多批提取测试，验证14块中的后批附件也接收邮件上下文；与5项展示投影测试合计6 passed、1 warning，7.86秒。该新增用例不包含在此前361项全量中。最终前端Vue/TypeScript与Vite构建通过，2411 modules、1.05秒，入口 `index-DwCHs_S_.js`。

浏览器记录见 `backend/tests/reports/bill-workspace-ui.json`：用户列表、置顶问题收件箱、全部业务字段表格、金额到邮件原文块、原题邮件4份参考材料/PDF预览、原生待补充表单、独立管理导航、Skill/经验入口、Trace统计和真实调用路径均已查看。390×844账单列表/详情无页面横向溢出；临时视口已恢复。未提交修订、审批、人工回复或新模型运行，历史真实EML仅用于读取旧中断与原件，不能作为1.4.0真实提取效果。
