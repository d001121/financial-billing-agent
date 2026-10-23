# 账单4首次保存异常与单次真实生命周期验证

## 根因与修复

原任务 c9e97999-4e4f-4ae6-b3f1-6cee1119d7e5（账单4）首次 save_document_extraction 发生 TypeError("argument of type NoneType is not iterable")，4次模型、4次工具调用，活跃24.857秒；OCR缓存命中，无远程OCR HTTP耗时。保存前 charges 为空，dispatch_history 的保存调用为 running，未有业务保存回执，不能盲重试。

DispatchPolicy.progress_transaction 读取尚不存在的 candidate_digests/documents/totals 等字段。StagedRepository.mutate_fields 此前将整个读取投影合回原任务，因此将不存在的字段实体化为 null；SQL Repository 的同名方法只提交实际变更。随后首次保存对 candidate_digests 做列表成员检查失败。修复暂存层只合并实际变化的键，与现有SQL路径一致；保留非空字段显式清空及嵌套修改，不迁移原账单或静默更改其调用回执。

新增3项存储回归先失败后通过（含Redis不可用回退），另1项真实暂存层+进度领取+提取工具离线回归通过。16项存储与调用进度检查8.34秒、集成回归1项6.66秒，均只用内存存储/固定材料，不调用真实模型/OCR。

## 框架查证

操作→原生入口：Docs MCP Agent Server OpenAPI /threads/{thread_id}/state（subgraphs=true），Reference MCP langgraph_sdk._async.threads.ThreadsClient.get_state。创建/恢复沿用现有应用API及官方runs；核对Docs MCP /threads/{thread_id}/runs与Reference RunsClient.create。现有LangChain1.4.6/LangGraph1.2.16/DeepAgents0.7.30/SDK0.4.8组合不变。此次缺口是应用GaussDB/Redis记录合并语义，框架不替应用定义财务存储键；仅修改既有仓库投影写入，无新runner、状态机或模型调用。

## 单次真实验证

已执行完毕，只有一次新建账单；全部人工干预和恢复均发生在同一任务，详情见后文。

## 单次在线验证发现的回复缺陷（2026-10-24）

唯一新建任务 a43744d3-9269-49db-986b-b690715bdf66，使用原账单4图片，原账单未修改。首次保存通过，但模型误用费用名引用并将模糊数量提为11。两轮修复后REPAIR_LIMIT停止，12次模型（其中账单专家3次）、11次工具、活跃99.148秒，转入原生conversation_review中断。此结果验证实际退出，不证明自动提取全对。

第一次联调人工回复要求测试主体、数量与付款方式调整，ReplyDecision的FieldEdit原无charge_id与quantity；多费用fields转换为无目标操作被拒绝。旧after_agent把last_error而无proposal的回复当answer完成，未实际修订并重新提问。修复：结构化field包含真实charge_id与数量/单价，逐项保留目标；无有效目标回到原生handler；可恢复拒绝通过现有jump_to=model进入一次纠正，last_error时跳过重复分类，第二次拒绝仍按已有decision_error/6次回复预算结束。提案提示不再提前宣称已应用。未新增Agent或runner，沿用human-review事务。

新增4项回归先失败后通过，涵盖目标/清空/原生图提交及拒绝恢复；10项回复相关定向离线检查7.04秒通过，未全量测试。同步既有纯主体测试缺少resolves_pending的旧断言。

框架查证：Docs MCP /oss/python/langchain/middleware/custom 的wrap_model_call、after_agent及jump_to；Reference MCP langchain.agents.middleware.types.AgentMiddleware。当前安装组合不变；现成中间件负责原生跳转，应用只补业务费用ID传递及失败回执处理。

## 最终在线结果（2026-10-24）

- 新建任务：a43744d3-9269-49db-986b-b690715bdf66；原生线程01a1697e-a599-7456-983f-7e20906b01e1。仅此一条新建，未重跑整单。
- 第一轮候选保存通过；REPAIR_LIMIT在两轮后真实停止并打开原生中断。首次回复因上述缺陷未应用，保留原始失败记录。修复后用新reply_id恢复现有中断、再次提交同一联调文字，1次真实模型请求成功生成revision2。
- 测试主体明确仅用于联调，取原件收款方；AR来自这次明确测试输入。两笔原件金额5.00 USD与21.90 USD保留。两笔quantity与payment_term为null，未补造模糊数量或PP/CC。人工修改使旧校验失效并重算。
- 原生状态next=[]、tasks=[]、run_status=success。complete-review返回200，业务status=completed，但review_confirmation.decision=completed_with_gaps、validation.ok=false、approval=null。这是带缺口完成审核，不是财务校验通过或批准。
- 仍有3项硬问题：2项FIELD_VALUE_UNSUPPORTED（费用名称引用错位）、1项TOTAL_MISMATCH。按联调输入暂缓保留。草稿导出200、2条PENDING_REVIEW；正式导出422，未绕过门禁。
- 共享计数器合计14次真实模型请求、11次工具派发，活跃106.796秒。首次自动轮12次模型（账单专家3次）、约99.148秒；两次人工回复各1次模型。创建到结束969.261秒，包含中途诊断、离线测试、两次服务启动等待及人工等待，不能当作纯处理性能。
- 解析/OCR沿用原件缓存；接入回执保留上次解析来源，补读一次也命中远程OCR响应缓存（本次补读耗时约0.115秒，HTTP为0）。没有新的远程OCR HTTP请求，不能把本次写成OCR在线冷调用验证；文本模型使用当前配置qwen3.7-flash，enable_thinking=false。
- 重载前确认无busy线程，使用控制台Ctrl-C正常停止，再启动官方服务。首次重载前后线程ID/状态一致；误开的一次辅助dev进程自动选择其他端口，已在创建验证账单前停止，未处理业务任务。最终仅2024端口服务，PID22576，GaussDB/Redis健康。
- 原账单4与本轮最初快照完整比较相同，未覆盖异常记录或修改它的业务数据。全部真实原件、请求、响应、状态、导出与日志只留本机忽略目录backend/tests/reports/bill4-diagnosis/；原件与密钥未入Git。

离线验收分批27项通过（存储/进度17，回复10），未跑全量，未使用第二条真实账单。真实结果证明保存异常、人工修订及结束/导出门禁路径生效；自动提取本身仍有上述证据与合计缺口，不能宣称总体准确率或无人工自动完成已验收。
