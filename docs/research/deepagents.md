# Deep Agents 官方源码研究记录

> **历史源码快照，2026-10-21复核。** 保留固定commit能力与研究过程；后续按[当前实现方案](../implementation.md)、[Skill/Hook设计](../skills-and-hooks.md)及[最终开发计划](../superpowers/plans/2026-10-21-final-development-plan.md)。早期自定义FilesystemMiddleware、受控网关、宿主业务服务和before_commit建议已被原生配置/Skill及显式业务入口替代，不作为待实现清单。

检查日期：2026-10-21，Asia/Shanghai。仅研究官方源码和测试，没有安装 Deep Agents、运行示例、调用业务服务或读取项目 `.env`；没有修改 `AGENT.md`。

## 1. 固定版本与取证方式

- 仓库：`langchain-ai/deepagents`。
- 检查时 HEAD：`3abfb0abcda658d4b64e74782f3316a11efc3faa`。
- 提交：`release(deepagents): 0.7.29 (#7029)`。
- GitHub commit 时间：`2026-10-20T16:14:22Z`，上海时间为 `2026-10-21 00:14:22`。
- SDK `libs/deepagents/pyproject.toml` 的版本为 `0.7.29`；声明 Python `>=3.11,<4.0`、LangChain `>=1.4.6,<2.0.0`、langchain-core `>=1.6.12,<2.0.0`，并直接依赖 Anthropic、Google GenAI 适配器。接入属于额外依赖取舍，不能把现有 LangChain 环境视为已经兼容。
- 优先通过 GitHub MCP `get_commit`、`get_file_contents` 固定 SHA 读取；另浅克隆到 `.build/research/deepagents-official`，核对本地 HEAD 一致，用 `rg` 定位测试和补充源码。
- 读取了 `ecosystem-primer` 与 Deep Agents core/orchestration/memory Skills 以定位概念；部分 Skill 样例落后于本次源码，不把它们当作当前 API 实现证据。

Primary URLs：

- https://github.com/langchain-ai/deepagents/commit/3abfb0abcda658d4b64e74782f3316a11efc3faa
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/pyproject.toml

## 2. 主循环与 harness 的实际归属

`libs/deepagents/deepagents/graph.py:create_deep_agent()`（278 行起）负责解析模型、backend、子 Agent、profile，组织 middleware 后，在 995 行调用 LangChain `create_agent(...)`。`response_format`、`checkpointer`、`store`、`context_schema`、`state_schema` 等直接传下去；返回的是带配置的图。它没有另写一套独立执行引擎。

在本次 SHA，主栈包括 `FilesystemMiddleware`、按条件加入的 `SubAgentMiddleware`、父任务通知、摘要/上下文管理、工具调用修补；传入 skills/memory/interrupt 配置才加入对应 middleware。模型响应、工具执行和重复调度由 LangChain/LangGraph 承担。`graph.py:1008-1017` 设置默认 `recursion_limit=9999`；这个值不能当成适合账单任务的调用预算、超时、费用上限或业务完成条件。

一个容易沿用旧资料产生的错误：SDK 目前不再普遍默认提供 `TodoListMiddleware`。`profiles/harness/_openai_codex.py:_build_extra_middleware()`（69-77 行）明确说明它因 Codex profile 的提示词而显式补入 `TodoListMiddleware()`。Qwen 接入需要计划工具时应显式安装，不能凭 `create_deep_agent()` 名称推定已有 `write_todos`。

`graph.py:75-78` 的 `DeepAgentState.messages` 使用 `DeltaChannel`，用于减少长对话检查点重复存储；这并不是已提供业务输入版本、并发编辑锁或副作用幂等账本。

Primary URLs：

- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/graph.py#L278
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/graph.py#L893
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/graph.py#L995
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/profiles/harness/_openai_codex.py#L69

## 3. 真实示例及不能直接移植的部分

### deep_research

`examples/deep_research/agent.py` 实际创建 `research-agent`，配置 Tavily 搜索和 `think_tool`，再交给 `create_deep_agent`。提示词要求主 Agent 计划、把请求写入虚拟文件、委派、综合来源、写报告和回读检查。这是可参考的“上下文分包—专职调查—汇总—验证”流程。

但 `max_concurrent_research_units=3`、`max_researcher_iterations=3` 仅被格式化到提示词。研究员最多搜索五次的要求也只在 `research_agent/prompts.py` 文本中；`research_agent/tools.py:tavily_search()` 没有相应预算计数器，`think_tool()` 只是返回包含 reflection 的字符串。不能把这些文字称为代码强制的并发或终止保障。

