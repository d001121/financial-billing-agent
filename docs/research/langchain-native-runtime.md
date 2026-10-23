# LangChain 原生运行时复用核验

> **研究快照，2026-10-21复核。** 当前规则见[AGENT.md](../../AGENT.md)、[实现方案](../implementation.md)及[最终开发计划](../superpowers/plans/2026-10-21-final-development-plan.md)。历史自写范围不是授权清单：逐职责先查MCP，领域算法只在Skill，服务及流协议优先官方现成能力。

核验日期：2026-10-21（Asia/Shanghai）。本轮按用户最新方向，重新区分框架已有能力和本项目必须保留的薄业务适配。已完整阅读 `AGENT.md`，先调用 LangChain Docs MCP 搜索及读取正文，再调用 Python API Reference MCP 查询符号，并只读核对项目已安装包及少量本地源码。未修改 `AGENT.md`、`architecture.md`，未安装依赖、读取 `.env` 或调用真实业务服务。

用户最新要求优先于旧文档中的具体实现方案：本轮建议不再把 PlanService、步骤 DAG 或自建执行调度框架作为前置条件。保留需要的业务保证，用 `create_agent`、原生 middleware、检查点、工具和少量适配完成。

## 1. 结论与最小组合

主控继续采用 LangChain `create_agent`，显式组合 `TodoListMiddleware` 与 Deep Agents 官方 `SubAgentMiddleware`。文档专家优先使用 `create_deep_agent`，账单专家可使用 `create_agent`；预编译专家通过 `CompiledSubAgent` 的 `name/description/runnable` 注册，采用隔离上下文，并显式配置模型、工具、Skill 和 middleware，不另写委派工具协议。Agent 自己的行动循环、工具执行、状态、todos、中断和事件流交给框架；金额、匹配、revision、审批有效性及幂等仍由业务代码决定。无需另外解释执行一套业务 DAG。Deep Agents 尚未安装，须先核实兼容版本。

当前默认交付采用 Python Agent Server 开发服务（`langgraph-cli[inmem]`）及自定义 FastAPI 业务路由，由官方服务管理 threads/runs、后台队列、检查点、中断和流；注册的 Agent 不重复注入 saver。GaussDB 保存业务 revision、证据与执行回执。后文关于直接 `get_state/update_state`、saver 注入及 GaussDB checkpointer 兼容性的讨论属于直接库嵌入或通用 SDK 语义，不是默认服务部署的要求；可选直接嵌入优先验证官方 SQLite saver，不默认自写 GaussDB saver。开发服务定期刷盘，正常重启与硬崩溃恢复须分开验收。默认部署与协议以 `docs/implementation.md` §10–11 为准。

| 需求 | 优先直接复用 | 保留的薄适配 |
| --- | --- | --- |
| 智能体规划与计划可视化 | `TodoListMiddleware`、`write_todos`、Agent state/stream | 将其标注为 Agent 的计划；业务完成依真实产物与校验判定 |
| 按需子 Agent | `SubAgentMiddleware`、`CompiledSubAgent` | 显式专家配置、隔离上下文、版本化结构化提案及产物引用 |
| 工具动作审批 | `HumanInTheLoopMiddleware`，首选显式 `per_call` | 绑定 revision、完整参数和能力版本，编辑后业务重验 |
| 缺少主体/材料等补问 | 工具或 middleware 中的 `interrupt()`、`Command(resume=...)` | 人工请求与业务输入校验；按具体 interrupt ID 续跑 |
| 状态与暂停后恢复 | 默认 Agent Server 管理检查点及恢复；直接嵌入可选官方 saver | 业务 revision/CAS、恢复时核对真实回执，实测服务刷盘及重启边界 |
| 前端实时展示 | 官方 `@langchain/vue` v1 `useStream`、`HttpAgentServerAdapter` 及匹配的 Agent Server 协议 | 锁定并联调版本、映射业务状态、验证重连与回放；Python v3 流 API 不等同于 HTTP 传输协议 |
| 暂时性故障 | `ModelRetryMiddleware`、`ToolRetryMiddleware` | 精确选择可重试异常；副作用未知时先核对结果 |
| 单 Agent 循环防护 | `ModelCallLimitMiddleware`、`ToolCallLimitMiddleware` | 跨 Agent/重试/内部请求的持久共享预算 |
| MCP 发现与调用 | `langchain.mcp.MCPAdapter`、FastMCP 连接及缓存 | 配置、刷新时机、启停与版本检查；动态工具的两处 middleware 适配 |
| Skill 渐进加载与刷新 | `deepagents.middleware.skills.SkillsMiddleware` | 依赖及兼容版本确认、受限 backend、内容版本与执行权限；不替换 LangChain 主控 |
| 暂停/禁用/取消 | 原生 interrupt 与 middleware 短路能力 | 控制状态、每次真实派发前检查、在途结果处理 |

