# LangChain 主控与 Deep Agents 子 Agent：原生能力复用核查

> **研究快照，2026-10-21复核。** 固定源码/API证据保留；当前规则以[AGENT.md](../../AGENT.md)、[实现方案](../implementation.md)及[最终开发计划](../superpowers/plans/2026-10-21-final-development-plan.md)为准。领域代码归Skill，拟自写职责逐项先查MCP；官方Server管理检查点，不恢复自研网关/runner或默认GaussDB saver。

核查日期：2026-10-21。本文只记录研究结果和拟定组合，不安装依赖、不执行业务代码，不代表当前便携环境已具备下述全部接口。

已完整读取当前 `AGENT.md`；采用 `ecosystem-primer`、`deep-agents-core` 与 `deep-agents-orchestration` Skill 作为检索入口，结论再经本轮 LangChain Docs/API MCP 核实。Skill 示例与当前官方资料冲突时，以本轮核实结果为准。保留“顶层 LangChain `create_agent`，Deep Agents 仅为子 Agent”的用户约束。

## 1. 结论与最小组合

不需要自建通用 Agent 循环、计划引擎、DAG 调度器、Skill 加载器或聊天压缩器。官方 LangChain Agents 文档的 **Planning and delegation** 已直接演示 `create_agent` 组合 `FilesystemMiddleware`、`TodoListMiddleware` 和 `SubAgentMiddleware`，这与现有主编排约束相容。[A1][D1]

推荐顶层采用以下装配顺序；这是原生组件组合清单，领域校验由所属Skill的唯一实现提供，Hook/API共用：

1. `FilesystemMiddleware`：仅提供所需的虚拟文件工具，承接大结果落盘及按需回读。
2. `TodoListMiddleware()`：**显式启用** `write_todos` 与 `todos` 状态。
3. `SubAgentMiddleware(backend=..., subagents=[...])`：以原生 `task` 工具委派已编译的 Deep Agent。
4. 原生 `SummarizationMiddleware` 或 `create_summarization_middleware`：复用压缩实现；阈值依据实际模型能力确定。
5. `SkillsMiddleware(backend=..., sources=[...], tools=...)`：按需披露技能及技能关联工具；放在摘要及模型路由之后。
6. 需要的原生 HITL、调用限制/重试等中间件，以及最薄的业务派发检查适配；本轮不重复核查这些接口。
7. `UnsupportedContentMiddleware()`：放最后，使实际模型不支持的内容转为明确提示，原状态仍保留原内容。[A2][A5][A7][A8][A9][A10][A13]

顶层构造入口仍是 `langchain.agents.create_agent(model=..., tools=..., middleware=..., context_schema=..., response_format=...)`，不另写顶层 `StateGraph`。默认由官方Agent Server管理检查点，注册Agent不另传saver；仅直接库嵌入时才配置checkpointer和thread_id，优先核对现成SQLite saver。GaussDB保存业务事实，不默认实现GaussDB saver。[A1；部署边界以当前实现方案为准]

子 Agent 使用 `deepagents.create_deep_agent(model=qwen_model, tools=role_tools, skills=role_skill_paths, backend=..., middleware=..., response_format=RoleProposal)` 构建，再以 `CompiledSubAgent` 的 `name`、`description`、`runnable` 注册给顶层 `SubAgentMiddleware`；建议明确 `mode="isolated"`。这复用 Deep Agents 的完整文件/摘要等能力，同时主控仍为 `create_agent`。[A5][A6][A7]

首期只配置“文档提取”“账单核对”角色；简单确定性操作直接作为工具，不为每个函数创建 Agent。提案应返回 `revision`、处理范围、产物引用及问题；大批费用写入独立产物，避免通过 `task` 将整篇 OCR 和全部明细重新塞入主控上下文。这是本项目输出契约，不是另建 Agent 框架。

## 2. Plan：复用 Todo，避免另建 DAG

`TodoListMiddleware` 原生提供 `write_todos`，Todo 项只有 `content` 与 `status`；状态枚举为 `pending/in_progress/completed`。每次调用替换整张清单，中间件限制一个模型轮次最多一次 `write_todos`，防止并行替换含糊。[A2][A3]

当前 `create_deep_agent` 的 **bare/full stack** 和 API 描述均未将 Todo 列为默认项；不要照抄本地 Skill 的“默认已启用 Todo”说法。需要计划时显式传入 `TodoListMiddleware()`。[A7][D2]