示例在 `agent.py:51` 固定 Anthropic 模型，没有使用本项目 Qwen 适配器；没有设置项目所需的检查点持久化、人工纠错、账单提交前校验或财务 schema。`prompts.py:7` 要求 `write_todos`，而这个脚本没有显式配置 TodoList middleware；结合当前 SDK 默认栈，迁移此示例时必须补查实际工具表。模型自行“确认已覆盖全部问题”也不能代替确定性验收。

网页获取工具把抓取失败包装为字符串返回。它适合作为研究示例，不应原样充当本项目文档/OCR 的成功失败契约；本项目需保留结构化错误与来源。

### rubric_middleware

`examples/rubric_middleware/rubric_agent.py:main()` 展示如何把 `RubricMiddleware` 装进 Agent，按 rubric 迭代改进。实际评级逻辑在 SDK `middleware/rubric.py`，不是示例中的一句提示词。可借其“候选输出—评价—有限修订”设计，不适合直接授予账单提交权限。

### better-harness

`examples/better-harness/better_harness/core.py:run_experiment()`（864 行起）是真实的外层优化循环：先跑 baseline train/holdout，提议候选，再跑两个 split，按合计通过数严格增加决定接受，最后可跑 scorecard 并保存报告；全通过、没有改动或迭代次数用尽会停。`agent.py:propose_variant()`/`invoke_deepagents_proposer()` 负责提议变体。

这是离线改进 prompt/harness 的工程样例，涉及 pytest/Harbor 与可修改 surface，不能当作在线账单处理循环。可借用 train/holdout/独立 scorecard 的分层验收，但本项目还要加入误更新、重复提交、来源丢失等业务指标。其接受准则是 train+holdout 总通过数增加，并不保证每个 split 或每个场景均无回退。

### ralph_mode

`examples/ralph_mode/ralph_mode.py:ralph()` 通过 CLI 的 `run_non_interactive()` 一次次启动新线程，文件系统继续保留。默认 `max_iterations=0`，`while` 将无限继续；仅停止码 130、键盘中断或显式迭代次数让它退出。代码没有“业务成功即停”的判定。本项目不应使用这个模式自动处理账单。

Primary URLs：

- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/examples/deep_research/agent.py
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/examples/deep_research/research_agent/prompts.py
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/examples/deep_research/research_agent/tools.py
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/examples/rubric_middleware/rubric_agent.py
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/examples/better-harness/better_harness/core.py#L864
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/examples/ralph_mode/ralph_mode.py#L46

## 4. 子 Agent：隔离范围、状态返回、Hook 覆盖

`middleware/subagents.py:create_sub_agent()`（575 行起）用 `create_agent()` 构建声明式子 Agent；`_build_task_tool()` 把它们变成 `task(description, subagent_type, runtime)` 工具。

- 默认 isolated 模式：`_validate_and_prepare_state()`（804 行起）把聊天消息换成仅含 description 的 `HumanMessage`，但仍复制没有被排除、也没有标记 private 的其他 state 字段。因此它是聊天上下文隔离，不是业务数据或权限自动完全隔离。
- 返回：`_return_command_with_state_update()`（747 行起）把非排除、非 private、发生变化的 state 字段写回父图；有 `structured_response` 就 JSON 序列化到 `ToolMessage`，否则提取最后一条非空 AI 文本。项目不能仅依赖父 state 的隐式合并，应以显式候选 schema 接收和验证结果。
- `CompiledSubAgent` 的 runnable 原样使用；调用方必须自行构建它的 state schema、工具和 middleware，不能宣称主 Agent 自动包住其所有内部动作。
- `graph.py:723-767` 为普通声明式子 Agent 组织独立栈；`graph.py:854-855` 的默认 general-purpose 子 Agent只继承与其默认槽同名的定制 middleware，普通主控业务 Hook 不会全部自动继承。
- 实验性的 `mode="fork"` 会复制父聊天并继承主控定制 middleware；`subagents.py:843-844` 等还拒绝 fork 中继续递归 task。不要按旧 Skill 的“子 Agent 永远无上下文”描述当前全部模式。
- `async_subagents.py` 实际实现远程异步启动、查询、更新、取消、列举及通知；`graph.py:923-926` 当前接的是 LangSmith deployment。它不是通用的本机进程调度器，也不能证明远端已执行操作可撤销。

Primary URLs：

- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/subagents.py#L575
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/subagents.py#L747
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/subagents.py#L804
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/graph.py#L723
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/async_subagents.py

## 5. Skills 渐进加载与热更新边界

`middleware/skills.py:SkillsMiddleware.before_agent()`（1168 行起）按 sources 扫描目录、解析 frontmatter，把 name/description/path 等 metadata 放进 state；同名按后 source 覆盖。`modify_request()` 只把索引和加载警告拼入 system message。完整正文通常由模型用 `read_file` 获取，或由 `pinned_skills` 在 `before_model()` 中主动插入消息。