依据：本报告第9节 D1–D8、A1–A10。

## 2. 本地版本及核验范围

项目 `./python.cmd` 的发行包元数据实测为：

```text
langchain==1.4.6
langgraph==1.2.16
fastmcp==4.1.2
mcp==2.3.0
deepagents: not installed
```

`langchain.mcp` 要求 `langchain[mcp]>=1.4.0`，目前属于 beta API；本地满足版本门槛。当前 API Reference 的上述 LangChain 类源码链接固定到 commit `84ba23c414eca6bf6f6ebd1394a3006378113540`；`Command/interrupt` 链接固定到 LangGraph commit `41c9c22fdc83d68a2859d0c9a2b627c8615a792f`。API 当前包含逐调用 HITL，不应误写为本地不支持。[D5、A1–A9]

本轮对 Skill 的结论来自官方 Deep Agents API Reference，当前链接的源码 commit 为 `9db018bf1b94c11f06ea4f33d69d133c34097e08`。本地未安装 `deepagents`，不能将该可复用组件写成已经集成。若选用，应先确认并锁定兼容版本；无需为了复用其 middleware 改用 Deep Agents 作为主控。[A10]

本轮没有再次执行前序 HITL 探针；相关源码/离线实测详见 `docs/research/langchain-hitl-crosscheck.md`。当前只读研究不证明在线模型、持久数据库、热更新或前端已经工作。

## 3. HITL、补问及状态编辑的正确边界

### 3.1 原生工具审批

`HumanInTheLoopMiddleware` 直接提供四类决定和两种模式：[A1]

| 决定 | 框架行为 | 业务含义 |
| --- | --- | --- |
| `approve` | 继续原工具调用 | 仍须检查输入 revision、版本、参数及业务约束 |
| `edit` | 使用 `edited_action` 替换调用 | `args` 是完整替换；UI 字段补丁需由后端补全并重验 |
| `reject` | 跳过工具，返回错误工具消息 | 保存拒绝及原因，不发生对应调用 |
| `respond` | 跳过真实工具，以人工内容返回成功工具消息 | 人工代答，不能当作真实提交回执或拒绝 |

默认 `batched` 在模型输出后统一暂停，决定按列表位置对应。`per_call` 在各工具开始时分别中断，用具体 interrupt ID回答；本地1.4.6支持，适合独立审批及并行只读工作。逐调用编辑不能换工具名，Pydantic类型及必填参数在保存答案前验证，完整工具 validators仍在实际执行时运行。字典 JSON Schema只展示，不产生同等服务端验证。[A1、A8]

`interrupt_on` 缺项或设为false代表自动批准，不能用来禁用工具。条件 `when` 返回false也代表免审批；恢复时会重新求值，因此必须稳定，不能把它用作随时变化的执行授权检查。[D1、A1]

### 3.2 补问与恢复

缺少记账主体、存在材料歧义等，可直接从受控工具调用 `interrupt(value, response_schema=...)`，由前端呈现请求并通过同一 `thread_id` 的 `Command(resume=...)` 回答。存在多个并发或嵌套中断时使用 ID映射，不按问题文本或第一项定位。[A8、A9]

恢复会从中断节点开头重跑；函数内调用子 Agent/子图时，父调用节点也可能重跑。中断之前的逻辑应无副作用或可幂等重放。不要用宽泛异常处理吞掉图控制信号；原生 retry实现会传播 `GraphBubbleUp`。[A8；本地 `model_retry.py/tool_retry.py` 对应控制流分支]

