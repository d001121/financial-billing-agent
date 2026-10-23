# 账单4首次保存异常与单次真实生命周期验证

## 根因与修复

原任务 c9e97999-4e4f-4ae6-b3f1-6cee1119d7e5（账单4）首次 save_document_extraction 发生 TypeError("argument of type NoneType is not iterable")，4次模型、4次工具调用，活跃24.857秒；OCR缓存命中，无远程OCR HTTP耗时。保存前 charges 为空，dispatch_history 的保存调用为 running，未有业务保存回执，不能盲重试。

DispatchPolicy.progress_transaction 读取尚不存在的 candidate_digests/documents/totals 等字段。StagedRepository.mutate_fields 此前将整个读取投影合回原任务，因此将不存在的字段实体化为 null；SQL Repository 的同名方法只提交实际变更。随后首次保存对 candidate_digests 做列表成员检查失败。修复暂存层只合并实际变化的键，与现有SQL路径一致；保留非空字段显式清空及嵌套修改，不迁移原账单或静默更改其调用回执。

新增3项存储回归先失败后通过（含Redis不可用回退），另1项真实暂存层+进度领取+提取工具离线回归通过。16项存储与调用进度检查8.34秒、集成回归1项6.66秒，均只用内存存储/固定材料，不调用真实模型/OCR。

## 框架查证

操作→原生入口：Docs MCP Agent Server OpenAPI /threads/{thread_id}/state（subgraphs=true），Reference MCP langgraph_sdk._async.threads.ThreadsClient.get_state。创建/恢复沿用现有应用API及官方runs；核对Docs MCP /threads/{thread_id}/runs与Reference RunsClient.create。现有LangChain1.4.6/LangGraph1.2.16/DeepAgents0.7.30/SDK0.4.8组合不变。此次缺口是应用GaussDB/Redis记录合并语义，框架不替应用定义财务存储键；仅修改既有仓库投影写入，无新runner、状态机或模型调用。

## 单次真实验证

尚未执行。用户只授权一次新账单生命周期；复用原账单4图片，原账单4不覆盖；所有后续人工干预与修复在新建的同一任务上完成。
