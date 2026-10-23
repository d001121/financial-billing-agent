# LangChain 文档与 GitHub 源码交叉核验

> **研究快照。** 下文按当时版本保留取证；当前实现职责与自写边界以[实现方案](../implementation.md)、[AGENT.md](../../AGENT.md)为准，逐项执行见[最终开发计划](../superpowers/plans/2026-10-21-final-development-plan.md)。不能以研究中曾提出某机制作为自写授权。

依赖状态更新（2026-10-21）：用户随后要求补齐 MCP 可选依赖，现已安装 `langchain[mcp]==1.4.6`、FastMCP 4.1.2、MCP 2.3.0，本地 stdio 发现及发现上下文退出后调用已通过。下文未安装、未进行真实 MCP 调用的描述为此前研究时状态；当前依赖和复验命令见 [portable-environment.md](../portable-environment.md)。

核验日期：2026-10-21，Asia/Shanghai。本轮沿用 `ecosystem-primer` 的分层方法，并核对 `langchain-middleware` 指导；先调用当前会话的 LangChain 文档/API MCP，再通过 GitHub MCP 阅读固定版本的教程代码、框架源码与测试。Skill 示例若与锁定版本不一致，以用户要求和该版本的实际接口为准。

本文补充 [此前八个官方仓库的研究](../agent-architecture-research.md)，记录新增发现，不重新将历史教学应用、SDK 与真实集成混称为生产案例。没有安装业务扩展、运行在线模型、OCR、发送消息或实现业务 Agent。

## 1. 对本项目的结论

继续采用 **LangChain `create_agent` 主控 + 工具封装的提取/核对子 Agent + 确定性校验 + 有界修订 + 人工介入 + 独立改进评测**。

主控负责补齐主体和材料、调度、收回提案与决定下一步。简单结构化材料可直接走解析工具；无需每种文件格式增加一个 Agent。子 Agent 返回标注 revision、来源和问题的结构化提案，金额、字段继承、匹配约束、幂等及最终操作由代码处理。

| 关注点 | 官方已有能力或源码行为 | 项目仍须实现的部分 |
| --- | --- | --- |
| 协同 | Subagents 工具委派；Router 分流/并行；Handoffs 按状态切换；Skills 渐进加载；自定义局部工作流 | 按任务启用角色、显式主体与 revision 上下文、证据契约、统一账单合并 |
| Harness | `create_agent` 可组合规划、上下文、工具、重试与限制等 middleware | 跨角色共享预算、能力版本、幂等账本、业务完成条件和恢复协议 |
| MCP | 1.4.6 的 `langchain.mcp.MCPAdapter` 已有源码 | FastMCP 可选依赖与真实连接验证、热刷新管理、在途版本固定、执行前禁用检查 |
| Skill / Hook | 指令按需加载；模型和工具调用可由 middleware 包装 | Skill 发布/回滚、脚本入口管理、参数修改后的重校验、账单提交 Hook |
| 人工介入 | 中断、决策与同一检查点恢复 | 人工 revision、影响范围重算、旧审批失效、并发编辑、真实副作用核对 |
| 纠错与改进 | Rubric 在运行内修订；better-harness 在运行外比较候选 | 确定性财务门禁、无进展停止、最终独立评测、明确审核发布 |

详细分工及固定源码证据：

- [多 Agent 模式及当前官方教程](langchain-patterns-crosscheck.md)
- [MCP、动态工具、Skills 与 Hook](langchain-extensions-crosscheck.md)
- [人工介入、嵌套子 Agent 与恢复](langchain-hitl-crosscheck.md)

## 2. 本轮固定的源码快照

| 仓库或组件 | 固定 commit | 用途 |
| --- | --- | --- |
| `langchain-ai/docs` | `274fcd26537b0c1440600b4bb3ecce896aaac5d3`，2026-10-20 UTC | 当前多 Agent 教程中的实际 Python 代码块 |
| LangChain `1.4.6` | `84ba23c414eca6bf6f6ebd1394a3006378113540`，2026-10-14 UTC | 与项目便携环境安装版本对应的 MCP 和 HITL 接口 |
| `langchain-mcp-adapters` | `52a4535f3eb4b98f386836e4d9b8c4cadf99afca`，2026-09-11 UTC | 停止主动维护及迁移声明 |
| `deepagents` | `d1962cf329681bb668a9a92b4a38833df235090b`，2026-10-20T16:40:25Z | Rubric 与 better-harness 的补充核验 |

快照用于可复核引用，不宣称后续始终是最新版本。Deep Agents 快照提交标题发布的是仓库内 `deepagents-code` 包，不能把该标题中的版本号当作 `deepagents` Python SDK 版本。