推荐让 Todo 承担 Agent 自身的任务拆分、当前工作与后续步骤；新材料、失败或人工纠错后，让主控更新原生 Todo。以 checkpointer 保存原生状态，Vue 从原生状态/流读取计划，不再维护一套平行的通用 Plan/DAG 引擎。

Todo **不提供**稳定业务步骤 ID、依赖约束、财务校验、revision 乐观锁、执行回执或副作用幂等协议；也不能因为模型写了 `completed` 就认可账单成功。[A2][A3] 这些要求落在已有任务/材料覆盖/提案/执行记录中，显示真实产物与校验状态即可。若需关联 Todo 与业务产物，只增加最少引用，不把原生 Todo 扩展成另一套调度语言。

## 3. 子 Agent 的确切边界

| 项目 | 本轮核实结果与采用方式 |
| --- | --- |
| 顶层 `SubAgentMiddleware` | 必填 `backend` 与 `subagents`，支持 `SubAgent` 或 `CompiledSubAgent`；不必自写一个路由型 `task` 工具。[A5] |
| 直接传 `SubAgent` | 直接使用 `SubAgentMiddleware` 时须给出完整 `model` 与 `tools`。`create_deep_agent(subagents=...)` 才负责补齐默认配置及默认栈；不能将两种入口的默认行为混为一谈。[A5][A7][A14] |
| `CompiledSubAgent` | `runnable` 的状态必须含 `messages`；原样使用，不继承父方 `state_schema` 或 `interrupt_on`。本项目的 Deep Agent 自己配置模型、工具、Skill、权限、业务中间件和 HITL。[A6][A7] |
| 结构化返回 | `structured_response` 非空时原生 JSON 序列化为父方 `ToolMessage`；否则使用最后一个非空 `AIMessage` 文本。因此复用 `response_format`，不另写“取最后一句并猜 JSON”的协议。[A6] |
| 对话隔离 | 默认 `isolated`，获得委派任务而不复制父对话；实验性 `fork` 会继承父对话。首期用 `isolated`，显式传材料引用、目标、revision、约束与问题。[A6][A14][D3] |
| 运行上下文 | 父 `invoke/ainvoke` 的 runtime context 原生传给子 Agent，适合承载任务/主体/revision/预算引用；其传播不等于复制聊天历史，也不是动态读取最新业务版本的保证。[D4] |
| 自定义 state | Declarative `SubAgent` 可以使用转发的 schema，并可能回写自定义字段；并行更新同字段需 reducer。`CompiledSubAgent` 的 schema 自己负责。首期避免让子 Agent共享写业务结果，返回提案再集中校验。[A7] |
| 工具权限 | 父中间件不自动成为子中间件；自定义子 Agent 的工具、Skill 和中间件显式配置。只读/提案角色不暴露最终记账工具。[A7][D3] |

`create_deep_agent` 默认还会增加 `general-purpose` 子 Agent。若业务子 Agent 不应再委派，使用原生 harness profile 的 `GeneralPurposeSubagentProfile(enabled=False)` 并不提供同步子 Agent；这样不暴露 `task`。这是 beta profile API，需要锁定版本后验证。不要以 `tools=[]` 假设清除了默认工具，也不要自写“禁止递归”解析器。[A7][A15][D3]

## 4. Skill 与热更新

`SkillsMiddleware` 已提供后端 Skill 发现、元数据先行、按需读取、同名后来源覆盖、`pinned_skills` 以及 Skill 工具披露。复用这些能力，不另写完整 Skill 执行框架。[A9]

- 用户明确指定 Skill 时，可用 `pinned_skills` 保证其指令进入下一次模型上下文；不要仅期待模型自主选择。
- `metadata.include_tools` 可列出关联工具，`tools` 可接工具列表或 `SkillToolResolver`；原生中间件在读到/固定 Skill 后才披露对应工具。技能指令及工具可见性都不等于业务授权。
- 元数据每线程缓存；刷新入口是将 `skills_metadata` 置 `None`，例如 `agent.update_state(config, {"skills_metadata": None})`，或在下一次输入中重置。无需自建整套缓存刷新机制。
- 定制子 Agent 不继承主控 Skill；其 Skill 状态与主控隔离。`CompiledSubAgent` 自己配置并管理相应实例。不要只刷新父 Agent 缓存便宣称所有子 Agent 已热更新。
- 框架不提供本项目的 Skill 审核发布、版本钉住、回滚或旧审批失效协议。用已发布目录/后端快照提供 `sources`，在安全边界重建必要 Agent 或重置相应缓存；业务版本记录仍需保留。[A9][A7][D3]

