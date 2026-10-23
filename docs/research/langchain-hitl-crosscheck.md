# LangChain 人工介入、续跑与状态编辑交叉核验

> **研究快照，2026-10-21复核。** 探针结果保留原范围；后续以[当前实现方案](../implementation.md)和[最终开发计划](../superpowers/plans/2026-10-21-final-development-plan.md)为准。领域规则归Skill、派发检查用原生middleware装配，不另建执行网关。默认Server管理检查点，GaussDB只承载业务事实。per_call部分回答已执行风险及最新约定见[开发工具记录](../development-tools.md)。

核验日期：2026-10-21（Asia/Shanghai）。本报告先使用 LangChain Docs / Reference MCP 读取官方文档，再通过 GitHub MCP 固定官方版本源码和测试，最后用项目内 `python.cmd` 执行离线探针。研究对象是本项目已安装的 Python API；没有安装或升级依赖，没有读取 `.env`，没有调用在线模型、OCR、Redis 或 GaussDB，也没有实现账单业务功能。

本项目主编排仍应使用 LangChain `create_agent`。下文的 LangGraph 是其检查点、中断和运行时基础；用于验证运行时语义的最小 `StateGraph` 探针不代表将项目主控改为 `StateGraph`。

## 1. 核心结论

1. 已安装的 LangChain **1.4.6** 支持 `approve`、`edit`、`reject`、`respond` 四类决定，以及默认 `batched` 和新增的 `per_call` 中断模式。不能沿用“仅三类决定”或“本地版本不支持 per-call”的旧说明。
2. `edit` 是替换工具调用参数。`per_call` 将工具名固定为原工具，校验 Pydantic 参数的类型及必填字段；完整工具校验仍在实际执行时运行。字典形式 JSON Schema 只提供给调用方展示，不能据此声称服务端已完成参数校验。
3. `Command(resume=...)` 恢复的是同一任务的中断。被中断节点从头重跑，函数内调用的子图中断还会使父调用节点从头重跑。审批前的副作用及 middleware 顺序必须据此设计。
4. `update_state` 产生新的检查点，遵守 reducer，并非原地改写历史或正在执行节点的局部变量。暂停后的修改可在恢复重跑时生效；“运行中任意改值立即安全生效”不成立。
5. HITL 不提供账单 revision/CAS、旧审批自动失效、工具禁用授权、跨工具副作用事务或 exactly-once 保证。领域规则由Skill持有，宿主提供条件写入/回执，派发用原生middleware装配；具体补充先按AGENT.md §3.5查证，不以此建立独立执行网关。
6. 内存 saver 只能证明同进程内的暂停/续跑。本轮没有验证跨进程恢复，也没有证明任何现成 checkpointer 与指定 GaussDB 服务兼容。

## 2. 版本和源码一致性

| 本地发行包 | 安装版本 | 官方固定版本 |
| --- | --- | --- |
| `langchain` | `1.4.6` | `langchain==1.4.6`，commit `84ba23c414eca6bf6f6ebd1394a3006378113540` |
| `langgraph` | `1.2.16` | `1.2.16`，commit `41c9c22fdc83d68a2859d0c9a2b627c8615a792f` |
| `langgraph-checkpoint` | `4.3.0` | 作为本地依赖快照记录；本轮未另行审计其全部后端实现 |
| `langgraph-prebuilt` | `1.1.1` | 作为本地依赖快照记录；本轮未另行审计其全部实现 |

LangChain 固定 commit 时间为 `2026-10-14T17:19:35Z`，LangGraph 固定 commit 时间为 `2026-10-16T22:02:08Z`。这表示本轮检查的版本来源，不表示此后版本永远不变。实时 API reference 的 HITL 源码链接也指向上述 LangChain commit。

以下本地文件位于 `bishi1/Lib/site-packages/`，按 Git blob 算法计算的 SHA 与官方固定版本完全相同：

| 文件 | 本地与官方一致的 Git blob SHA |
| --- | --- |
| `langchain/agents/middleware/human_in_the_loop.py` | `a8955d6302860d52b56ca1569e98e816c8c3617b` |
| `langgraph/types.py` | `8fba752a1d20d98721d2afcdfff8ee92dfa4c84b` |
| `langgraph/pregel/main.py` | `f944b1bf383677377581c3db8a187e248481dc30` |

