# 财务智能体收敛

2026-10-23。先创建并上传私人仓库 d001121/financial-billing-agent，基线 30be1a6，再分阶段修改和提交。只做定向离线验证，不调用真实模型/OCR、不启停后端、不迁移历史任务。

采用图片中的工程原则：确定性的重复执行控制、明确任务契约、上下文隔离、结构化交接和共享预算。保留现有原生 LangGraph/Deep Agents、todos、中断与检查点；不新增执行引擎或固定财务 DAG，不以模型自评替代财务证据。

## 第一步：派发事实持久化

现有 DispatchPolicy.attempts 只在实例内记录失败，图重建、重新委派和并发调用可绕开。使用已有 repository 条件事务保存 dispatch_history：运行、revision、角色、参数摘要、候选事实摘要、工具状态和调用标识，不保存额外材料副本。

只对 task/intake_documents/read_document_sources/save_document_extraction 控制重复执行；普通只读搜索仍可在上下文清理后重新读取。相同事实的已完成/失败调用再次派发时实际阻断并停止自动纠错；并发在途或结果未知时拒绝盲重试。候选变化允许定向后续操作；补读理由改写和接入工具的提示 asset_ids 不算新事实。网络错误交给原生有界 ToolRetry；嵌套 GraphInterrupt 仅原调用可恢复。摘要不推断语义等价，也不保证远端未知副作用可回滚。

官方查证：Docs MCP custom middleware 的 wrap-style hooks 允许零次/一次调用 handler；Reference MCP AgentMiddleware、langgraph.prebuilt.ToolCallRequest；本机 LangChain1.4.6/LangGraph1.2.16。原生 Hook 没有本项目候选/revision/任务事务语义，缺口只补在现有派发策略里。Codex 本地源码的工具消息/回合职责用于对照，未复制执行循环。

第一轮定向检查24项通过（本轮4项与既有20项循环控制），后续补充中断恢复/未知结果检查并与下一阶段合并验证。一个既有 LangChain MCP Beta 提示，不代表线上时延或准确率结果。

## 后续实施范围

第二步在原生 task 的 description 内校验目标、范围、问题与验收条件，宿主补充真实身份/版本/预算，隔离完整聊天与非必需状态。第三步复用原生 compiled subagent 的 structured_response 交接，校验输出和真实保存状态，附宿主计量与未解决项。格式不合法直接返回 blocked，不为修复格式另发模型请求。每一步完成后提交并推送。
