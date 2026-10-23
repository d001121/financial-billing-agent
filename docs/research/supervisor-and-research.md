# 官方历史案例源码研究：Open Deep Research 与 Supervisor

> **历史案例快照。** 用于解释协作模式，不是本项目的实现清单；后续以[当前实现方案](../implementation.md)和[最终开发计划](../superpowers/plans/2026-10-21-final-development-plan.md)为准。归档案例中的顶层图、调度或执行设施不直接搬入项目。

研究日期：2026-10-21（项目当前日期）。读取方式：GitHub MCP 的 get_commit、get_file_contents。未读取 .env，未修改 AGENT.md，未运行第三方仓库代码。以下均为源码审阅结论，不能代表本项目已经集成。

## 固定版本

- open_deep_research：默认 main 本次返回 HEAD `1b7d2e80db9faa586165c60e09096dbbfd483a64`，提交时间 `2026-08-10T18:13:29Z`。[commit](https://github.com/langchain-ai/open_deep_research/commit/1b7d2e80db9faa586165c60e09096dbbfd483a64)
- langgraph-supervisor-py：main 本次返回 HEAD `88859b34017ac3569bbd4a3092c7e77593a0a960`，提交时间 `2026-07-15T06:32:51Z`。项目版本 0.0.31，依赖 langgraph>=1.0.2,<2.0.0；不是将一个依赖精确锁死。[commit](https://github.com/langchain-ai/langgraph-supervisor-py/commit/88859b34017ac3569bbd4a3092c7e77593a0a960) · [pyproject](https://github.com/langchain-ai/langgraph-supervisor-py/blob/88859b34017ac3569bbd4a3092c7e77593a0a960/pyproject.toml)
- 为核对 Supervisor 委托的基础 Agent 终止逻辑，另读 langgraph main 本次解析的 `a24fc97778fca67cfac4cd3fc63e508ee1d29f59`，提交时间 `2026-10-20T10:09:26Z`。这是独立的依赖源码参照，不声称它是上仓库 lockfile 中的精确安装版本。[commit](https://github.com/langchain-ai/langgraph/commit/a24fc97778fca67cfac4cd3fc63e508ee1d29f59)

三者提交时间均早于当前项目日期，未发现日期冲突；HEAD 仅指本次实际返回，不预言后续更新。

## 维护状态补核

2026-10-21 通过 GitHub MCP search_repositories 核实：`repo:langchain-ai/open_deep_research archived:true` 命中 1 个仓库，完整元数据 `archived=true`；`repo:langchain-ai/langgraph-supervisor-py archived:true` 同样命中 1 个，`archived=true`，其 `archived:false` 查询返回 0。两个仓库均已归档，应作为历史源码与设计模式参考，不能列为活跃维护的新项目主框架候选。[ODR 仓库元数据](https://api.github.com/repos/langchain-ai/open_deep_research) · [Supervisor 仓库元数据](https://api.github.com/repos/langchain-ai/langgraph-supervisor-py)

MCP 本次返回的元数据不含归档时间字段，不能把 pushed_at 或 updated_at 当作归档日期。主 Agent 本轮另从 ODR 网页横幅读取到“archived Aug 21, 2026; read-only”，对应 2026-08-21；该精确日期的证据来自网页横幅，而非上述 MCP 元数据。Supervisor 的精确归档日期在本笔记中不作推断。

## Open Deep Research：真实控制流

实际阅读：src/open_deep_research/deep_researcher.py（719 行）、configuration.py、state.py，以及 utils.py 的工具装配/MCP 部分。这个项目的主编排直接使用 LangGraph StateGraph，模型与工具调用来自 LangChain，不能称为直接使用 LangChain create_agent 的范例。

- 主图：START → clarify_with_user → write_research_brief → research_supervisor 子图 → final_report_generation → END。clarify_with_user 用 Pydantic schema 判断是否补问；需要时返回 END 与问题，而不是在该函数中 interrupt 等待。这份模块的 compile() 没有传入 checkpointer，不能仅凭这个文件证明本地跨重启恢复。[主图与函数](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py#L60-L175) · [图装配](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py#L699-L719)
- 主管循环：supervisor 绑定 ConductResearch、ResearchComplete、think_tool；supervisor_tools 执行。多个 ConductResearch 先截到 max_concurrent_research_units，再 asyncio.gather 并行调用 researcher_subgraph；超出的请求返回工具错误，未排队等下一批。默认并发数 5。[主管执行](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py#L178-L350)
- 主管终止：迭代次数 > max_researcher_iterations、没有工具调用、或出现 ResearchComplete。默认上限 6，但计数在模型返回后加一，因此最多有第 7 次主管模型调用，然后在执行工具前退出；不是简单的“只调用六次模型”。[终止判断](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py#L245-L272) · [默认参数](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/configuration.py#L64-L119)
- 研究员循环：researcher → researcher_tools → researcher，工具使用 asyncio.gather 并行执行。没有工具调用且没有原生搜索时转 compress_research；执行完工具后，次数 >= max_react_tool_calls（默认 10）或 ResearchComplete 时转压缩。压缩产物是 compressed_research 与 raw_notes；主管接收精简结果，避免汇入所有子任务完整对话。[子任务循环](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py#L365-L605) · [状态 schema](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/state.py#L54-L113)
- 工具装配：get_all_tools 先放 ResearchComplete 与 think_tool，再加入配置选定的搜索工具和 MCP 工具；load_mcp_tools 按名字过滤工具、跳过重名、连接失败返回空列表。这是真正“配置影响可调用工具集合”的例子；但它当前按一个配置 URL 创建 server_1，不能直接等同于通用插件平台。[工具装配](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/utils.py#L449-L597)

适用：范围尚不确定、可以分解成独立证据搜集任务、需要汇总报告的工作。对本项目可借鉴主体检查/补齐、按文件独立提取、受控并发、结构化阶段产物和工具注册。

限制与不可照搬点：
1. supervisor_tools 的 except 中含 `is_token_limit_exceeded(...) or True`，任何该 try 块的异常都会结束子图；外层还会继续走 final_report_generation。账单提取不能把服务失败等同于“研究已完成”。[异常分支](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py#L324-L338)
2. execute_tool_safely 将异常转成普通错误字符串；compress_research 三次失败也返回带 Error 文本的压缩结果。财务工具应返回明确的成功/可重试失败/需补齐/待复核结构，不能让普通字符串流入合法账单结果。[工具错误](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py#L427-L432) · [压缩失败](https://github.com/langchain-ai/open_deep_research/blob/1b7d2e80db9faa586165c60e09096dbbfd483a64/src/open_deep_research/deep_researcher.py#L540-L585)
3. 其中 think_tool 是显式反思文本工具。它与 Qwen 服务端 enable_thinking 开关不是同一个机制；本项目不需要复制该工具来满足规划要求。应输出计划、缺失信息与可核验依据，并在所有模型适配入口关闭服务端思考。
4. 压缩总结适合报告，不足以承载字段级财务证据；金额、币种、行定位、变更前后值必须保留结构化引用，不能只留压缩文字。

## Supervisor：handoff 与上下文控制

实际阅读：langgraph_supervisor/supervisor.py、handoff.py；README 只用于核对维护者的推荐，未用 README 代替源码。

- create_supervisor 先校验子 Agent 名称唯一，再 _prepare_tool_node 自动构建/收集 handoff tools，内部 create_react_agent 作为 supervisor；外图 START → supervisor，每个子 Agent 完成后都有固定边回 supervisor。[create_supervisor](https://github.com/langchain-ai/langgraph-supervisor-py/blob/88859b34017ac3569bbd4a3092c7e77593a0a960/langgraph_supervisor/supervisor.py#L393-L469)
- create_handoff_tool 的单次转移返回 Command(graph=Command.PARENT, goto=agent_name)；同一模型消息有多个工具调用时，返回 Send 给对应子 Agent，并过滤无关 tool-call，维持消息协议。并行能力还受模型 bind_tools 是否支持 parallel_tool_calls 影响，源码默认 False，不能假定 Qwen 兼容接口支持同样参数。[handoff](https://github.com/langchain-ai/langgraph-supervisor-py/blob/88859b34017ac3569bbd4a3092c7e77593a0a960/langgraph_supervisor/handoff.py#L55-L129) · [参数能力检查](https://github.com/langchain-ai/langgraph-supervisor-py/blob/88859b34017ac3569bbd4a3092c7e77593a0a960/langgraph_supervisor/supervisor.py#L48-L63)
- _make_call_agent 控制消息回收：full_history 返回全部消息；默认 last_message 一般只返回末条，若末条是 ToolMessage 则保留最后两条；可另加返回主管的 handoff 消息。这个策略控制上下文，不等于保存审计证据。[输出处理](https://github.com/langchain-ai/langgraph-supervisor-py/blob/88859b34017ac3569bbd4a3092c7e77593a0a960/langgraph_supervisor/supervisor.py#L66-L127)
- 外层没有账单业务完成条件。基础 create_react_agent 的 should_continue 在模型不再调用工具时结束，或先跑 post_model_hook / structured response；return_direct 工具也可结束，remaining_steps 约束工具循环。主管仍需业务规则和显式预算，不能把模型不调用工具当作校验成功。[基础终止逻辑，独立固定版本](https://github.com/langchain-ai/langgraph/blob/a24fc97778fca67cfac4cd3fc63e508ee1d29f59/libs/prebuilt/langgraph/prebuilt/chat_agent_executor.py#L831-L859) · [return_direct](https://github.com/langchain-ai/langgraph/blob/a24fc97778fca67cfac4cd3fc63e508ee1d29f59/libs/prebuilt/langgraph/prebuilt/chat_agent_executor.py#L970-L1002)

适用：确有多种专门能力、每种能力需要独立上下文和工具集合时的中心主管模式。局限：该库当前源码内部仍调用标注 deprecated 的 create_react_agent；仓库 README 明确建议多数新项目直接用工具构建 supervisor pattern，以更细地控制上下文。[源码调用](https://github.com/langchain-ai/langgraph-supervisor-py/blob/88859b34017ac3569bbd4a3092c7e77593a0a960/langgraph_supervisor/supervisor.py#L443-L452) · [维护者建议](https://github.com/langchain-ai/langgraph-supervisor-py/blob/88859b34017ac3569bbd4a3092c7e77593a0a960/README.md#L1-L5)

## 对航运账单项目的建议

保持 AGENT.md 的 LangChain 主编排约束：顶层采用 LangChain create_agent 管理缺失信息检查、任务计划与工具选择；把文档解析、OCR、结构化提取、匹配、校验、合并和必要的专门 Agent 封装成工具。确实需要 LangGraph 时，仅将其作为 LangChain 调用的子流程，不能直接照搬 ODR 的 StateGraph 作为项目顶层。

并行只用于独立文件/OCR/候选提取，不并行修改同一账单；跨文件归并和增量更新由代码统一裁决。子工具返回结构化字段、证据引用、问题与执行状态，主管可看简要结果，原始证据另行持久化。预算终止或服务失败产生待复核/失败状态；任务的业务完成必须由 schema、金额核对、匹配唯一性和主体充分性共同确定。

两个参考仓库均已归档，不建议先引入 langgraph-supervisor 包或把 ODR 整体作为基础框架。先采用 Supervisor 仓库明确推荐的“子 Agent 包装为工具，LangChain 主 Agent 调用”方式，待确有上下文隔离需求时再增加专门 Agent。Qwen 的关闭思考配置在统一模型工厂实现；案例自带的 think_tool 无需引入。

