# 开发插件与 MCP 状态

核验日期：2026-10-21。这里记录开发机状态，不是交付程序的运行依赖。

当前开发任务统一见 [最终开发计划](superpowers/plans/2026-10-21-final-development-plan.md)，文档核对结论见 [文档导航](README.md)。本页原有修复/探针均保留其发生时的范围，不代表本次全部重跑。

## 配置与修复

用户级配置位于 `C:/Users/dzx/.codex/config.toml`。本次修改前已备份到同目录的 `config.toml.before-mcp-20261021-002336.bak`；语义比较确认只修改 `mcp_servers`，其他配置未变。

14 个显式配置插件均为启用：browser、unified-computer-use、chrome、computer-use、visualize、documents、pdf、spreadsheets、presentations、template-creator、github、product-design、openai-developers、stop-that-shit。缓存目录中的旧包不等于当前安装注册，未将旧缓存擅自重新注册。部分插件只提供 Skills，不应预期每个都有独立 MCP namespace。

| 手动 MCP | 当前配置 | 验证 |
| --- | --- | --- |
| node_repl | 保留原本的本机运行时 | 当前原生工具表可见 |
| langchain-docs | `https://docs.langchain.com/mcp` | 重启后 3 个工具已原生暴露；文档搜索与正文读取实际调用成功 |
| langchain-reference | `https://reference.langchain.com/mcp` | 重启后 2 个工具已原生暴露；Python API 搜索与符号详情实际调用成功 |

原 `langchain-docs` 配置为 `npx -y @langchain/mcp-docs`，npm registry 查询返回 E404；已替换成官方 HTTP 地址，并补充互补的 API reference MCP。三项均未配置工具白名单或黑名单。

