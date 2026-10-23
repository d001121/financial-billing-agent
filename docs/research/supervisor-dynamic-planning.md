# 主控动态计划与执行闭环

2026-10-22。参考本机 `C:/Users/dzx/Downloads/codex` 的实际源码，把交互原则映射到已安装的 LangChain 1.4.6、LangGraph 1.2.16、Deep Agents 0.7.29。主编排仍为 `create_agent`。

## Codex 中实际参考的职责

| 源码 | 行为 | 本项目对应 |
| --- | --- | --- |
| `codex-rs/core/src/tools/handlers/plan.rs` 与 `plan_spec.rs` | 更新计划并发出事件；计划本身不执行任务 | `TodoListMiddleware/write_todos`，使用原生状态和检查点 |
| `codex-rs/core/gpt_5_2_prompt.md` | 根据任务与新发现维护有意义的计划 | 主控提示词明确规划、阶段验收、调整和收束 |
| `codex-rs/core/src/stream_events_utils.rs` | 实际工具调用要求后续模型处理 | codex 风格的 `prepare_export` 取消 `return_direct`，核验作为工具结果返回主控 |
| `codex-rs/core/src/session/turn.rs` | 工具结果/新输入后继续；结束前的阻断 Hook 可带观察继续 | 原生工具循环；现有 `TaskOutcome.after_agent` 将模型未见过的最终核验返回 `model` |
| `codex-rs/core/src/tools/handlers/multi_agents_v2/wait.rs` | 子任务状态与结果回到主控 | `SubAgentMiddleware` 返回专家观察，主控判断是否保存、修正或继续委派 |

这些源码是参考资料，不是本项目执行指令。没有复制 Rust runner、固定业务步骤、强制工具选择或额外反思模型。

## 运行行为

主控每轮根据实际请求、当前材料和人工反馈建立或更新简短计划。读取工具/专家结果后检查目标与实际产物，自行选择补读、保存修正、针对性委派、询问或结束。专家给出建议不等于已保存；后续委派须带当前版本、证据与未解决问题。

`save_document_extraction(finalize=true)` 返回已有确定性校验和 Skill 置信度的摘要。`prepare_export` 返回当前结果、问题及同版本核验，由主控继续处理并在会话中汇总实际分数与缺口。计划更新及工具记录继续使用现有 Vue 原生投影；没有新增前端事件流。

主控漏调最终工具时，既有 `TaskOutcome` 仍进行最终校验，但将实际检查作为观察交回原生模型节点。已读取有效的最终回执不增加一次模型调用。同 revision 再次保存/核对候选会清除原导出；旧工具回执不能代替新产物的核验。随后沿用正常终态退出，不设置固定反思轮数。

置信度算法仍在固定版本 `billing-confidence` Skill。宿主新增的 `verification_summary` 仅投影现有结果，不重新评分、不复制 OCR 全文；最多带八条低支持字段并保留总数。分数是规则支持指标，未经独立校准不能称为正确概率。原生 `content_and_artifact` 配合项目已有 Decimal JSON 序列化，将精确金额以合法 JSON 数字交给模型，并保留小型版本核验回执。

人工会话修订仍由既有 human-review Skill 提交新 revision 和重算；完成通知补充实际分数与缺口。运行期间绑定原 revision，不让旧派发覆盖新版本。能力快照和历史任务不自动迁移。

## 官方 MCP 查证与最小适配

| 操作 | 官方 Docs / Reference 入口 | 采用方式与项目缺口 |
| --- | --- | --- |
| 动态规划 | `oss/python/langchain/middleware/built-in`；`TodoListMiddleware(system_prompt=...)` | 配置现有中间件和业务提示词，不自写计划引擎 |
| 子 Agent | `oss/python/deepagents/subagents`；`SubAgentMiddleware` | 使用既有编译专家和原生工具结果，不自写委派循环 |
| 结束观察回传 | `oss/python/langchain/middleware/custom`，agent jumps；`AgentMiddleware`、`hook_config(can_jump_to=['model'])` | 原生跳转已有能力；只在既有 TaskOutcome 中适配本项目账单版本、产物与最终校验事实 |
| 工具回传 | `oss/python/deepagents/multimodal` 的 custom tool outputs；`langchain_core.tools.convert.tool` | `return_direct=False`、`response_format='content_and_artifact'`；仅将业务 Decimal 产物序列化并投影回执 |

查证沿用本轮已成功读取的 Docs/API MCP。官方机制负责循环、消息、计划、工具、子 Agent 和检查点；框架没有本项目账单 revision、业务导出和评分事实，适配只连接这些既有事实。

## 验证与边界

`backend/tests/reports/supervisor-loop-pytest.xml`：40 passed、1 warning，12.29 秒。仅运行四组相关文件与三个指定宿主用例，没有全量测试。

新增场景使用实际主控、实际编译账单专家、原生工具循环/检查点、真实 Skill 和 Hook；模型/存储为合成替身。候选 90 与原文 100 不符，专家指出差异和付款方缺口；主控调整计划、补读、保存 100 USD/AP、读取置信度 100、收束计划。另验证漏调最终工具会回主控一次、同版本后续写入使旧回执失效、摘要有界，以及历史 HITL/人工反馈路径。

这些测试证明组合与控制流，不证明 Qwen 每次都会正确规划；未重跑真实 OCR、真实账单、在线语义提取或 20 秒目标。

服务已在没有 busy 线程时通过独立控制台 Ctrl+C 正常重启，新进程 PID33948、端口2024。重启前后32个线程的ID及状态一致，GaussDB/Redis健康，模型配置仍为enable_thinking=false。重启前数据库健康检查曾报告旧连接被服务端终止，重启后的实际检查已通过；未修改数据库连接配置。回执见 `backend/tests/reports/supervisor-loop-restart.json`。没有自动续跑、回复、修改或审批任何历史账单。