### 当前文档与本地版本

| 文档所述能力 | 版本门槛或约束 | 本地核验结论 |
| --- | --- | --- |
| 四类 HITL 决定，含 `respond` | 当前官方 HITL 源码定义四类 | `1.4.6` 已支持，且离线逐类运行通过 |
| `interrupt_mode="per_call"` | LangChain ≥ `1.4.6` | 已满足；实际 middleware 探针验证通过 |
| `interrupt(..., response_schema=...)` | LangGraph ≥ `1.2.12` | `1.2.16` 已满足；固定源码包含实现 |
| `stream_events(..., version="v3")` | 当前文档推荐的事件消费方式 | 本地 `pregel/main.py` 存在 `stream_events`；本轮未对所有事件形状执行集成测试 |
| 默认 `invoke()` 的 `__interrupt__` 返回 | 与较新 `invoke(version="v2")` 的结果形状区分 | 本轮探针使用默认调用；接入前端时应固定一种调用协议并适配其返回形状 |

本轮审计的关键 HITL 和恢复 API 没有发现“文档要求的功能尚未安装”的实质版本缺口。流式 UI、跨进程恢复和真实服务仍需另行实现并验收。

## 3. HITL 决定及参数编辑

`HumanInTheLoopMiddleware` 的 `interrupt_on` 按工具名配置。值为 `True` 时允许全部四类决定；值为 `False` 或没有该工具条目时自动批准，而非禁止执行。可用 `allowed_decisions` 限定允许的决定，并可配置条件 `when`。[源码 S1，L85、L115–165、L489–598]

| 决定 | Python/JSON 有效载荷 | 工具是否执行 | 交给模型的结果 |
| --- | --- | --- | --- |
| 批准 | `{"type":"approve"}` | 执行原调用 | 实际工具结果 |
| 修改 | `{"type":"edit","edited_action":{"name":"tool_name","args":{"amount":200}}}` | 执行替换后的调用 | 实际工具结果，默认附编辑提示 |
| 拒绝 | `{"type":"reject","message":"原因"}`，`message` 可省略 | 跳过 | `ToolMessage(status="error")` |
| 代答 | `{"type":"respond","message":"人工提供的工具结果"}` | 跳过 | `ToolMessage(status="success")` |

`respond` 是人工代表工具提供回答。它不等于“拒绝财务动作”，也不证明财务系统实际执行成功；业务状态不能仅由这个 `success` 推导。[S1，L266–284]

### batched 与 per_call

| 对比项 | `batched`（默认） | `per_call` |
| --- | --- | --- |
| 中断位置 | `after_model`，进入工具节点前 | 每次调用的 `wrap_tool_call` |
| 请求内容 | 一个请求包含 `action_requests` 和 `review_configs` | 每个待审调用独立 interrupt，带 `response_schema` |
| 恢复答案 | `Command(resume={"decisions":[...]})`；数量和顺序对应待审动作 | 单个 interrupt 可用决定对象；多个中断以 interrupt ID → 决定映射恢复 |
| 同轮未配置审批的工具 | 也要等本轮批量中断恢复后才进入工具节点 | 可在需审工具等待时完成 |
| 编辑工具名 | 可改为 Agent 当前可用的另一个工具；未知工具报错 | schema 将 `name` 固定为原工具，不能换工具 |
| 答案校验时机 | 从未指定类型的 interrupt 返回后由 middleware 处理 | LangGraph 在保存答案前验证类型；非法答案不保存，仍可重试同一中断 |
| 并行完成情况 | 不构成业务事务 | 可部分恢复，已完成调用不必重复执行；不同中断不构成全有或全无事务 |

依据：[S1，L196–263、L727–859、L875–911]；官方测试 [T1，L1894–2141]。

编辑参数是**完整替换**，不是把新字典与旧字典合并。未写入的可选参数回到工具默认值；不能把 UI 的“只改一个字段”补丁直接当作完整 `edited_action.args`。Pydantic 工具 schema 会检查类型和必填参数，但工具的自定义 validator 仍在实际执行时运行；JSON Schema 字典只展示、不由这套机制执行校验。[S1，L196–217；T1，L2003–2095]