## 5. 文件、摘要与权限

`StateBackend()` 将虚拟文件放在 Agent state，线程内由原生 checkpoint 管理，不是跨线程共享存储，也不自动意味着跨重启持久化。可以先用于工作上下文，原件、OCR 和审计证据仍独立归档；不必为了上下文文件先实现自定义后端。[A12]

`FilesystemMiddleware` 原生支持文件工具和超阈值结果卸载；通过公开 `tools=[...]` 选择实际提供的工具。建议仅启用业务所需的读取/搜索工具，必要时增加工作区写工具。额外 `tools=` 是加法，不能当作删除内置工具；`create_deep_agent` 可通过同名 `FilesystemMiddleware` 替换默认实例，或用 profile 排除工具。[A7][A8]

`execute` 需要支持 `SandboxBackendProtocol` 的后端。首期无需 shell，则不提供执行后端及工具。上下文隔离、虚拟目录和工具隐藏均不等于操作系统沙箱。[A7][A8][D5]

原生 `permissions=` 的首条匹配生效，未匹配默认允许；需要收紧时加入兜底规则。它只约束内置文件工具，不约束任意自定义/MCP 文件访问、直接 backend 调用或 shell。对子 Agent 自设权限是替换父规则，不是追加。因此它不能替代任务级业务工具检查。[A7][D5]

摘要方案优先复用原生实现：

- LangChain `SummarizationMiddleware` 提供 `trigger`、`keep`、`token_counter` 和 `summarizer`；支持 token/message/fraction 阈值。`trigger=None` 不表示已配置了合适的触发阈值。[A10]
- Deep Agents 默认包含摘要；`create_summarization_middleware(model, backend, summarizer=...)` 还提供历史卸载、工具参数压缩、上下文溢出后重试与非破坏式消息状态。顶层 `create_agent` 也可复用这个工厂，不另写压缩循环。[A11][D2][D6]
- 默认模型 profile 缺失时，Deep Agents 可能回退到较大的固定阈值；Qwen 的实际窗口未验证前不能依赖该值。验证模型 profile 或显式用 LangChain 的 token 阈值，不能以摘要机制代替结构化长文分块。[D6][A10]
- 摘要模型调用及其内部重试也消耗真实请求。顶层 `wrap_model_call` 不自动覆盖另一个摘要模型的调用路径；共享计量和 `enable_thinking=false` 必须实际应用于传入的模型/`summarizer`。不应为此重写整个摘要中间件。[A10][A11]

摘要与大结果卸载仅管理工作上下文，不能证明所有页面/费用行均处理完成；材料覆盖、原件证据与财务校验仍是本项目不可省的领域逻辑。

## 6. 原生机制不能代替的最小业务层

保留文件格式读取、指定 OCR 接入、跨页行重建、覆盖账本、费用映射/金额关系、明确更新意图、AR/AP、revision、执行事实/幂等及任务总预算。它们是题目领域需求，不应描述成已有中间件自动保证。

以上是候选职责，不是默认自写范围。每项先查Docs/API MCP及现成集成，确认具体缺口才补最小实现；领域算法全部在所属Skill，宿主仅提供原生装配、记录与条件写入，Hook引用同一算法。使用原生工具、中间件、backend、`response_format`、`context_schema`、checkpoint、Todo与Skill，不另造注册、计划、调度或执行框架。

本轮没有证明 GaussDB checkpointer 可用、Deep Agents 已安装、Qwen 的结构化/模型 profile/视觉能力或 OCR 真实响应可用。后续锁定依赖版本后，必须验证文档中采用的符号及父子中断、文件/状态传播、摘要计量；不要直接将动态站点最新 API 当成本地锁定版本能力。

## 7. 本轮 MCP 证据索引