注意：这是模型上下文的渐进披露，并不代表只读取了 frontmatter 字节。`_list_skills_with_errors()`（687 行起）会下载各个完整 `SKILL.md` 再解析 metadata。

已经加载的 `skills_metadata`（包括空列表）会跳过重载；设置为 `None` 才在下一次 run 的 `before_agent` 重载。没有看到默认文件监听器或 MCP/Skill 注册事务；索引重载时可返回部分结果并记录 warning，而不是本项目要求的“整体校验后发布新版本、失败保留上一有效版本”。

当前版本还有真正实现的延迟工具披露：

- `SkillsMiddleware(..., tools=...)` 可接受工具列表或 resolver。
- 读取某 Skill 后，`wrap_model_call()` 根据该 Skill 的 `metadata.include_tools` 调 resolver，才把相关工具 schema 暴露给模型，并记录此次披露。
- `wrap_tool_call()` 在执行边界再次调 resolver；工具不再由 resolver 返回时，返回无效工具错误。这能作为动态禁用的参考。
- 若同名工具原本已经注册在 request 中，不能把 Skill 读取门槛当成对该工具额外的授权；`allowed-tools` 也是推荐元数据，不是执行权限系统。
- resolver 在模型时和执行时可能得到不同实现；源码没有业务能力版本锁定、schema 迁移或审批失效机制，这些仍由项目运行时管理器提供。

对应单元测试 `test_skill_tool_resolver.py` 覆盖同一轮读 Skill 不能立即绕过披露、resolver 撤回工具、跨恢复重新解析等行为。这里只核对测试源码，没有执行测试。

Primary URLs：

- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/skills.py#L687
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/skills.py#L1028
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/skills.py#L1168
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/skills.py#L1322
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/tests/unit_tests/middleware/test_skill_tool_resolver.py

## 6. Middleware、权限与上下文控制

源码使用 LangChain middleware 的 before/after agent、before/after model、wrap model、wrap tool 等接口。主控传入的 middleware 按名称替换同名默认项，其他项插入既定位置；需要同时实现 sync/async 路径，不能只拦一种入口。

`FilesystemMiddleware(tools=[...])` 支持限制实际内建文件工具，且列表必须保留 `read_file`。工具自身实现检查路径权限。`filesystem.py:1976` 对提供执行能力的 backend 与一般文件 permissions 的组合会抛 `NotImplementedError`，并明确说明 execute 的工具级权限还没实现；不能把文件路径规则当成 shell 沙箱。

`_ToolExclusionMiddleware` 同时从模型工具表剔除名称，并在执行边界拒绝对应调用；但源码明确称它不是 security surface，且排除表随构建的模型/profile确定，不能直接代表本项目热插拔权限网关。

`summarization.py:create_summarization_middleware()`、`compute_summarization_defaults()`、`_call_with_budget()` 实际提供历史卸载、参数截短、摘要、上下文溢出后有界恢复等能力。有模型 profile 时默认 trigger 为输入容量的 85%，保留 10%；没有 profile 时是固定 170000 token trigger、保留六条消息。Qwen 兼容客户端是否有准确 profile 必须实测，否则不能假设默认阈值适合目标窗口。原始消息与摘要事件分开保存有助审计，但摘要文本仍不能作为财务原始证据的唯一存档。

Primary URLs：

- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/graph.py#L211
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/filesystem.py#L1891
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/_tool_exclusion.py#L34
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/summarization.py#L263
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/summarization.py#L1464

## 7. Memory 与持久恢复必须区分

`middleware/memory.py:MemoryMiddleware.before_agent()` 通过 backend 下载传入的 memory sources 并缓存到 `memory_contents`，已经有该 key 就不重读；`modify_request()` 把内容拼入系统提示词。SDK 不会在 `memory=None` 时自动全盘发现项目 AGENTS.md，也没有因某轮人工纠错就自动沉淀全局正确规则的代码。

`backends/state.py:StateBackend` 通过 LangGraph 的 files channel 读写，属于线程状态；是否跨进程保留取决于 checkpointer，不能由名称推断持久化。`backends/store.py:StoreBackend` 使用 BaseStore，当前构造要求明确传 `namespace` factory，用于用户/租户/助手隔离；store 本身是否落盘取决于传入的实现。`CompositeBackend` 按最长路径前缀路由，可以把临时工作文件和共享记忆分开。

本次 0.7 源码不接受旧样例常见的 backend factory：`filesystem.py:1964` 会拒绝可调用的 backend，要求已经初始化的 backend 实例。接入应按固定版本 API 写，不能直接抄旧 Skills 的 `backend=lambda rt: StoreBackend(rt)`。