`approve` 只表示允许原工具调用继续，`edit` 表示使用人工替换的调用继续；二者都没有实现本项目的金额合计、币种、记账主体、AR/AP、账单版本或工具启停业务校验。真正派发前须核对审批绑定的 revision、参数及能力版本；编辑后重新执行受影响的校验，并按策略重新审批。不能因人工批准或 Pydantic 校验通过，就直接将候选标记为可入账。

默认的 `edit_notice` 会在工具结果前提示模型实际执行了人工替换的调用。该提示有助于后续推理保持一致，但不是审计日志、业务 revision 或完整参数差异的替代品。[S1，L489–522、L979–1043]

### 条件审批与重试的边界

- `when` 是“本次是否需要审批”的条件，不是执行授权。它在恢复重跑时再次求值，必须确定；如果恢复后变成 false，工具可能运行并忽略先前的拒绝答案。工具已禁用、账单版本过期等硬性限制，应在真正派发前独立检查。[D1；S1，L727–749]
- per-call 中 HITL 应包住工具重试/错误处理 middleware。位于 HITL 外层、在 interrupt 之前执行的逻辑会重跑，应避免不可重放的副作用。[D1；S1 的 middleware 文档与执行包装]
- 官方测试明确保留了已记录的人工编辑：即使后续收紧允许的决定，先前的 edit 仍生效。因此配置变化不会自动使已完成审批失效。[T1，L1700–1750]
- 官方重试测试展示一次人工审核后，工具可能因执行重试而运行两次。审批通过不能推出副作用只发生一次。[T1，L2245–2270]

## 4. 恢复、中断重放和子 Agent

动态中断需要 checkpointer，恢复时使用相同的 `thread_id`，将人工输入放入 `Command(resume=...)`。`Command.resume` 可以是一个值，也可以是 interrupt ID 到答案的映射。恢复并非继续原 Python 指令指针：中断所在节点会从头运行，直到再次走到相应 `interrupt()` 并取得已保存的答案。[D2；S2，L833–858、L903–1046]

同一节点内多个中断按出现顺序匹配。不能在恢复时重排、条件跳过或新增改变顺序的中断；中断前的代码必须可重放。类型形式的 `response_schema` 会在保存恢复值前验证，返回验证后的对象；JSON Schema 字典仅向客户端暴露 schema，不执行同等 Python 校验。[D2；S2，L903–1046；T2，L150–217]

`Command(update=...)`、`goto`、`graph` 主要用于节点返回的图控制；不要把只有 `update` 的 `Command` 当作通用编辑后继续 API。暂停编辑使用显式检查点更新，再以 `Command(resume=...)` 继续相应人工请求。[D2、D5]

### 嵌套子流程的持久化选择

| 子图编译设置 | 状态与恢复语义 | 项目接入含义 |
| --- | --- | --- |
| 默认 `checkpointer=None`，父图有 saver | 继承父图的单次调用持久化；支持 HITL；每次子调用重新开始其调用状态 | 适合独立的提取/核对子任务 |
| `checkpointer=True` | 同一线程下跨调用积累子图状态 | 并行调用同一有状态子图时需隔离 namespace，避免检查点冲突 |
| `checkpointer=False` | 关闭子图持久化 | 不能承诺该子流程可持久暂停与恢复 |

函数内部调用子图时，子图的 interrupt 会向外传播；恢复时**父调用节点和子图中断节点都会从头执行**。父节点中“调用子 Agent 之前”的代码也须可重放。[D4]

`get_state(config, subgraphs=True)` 的嵌套状态检查要求图结构可被静态发现。把子 Agent 隐藏在普通工具函数里，interrupt 仍可传播，但不能据此保证父图能枚举其全部嵌套检查点。[D4]

这些是图/Agent 正确接入时的合同。外部 Codex、Deep Agents 或任意 MCP 服务不会仅因被称为“子 Agent”就自动继承本地所有 Hook、检查点和工具网关；仍须适配其调用和结果。

## 5. 检查点编辑与运行中修改

`update_state` / `aupdate_state` 委托给批量状态更新实现。更新从已有检查点重建通道，按 reducer 应用值并保存**新检查点**；原检查点保留。指定 `as_node` 还会影响后继路由，不能视为无条件只改数据的标签。[D3、D5；S3，L1619–1696、L2617–2642]

本轮离线探针说明了两种需要区别的时机：

