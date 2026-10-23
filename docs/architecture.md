# 航运智能账单助手：架构入口

当前前后端实现方案见 [implementation.md](implementation.md)，开发约定见根目录 [AGENT.md](../AGENT.md)。

2026-10-21 本轮按用户批准的目录设计实施职责重构。当前已通过163项全量回归、后续40项配置定向回归、项目外运行时与依赖检查，以及服务接口和历史状态核验，后续工作以 [最终开发计划](superpowers/plans/2026-10-21-final-development-plan.md) 为准，实际范围见 [文档导航](README.md) 与 [验收记录](acceptance.md)。用户已明确先完成需求，本轮暂不处理交付包。

2026-10-21 根据用户“尽可能复用 LangChain/Deep Agents、每步先经 LangChain MCP 查证”的新要求重写方案。原先自建 PlanService、submit_plan/revise_plan、步骤 DAG、Agent runner 和重复流式状态层的设计已被替代，后续不要据旧研究记录恢复这些实现要求。

新方案采用 LangChain create_agent 主控、官方 Todo/子 Agent/middleware、Deep Agent 文档专家、Vue 官方 SDK与本地 Agent Server。文档解析、跨页与证据、财务规则、人工修订、导出和反馈改进全部封装为可插拔业务 Skill（SKILL.md、references、scripts）；每种校验为独立 Hook，统一配置与管理。

Skill 加载与执行复用官方 SkillsMiddleware、工具绑定，以及需要时的 FilesystemMiddleware 原生 execute 和现成执行 backend；不另造Skill加载器或通用脚本runner。细则见 [skills-and-hooks.md](skills-and-hooks.md)。每个智能体操作实施前必须先查LangChain MCP，代码编写/运行必须使用stop-that-shit，前端编写必须使用design。

所有智能体相关自写脚本与Hook还须遵守 `AGENT.md` §3.5：只有经MCP查证官方缺少对应具体能力才允许补实现，目标目录不是预先授权的自写清单。普通环境/构建/打包工具与Agent能力范围分别处理。

具体前后端职责、目录、接口、长 PDF 与 Word、人工介入、MCP/Skill/Hook、恢复边界、时延及验收统一在 implementation.md 中维护。`backend/` 直接作为 Python 包；`agents/`、`middleware/`、`tools/`、`hooks/`、`mcp/`、`extensions/`、`harness/`、`api/`、`infrastructure/`、`config/` 分别承担各自职责，七个业务 Skill 保留包边界。官方入口保持 `backend.agents:make_graph` 与 `backend.api:app`。旧工作区和 ZIP 迁移结果只覆盖原版本，不是本轮结论。