### 3.3 人工字段纠错

`update_state/aupdate_state` 已能创建新检查点并按reducer更新值，历史检查点保留；`as_node` 会影响后继路由。因此无需自造 Agent 状态引擎。[D3]

业务补丁先以 `expected_revision` 校验并保存，再在可控暂停边界更新相关 Agent 状态/引用并续跑。该 API不会原地改写在途函数的局部快照，也不提供金额依赖重算、CAS或审批失效。这些仅保留为领域服务的确定性逻辑；不要另造计划 DAG来实现字段依赖。[D3；前序HITL研究]

使用可持久 saver才能主张进程重启后恢复；内存 saver只用于开发验证。`sync/async/exit` 各有持久性取舍，指定GaussDB的认证、SQL及saver兼容性仍需实测。现成saver验证可用后优先直接复用，不能提前宣称必须自写完整checkpointer。[D3]

## 4. Middleware 顺序：准确到每次重试

官方合同是：`before_*` 按列表正序，`after_*` 逆序，`wrap_*` 按列表嵌套，前面的wrapper包住后面的wrapper。不能只凭“优先级高就放最前”安排所有职责。[D4]

### 4.1 工具调用链建议

以下为建议的wrapper嵌套关系，箭头表示调用下一个handler；它不是新增调度器：

```text
动态工具解析（只读，固定本次能力快照并补入 request.tool）
  → 原生 HumanInTheLoopMiddleware(per_call)
    → 原生 ToolRetryMiddleware
      → 薄派发检查与共享计量
        → 原生工具handler / 已适配MCP工具
```

1. 动态解析放在HITL外侧，使审批能读取实际工具及参数schema；这部分在恢复时可能再次运行，不得在此执行外部副作用。已选实现与schema绑定同一能力快照，最终检查发现版本不符时返回冲突，不能静默换实现后沿用旧审批。[D6、A1]
2. HITL在重试外层，符合官方逐调用模式要求；一次审核包住后续允许的工具重试，避免每次网络重试重新问人。审批不会因此保证exactly-once。[A1]
3. **禁用、暂停、revision/审批有效性及预算检查放在重试内层。** 原生retry每次再次调用handler时都会重新经过它。若仅在外层检查一次，退避期间工具被禁用，下一次重试仍可能派发。检查与派发许可/共享额度预留需保持原子边界。[D4；本地 `tool_retry.py` L295–329]
4. 这层只调用已有业务校验、配置和计量函数，再调用handler；不持有另一套步骤队列、DAG或规划状态。动态resolver不能自行绕过handler直接执行工具。[D6]
5. retry使用明确的暂时性网络错误白名单；策略拒绝、预算耗尽、版本冲突和已知不可重试错误不纳入重试。副作用结果未知先查回执。关键步骤可采用 `on_failure="error"` 交给应用映射状态，避免把最后错误消息当业务成功。[A4、A5]

如使用原生 `ToolErrorMiddleware`，只转换已明确可由模型修正的错误；转换层须位于retry外侧，避免先把暂时性异常变成ToolMessage而阻止retry。图中断及策略控制异常应继续传播。HITL仍包在工具retry/error处理外侧。[A1；D2]

成功工具结果须先保存真实回执。后置审计/Hook失败使用独立后处理状态，不能把该异常抛回retry链导致已成功工具再次执行。该部分是领域副作用账本的薄适配，不要求改写原生重试器。

### 4.2 模型调用链建议

```text
本轮工具目录/上下文选择
  → 原生 ModelRetryMiddleware
    → 本次真实模型请求的共享计量与控制检查
      → 原生chat model
```

模型retry同样会多次调用内层handler。摘要、评分器和工具选择器可能直接使用它们自己的模型，不一定经过主控的 `wrap_model_call`；这些模型必须由统一工厂取得相同的计量适配，才能计入全任务预算。供应商SDK内部隐藏重试也要显式配置或另行计量，不能由外层一次回调推断其请求数。[D2、A4；本地 `model_retry.py` L221–255]

