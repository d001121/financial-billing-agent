# 实现的官方依据与最小缺口

2026-10-21。先调用 LangChain Docs/API MCP，再核对安装包与实际行为。完整历史符号依据见 langchain-native-runtime.md、langchain-native-agents.md、langchain-hitl-crosscheck.md 以及 ../ui-design.md。

| 操作 | 官方入口 | 实际组合与最小补充 |
| --- | --- | --- |
| 主控与计划 | create_agent、TodoListMiddleware | langchain1.4.6，真实模型与todos完成；补目标提示和材料引用 |
| 专家 | create_deep_agent、SubAgentMiddleware/CompiledSubAgent | deepagents0.7.29，真实委派；补角色配置与显式策略 |
| Skill | SkillsMiddleware、pinned_skills、FilesystemMiddleware | StateBackend播种固定资源；真实read_file后调用包内函数；补内容hash与发布目录 |
| 包内执行 | SkillsMiddleware(tools=...)、LangChain tool | 原生handler执行普通函数，独立CLI验证；领域算法只在Skill |
| MCP | MCPAdapter、ToolCallRequest.override | FastMCP stdio发现并计算19+23=42，禁用后第二次派发被阻；补配置身份和resolver |
| 审批与重试 | HumanInTheLoopMiddleware、ToolRetryMiddleware | resolver→HITL→retry→实际检查/计量→handler；暂停阻止内部重试 |
| 模型 | ChatOpenAI、ModelRetryMiddleware、call-limit | SDK max_retries=0，真实HTTP计量并关闭思考；补跨父子/隐藏请求共享额度 |
| 检查点 | Server custom-checkpointer、AsyncSqliteSaver | checkpoint-sqlite3.1.2；58项基础conformance、重开HITL与整Server重启；只装配生命周期 |
| 改进 | LangSmith evaluate(upload_results=False) | langsmith0.14.11服务端实测合成例；补主体映射候选/审核/回滚与用途记录 |
| 配置 | 原生Skill metadata、tool schema、MCPConfig | Pydantic与原生校验；应用文件锁/CAS/原子替换不复制Agent机制 |
| 迁移 | 原生资源与应用文件存储职责核对 | 相对storage_path和旧路径受限兼容；只补通用定位 |

恢复操作读取的 Docs 路径为 /langsmith/custom-checkpointer.mdx、/langsmith/configure-checkpointer.mdx、/oss/python/langgraph/interrupts.mdx，API 符号为 langgraph.checkpoint.sqlite.AsyncSqliteSaver、langgraph.Command。按官方 async contextmanager 配置，并先跑 conformance。checkpointer用文件路径、graph用模块路径，适用当前Server0.16.2。

题目的费用映射、税折扣角色、四级匹配、明确更新语义、调用方主体和私有OCR协议不是通用框架算法；逐项loader/tool/validation查证后只补入业务Skill。领域合同与缺口依据见各包references/及本目录的官方能力查证记录；document-intake另有references/framework-reuse.md。循环、middleware、持久状态和协议继续交给框架。

当前没有启用本机shell execute；StateBackend负责可读资源，普通包函数通过官方工具执行，没有通用脚本runner。Codex插件和文档MCP只辅助开发，不是应用运行前提。

## OBS 与题面结构化响应补充

2026-10-21：先经LangChain Docs/API MCP核对loader和AgentMiddleware边界，再核对官方固定源码。`OBSFileLoader` 存在，其 `downloadFile → UnstructuredFileLoader.load` 不负责本地上传和签名；document-intake 1.1.0直接组合 `esdk-obs-python==3.26.6` 的 `putFile/createSignedUrl/close`，没有自写签名或改变ACL。SDK传入certifi CA路径、max_retry_count=0，临派发签名有效期3600秒。固定源码与具体参数在Skill的 `references/framework-reuse.md`。

原生工具middleware只包围工具handler，SDK内部HTTP不会自动独立生成工具事件。宿主在上传及OCR实际派发前注入原有policy检查暂停、revision、Skill启停与必需Hook；不声称每个SDK内部HEAD/HTTP都独立拦截或计入工具数。凭证留在宿主环境闭包，不成为模型工具参数、任务或能力配置。旧快照不注入新增参数。

真实OCR返回 `success/data.list`，并非约定的全文字符串。官方 `JSONLoader(text_content=False)` 已能通用JSON投影，固定 `_get_text` 直接调用标准库 `json.dumps`。本包也直接序列化原键值，仅补题面success、单据边界与来源/覆盖业务合同，不另建通用JSON加载层。GitHub MCP在本轮读取该文件时OAuth刷新失败；同一固定提交随后从官方raw域名读取200，未把MCP检索未命中视为能力不存在。

结构化块保存 `/data/list/<index>` 和原始响应引用；服务 `page_index/pages_split` 语义未核实，仅原样保留，不生成页内坐标。证据页码只来自单页传输映射。字段缺失继续交财务校验和人工介入。每次接入产生独立UUID产物目录，失败重试或新任务不会覆盖历史OCR响应；缓存身份含响应格式、pointer、endpoint与非秘密OBS配置。


## 前后端目录整理依据

