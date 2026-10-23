# 四项 Harness 收尾

日期：2026-10-23。用户放弃让模型重写输入材料，授权按实际退出、证据保护、专家职责和共享预算四项收尾。沿用原件、原生图和人工待办，没有新增监督 Agent、runner 或队列。

## 实际退出

重复候选/纠错到限抛出带代码的 RepairStop。DispatchPolicy 保存绑定 revision/运行预算 ID 的 automatic_stop，阻止后续工具，在原生 before_model 使用 jump_to=end；完全相同的失败保存也记录失败，不能只返回一句停止提示后继续跑。

专家停止时返回结构化 status=blocked/saved=false，主控同样看到停止事实，不再重新抄写整单。ConversationReplies/TaskOutcome 确定性重算保留的候选、校验并进入已有 conversation_review 待办：优先询问缺少的主体/AR/AP关系，其余停止原因由 human-review Skill 转成具体问题。停止不能生成自动核验通过或人工批准。没有在 after_agent 跳 end，避免回到第一项收尾 Hook 循环。

真实新运行/用户回复可以清除上轮停止标志，任务累计计量保留；服务拒绝续跑时恢复原停止记录。人工 revision 和中断恢复沿用既有机制。

## 修复不能破坏已有证据

evidence-linking 2.1.4 新增 validate_repair({previous,candidate})，两侧按相同的当前原件重新回读，不相信原有 verified 标记。支持检查覆盖单号、费用名、金额、币种、数量、单价、付款方式。既有受支持字段变成非空但无支持的值时，拒绝整个候选事务，旧值、引用、修复计数和候选摘要保持原样。被拒绝的提案及字段反馈保留在原生工具轨迹中。

原本缺失的字段不填造，显式 null 可清空，有实际引用支持的不同值可接受。此检查只防止证据支持退化，不代替模型做业务语义判断，也不会自动把旧值填回新候选。

document-extraction 2.2.3 对提取结果根层未知参数报错，避免 result.replace 被静默丢弃；replace/finalize 应在工具顶层。内部合并生成的 revision/valid 在重新校验前去掉。human-review 2.0.7 提供停止待办，并防止停止后仍显示自动完成。

账单3只读快照回放：首次候选为 USD 5、USD 21.90；原第26条消息把多个字段引用换成费用名，新守护拒绝两行金额/币种/单价的退化；原第28条有支持的候选通过。回执 backend/tests/reports/bill3-loop-controls-replay.json。没有修改真实账单、重跑 OCR 或请求模型。

## 专家职责

Agent 配置增加可选 tools 清单。billing-specialist 仅保留读取候选、材料、文件搜索、计划及经验检索；不提供保存、重算、评分、OCR、提问、委派能力。工具披露、MCP/扩展工具过滤和派发边界均应用清单，权限不只依赖提示词。

提示词同步明确：候选未保存时核验委派内容，返回具体 proposals/ref_id；计算与提交交主控，不寻找 API 路径或重提取整单。文档专家保留必要的提取/保存能力，只处理委派范围。工厂通用提示不再要求所有专家都先保存产物。

## 统一预算

每次原生 start_run 分配 task_budget_id，工厂给父/子模型传入相同 ID 和各自角色。HTTP before_send 在已有事务中计入共享 task usage，包括重试、原生摘要及结构化回复。没有为计数增加模型调用。

| 限制 | 当前值 | 范围 |
| --- | --- | --- |
| model_calls | 24 | 整项任务，跨运行保留 |
| run_model_calls | 16 | 单次运行内主控、所有专家和重试共用 |
| expert_model_calls | 4 | 同一运行每种专家累计，重新委派不重置 |
| supervisor_reserve | 2 | 专家不能消耗的主控收尾空间，同时受任务剩余额度限制 |

原生 ModelCallLimitMiddleware 保留为图内限制，HTTP 层共享计数是跨图权威。before_model 提前结束；检查后触及额度的请求由 wrap_model_call 将 RunBudgetStop 转成停止回执。普通专家额度到限不把整个任务误标为 budget_exhausted。工具与活跃时间总上限保持。

检查使用字段投影，不在每个边界重新搬运整包 OCR。投影预算事务也包含 automatic_stop，避免仅内存测试能看到停止状态。

## 版本和验证

配置：skills v39、agents v15、runtime v8，Skill 元数据一致。历史发布目录及账单3固定能力 d8cb85b69f817092c6e4 未改，新任务沿用原有 snapshot 机制固定能力；未迁移历史任务。未启停后端，进程重载后使用新源码/新任务配置。

最终34项相关离线检查全部通过，16.87秒；其中20项新用例、14项既有回归，一个既有 LangChain MCP Beta 警告。使用真实安装的原生图、编译子 Agent、中断、检查点与 HTTP 请求前守护，模型响应替换为 httpx.MockTransport。

覆盖：重复保存后没有第3次模型请求；两轮纠错后停止；专家4次返回 blocked；真实委派共计7次模拟HTTP（专家4次、主控3次含最终核验回看）；并发专家共享14次可用额度；主控16次后没有第17次请求；文档专家停止后主控不重写；待办恢复并暂缓；null/有支持的新值可保存；投影停止校验；拒绝续跑保留停止事实。

记录 backend/tests/reports/loop-controls-targeted.xml。没有跑全量、真实模型/OCR、在线端到端或正式数据库并发测试；不能据此证明线上提速或总体准确率提升。

## 本轮已查证的原生操作

| 操作 | 官方入口/符号 | 实际组合与验证 |
| --- | --- | --- |
| 下一轮模型前退出 | Docs MCP custom middleware；Reference MCP hook_config/ModelResponse | LangChain1.4.6；before_model jump_to=end，原生 after_agent 收尾；离线图验证 |
| 编译子 Agent及工具限制 | Docs MCP Deep Agents subagents、安装源码 | DeepAgents0.7.30；独立子图显式装配 middleware，共用事务计量 |
| 原生图次数限制 | Reference MCP ModelCallLimitMiddleware(thread_limit,run_limit,exit_behavior) | 原生 end 加既有 HTTP 计数；编译父子图离线验证 |
| 待办与恢复 | 当前会话已核对的 interrupt/Command、现有 ConversationReplies | LangGraph1.2.16、SDK0.4.8；既有接口和检查点恢复验证 |

官方入口：https://docs.langchain.com/oss/python/langchain/middleware/custom 、https://docs.langchain.com/oss/python/deepagents/subagents 、https://reference.langchain.com/python/langchain/agents/middleware/model_call_limit/ModelCallLimitMiddleware 。没有安装或升级依赖。
