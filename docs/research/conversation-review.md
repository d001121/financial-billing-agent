# 会话式人工审核，2026-10-22

## 最新修复：发送稳定与主体目标闭环

121d的真实问题分两层：用户“主体是纳斯达克公司”已保存为revision2；材料识别的收款方为CMA CGM (AMERICA) LLC、付款方为NEPTUNE SHIPPING LIMITED，现有posting Hook返回“当前记账主体不属于已识别的收费关系”，不是主体漏保存。旧收束规则把这类有输入但关系冲突也归入completed_with_gaps，最后receipt只给已有字段100分，缺少继续问答。本轮主控提示与结束边界明确：可选缺值不强迫人工核对；已提供主体但posting仍不成立，应从证据解决或原生中断询问具体角色/关系，收到真实答复才继续。明确暂缓保留结果。`hooks/completion.py`只消费绑定当前revision的既有财务Hook事实，不解析或重新计算AR/AP；财务算法及实际人工修订仍在固定版本Skill中。

自然语言修订事务提交后若仍有上述问题，ConversationReplies保存带source=completion的review_request，原生interrupt展示明确主体、材料双方及需回答的关系。恢复核对真实reply_id与revision再交给模型；原节点重放不得重复提交已完成的修订。调用方明确本主体付款时，用原human-review的debtor修订和既有对账算法得到AP；只编辑posting_type不构成财务关系依据。新任务human-review2.0.1/skills配置v20；既有任务财务Skill快照保持不变，新的Harness结束检查适用于后续继续的运行。

另一个根因在Agent Server0.16.2：commands/run.start遇到遗留thread interrupt map，会把普通input.messages变成Command.resume，已结束的图因此空跑success，业务状态留running；pending review_request又阻止重试。已结束线程的新轮现使用官方POST threads/{id}/runs的显式input，真实中断回答仍用原生commands resume；保留reject/sync、原生v2消息形状。REST OpenAPI不接受tools/lifecycle这两个stream_mode，实际模式为values/updates/messages/custom/tasks/checkpoints；它们仍有实时v2事件，刷新恢复已保存ToolMessage，不能把这写成tools/lifecycle完整事件回放。sync_task只读投影识别“native成功、无next/interrupt但业务仍running”为recovery_required；用户点击时可重开同一待修订请求，不批量自动重跑历史账单。

前端发送会闪烁，是父组件按streamEpoch整体重挂AgentPanel，清掉sentInterrupt、本地提交状态和消息；用户原话又等待API返回才显示。现在组件按thread固定，epoch只触发官方Vue SDK响应式threadId重接，已展示投影保持到新投影到达。发送即按reply_id追加原话和sending状态，成功合并服务端记录，失败保留输入与同一请求ID；发送中禁用同一输入框，受理后隐藏旧问题，只有新真实中断才显示新输入框。错误与新中断之外不重复聚焦，不重建会话面板或自造SSE。

验证：31项定向测试通过（9.42秒，1项langchain.mcp beta warning），报告conversation-goal-fix-pytest.xml；Vue类型及生产构建通过（2495 modules、1.08秒、index-BYNGcjdS.js）。真实隔离Agent Server2025配合最终Vue、合成模型/存储，reply接口故意延迟3秒：点击即出现原话/正在发送，主体Unrelated产生新关系问题，刷新仍能回答，再回复Unrelated是付款方得到AP、revision3且旧输入框隐藏。合成金额65与原文100仍有其他缺口，最终completed_with_gaps不能宣称整单核验通过。截图conversation-goal-sending-final.jpg、conversation-goal-completed-final.jpg。真实121d恢复既有待修订中断，业务revision2、金额245.0000未变，未代答/重跑OCR/Qwen/审批；重启完整性与实际页面以conversation-goal-restart.json和conversation-goal-live.json为准。未做全量测试或真实模型语义评测。

## 当前交互

账单详情的“智能体处理过程”改为“账单助手”会话：助手回复与用户补充按轮展示，Markdown表格正常渲染，工具名称、参数、实际命令与返回按需展开，计划及专家记录折叠。默认不放常驻输入框；只在检查点确有待回答中断时显示一个内联回复框。多个问题时选择正在回复的问题，不把同一句话批量批准所有请求。

“补充/修改记账主体”“人工修订”“修订费用”“拆分/删除费用”和针对性复核入口，对原生线程账单统一进入会话。用户直接说明正确内容或确认意见，不再填写中断JSON、选择处理类型或打开审核弹窗。原件预览、定位和结果表格继续可用。完成、运行中、暂停和已处理的旧中断不显示输入框；同步失败提供原位重新连接并保留记录。

## 运行与业务边界