本项目的 GaussDB 是否兼容某 checkpointer/store，以及重启恢复后的幂等回执、账单版本与审批绑定，仍需独立实现/测试；这里没有相应项目集成证据。

Primary URLs：

- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/memory.py#L279
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/backends/state.py#L38
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/backends/store.py#L100
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/backends/composite.py#L195

## 8. Eval、终止与完成状态

`RubricMiddleware.after_agent()` 在 Agent 自然停止后调用 grader。`needs_revision` 时通过 `jump_to='model'` 加入修订消息；`max_iterations` 默认三轮，到上限变为 `max_iterations_reached`。`grader_error`、`failed`、`satisfied` 也会结束评级循环。上限约束的是评级修订轮数，不是其间所有模型调用或工具调用。

grader 异常会保存 `grader_error` 状态；`on_evaluation` 的普通异常只记录日志。调用方必须检查状态，不能把返回了 final message 或图结束直接当“校验成功”。此外首轮提取到的 criterion 集合会冻结，但源码明确指出 rubric 文本并未被确定性解析，首轮漏项可能被当作基准。因此这适合补充语义检查，不适合承担金额、币种、权限、版本冲突等必须成功的提交前规则。

`libs/evals/tests/evals/` 包含 skills、subagents、memory、多轮 memory、summarization、工具选择等真实测试；`conftest.py:model()` 构建模型，`utils.py:run_agent()` 真正 invoke 图。`TrajectoryScorer.success()` 是失败即测试失败的正确性断言；`.expect()` 的步骤数/工具调用等仅记录效率反馈，不使测试失败。评测存在不等于某模型、本项目样本或线上服务已经通过。

本项目宜借鉴：离线固定响应回放 + 正确性硬断言 + 单独效率观测 + 少量真实模型集成。特别为禁止调用、热禁用、参数修改后重新校验、工具已成功但后置 Hook 失败、重启恢复不重复副作用建立自己的硬断言。

Primary URLs：

- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/rubric.py#L661
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/rubric.py#L1230
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/deepagents/deepagents/middleware/rubric.py#L1277
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/evals/tests/evals/utils.py#L1198
- https://github.com/langchain-ai/deepagents/blob/3abfb0abcda658d4b64e74782f3316a11efc3faa/libs/evals/tests/evals/test_subagents.py

## 9. 面向本项目的取舍（建议，不是已实现状态）

保留 LangChain `create_agent()` 主控，按 `AGENT.md` 负责信息补齐、任务规划、专职子任务调度和最终汇总。Deep Agents 可作为按需的复杂材料理解/证据研究子 Agent，优先让它产出候选结果；简单格式解析、金额核对、匹配和增量更新继续由普通工具/确定性服务完成。

受控接入应满足：

1. 主控通过注册的工具/子 Agent 适配器调用 Deep Agents，输入明确携带任务目标、材料引用、记账主体、账单版本、能力版本和输出 schema；不传整份全局聊天或未筛选 state。
2. 显式传本项目初始化后的模型适配器及 `enable_thinking:false`，不依赖默认 Anthropic 模型；Qwen 工具调用、structured output、上下文 profile 和错误恢复另做实测。
3. 使用任务范围 StateBackend 或受限 backend；以自定义 FilesystemMiddleware 减小内建工具集合；不配置本机 shell 执行能力。普通工具/MCP 工具都封装为同一受控网关的工具对象。
4. 业务 Hook 必须在每个会执行受控工具的子 Agent 栈显式安装，或把真正权限检查放在工具服务端/网关。只拦外层 task 不能观察 opaque runnable 内每次调用。
5. 接收 `structured_response` 中的候选字段与来源，重新执行 schema、金额、币种、主体、匹配、版本和去重检查；最终提交工具不交给子 Agent，提交由统一业务服务和 before_commit Hook 控制。
6. 显式设置模型/工具次数、耗时和任务预算、并发上限及停止状态，不使用 9999 recursion 或提示词里的 hard limits 冒充保障。Rubric 可作可选修订器，任何未验证或失败状态进入待复核。
7. Skills 动态工具 resolver 可以复用其接口思想，但能力注册、版本快照、在途连接释放、失败保留旧版本、审批失效和恢复版本检查仍是本项目运行时管理器职责。
8. 长期 memory 只保留用户明确允许沉淀的规则/偏好；当前账单原件、人工修改、审核与提交事实进入项目审计和版本存储。人工改字段不自动覆写共享 Skill 或全局记忆。

适用结论：适合作为受控的可选子 Agent 及上下文管理组件；不应替换 LangChain 主控，不应作为现成账单引擎、完整热插拔管理器、事务系统或业务审批系统。