| 时机 | 实际观察 | 能据此承诺的行为 |
| --- | --- | --- |
| 已 interrupt 暂停，更新 amount=200，再恢复 | 节点进入值为 `[100,200]`；旧检查点仍为100；最终 amount=200 | 恢复重跑可读取新检查点中的编辑值 |
| 节点已在运行，另一路 `update_state` 写 amount=200，再释放原节点 | 原节点仍读100；该探针完成后最新状态也是100 | 更新检查点不会实时改写已运行节点的局部状态，后续写回可能覆盖独立更新 |

第二项是在 `InMemorySaver`、线程 Event 控制的最小图上观察到的结果，不外推为每个数据库后端的全部并发保证。它足以否定“任意在途修改自动合并并安全生效”的设计前提。

因此，人工纠错应先进入可控暂停边界，再以业务 revision/CAS 记录新版本，更新必要的 Agent 状态，重算受影响结果，使依赖旧内容的校验/审批失效，最后恢复。checkpoint ID、业务 revision、人工请求 ID 与已执行动作回执需要显式关联；`update_state` 本身没有提供财务字段依赖失效和冲突保护。

## 6. 持久性和副作用

官方 checkpointer 文档区分 durability：`sync` 在下一步骤开始前写完检查点；`async` 异步保存，崩溃时可能丢失最近检查点；`exit` 在正常结束、错误或中断时保存，不提供每个中间步骤的崩溃恢复。[D3]

本轮使用 `InMemorySaver` 验证节点重放和同进程状态语义，没有进行 kill/restart 或数据库认证测试。要通过本项目“暂停后重启继续”验收，需要可持久 saver，并验证其与指定 GaussDB 的驱动、SQL、事务、序列化及并发行为。不能因名称相近而宣称 PostgreSQL saver 已与 GaussDB 兼容。

LangGraph 的恢复消息也不是多个外部操作的原子提交：官方测试向多个并行中断同时提供答案时，一个合法答案对应的任务可以完成，即使另一个答案非法。此时只剩非法答案的任务继续等待，前者的副作用不会自动回滚。[T2，L263–314]

对于本项目，执行账本应记录动作标识、参数摘要、账单 revision、工具/规则版本、派发状态、真实回执及未知结果。重跑节点或恢复中断之前查询执行事实；工具成功而后置 Hook 失败时，只重试后处理。结果未知则先核对远端状态，不能把再批准一次当作安全重试机制。

## 7. 已执行的离线探针

运行入口为项目 `./python.cmd`，无真实业务写入。LangChain 探针使用本地假聊天模型（`FakeMessagesListChatModel` 的最小 `bind_tools` 适配），其固定输出为一次工具调用和随后一次结束消息；图探针使用内存 saver。以下为实测记录，不是在线模型或持久数据库验收结果。

### A. 暂停后编辑检查点

```text
initial interrupt: {"amount":100}
node entries: [100,200]
old checkpoint amount: 100
final: {"amount":200,"log":["original","human-edit","approved"]}
```

探针先暂停，再调用 `update_state` 修改 amount 并通过 reducer 添加日志，然后恢复。确认历史保留、reducer 合并以及恢复重跑读取新值。

### B. 嵌套子图重放

```text
initial interrupt count: 1
calls: ["parent-before","child-before","parent-before","child-before"]
final: {"value":"xy"}
```

确认父调用节点与子图中断节点的前置代码均执行两次。

### C. 实际 per-call middleware 的四类决定

| 决定 | 工具实际收到的 amount 列表 | 最终工具消息状态 |
| --- | --- | --- |
| approve | `[100]` | `success` |
| edit 为200 | `[200]` | `success` |
| reject | `[]` | `error` |
| respond | `[]` | `success` |

四次均暴露 response schema。该探针验证本地真实 middleware 行为，不能用于证明模型正确规划、业务金额校验或外部系统成功。

### D. 在途节点不读取并发 checkpoint 编辑

```text
worker initial amount: 100
checkpoint immediately after external update: 200
worker result after release: {"amount":100,"seen_amount":100}
latest checkpoint after worker completion: {"amount":100,"seen_amount":100}
```

原节点由 Event 暂停在其函数内部；另一执行路径以 `as_node=START` 更新检查点后释放它。此处没有触发 `interrupt()` 人工暂停，故原节点保留其启动时的局部状态。该结果用于区分“图检查点编辑”与“正在执行函数的实时编辑”。