`SummarizationMiddleware` 等原生上下文能力可以直接使用，但完整证据仍保存在材料产物中；摘要不取代财务来源。不要为复用现成middleware再构造一个并行的Agent执行框架。

## 5. 原生限额与任务共享预算不是同一个计量口径

`ModelCallLimitMiddleware` 和 `ToolCallLimitMiddleware` 可作为开箱即用的局部循环防护。前者可结束或抛出异常；后者可阻止超额工具、抛异常或结束。到限结束是技术终止，不是财务校验通过。[A2、A3]

| 原生计数 | 官方明确的范围 | 不能直接推导的保证 |
| --- | --- | --- |
| `run_limit` | 对应Agent单次invocation | 跨恢复调用、多个子Agent及工具内部请求的统一任务总额 |
| `thread_limit` | 对应Agent线程状态，配checkpointer跨invocation保存 | 仅传相同thread ID就让不同子图/Agent共享一个原子计数器 |
| 模型调用数 | Agent的模型调用节点 | retry内部每次供应商HTTP尝试、独立摘要/评分模型请求 |
| 工具调用数 | 模型提出的tool calls，经原生限额筛选 | retry次数、一个OCR工具内部的30次外部子请求、真实执行成功次数 |

本地只读源码直接说明了最后两点：`model_call_limit.py` L236–251在 `after_model` 每轮加1；`tool_call_limit.py` L327–381读取末条AI消息中的tool calls并更新计数；`model_retry.py/tool_retry.py` 在wrapper内部循环调用handler。故这些原生状态不是项目要求的“每次真实外部请求”账本。[A2–A5对应固定源码]

建议保留一个小的任务预算适配：以task/run标识查持久计量，在真实派发处原子预留，主控、子Agent和附加模型共用。原生limits继续提供局部防护，避免为共享额度重写其全部逻辑。任务初值仍是24次模型、64次工具派发、1200秒活跃墙钟、文档并发3和每受影响产物自动纠错2轮；分批/续跑/换子Agent不重置同次运行预算。

活跃计时以任务互斥区间累积：任一分支执行或等待已发外部调用时仍活跃；所有分支阻塞后才计人工等待/暂停。持久化用量与时间区间，重启后继续。到限停止新派发、保存真实在途结果并返回明确状态；显式调整预算留痕，不以自动分批暗改额度。这是项目策略，不是原生call-limit自带的1200秒共享计时器。

## 6. MCP刷新、动态工具和Skill版本

### 6.1 MCP直接复用的部分

内置 `MCPAdapter` 已负责工具发现、到异步LangChain工具的转换及FastMCP协议/连接适配；得到的工具可直接交给 `create_agent`。支持URL、显式Path/transport、MCPConfig或预建client；配置中的普通字符串仅接受http(s) URL，不能把任意本地脚本字符串当成相同合同。[A6]

适配工具具有reentrant调用生命周期，发现上下文退出后仍可调用，每次工具调用进入并退出client；有意保持adapter上下文时可复用已有连接。不要沿用“发现结束就必须失效”的旧假设，也不必为此自写连接池。多服务可以复用 `MCPConfig` 或 `ClientGroup`，各自协议/认证边界按官方连接文档选择。[D5]

原生发现刷新接口为：

```python
tools = await adapter.list_tools(cache_mode="refresh")
```

`use/refresh/bypass` 分别使用有效缓存、重新获取并填充、绕过缓存；缓存需client显式配置且取决于服务的cache hints，不能宣称所有发现调用天然有缓存。[D5]

### 6.2 薄能力配置适配

已知工具可在 `wrap_model_call` 动态过滤；运行时新发现的工具要同时通过 `wrap_model_call` 注入模型可见工具，并在 `wrap_tool_call` 以 `request.override(tool=...)`提供实际实现。只刷新工具列表而没有执行resolver，模型会看见却无法调用新工具。[D6]

因此首期只保留能力配置数据、刷新函数和一个middleware解析器：前端保存候选配置→测试/发现→发布新的配置版本→下一模型调用/安全边界使用该版本。旧调用保留原能力快照，派发前再检查禁用和版本；在途返回后释放不再需要的资源。无需建设独立插件调度系统。