官方配置来源：[LangChain use-these-docs 源码](https://github.com/langchain-ai/docs/blob/274fcd26537b0c1440600b4bb3ecce896aaac5d3/src/use-these-docs.mdx)。Codex 与 CLI 共享配置的说明：[OpenAI Codex MCP](https://developers.openai.com/codex/mcp/)。

## 当前会话工具与边界

GitHub、Node REPL、code-review、Codex 应用工具以及浏览器/计算机控制入口已由宿主提供。本次重启后还可见 Artifact Session，用于表格、演示文稿和绑定画布的操作；这里只确认其工具已暴露，没有为测试创建无关产物。文档、PDF、表格、可视化等 Skills 已列入会话技能目录，使用前读取对应 SKILL.md。

修复配置后、重启之前，原生工具表未刷新。用户重启后，本次检查确认 `ALL_TOOLS` 已包含 `mcp__langchain_docs` 和 `mcp__langchain_reference` 的全部 5 个工具。

2026-10-21 已通过宿主提供的原生 MCP 工具完成以下验证，均返回成功：

- 文档搜索：检索 LangChain `create_agent`、middleware 与 human-in-the-loop，返回官方文档内容与链接。
- 正文读取：根据搜索发现的真实路径，读取 `/oss/python/langchain/human-in-the-loop.mdx` 前 30 行。
- API 搜索：Python `create_agent` 返回匹配符号。
- 符号详情：`package=langchain, symbol=create_agent, language=python` 返回函数签名与参数说明。

后续每一个智能体相关操作实施前，均须按下节通过这两个 MCP 查阅 LangChain 文档与 API，必要时通过 GitHub MCP 核对固定提交源码。`submit_feedback` 仅确认已暴露，没有发送反馈。

返回的工具名：

- langchain-docs：`search_docs_by_lang_chain`、`query_docs_filesystem_docs_by_lang_chain`、`submit_feedback`。
- langchain-reference：`search_api`、`get_symbol`。

工具可见不等于授权发送反馈或执行外部写入。当前研究使用只读源码和文档查询。

## 开发强制纪律

本节记录用户 2026-10-21 的最新明确要求，约束开发 Agent 的实施过程；项目需求正文仍以 `AGENT.md` 为准。开始工作或恢复上下文时，先完整读取当前 `AGENT.md`，再核实相关工具、Skill 和项目实际状态。

1. **每一个智能体相关操作都先查 Docs 与 API MCP。** 创建或配置 Agent、规划与重规划、Skill 发现/加载/执行/刷新、MCP 发现/调用/热更新、子 Agent 委派、HITL、Hook 装配/拦截、暂停/恢复/检查点、预算/重试/并发、反馈/评测/改进等，实施前均先用 LangChain Docs MCP 核对用法，再用 API Reference MCP 核对符号、签名、参数及所属包。该要求逐操作适用，不能用项目开始时的一次查询或工具已连接代替。既有证据只在逐项确认版本与场景仍适用后复用；版本、配置或调用路径改变时重新核对。非 LangChain 库与构建工具查其官方资料。
2. **记录适用版本、原生组合和验证结果。** 在相应研究或实现记录中保存核验日期、操作与问题、实际安装版本及所查 API 的适用版本、Docs/API 来源、采用的官方组件及组合顺序、必要薄适配与现成组件缺口，以及实际验证和未验证项。需要源码时记录固定 commit。未安装、仅查文档、离线验证和真实集成分别陈述，不把 API 当前存在写成项目版本已兼容。MCP 暂不可用时先排查并记录具体缺口，推进独立工作；网页或记忆不能冒充已经完成 MCP 核查。
3. **铁律：只有查证官方缺少该项具体能力才允许自写。** 所有智能体相关代码、脚本与Hook，决定自写/编写/修改/运行前都先查询LangChain MCP，确认现成工具、middleware、官方集成、子Agent、中断、检查点和服务协议是否已覆盖职责；能直接配置或组合时必须复用。业务Skill脚本、薄适配、共享计量和反馈循环不豁免。记录官方入口/版本、不能满足的具体职责及最小补充范围；未安装、没搜到或一次运行失败不是官方能力缺失证据。普通环境准备、纯构建/打包不要求LangChain提供，但其中的Agent逻辑仍适用。不得先自写Plan、DAG、runner、Skill/Hook引擎再补引用。完整边界见`AGENT.md` §3.5。
4. **代码编写和运行前必须读取并应用 `stop-that-shit`。** 包括新增/修改代码、脚本、安装与构建操作，以及运行项目、测试或验证代码；主控与承担相关工作的子 Agent 均遵守。按实际任务应用其范围与直接解决问题的指导。Skill 是建议性指令，不等于 Guard 已安装或生效；没有宿主确认的安装、明确武装模式及真实拒绝事件，不得宣称动作已被 Guard 拦截，更不能编造 Guard 状态或拦截记录。
5. **前端工作必须读取并应用 `design` Skill。** 前端设计、页面/组件实现和交互修改前，先读取当前会话提供的 `design/SKILL.md` 并按任务应用；Vue、构建工具与官方 Agent SDK 的版本核对仍须分别完成。不能把 Skill 可见、设计建议或设计稿存在说成页面已经实现和联调通过。
6. **交付运行不依赖 Codex 插件。** Docs/API MCP、开发 Skills 和其他 Codex 插件用于开发查证；业务程序依赖在项目中显式声明、锁定并按便携交付约定打包。业务 Skill 的资源和脚本由交付程序自身可用的工具/backend 执行；Hook 由宿主显式装配到实际调用路径。迁移平台时核实这些执行与 Hook 桥接条件，不能仅复制 Skill 目录就宣称原宿主的拦截、审批及共享预算自动迁移。

## Middleware 查证记录与覆盖边界

2026-10-21 本轮文档修改前，已通过 Docs MCP 读取官方 custom middleware 正文，并通过 API Reference MCP 查询 `langchain.agents.middleware.types.AgentMiddleware.wrap_tool_call`。Docs 区分 `before_agent`、`before_model`、`after_model`、`after_agent` 等节点 Hook 与 `wrap_model_call`、`wrap_tool_call` 包装 Hook；API 明确 `wrap_tool_call(request, handler)` 包装工具执行，前面的 middleware 是外层，handler 可被重试调用。API 返回源码固定到 LangChain commit `84ba23c414eca6bf6f6ebd1394a3006378113540`；这属于查询证据，不代替当前安装版本和实际装配验证。

Hook 覆盖范围须沿真实入口核实：工具 wrapper 不自动拦截工具内部脚本的每个函数、网络请求、SQL、子进程或外部 Agent 动作；人工编辑/导出等领域 API 直接调用也需显式接入对应校验。Skill 脚本、动态 resolver、子 Agent 和重试是否经过同一策略，以实际原生组合和验证结果为准。不得以提示词、日志或读取 Skill 证明执行已被拦截。

官方依据：[Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)、[AgentMiddleware.wrap_tool_call](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware/wrap_tool_call)。Skill 执行与工具/backend 边界另见 [Skills](https://docs.langchain.com/oss/python/deepagents/skills) 及本项目 `docs/research/langchain-native-runtime.md`。

本轮只更新本文并进行内容核对；未安装依赖、运行项目或验证 Guard，也不新增 Hook 已实现的声明。

## 最终计划核对补充（2026-10-21）

本次继续通过Docs MCP读取Skills正文，并通过API MCP读取 `SkillsState`、`HumanInTheLoopMiddleware`，结合固定SDK源码核对结果，确认以下开发门槛；没有调用在线业务服务或安装依赖：

- Skills工具披露要求 `deepagents>=0.7.22`；本方案的pin另要求 `>=0.7.23`。include_tools为空格分隔字符串；pin须验证实际内容、未知/不可读项跳过和输入键消费行为。消费不删除历史内容；元数据重置在run之间或after_agent进行，下次run重载，不在运行中途重载。
- HITL的per_call多项回答中，一项无效时其他工具可能已执行。逐项验证/提交，失败后核对中断状态和回执，不能整批重发，也不能以pending证明未执行。恢复可重放其外层middleware，handler前不能放不可重复副作用；审批在retry外层，真实派发计量在其内侧。
- Vue官方adapter与Python Agent Server均存在v2 commands/stream/events合同，支持优先配套使用；本地CLI/API/inmem runtime、Vue/协议包、LangGraph、Windows便携与FastAPI共存仍须T04真实联调，不能把研究版本视为已验证组合。
- T01–T06优先完成依赖、标准样本、模型关闭思考、官方协议、数据库认证、OCR文件URL/真实响应；依赖可导入和端口可达均不足以完成业务验收。

来源：官方 [Skills（含Add tools、Reload与Pin）](https://docs.langchain.com/oss/python/deepagents/skills)、[SkillsState](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsState)、[HITL API（interrupt_mode的Answering several calls at once警示）](https://reference.langchain.com/python/langchain/agents/middleware/human_in_the_loop/HumanInTheLoopMiddleware)。Server/Vue固定源码和协议入口见 [langchain-native-vue.md](research/langchain-native-vue.md)，实际本地组合状态以后续任务记录为准。