```mermaid
flowchart LR
  E[Agent请求人工信息或用户选择修改] --> I[原生HITL或middleware中的interrupt]
  I --> C[会话问题与一个输入框]
  C --> R[保存真实回复及interrupt ID]
  R --> N[同线程原生Command resume]
  N --> A[现有Agent理解回复]
  A --> P[record_review_decision记录提案]
  P --> S[原human-review Skill校验与事务应用]
  S --> V[新revision与既有财务核验]
  V --> M[结果回到同一会话]
```

- `api/routes/conversation.py`提供reply和review-conversation两个薄接口。只接受真实中断ID、当前revision和非空自然语言；保留reply_id以避免重复受理。检查暂停、运行并发与共享预算。不是把缺字段全部变成人工任务。
- 用户主动选择修改时，ConversationReplies.before_agent调用原生interrupt，打开问题本身不调用模型。真实ask_user按原生per_call respond传回文本。历史confidence_review将自由文本送回模型，绝不默认转换为confirm。其他受控工具的文字反馈不等于执行授权。
- `middleware/conversation.py`用AgentMiddleware.tools注册原生工具，ModelRequest.override注入真实用户回复；没有待处理回复时向模型隐藏该工具。回复文本不能扩大工具权限，材料中的句子不能冒充用户回复。
- Agent提出结构化修订后，原human-review.apply_revision/prepare_recalculation负责字段白名单、类型、确认锁与删除/拆分历史。after_agent只在本轮调用结束时事务写revision+1并重新核验，避免正在执行的图中途改变版本。新旧主体与费用不静默混用；修改不等于批准财务导出。
- 已结束会话仍用普通messages input，真实等待问题使用Command(resume)。本轮不新建Agent循环、SSE装配器、队列、Skill runner或财务算法。原生after_agent的model跳转使历史return_direct审核工具的回复真正交给模型，不跳过解释直接完成。
- conversation保存问题、真实原话、归属工具/消息、revision、提案与应用版本。刷新后按原生检查点和回复出处恢复问答顺序，内部任务快照不显示成用户发言。
- 新增middleware的正常轮只读取conversation/review_request小投影；回复已被模型读取的标记也用mutate_fields，避免每次模型调用传输完整PDF/OCR产物。
- run返回success不代表没有人工问题，必须检查原生tasks[].interrupts。前端结合这一投影和已受理回复过滤旧中断，防止审核后仍留下输入框。
- 没有修改不可变Skill发布目录、历史任务能力或历史材料，没有自动续跑/代答真实任务。模型仍关闭思考。

## 官方能力查证

开发前通过LangChain Docs MCP读取`oss/python/langchain/human-in-the-loop`的per_call/respond、`oss/python/langgraph/interrupts`的同线程resume与多中断、`oss/python/langchain/middleware/custom`的tools、ModelRequest.override、after_agent状态更新及hook_config跳转。API Reference MCP查到HumanInTheLoopMiddleware、AgentMiddleware.tools与StateSnapshot；精确get_symbol未命中时不据此宣称能力不存在，并核对安装源码factory.py的after_agent条件边。

安装版本：langchain1.4.6、langgraph1.2.16、deepagents0.7.29、Agent Server0.16.2，Vue SDK1.2.5/core1.2.19。官方承担执行/恢复/工具注册；项目仅补真实业务回复与既有revision的接线、落库和用户界面。Markdown采用markdown-it14.3.3，关闭原始HTML，外部图片只显示文字；npm安装检查为0 vulnerabilities。

## 定向验证

- 32项相关测试通过（9.76秒，1项既有langchain.mcp beta warning），报告`backend/tests/reports/conversation-pytest.xml`；没有全量测试。覆盖原生单句回复、同线程恢复、字段/主体修订及确认锁、旧revision、过期问题、预算/暂停、重复受理、修改不当作批准、历史return_direct审核回到模型、真实中断与success区分、原Harness反馈及旧结构化接口兼容。
- Vue类型与生产构建通过：2494 modules，Vite0.961秒，入口index-BShsDezv.js；保留较大的Agent SDK分包构建提示。
- 隔离2025端口的真实Agent Server配合最终生产Vue，只有模型、材料及业务存储为合成替身。通过浏览器发送两句合成回复，revision1→2→3，用户问答/折叠工具/Markdown表格可见；刷新恢复，结束无输入框，修改主体进入原生中断而无dialog。没有真实OCR/Qwen调用或真实业务修改。
- 浏览器截图与最终服务状态见`conversation-ui.json`、`conversation-review.png`、`conversation-actual.png`和`conversation-restart.json`。截图不能替代真实模型语义准确率、长材料时延和全部异常矩阵的评估。