以下均通过 `mcp__langchain_reference.get_symbol` 或 `search_api` 实际取得；不是仅凭 Skill 或搜索标题推断。API 返回的源码链接分别指向 Deep Agents `9db018bf1b94c11f06ea4f33d69d133c34097e08`、LangChain `84ba23c414eca6bf6f6ebd1394a3006378113540`；这表示本轮参考页引用的版本，不表示已安装该 commit。

| 编号 | MCP package / symbol | 官方 API |
| --- | --- | --- |
| A1 | `langchain` / `create_agent` | [create_agent](https://reference.langchain.com/python/langchain/agents/factory/create_agent) |
| A2 | `langchain` / `TodoListMiddleware` | [TodoListMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/todo/TodoListMiddleware) |
| A3 | `langchain` / `langchain.agents.middleware.todo.Todo` | [Todo](https://reference.langchain.com/python/langchain/agents/middleware/todo/Todo) |
| A5 | `deepagents` / `SubAgentMiddleware` | [SubAgentMiddleware](https://reference.langchain.com/python/deepagents/middleware/subagents/SubAgentMiddleware) |
| A6 | `deepagents` / `CompiledSubAgent` | [CompiledSubAgent](https://reference.langchain.com/python/deepagents/middleware/subagents/CompiledSubAgent) |
| A7 | `deepagents` / `create_deep_agent` | [create_deep_agent](https://reference.langchain.com/python/deepagents/graph/create_deep_agent) |
| A8 | `deepagents` / `FilesystemMiddleware` | [FilesystemMiddleware](https://reference.langchain.com/python/deepagents/middleware/filesystem/FilesystemMiddleware) |
| A9 | `deepagents` / `SkillsMiddleware` | [SkillsMiddleware](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware) |
| A10 | `langchain` / `SummarizationMiddleware` | [SummarizationMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/summarization/SummarizationMiddleware) |
| A11 | `deepagents` / `create_summarization_middleware` | [create_summarization_middleware](https://reference.langchain.com/python/deepagents/middleware/summarization/create_summarization_middleware) |
| A12 | `deepagents` / `StateBackend` | [StateBackend](https://reference.langchain.com/python/deepagents/backends/state/StateBackend) |
| A13 | `deepagents` / `UnsupportedContentMiddleware` | [UnsupportedContentMiddleware](https://reference.langchain.com/python/deepagents/middleware/unsupported_content/UnsupportedContentMiddleware) |
| A14 | `deepagents` / `SubAgent` | [SubAgent](https://reference.langchain.com/python/deepagents/middleware/subagents/SubAgent) |
| A15 | `search_api("GeneralPurposeSubagentProfile register_harness_profile")` | [GeneralPurposeSubagentProfile](https://reference.langchain.com/python/deepagents/profiles/harness/harness_profiles/GeneralPurposeSubagentProfile)、[register_harness_profile](https://reference.langchain.com/python/deepagents/profiles/harness/harness_profiles/register_harness_profile) |

以下正文通过 `mcp__langchain_docs.query_docs_filesystem_docs_by_lang_chain` 实际读取或定向查询；先经搜索/目录发现真实路径，再读取：

| 编号 | 虚拟文件与定位 | 官方文档 |
| --- | --- | --- |
| D1 | `/oss/python/langchain/agents.mdx`，`Planning and delegation` 示例，约1254–1292行 | [Agents: planning and delegation](https://docs.langchain.com/oss/python/langchain/agents#planning-and-delegation) |
| D2 | `/oss/python/deepagents/customization.mdx`，1076–1142行，bare/full/synchronous stack | [Customize: middleware](https://docs.langchain.com/oss/python/deepagents/customization#middleware) |
| D3 | `/oss/python/deepagents/subagents.mdx`，1–105行及 `middleware/skills/permissions` 定向查询 | [Subagents](https://docs.langchain.com/oss/python/deepagents/subagents) |
| D4 | `/oss/python/deepagents/subagents.mdx`，2079–2113行 | [Subagent context management](https://docs.langchain.com/oss/python/deepagents/subagents#context-management) |
| D5 | `/oss/python/deepagents/permissions.mdx`，1–90行 | [Permissions](https://docs.langchain.com/oss/python/deepagents/permissions) |
| D6 | `/oss/python/deepagents/context-engineering.mdx`，807–881、1007–1041行 | [Context compression](https://docs.langchain.com/oss/python/deepagents/context-engineering#context-compression) |

核查过程没有读取 `.env`、安装包、连接业务服务或修改其他项目文档。