目录刷新不等于审批迁移或撤销远端调用；远端服务器原地升级也不由本地包装对象控制。保存服务配置身份、schema/资源摘要和可验证版本，无法固定远端版本时如实说明，并对受影响动作重新校验/审批。[D5、D6；项目业务要求]

`MCPAdapter` 默认把服务elicitation接到LangGraph interrupt；自带elicitation handler的client会保留其handler。它解决工具中途补充输入，不等于批准执行副作用，仍需相同业务策略检查。[A6]

### 6.3 Skill直接复用的部分

官方 `SkillsMiddleware` 属于可选 `deepagents` 包，能在普通 `create_agent` 中独立组合；需要同backend的 `FilesystemMiddleware/read_file` 支持。原生已提供渐进式元数据加载、读取正文、`pinned_skills`、按Skill暴露include_tools及resolver，不建议重写这些功能。[A10]

Skill元数据按thread缓存。新增、编辑或删除后，可在安全边界清空缓存：

```python
agent.update_state(config, {"skills_metadata": None})
```

也可在下一次invoke输入中传同名字段为None。官方放置建议是Skills在摘要及模型fallback/routing之后、prompt caching之前；这与工具wrapper的HITL/retry顺序是两个不同维度，不能混为一个“放最前”的规则。[A10]

此刷新合同不等于原子撤回在途动作或使旧业务审批失效。薄适配保存Skill路径/内容hash/配置版本，在步骤边界刷新并记录实际使用版本；Skill读取或文字不能提升工具权限。若暂不安装该可选包，只采用受限资源读取与提示词适配，并明确能力范围，不能写成原生Skill已集成。

## 7. 流式体验：复用原生事件，区分传输与业务事实

当前文档优先推荐v3 event streaming。可直接消费模型消息、文本增量、state snapshots、工具生命周期、最终状态、嵌套subgraphs，以及命名子Agent投影；自定义领域投影可用原生transformer扩展。异步消费使用 `astream_events`，不同投影可以并发读取，避免某个投影消费完才开始展示另一类事件。[D7]

Vue可以展示原生todos、工具/子Agent进度和人工请求，再用业务结果引用展示原文、费用、校验及回执。无须另外维护一套步骤调度状态来生成进度。按项目要求关闭模型思考，也不要把reasoning投影发送为业务解释。

原生SDK事件对象本身不承诺自建HTTP接口的持久SSE重放、跨浏览器刷新快照或Last-Event-ID合同。若选择框架现成服务，优先使用并验证其threads/runs/stream能力；若选择薄ASGI桥接，只补必要的事件/快照传输。不能把原生stream等同于已经解决断线重放，也不应不经选择就再造完整任务服务器。

`stream.output`、图结束、todos全completed或ToolMessage成功均不能直接标记业务完成。最终可用性由输出schema、覆盖范围、金额/匹配/AR/AP及revision检查决定；框架流提供展示资料，确定性校验给出业务结论。[D7、A7；项目业务要求]

## 8. 必须逐项查证的候选职责

首期围绕现成 `create_agent` 工厂组织代码，不新增自有工作流语言或DAG执行器：

1. **业务Skill职责**：格式解析、指定OCR、金额/匹配、revision提案及导出。先核对官方loader、工具、验证及现成集成，确有具体缺口才补包内scripts；不能笼统断言全部都需要自写。
2. **middleware装配与共享计量**：先查原生动态工具、HITL、retry/call-limit及实际父子/隐藏调用覆盖，只补已验证的缺口。薄适配同受先查证约束，直接复用handler，不自己调度Agent步骤。
3. **最小持久事实**：业务revision、人工修改/审批绑定、外部执行幂等键与回执、任务共享用量、能力版本。Agent消息、todos、中断及检查点交给框架保存，避免双份可写事实。
4. **官方传输与业务HTTP**：Agent流/状态/中断用官方Server与Vue SDK，材料产物按引用读取；不因研究讨论过薄桥接就自写协议服务器。

原生todos是可持久的Agent计划与进度列表，`write_todos`替换整个列表并限制同轮最多一次；它没有真实财务回执或金额验收合同。因此复用它展示计划，同时让领域结果决定完成，既不冒充保证，也无需为了补足保证重新引入PlanService/DAG。[A7]

