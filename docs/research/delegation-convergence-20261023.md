# 财务智能体收敛

2026-10-23。先创建并上传私人仓库 d001121/financial-billing-agent，基线 30be1a6，再分阶段修改和提交。只做定向离线验证，不调用真实模型/OCR、不启停后端、不迁移历史任务。

采用图片中的工程原则：确定性的重复执行控制、明确任务契约、上下文隔离、结构化交接和共享预算。保留现有原生 LangGraph/Deep Agents、todos、中断与检查点；不新增执行引擎或固定财务 DAG，不以模型自评替代财务证据。

## 第一步：派发事实持久化

现有 DispatchPolicy.attempts 只在实例内记录失败，图重建、重新委派和并发调用可绕开。使用已有 repository 条件事务保存 dispatch_history：运行、revision、角色、参数摘要、候选事实摘要、工具状态和调用标识，不保存额外材料副本。

只对 task/intake_documents/read_document_sources/save_document_extraction 控制重复执行；普通只读搜索仍可在上下文清理后重新读取。相同事实的已完成/失败调用再次派发时实际阻断并停止自动纠错；并发在途或结果未知时拒绝盲重试。候选变化允许定向后续操作；补读理由改写和接入工具的提示 asset_ids 不算新事实。网络错误交给原生有界 ToolRetry；嵌套 GraphInterrupt 仅原调用可恢复。摘要不推断语义等价，也不保证远端未知副作用可回滚。

官方查证：Docs MCP custom middleware 的 wrap-style hooks 允许零次/一次调用 handler；Reference MCP AgentMiddleware、langgraph.prebuilt.ToolCallRequest；本机 LangChain1.4.6/LangGraph1.2.16。原生 Hook 没有本项目候选/revision/任务事务语义，缺口只补在现有派发策略里。Codex 本地源码的工具消息/回合职责用于对照，未复制执行循环。

第一轮定向检查24项通过（本轮4项与既有20项循环控制），后续补充中断恢复/未知结果检查并与下一阶段合并验证。一个既有 LangChain MCP Beta 提示，不代表线上时延或准确率结果。

## 第二步：原生委派契约

agents v16 为两个专家启用 delegation_contract，旧能力缺省 false。保持 task(description, subagent_type) 原生协议；description 用 Pydantic 校验 goal/source_ids/charge_ids/questions/acceptance。拒绝未知来源/费用和不一致范围，宿主补充任务ID、revision、能力版本、主体、候选、停止条件、工具权限和剩余共享预算；主控不能自报这些权威字段。相同契约JSON的格式/清单顺序变化不产生新任务身份。

原生 SubAgentMiddleware 自定义 task_description/system_prompt，继续隔离聊天；显式排除父图的私有次数状态，HTTP共享预算不变。文档专家工具清单移除接入、评分、问用户及再次委派；补读/保存按契约校验，不允许 replace 整单，默认 read_materials 只展开委派来源。正文与原件保留，不进行模型改写。文件搜索仍可读取当前任务存档，范围约束不宣称是跨租户文件沙箱。

Docs MCP subagents、custom middleware；Reference MCP SubAgentMiddleware、langgraph.prebuilt.ToolCallRequest.override；本机 DeepAgents0.7.30 实际支持 task_description、private_state_keys。原生负责隔离和派发，业务范围与身份校验是当前薄适配的具体缺口。

29项定向离线检查通过，17.60秒，包括旧循环控制20项、本轮派发6项、委派契约3项。新增模糊指令/外部来源不派发、真实版本预算注入、未知结果不盲重试与原生中断恢复。无真实模型/OCR请求。

## 第三步：有回执的结构化交接

ExpertHandoff 通过原生 after_agent 写入 structured_response，由现成 CompiledSubAgent/task 序列化给主控。Pydantic 验证 status/summary/saved/proposals/issues/evidence_refs，宿主追加真实任务/能力版本、委派范围、已知引用来源和共享计量。引用索引复用 document-extraction.citation_index，既不另写证据算法，也不把“引用存在”宣称为语义正确。

格式不合法、未知/跨委派来源引用、修改建议没有引用、费用范围错误或无保存回执却声称保存时返回 blocked，不增加格式修复模型请求。saved 来自本运行/角色/委派ID对应的成功保存事实，不相信专家自报。结构化提案仍需主控提交与既有财务校验；done 只表示本次专业检查结束，不代表财务审批通过。

验证合法保存时发现：原生隔离委派会排除父级 pinned_skills，文档专家首轮可能只有 read_task_context，直接保存会报工具不存在。现以原生 before_agent 给专家独立 pin document-extraction，只补必需正文与工具，不复制父级聊天；恢复时已有 pin 不重复添加。Docs MCP skills#pin-skills / skills-for-subagents、Reference MCP SkillsMiddleware 与本机0.7.30源码均已核对。原生 compiled structured_response 也已从 Docs/API 与安装源码核对；使用 after_agent 格式校验而非另发 with_structured_output 请求，避免增加付费调用。

resource_usage 明确区分任务累计模型/工具次数与当前专家角色的单轮累计模型次数，不冒充单次委派的精确token/耗时或统计置信度；原有模型耗时/token回执仍保留。symbol/API核对使用当前两台MCP，不升级依赖。

最终45项定向离线检查全部通过，24.18秒，一个既有LangChain MCP Beta提示。覆盖原生编译专家：不合法格式、假保存、假引用、无依据修改建议均blocked；合法只读交接1次专家模拟HTTP，合法保存2次，未额外修复格式；主聊天标记不进入专家，任务版本/共享次数来自宿主。还覆盖范围越界/整单replace阻断、默认阅读范围、专家额度用尽时不启动、图重建/并发重复拦截、未知结果/原生中断恢复、既有证据保护与人工回复，以及配置与Skill版本一致性。

回执：backend/tests/reports/delegation-convergence-targeted.xml（本机报告，不上传真实业务材料）。模型HTTP均为MockTransport，存储为隔离事务替身；未跑全量、真实模型/OCR、正式数据库并发或在线端到端。不能据此声称实际时延/准确率提升。未启停后端、修改历史账单/原始材料或迁移固定能力；进程重载后新任务使用agents v16，旧能力缺省不强制新委派契约。
