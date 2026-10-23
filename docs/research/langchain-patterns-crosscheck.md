# LangChain MCP 与官方源码交叉核对：多 Agent 模式

> **研究快照。** 固定案例与源码事实保留；其中宿主业务服务等早期建议已由[当前实现方案](../implementation.md)及[Skill/Hook设计](../skills-and-hooks.md)替代，全部领域实现归Skill。实施顺序见[最终开发计划](../superpowers/plans/2026-10-21-final-development-plan.md)，不恢复案例中的自有顶层图或执行网关。

核验日期：2026-10-21，Asia/Shanghai。先用当前会话原生 LangChain 文档 MCP 的 search_docs_by_lang_chain 检索，再用 query_docs_filesystem_docs_by_lang_chain 读取检索返回的真实页面路径；随后通过 GitHub MCP 读取对应 MDX 内的 Python 示例代码。GitHub 身份已按工具规则核对，未在材料中保存个人资料。未读取 .env，未修改 AGENT.md，未运行示例模型、外部写入或业务代码。

本轮原生文档 MCP 的 search 与 query 均实际成功。这一事实更新的是本轮工具可用证据，不代表项目业务 Agent 已接入 MCP。

## 1. 源码版本与范围

langchain-ai/docs 的 main 在本次调用中解析为 **274fcd26537b0c1440600b4bb3ecce896aaac5d3**，提交时间 **2026-10-20T16:16:15Z**，早于项目当前日期。后续引用固定此 commit：[提交记录](https://github.com/langchain-ai/docs/commit/274fcd26537b0c1440600b4bb3ecce896aaac5d3)。

读取的当前文档页面包括：

- /oss/python/langchain/multi-agent/subagents.mdx
- /oss/python/langchain/multi-agent/router.mdx
- /oss/python/langchain/multi-agent/handoffs.mdx
- /oss/python/langchain/multi-agent/skills.mdx
- /oss/python/langchain/multi-agent/custom-workflow.mdx

另读当前教程相关章节，并通过 GitHub MCP 阅读四份对应源文件中的 Python 代码：

- src/oss/langchain/multi-agent/subagents-personal-assistant.mdx
- src/oss/langchain/multi-agent/router-knowledge-base.mdx
- src/oss/langchain/multi-agent/handoffs-customer-support.mdx
- src/oss/langchain/multi-agent/skills-sql-assistant.mdx

这些是官方教程 MDX 中的实际 Python 代码块，不是声称存在一套已经运行过的独立 Python 应用。对 SUPERVISOR_PROMPT 的 docs 仓库 .py 搜索未返回匹配，未据此推断仓库完全没有 Python 文件。旧案例与其归档状态复用此前研究，本轮没有重新克隆。

## 2. 官方五种模式的推荐条件

| 模式 | 本轮原生 MCP 读取的官方条件 | 航运账单项目采用方式 |
| --- | --- | --- |
| Subagents | 需要集中主控，领域工具或逻辑不同，子 Agent 通常不直接与用户对话；子 Agent 以工具调用，默认独立上下文。工具很少时可用单 Agent。 | 保留 LangChain 主控 + 提取/核对子 Agent；复核按问题需要启用。文档格式本身不必各建一个模型 Agent。 |
| Router | 输入类别清晰、独立知识源可并行查询、需要显式分类与汇总；通常是一次分流，不承担多轮主控。 | 文件格式/解析能力优先代码路由；独立附件可并行。若有专门 router/workflow，将其封装成主控调用的工具。 |
| Handoffs | 需按状态逐步收集信息、满足前置条件才开放下一能力，或多阶段直接对话。可切换 Agent，也可由同一 Agent 动态切换提示词/工具。 | 不必把用户交给不同账单角色。可借鉴单主控 current_step 状态门禁，缺记账主体时先补齐，相关财务能力尚不开放。 |
| Skills | 一个 Agent 有多种按需专业知识，需要轻量渐进加载，不要求单靠 Skill 强制复杂约束。 | 费用映射、单据说明和行业知识可按需加载；计算、匹配、发布与副作用仍由代码和网关约束。 |
| Custom workflow | 标准模式不够，需明确混合确定性逻辑、模型、分支、循环和多阶段处理。 | 合适的局部确定性子流程可以采用；本项目仍遵守 LangChain create_agent 主控约定，不将顶层替换为 StateGraph。 |

对应官方页面：[Subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents) · [Router](https://docs.langchain.com/oss/python/langchain/multi-agent/router) · [Handoffs](https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs) · [Skills](https://docs.langchain.com/oss/python/langchain/multi-agent/skills) · [Custom workflow](https://docs.langchain.com/oss/python/langchain/multi-agent/custom-workflow)。

## 3. 当前教程实际实现与项目差异

### 3.1 Subagents 个人助手

实际 Python 源码先 create_agent 构造 calendar/email 子 Agent，再用 schedule_event/manage_email 工具包装 invoke，最后 create_agent 主管只注册这两个高层工具。主管不需要直接面对底层 API 参数。[源码 L825–908](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/subagents-personal-assistant.mdx#L825-L908)

这支持项目的主控—专职提取/核对分层。不过教程包装器只传 request 字符串，并返回最后消息文本。本项目应将 task_id、revision、记账主体、文件/证据引用、人工锁定字段、规则/能力版本作为显式受控上下文，返回结构化提案、证据引用、问题及状态；不能只保存自然语言摘要。[信息流源码 L1465–1601](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/subagents-personal-assistant.mdx#L1465-L1601)

高级示例从消息中 next 取得第一条 human 消息；这不足以自动代表后续人工修订。本项目恢复时必须读取最新 revision，不能依赖最初问题推断当前主体或已修改金额。此为项目适配判断，不是官方保证。

人工介入章节在两个子 Agent 各自安装 HumanInTheLoopMiddleware，顶层主管配置 checkpointer；后续按 interrupt.id 构造 approve/edit 决策，再 Command(resume=...)。这支持“子工具处拦截、顶层恢复”的层级，不支持“父 Hook 自动继承给子工具”的推断。教程使用 InMemorySaver，不能作为本项目跨重启持久恢复的证明。[人工介入源码 L1161–1205](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/subagents-personal-assistant.mdx#L1161-L1205) · [恢复源码 L1364–1398](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/subagents-personal-assistant.mdx#L1364-L1398)

### 3.2 Router 知识库

classify_query 使用 with_structured_output 生成分类；route_to_agents 返回 Send 列表；各 source Agent 独立返回结果，operator.add reducer 汇集，synthesize_results 汇总，外图结束。它不是动态处理缺失信息和纠错的主管。[源码 L978–1075](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/router-knowledge-base.mdx#L978-L1075)

同一教程的 stateful 扩展恰好展示：将 router workflow 封装为 search_knowledge_base 工具，由外层 create_agent 持有会话和检查点。这与本项目“局部图被 LangChain 主控调用”的约束相容。[源码 L1389–1421](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/router-knowledge-base.mdx#L1389-L1421)

独立附件提取可复用其 fan-out / reducer 思路；同一账单的匹配和合并不交给并行分支分别提交。教程的 GitHub/Notion/Slack 搜索函数是返回固定文本的 stub，不代表已完成真实服务集成。[示例工具 L900–940](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/router-knowledge-base.mdx#L900-L940)

### 3.3 Handoffs 客服

当前 Python 教程并没有要求多个角色 Agent：同一个 create_agent 使用 SupportState.current_step。工具返回 Command 更新状态并补齐匹配 tool_call_id 的 ToolMessage；apply_step_config 在模型调用前校验 requires，再动态选择提示词与工具集合。[状态与工具 L188–229](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/handoffs-customer-support.mdx#L188-L229) · [门禁 middleware L427–513](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/handoffs-customer-support.mdx#L427-L513) · [单 Agent 装配 L565–589](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/handoffs-customer-support.mdx#L565-L589)

项目可以借鉴前置条件控制：记账主体缺失时主控请求补齐；相关判断工具的执行端再次校验主体与版本。仅动态隐藏工具不足以替代派发时校验，尤其存在热禁用、恢复和旧计划时。无需为此增加用户可见的角色交接。

### 3.4 Skills SQL 助手

SkillMiddleware 将技能名称/描述注入系统消息，load_skill 只按需返回正文。基本版本在 __init__ 缓存列表；文档另外建议需要刷新时考虑 before_agent。高级版本用 skills_loaded 与 Command 跟踪加载状态，再在工具内检查前置条件。[加载与 middleware L477–590](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/skills-sql-assistant.mdx#L477-L590) · [状态扩展 L810–877](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/skills-sql-assistant.mdx#L810-L877)

必须区分教程名称与实际执行：write_sql_query 只检查 vertical 是否在 skills_loaded，随后格式化字符串，其中的“validated”文字不是 SQL 解析或数据库校验。这能证明“加载状态门禁”模式，不能证明业务校验本身已实现。[实际函数 L946–983](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/oss/langchain/multi-agent/skills-sql-assistant.mdx#L946-L983)

本项目应固定在途任务使用的 Skill/规则版本；刷新与候选发布走既定边界。动态发现或加载能力不等于获得发布全局规则的权限，人工纠错不自动沉淀发布。

## 4. 建议保留与具体调整

保留：LangChain create_agent 单主控；专职提取与核对子 Agent；只在问题需要时启用语义复核；确定性业务服务负责金额、匹配、字段继承、幂等和最终合法 JSON。当前官方 subagents 与 stateful router 教程都支持这种组合。

建议在后续实现细化时补充：

1. **角色与工具按需启用。** 不是每种格式一个模型 Agent；简单结构化材料可由解析/校验工具直接完成，复杂语义才委派。当前少量稳定角色优先各自作为显式高层工具，例如提取、核对和按需语义复核，便于各自定义输入/输出契约与派发条件，不先增加通用角色发现层。主控工具描述需清楚列明子任务适用条件与返回契约。
2. **用结构化 revision 上下文代替单一句子。** 所有子提案标明输入版本和证据引用；人工纠错后旧提案不能直接复用。主控看到精简结果，完整证据独立持久化。
3. **主体门禁采用同一主控的状态约束。** 可借鉴 handoffs 的 current_step 和 requires，不增加角色接管；调用前和业务执行前都检查必需信息。
4. **区分两种异步。** 官方 subagents 页的“async”指主控派后台任务后继续；不是 Python async/await。账单核对依赖提取结果，worker 内可 await；独立附件可有界并行，不能提前报告整个账单完成。[官方说明](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents#sync-vs-async)
5. **教程 API 以项目锁定版本验证。** 新教程出现 stream_events(version="v3")；本项目不因文档有示例就默认现有便携依赖已支持。前端 SSE 可使用独立业务事件契约；先核对锁定的 LangChain API，再选择适配。
6. **继续保留人工/发布和真实集成边界。** 子 Agent 的 HITL 显式配置，顶层持久化与恢复另测；Qwen 全部调用仍实际传 enable_thinking=false。示例 stub、字符串“成功”和 InMemorySaver 均不作为业务实现或在线验证依据。

本轮结论是对设计依据的交叉核对，不是实现验收；没有证明 OCR、GaussDB、模型调用或重启恢复已通过。