## 9. MCP证据记录

以下均于2026-10-21实际调用成功。Docs MCP先作概念检索，再读取已发现路径；API Reference MCP用于精确签名和语义。外部网页仅作为官方链接辅助访问，结论以MCP正文、符号和本地只读记录为依据。

| 编号 | MCP调用与定位 | 本轮核实点 |
| --- | --- | --- |
| D1 | Docs检索后读取 [HITL](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) | 四类决定、per_call门槛、when重算和wrapper顺序 |
| D2 | Docs读取 [Built-in middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) | retry、调用限额及todo现成能力 |
| D3 | Docs读取 [Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) | update_state新检查点、reducer、durability |
| D4 | Docs读取 [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom#execution-order) | before正序、after逆序、wrapper外内嵌套 |
| D5 | Docs读取 [MCP connections](https://docs.langchain.com/oss/python/langchain/mcp/connections) | reentrant连接、分组、cache_mode刷新 |
| D6 | Docs读取 [Tools: runtime registration](https://docs.langchain.com/oss/python/langchain/tools#runtime-tool-registration) | 动态工具需模型与执行两处hook |
| D7 | Docs读取 [Event streaming](https://docs.langchain.com/oss/python/langchain/event-streaming) | v3投影、异步消费、子Agent和扩展 |
| D8 | Docs检索 [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | 中断与同线程resume入口 |
| A1 | API `get_symbol(langchain, HumanInTheLoopMiddleware)`，[符号](https://reference.langchain.com/python/langchain/agents/middleware/human_in_the_loop/HumanInTheLoopMiddleware) | 四类决定、两种模式、类型验证、先HITL后retry/error |
| A2 | API `get_symbol(langchain, ModelCallLimitMiddleware)`，[符号](https://reference.langchain.com/python/langchain/agents/middleware/model_call_limit/ModelCallLimitMiddleware) | invocation/thread范围、计数及退出 |
| A3 | API `get_symbol(langchain, ToolCallLimitMiddleware)`，[符号](https://reference.langchain.com/python/langchain/agents/middleware/tool_call_limit/ToolCallLimitMiddleware) | tool筛选、invocation/thread和退出方式 |
| A4 | API `get_symbol(langchain, ModelRetryMiddleware)`，[符号](https://reference.langchain.com/python/langchain/agents/middleware/model_retry/ModelRetryMiddleware) | 重试数量、筛选、退避和on_failure |
| A5 | API `get_symbol(langchain, ToolRetryMiddleware)`，[符号](https://reference.langchain.com/python/langchain/agents/middleware/tool_retry/ToolRetryMiddleware) | 工具范围、重试和异常边界 |
| A6 | API `get_symbol(langchain, MCPAdapter)`，[符号](https://reference.langchain.com/python/langchain/mcp/adapter/MCPAdapter) | 目标类型、原生工具适配、elicitation |
| A7 | API `get_symbol(langchain, TodoListMiddleware)`，[符号](https://reference.langchain.com/python/langchain/agents/middleware/todo/TodoListMiddleware) | 原生write_todos、整表替换、单轮调用约束 |
| A8 | API `get_symbol(langgraph, interrupt)`，[符号](https://reference.langchain.com/python/langgraph/types/interrupt) | 节点重放、检查点、response_schema |
| A9 | API `get_symbol(langgraph, Command)`，[符号](https://reference.langchain.com/python/langgraph/types/Command) | resume值及interrupt ID映射 |
| A10 | API `get_symbol(deepagents, SkillsMiddleware)`，[符号](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware) | create_agent组合、缓存失效、include_tools及位置 |

Docs/API搜索查询包括调用限额与retry、动态MCP/Skill刷新、state update/stream/resume，以及对应类名；已排除搜索结果中的JavaScript和托管产品示例，未将其当作本地Python能力。

文档正文中ToolCallLimit的 `end` 限制说明与当前API Reference存在差异；本轮读取本地1.4.6 `tool_call_limit.py` 后，以本地与固定API源码语义为准。项目选择具体退出行为时仍需针对采用的组合做离线验证。本报告没有声称这些新组合已通过运行测试。
