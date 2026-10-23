# 账单4首次保存异常与单次真实生命周期验证

## 根因与修复

原任务 c9e97999-4e4f-4ae6-b3f1-6cee1119d7e5（账单4）首次 save_document_extraction 发生 TypeError("argument of type NoneType is not iterable")，4次模型、4次工具调用，活跃24.857秒；OCR缓存命中，无远程OCR HTTP耗时。保存前 charges 为空，dispatch_history 的保存调用为 running，未有业务保存回执，不能盲重试。

DispatchPolicy.progress_transaction 读取尚不存在的 candidate_digests/documents/totals 等字段。StagedRepository.mutate_fields 此前将整个读取投影合回原任务，因此将不存在的字段实体化为 null；SQL Repository 的同名方法只提交实际变更。随后首次保存对 candidate_digests 做列表成员检查失败。修复暂存层只合并实际变化的键，与现有SQL路径一致；保留非空字段显式清空及嵌套修改，不迁移原账单或静默更改其调用回执。

新增3项存储回归先失败后通过（含Redis不可用回退），另1项真实暂存层+进度领取+提取工具离线回归通过。16项存储与调用进度检查8.34秒、集成回归1项6.66秒，均只用内存存储/固定材料，不调用真实模型/OCR。

## 框架查证

操作→原生入口：Docs MCP Agent Server OpenAPI /threads/{thread_id}/state（subgraphs=true），Reference MCP langgraph_sdk._async.threads.ThreadsClient.get_state。创建/恢复沿用现有应用API及官方runs；核对Docs MCP /threads/{thread_id}/runs与Reference RunsClient.create。现有LangChain1.4.6/LangGraph1.2.16/DeepAgents0.7.30/SDK0.4.8组合不变。此次缺口是应用GaussDB/Redis记录合并语义，框架不替应用定义财务存储键；仅修改既有仓库投影写入，无新runner、状态机或模型调用。

## 单次真实验证

尚未执行。用户只授权一次新账单生命周期；复用原账单4图片，原账单4不覆盖；所有后续人工干预与修复在新建的同一任务上完成。

## 单次在线验证发现的回复缺陷（2026-10-24）

唯一新建任务 a43744d3-9269-49db-986b-b690715bdf66，使用原账单4图片，原账单未修改。首次保存通过，但模型误用费用名引用并将模糊数量提为11。两轮修复后REPAIR_LIMIT停止，12次模型（其中账单专家3次）、11次工具、活跃99.148秒，转入原生conversation_review中断。此结果验证实际退出，不证明自动提取全对。

第一次联调人工回复要求测试主体、数量与付款方式调整，ReplyDecision的FieldEdit原无charge_id与quantity；多费用fields转换为无目标操作被拒绝。旧after_agent把last_error而无proposal的回复当answer完成，未实际修订并重新提问。修复：结构化field包含真实charge_id与数量/单价，逐项保留目标；无有效目标回到原生handler；可恢复拒绝通过现有jump_to=model进入一次纠正，last_error时跳过重复分类，第二次拒绝仍按已有decision_error/6次回复预算结束。提案提示不再提前宣称已应用。未新增Agent或runner，沿用human-review事务。

新增4项回归先失败后通过，涵盖目标/清空/原生图提交及拒绝恢复；10项回复相关定向离线检查7.04秒通过，未全量测试。同步既有纯主体测试缺少resolves_pending的旧断言。

框架查证：Docs MCP /oss/python/langchain/middleware/custom 的wrap_model_call、after_agent及jump_to；Reference MCP langchain.agents.middleware.types.AgentMiddleware。当前安装组合不变；现成中间件负责原生跳转，应用只补业务费用ID传递及失败回执处理。