旧适配库的 [维护与迁移声明](https://github.com/langchain-ai/langchain-mcp-adapters/blob/52a4535f3eb4b98f386836e4d9b8c4cadf99afca/README.md) 与 [当前官方迁移指南](https://docs.langchain.com/oss/python/migrate/langchain-mcp-adapters) 均已核对。项目内缺少 `fastmcp`，实际导入内置 MCP namespace 仍报缺依赖；后续采用该接口时，需安装并锁定 `langchain[mcp]` 的依赖后验证，不能把开发机 MCP 服务可用等同于项目已接入。

## 3. Harness 可以围绕 LangChain 主控组合

官方 [Agents：Configure the harness](https://docs.langchain.com/oss/python/langchain/agents#configure-the-harness) 明确以 middleware 作为扩展单元。规划与委派示例在 `create_agent` 中组合 `TodoListMiddleware`、Deep Agents 的文件上下文与子 Agent middleware。

这说明满足规划、子 Agent 和 Skill 等需求并不自动要求替换主控。本项目首先保持用户指定的 LangChain 主编排；需要的 Deep Agents 组件作为明确依赖或受控子 Agent 接入。文档中的 provider 字符串和默认模型不能覆盖项目统一模型配置，也不能替代 Qwen 实际关闭思考模式。

框架计数器与局部 middleware 的限制不是完整任务预算。主控、子 Agent、评分器、摘要、输出修复、优化器和重试的真实模型请求都应经过统一模型工厂与调用计数；外层委派次数不能代替内部模型请求数。工具预算同样计入真实派发和重试。

## 4. Rubric：有输出不代表通过

已读取 [官方 Grading rubrics 文档](https://docs.langchain.com/oss/python/deepagents/rubric) 和固定版本的 [rubric.py](https://github.com/langchain-ai/deepagents/blob/d1962cf329681bb668a9a92b4a38833df235090b/libs/deepagents/deepagents/middleware/rubric.py)。文档标注组件需要 `deepagents>=0.6.5` 且仍为 beta；这不是要求本项目安装它。

源码中的控制事实：

- [L75–97](https://github.com/langchain-ai/deepagents/blob/d1962cf329681bb668a9a92b4a38833df235090b/libs/deepagents/deepagents/middleware/rubric.py#L75-L97)：终态包含 `satisfied`、`max_iterations_reached`、`failed` 和 `grader_error`。只有 `needs_revision` 继续循环。
- [L500–511](https://github.com/langchain-ai/deepagents/blob/d1962cf329681bb668a9a92b4a38833df235090b/libs/deepagents/deepagents/middleware/rubric.py#L500-L511)：非通过终态仍保留最后模型输出；调用方必须读取状态或评测事件。
- [L609–621](https://github.com/langchain-ai/deepagents/blob/d1962cf329681bb668a9a92b4a38833df235090b/libs/deepagents/deepagents/middleware/rubric.py#L609-L621)：终止后再次调用可以开启新 grading run，重新计算局部迭代数。
- [L811–830](https://github.com/langchain-ai/deepagents/blob/d1962cf329681bb668a9a92b4a38833df235090b/libs/deepagents/deepagents/middleware/rubric.py#L811-L830)：grader 自身也是另一个 `create_agent`，使用自己的模型、工具和 middleware。

因此本项目的纠错上限和总预算必须位于持续存在的任务状态中，不能靠重新调用局部评分器刷新预算。若复用 grader，也必须将它的模型与工具纳入同一网关、思考关闭配置和预算。模型评审通过仍不能越过金额、币种、主体及更新语义等确定性校验。

文档与该固定快照关于回调的细节已有差异：文档描述上限回调仍收到 `needs_revision`，而该快照在发事件/回调前将结果改为 `max_iterations_reached`，见 [L798–809](https://github.com/langchain-ai/deepagents/blob/d1962cf329681bb668a9a92b4a38833df235090b/libs/deepagents/deepagents/middleware/rubric.py#L798-L809)。未来若采用组件，须固定依赖并测试适配，不把网页描述当跨版本保证；普通观察回调也不应承担财务提交门禁。

## 5. better-harness：选择集与最终测量分开

固定版本的 [run_experiment](https://github.com/langchain-ai/deepagents/blob/d1962cf329681bb668a9a92b4a38833df235090b/examples/better-harness/better_harness/core.py#L864) 提供真实的外层实验循环：

1. 运行 baseline 的 train 和 holdout。
2. 根据 train 结果生成候选，分别运行 train 和 holdout。
3. 比较两者合计通过数，增加才接受候选，见 [L921–941](https://github.com/langchain-ai/deepagents/blob/d1962cf329681bb668a9a92b4a38833df235090b/examples/better-harness/better_harness/core.py#L921-L941)。
4. 循环结束后，可选运行 baseline 和最终候选的 scorecard，见 [L969–981](https://github.com/langchain-ai/deepagents/blob/d1962cf329681bb668a9a92b4a38833df235090b/examples/better-harness/better_harness/core.py#L969-L981)。

该实现没有将 holdout 正文直接公开给提案，但 holdout 分数参与候选接受。因此它已经属于多轮选择过程。本项目据此将数据职责明确为：反馈/候选生成集、用于迭代选择的回归或验证集，以及不参与本轮生成与接受的最终独立评测集。最后一组若又用于下一轮调参，应记录其用途变化，不能继续声称完全独立。

此外，合计通过数增加可能同时伴随个别样本退步。金额、币种、主体、AR/AP、误新增/误更新、费用误合并、来源丢失和重复副作用必须分别检查；任何已覆盖关键错误新增都不能通过发布。沿用现有“候选→评测→明确审核→发布/回滚”约定，不允许线上任务自动改写全局财务规则。

## 6. 核验范围

除文档与源码比对外，已在项目 `python.cmd` 中执行离线运行时探针，使用固定假模型、内存 saver 和局部测试图：

- 拒绝工具 wrapper 时调用计数为 0；动态注入工具实现时调用计数为 1。
- 逐调用 HITL 的 approve/edit 真实执行本地 spy，reject/respond 均不执行；respond 仍返回框架成功消息。
- 暂停后更新检查点，恢复读取新值并保留旧检查点；在途节点不会实时读取另一路检查点编辑。
- 嵌套恢复重跑父调用节点和子中断节点的前置代码。

探针只验证所列框架语义，完整记录见相应子报告；未使用在线模型、真实 MCP 或数据库。没有证明项目已实现热插拔、Hook、人工修改或持久恢复。开发机原生 MCP 可用、项目运行时存在 MCP 源码、项目完成真实 MCP 调用是三个分别核验的状态。文档变更只需一致性和链接检查；真实集成与业务验收留给实现阶段。
