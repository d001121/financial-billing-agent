# 条件复核与直接修订

日期：2026-10-21。用户要求仅针对低置信度提取值进行人工中断，未提供的信息不算低分，正常账单自动审核结束。用户能够在结果页查看六字段、分数、原文及原件定位，按需修改提交。

## 规则与状态

整体证据支持score保留70/20/10公式，缺可选算术或总额不凭空补分。已有字段review_score独立计算，只消费新鲜来源事实和确定性方向校验；金额45%、币种35%、费用名20%，存在的编号/付款方式/AR/AP各10%后按可观察权重归一。无原文值的缺失项完全排除；有引用raw但无法解释的金额或币种仍是需复核的真实观测。任务取最低费用分，任一字段低于阈值仍产生具体复核项，不能被平均分掩盖。默认阈值80，严格小于，runtime.confidence_review_threshold按任务固定；未经金标校准，不称统计正确率。

- completed：完整硬校验通过且无待处理低分字段，自动核验完成；auto_review与人工approval分开记录。
- awaiting_review：实际低置信度已有值，包含字段、现值、原因和原文入口的原生中断。
- completed_with_gaps：已有提取可查看、修改或下载草稿；财务必需信息缺失/校验失败仍禁止正式导出。
- incomplete/error/budget_exhausted：保留真实未完成事实，不因为Agent停下就强制标成待人工确认。
- review_deferred：用户明确暂缓，保留结果，不能作为通过。

修订失效旧自动核验、人工审批和确认；重算当前候选、证据、财务与置信度，不重复OCR。原生中断待回复期间即使修正完成，也须消费该中断的明确答复后才能清理。旧答复版本过期时再产生原生表单，不接受过期确认。高分、自动核验和人工确认均不能覆盖硬财务错误。正式导出在当前版本锁内重算全部Hook，核对完整导出参数及能力绑定。

## 官方能力查证

实际调用LangChain Docs MCP和API Reference MCP后采用原生组合，安装langchain1.4.6/langgraph1.2.16/deepagents0.7.29，Vue SDK1.2.5。

| 操作 | 官方入口/符号 | 本项目组合 |
| --- | --- | --- |
| 条件中断 | /oss/python/langchain/human-in-the-loop#conditional-interrupts，HumanInTheLoopMiddleware.when | 原生能力已存在；评分发生在工具内部，使用下面的官方工具内中断，而不在可变数据库分数上设置不稳定when |
| 字段复核表单 | /oss/python/langgraph/interrupts，langgraph.types.interrupt | prepare_export/原生after_agent只组合原生interrupt，不自建runner；持久化pending载荷确保恢复时仍到相同第一个中断 |
| 恢复与重放 | /oss/python/langgraph/graph-api#re-execution-and-idempotency | replay前操作仅幂等产物核验，复用源材料；按原生中断ID用Vue respond/respondAll，过期答复不覆盖新revision |
| 业务规则 | SkillsMiddleware现成发现、披露、工具执行 | 置信度/分流在billing-confidence，核验绑定/结果裁决在human-review，宿主只有存取与原生调用适配 |

## 界面修正

所有409曾被前端统一显示为版本冲突并永久禁用提交，这是主体表单被锁的直接交互原因。现在AGENT_RUNNING、策略失败和CAS冲突区分处理；提交前读取最新结果，若所修改字段没有冲突可安全使用新revision；若字段同时被改，在窗口内显示双方内容并允许用户明确保留本次输入。表单不关闭、不要求复制重填。主体修订前没有正式records时也保留已提取候选。

更多业务信息改为每项费用独立纵向字段表和响应式分组，去掉1900px宽表；修订弹窗可滚动且操作栏可达。低分中断仅列真实字段，提供原文/修改入口和普通表单，业务用户无需填写JSON。

## 验证范围

后端验证使用明确合成材料和隔离存储，保留官方create_agent、工具、检查点、interrupt和Command的实际运行；模型HTTP替换为固定响应。覆盖自动核验直接导出、硬错误不可导出、缺信息不生成人审、付款方式、raw歧义、旧版本答复、修改后恢复不重新提取、主体补充不重置预算、运行中409和模型漏调prepare_export。全量及浏览器最终记录由本轮验收更新，不将模拟验证声称为真实OCR/模型准确率。

最终全量374 passed、43 warnings、4 subtests passed，126.21秒，日志conditional-review-pytest.txt/XML。前端vue-tsc及Vite成功，2411 modules、构建段1.10秒，入口index-bXBaz-K0.js。

浏览器真实提交仅操作明确合成任务9c05b673-f550-42dc-b88c-a114891bcf7a：初始budget_exhausted、主体null、模型调用24次；补充Synthetic Client后revision2、AP、completed、auto_review.mode=automatic、approval=null、review_required=false、review_score100，模型调用保持24次。此样例缺单号、付款方式、数量单价和总额，均未强制转人工审批；原总体score仍保留独立支持度口径。见conditional-review-browser-fixture.json、conditional-review-browser-result.json及conditional-review-completed.png。真实历史账单f29ad90d-12b2-4035-98ae-b4eb82719c81只查看更多信息、打开/填写/取消主体弹窗，没有提交或迁移。

运行服务已应用新代码。最初强制停服操作被自动策略拒绝，随后通过核实独立控制台且无busy，发送Ctrl+C正常退出并等待端口释放再启动；未强杀。重启前后18个线程ID和status相同，数据库/Redis健康，报告conditional-review-server.json和conditional-review-restart-check.json。当前新任务能力3d1f75d53d4d20188672，skills v8/runtime v2；旧能力仍固定旧契约，不以新分流静默重算历史任务。

浏览器低分中断恢复、完整窄屏/键盘/并发交互矩阵未全验；原生低分恢复已有上述隔离测试。独立真实金标和真实长材料性能仍待验。