2026-10-21：本轮先由 Docs MCP 读取 `/langsmith/monorepo-support` 和 `/langsmith/cli`。官方建议将 `langgraph.json`、`.env` 与依赖放在具体 Agent 工程内，并支持相对依赖和配置路径。本项目据此将后端资源集中到 `backend/`，保留 `backend` Python 包名，源码置于 `backend/src/backend/`；根启动入口转调后端并固定 cwd，Vue dist 仍由同级 `frontend/` 提供。此项仅调整应用文件位置与现有路径装配，不增加 Agent runner 或 Skill 执行机制。

Reference MCP 同步核对 `langgraph_sdk._async.threads.ThreadsClient.get_state`（项目SDK 0.4.8、Server API 0.16.2）：通过原生只读状态接口比较历史 checkpoint、消息与原中断；不创建 run 或代答中断。已发布 Skill 内容与历史业务 revision 原样保留。本次新布局工作区回归已通过161项（30.93秒），运行时、依赖与服务检查通过，三任务状态保留，见[验收记录](../acceptance.md)；新结构完整候选ZIP迁移已通过161项回归（61.19秒），证据见[新结构迁移报告](../../backend/tests/reports/app-portability-structure.json)；标准名交付包已收录本轮文档和报告，旧OBS包报告保留原版本身份。


## 后端职责重构依据（2026-10-21）

本节只追加本轮依据；上方前后端目录整理记录及其路径、测试数、ZIP哈希继续保留原验收版本身份。本轮按用户批准的设计，使`backend/`目录直接成为Python包，按agents/middleware/tools/hooks/mcp/extensions/harness/api/infrastructure/config分责；七个业务Skill不改写，交付包制作与迁移按用户最新要求暂停。

| 本轮操作 | 已通过MCP核对的官方能力 | 实际复用与边界 |
| --- | --- | --- |
| 后端包与服务路径 | Docs `/langsmith/monorepo-support` 的Agent目录、相对dependencies与配置；`/langsmith/custom-checkpointer` 的checkpointer.path | `backend/langgraph.json`保留`dependencies=["."]`；graph入口`backend.agents:make_graph`、HTTP入口`backend.api:app`，现成AsyncSqliteSaver生命周期移至`./infrastructure/checkpoints.py:checkpointer` |
| 角色拆分 | Reference `create_agent`、`create_deep_agent`、`SubAgentMiddleware` | 主控、文档专家、账单专家分别放在agents子目录，工厂组合原有官方循环和委派；不自建执行框架 |
| 工具与调用边界 | Reference `MCPAdapter`及既有ToolCallRequest/handler、HITL、retry组合查证 | MCP连接与命名适配归mcp，原生middleware装配归middleware，宿主工具绑定归tools，共享派发/预算/计时归harness；resolver→HITL→retry→实际检查/计量→handler组合继续复用 |
| 历史状态核对 | Docs挂载的Agent Server OpenAPI：`GET /threads/{thread_id}/state?subgraphs=true` | 使用官方SDK/状态接口比较原checkpoint、messages、interrupts，不创建run或回答中断；SDK Reference搜索可定位RunsClient.create，部分get_symbol未命中时以官方OpenAPI核实请求合同，未将索引缺失视为能力不存在 |
| 角色提示词资源 | `create_agent(system_prompt=...)`、`create_deep_agent(system_prompt=...)`等原有参数 | `config/prompts.py`的prompt_file仅读取项目内受信本地资源；配置读取时解析正文，能力快照冻结解析结果，不增加提示词执行器或运行时动态读取业务材料的权限 |

本轮仍使用LangChain 1.4.6、Deep Agents 0.7.29、LangGraph SDK 0.4.8与Agent Server API 0.16.2。业务算法唯一保留在Skill；Hook注册与触发、配置事务、能力快照和基础设施只按职责迁移，没有新增Agent loop、Skill runner、SSE协议或自研检查点实现。

全量回归为**163 passed、43 warnings、4 subtests passed（68.90秒）**，随后prompt_file非法形状修复的配置/事务/主控定向回归为**40 passed（28.73秒）**，两批重叠，不相加为203项。证据为[全量输出](../../backend/tests/reports/responsibility-tests.txt)与[配置定向输出](../../backend/tests/reports/responsibility-configuration-tests.txt)。项目外运行时、原生扩展、OBS离线签名和pip check通过，见[运行时报告](../../backend/tests/reports/responsibility-runtime.json)。

最终官方服务`/ok`、`/api/health`、`/app/`、`/api/samples`全部200。三个历史任务保持checkpoint、19/9/17条消息、原interrupt、revision 1及control；旧EML原件仍1,479,995字节且哈希不变，批准导出200、两条CREATE/AP、数字金额20/50，OBS待补充导出422、0条正式records。1166个skills/releases文件及.env哈希不变，没有新task、revision或run，没有resume，也没有调用在线模型或OCR。原GET导出核验会更新last_export和审计回执，这一原有行为已由[状态报告](../../backend/tests/reports/responsibility-after.json)的`export_get_metadata_updated=true`明确记录；最终`passed=true`。本轮没有重包ZIP，不把旧迁移结果作为当前结构的交付验收。