## 8. 对项目实现与验收的直接约束

| 项目要求 | 可使用的框架基础 | 项目必须补齐并验收的部分 |
| --- | --- | --- |
| 批准、修改、拒绝动作 | HITL middleware、四类决定、typed interrupt | 动作白名单、完整参数组装、业务校验；避免把 `respond` 当成真实执行回执 |
| 修改提取字段后继续 | checkpoint 更新、reducer、resume | revision/CAS、原始证据保留、人工字段约束、依赖重算、旧审批/导出失效 |
| 暂停任务 | interrupt 和持久 saver | 停止新派发、结算在途结果、可控边界、前端任务状态 |
| 子 Agent 需人工输入 | 子图中断传播与 namespace | 显式任务上下文、父/子重放幂等、受控工具网关 |
| 热更新或工具禁用 | 新规划读取能力配置 | 真正派发前再授权；工具/规则/Skill 版本固定；受影响审批重新申请 |
| 恢复与重试不重复提交 | checkpoints 和已完成任务记录 | 业务执行账本、幂等键、远端未知结果核对、必要的数据库唯一约束/事务 |
| 进程重启后恢复 | 默认官方Agent Server管理框架状态 | 分验正常重启与硬崩溃；GaussDB保存业务revision/回执，核对其与已保存检查点关系，不默认注入GaussDB saver |

本报告只提供已核实的框架合同和设计约束。这里列出的应用层机制尚未由本轮研究实现，也未完成指定外部服务的真实集成验收。

## 9. 可定位的官方证据

以下文档于2026-10-21通过 Docs / Reference MCP 读取；文档会更新，固定版本源码与测试用于限定本轮结论。

- **D1**：[LangChain Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)。四类决定、两种模式、`when`、middleware 顺序及恢复协议。
- **D2**：[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)。重放、同线程恢复、多 interrupt 顺序、类型化响应。
- **D3**：[LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)。状态更新与 durability；具体持久化说明以此页为主。
- **D4**：[LangGraph Use subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)。子图持久化、嵌套状态检查、函数调用子图的重放。
- **D5**：[LangGraph Use time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)。检查点分叉与 `update_state`。
- **D6**：[HumanInTheLoopMiddleware API reference](https://reference.langchain.com/python/langchain/agents/middleware/human_in_the_loop/HumanInTheLoopMiddleware)。签名及固定源码入口。
- **S1**：[LangChain 1.4.6 HITL 源码](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/langchain/agents/middleware/human_in_the_loop.py#L85)。重点 L115–165、L196–284、L489–598、L727–859、L875–911、L979–1043。
- **S2**：[LangGraph 1.2.16 types 源码](https://github.com/langchain-ai/langgraph/blob/41c9c22fdc83d68a2859d0c9a2b627c8615a792f/libs/langgraph/langgraph/types.py#L833)。`Command` L833–858；`interrupt` L903–1046。
- **S3**：[LangGraph 1.2.16 Pregel 主实现](https://github.com/langchain-ai/langgraph/blob/41c9c22fdc83d68a2859d0c9a2b627c8615a792f/libs/langgraph/langgraph/pregel/main.py#L1619)。批量状态更新 L1619–1696；`update_state/aupdate_state` L2617–2642。
- **T1**：[LangChain HITL 官方测试](https://github.com/langchain-ai/langchain/blob/84ba23c414eca6bf6f6ebd1394a3006378113540/libs/langchain_v1/tests/unit_tests/agents/middleware/implementations/test_human_in_the_loop.py#L1700)。已记录编辑不因策略收紧失效 L1700–1750；per-call 响应及执行 L1894–2141；重试不重复审核但工具可执行两次 L2245–2270。
- **T2**：[LangGraph interruption 官方测试](https://github.com/langchain-ai/langgraph/blob/41c9c22fdc83d68a2859d0c9a2b627c8615a792f/libs/langgraph/tests/test_interruption.py#L150)。响应校验 L150–217；并行答案部分成功 L263–314。

前序案例的交付研究记录见 [feedback-and-learning.md](feedback-and-learning.md)，覆盖 agents-from-scratch、LangMem 与 OpenEvals；`.build/research/extensions_hitl_review/official_hitl_feedback_learning_audit.md` 为可排除的原始笔记。本报告补充当前框架版本的恢复与人工介入语义。
