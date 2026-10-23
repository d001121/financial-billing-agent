# 航账 Harbor · 航运智能账单助手

从邮件、账单和附件提取费用，结合已有账单生成 CREATE / UPDATE / NO_CHANGE / PENDING_REVIEW 建议；保留来源证据，支持人工修订、审批与 JSON 导出。

采用 LangChain 主控、Deep Agents 文档专家和 Vue 工作台。项目内附 Windows x64 便携 Python 环境 bishi1，运行不需要 conda、系统 Python、Node.js 或 Codex 插件。

## 快速启动

1. 确认backend/.env 中已有服务配置，并启动该配置指定的本机 Redis。
2. 双击 **start.cmd**，等待 Agent Server 启动完成。
3. 打开 **http://127.0.0.1:2024/app/**。健康检查：**http://127.0.0.1:2024/api/health**。

启动入口根据自身目录定位解释器和项目。默认端口 2024，使用前确认端口空闲。当前是本机单实例开发/演示服务；本轮按职责重构后的项目外运行与历史状态核验以本轮报告为准。

## 先运行一个完整示例

上传 backend/tests/fixtures/synthetic-invoice.xlsx，记账主体填写 **Demo Trading Ltd**，已有账单填写空数组。智能体实际规划、委派、提取和核对，预期产生两条 AP / CREATE：Handling Charge 50 USD、Documentation Fee 20 USD，合计 70 USD。

在工作台查看证据和校验，批准当前版本后下载正式 JSON。已验收输出在 [examples/synthetic-bills.json](backend/examples/synthetic-bills.json)。该文件和 Excel 均为人工构造的合成数据。

可把金额 50 改成 51：系统生成新 Revision，金额与合计校验会阻止正式导出；改回正确值后重新审核。两个浏览器同时编辑时，旧 Revision 提交返回 409 并保留表单输入。

<details>
<summary>查看实际工作台截图（合成材料）</summary>

![已批准费用、原生计划、专家协作与来源证据](docs/images/workbench.png)

</details>

用户提供的原题材料已接入样本列表。`backend/.env` 已按用户确认启用 `OBS_ENABLE=true`：缺少调用方URL时，document-intake通过华为官方SDK上传原件/附件/PDF切片并生成临时签名下载地址，再调用题面OCR。原题PNG与两份PDF已验证上传、签名下载哈希一致及OCR成功；新EML任务的正文、JPG和两份PDF共4来源均ready。

OCR实际返回结构化 `data.list`，保留响应原键值和来源引用，不冒充原件逐字全文。新EML正文 `H/C $50` 的币种及收费双方未明确，智能体已原生请求补充，正式导出返回422；未批准、0条正式records。附件服务返回空chargeList不等于证明没有费用。旧的待URL任务保留原快照和中断，新能力由新任务使用。真实请求与PNG响应回放的区分见 [验收记录](docs/acceptance.md)。

## 实际架构

~~~mermaid
flowchart LR
  Vue["Vue 工作台 / 官方 useStream"] --> Server["官方 Agent Server"]
  Vue --> API["FastAPI 业务接口"]
  Server --> Main["LangChain create_agent 主控"]
  Main --> Todo["原生 Todo 计划"]
  Main --> Experts["官方 SubAgent：文档 / 账单专家"]
  Main --> Skills["官方 SkillsMiddleware / 工具绑定"]
  Experts --> Skills
  Skills --> Hooks["统一配置的十一类 Hook"]
  API --> Hooks
  Hooks --> Business["八个可移植业务 Skill"]
  Business --> OCR["指定 OCR / 格式读取库"]
  Server --> SQLite["官方 AsyncSqliteSaver"]
  API --> DB["GaussDB：业务记录 / Revision / 回执"]
  API --> Cache["Redis：解析缓存"]
~~~

主控根据材料、已有产物和校验问题调整原生 todos；最多两轮纠错。没有另建工作流 DAG、Agent runner、Skill 执行器或 SSE 服务。模型请求统一关闭思考，子 Agent、重试与实际模型 HTTP 请求共同计入任务预算。

默认预算为 24 次模型请求、64 次工具派发、1200 秒活跃时间，独立文档并发 3。超限停止新派发并显示状态；图结束和 todos 全部完成不能代替业务校验。

## 项目目录

~~~text
笔试1/
├─ backend/                      后端工程，也是 backend Python 包
│  ├─ agents/                    supervisor / document / billing 专家与工厂
│  ├─ middleware/                原生 middleware 组合与边界适配
│  ├─ tools/                     上下文、人工输入、产物与 Skill 工具绑定
│  ├─ hooks/                     十一类校验的注册与统一触发
│  ├─ mcp/                       官方 MCP 连接和发现适配
│  ├─ extensions/                能力快照与固定 Skill 版本
│  ├─ harness/                   派发、共享预算与活跃计时
│  ├─ api/                       应用装配及按职责分组的业务路由
│  ├─ infrastructure/            模型、仓储、资产与官方检查点适配
│  ├─ config/                    配置模型、校验、事务、提示词与 YAML
│  ├─ skills/                    八个可插拔业务包
│  ├─ tests/、evals/、examples/   宿主测试、评测、报告与示例
│  ├─ data/                      样本、资产、固定版本和 SQLite
│  ├─ scripts/、bishi1/           工程工具与便携 Python
│  └─ .env、langgraph.json、依赖声明与启动入口
├─ frontend/                     Vue + TypeScript + Vite
├─ docs/                         架构、验收、题面与开发依据
├─ delivery/                     既有交付产物，本轮暂不处理
├─ AGENT.md、AGENTS.md            开发约定正文与入口
└─ README.md、start.cmd           使用说明与启动入口
~~~

## 扩展、人工与改进

| 能力 | 当前实现 |
| --- | --- |
| 八个业务 Skill | document-intake、document-extraction、evidence-linking、billing-reconciliation、billing-confidence、human-review、billing-export、feedback-improvement；算法随包独立迁移 |
| 十一类 Hook | schema、coverage、evidence、amount、matching、update、posting、revision、approval、capability、budget；正式导出强制检查 |
| MCP | 内置 langchain.mcp；配置测试/发现、原生工具派发及实时禁用已验证 |
| 子 Agent 与 Skill | 配置启停与注册；新任务固定内容哈希快照，在途任务保留版本，禁用在下次实际派发检查 |
| 人工介入 | 原生 HITL、费用 set/delete/split、证据与主体修订、Revision 冲突、审批失效及重新计算 |
| 跨任务改进 | 进化库支持AI总结、编辑确认和同主体经验检索；费用映射另走固定样例评测、审核发布和回滚 |

运行中任务不会自动切换到新 Skill 指令。添加工具需同时提供有效的 Skill 与工具配置；Skill 文本不能自行获得本机 shell 权限。远端 MCP 原地修改实现的边界见扩展文档。

## 用进化库沉淀一次纠错

进化库顶部的 **使用已确认经验** 是总开关，默认开启。关闭后新任务不载入经验，已有任务再次检索也不会返回经验；草稿整理、卡片保存和单条停用仍可使用。设置刷新后保留。已进入模型上下文的参考无法撤回；重新开启时，已有任务仍只使用各自原快照中的经验，不自动加入新卡片。此开关不影响“执行规则”的费用映射。

1. 在账单详情完成核对或修改，点击 **总结这次纠错**；也可从管理员控制台的 **进化库 → 参考经验** 选择来源账单。
2. 可选填一句希望AI记住的内容，点击 **生成经验草稿**。AI生成问题、适用情况、处理建议、不适用情况和检索词；来源账单、版本和记账主体自动绑定。
3. 核对卡片，需要时点击 **修改内容**。勾选确认后点击 **确认入库，供新任务参考**。来源账单没有记账主体时只能留作草稿，补充主体后重新总结。
4. 后续同主体的新任务遇到具体疑点时，可以通过 `search_reviewed_experiences` 检索最多3条经验。卡片展示实际被哪些任务检索过；该记录不等于模型采纳，也不表示正确率提高。可随时停用，修改后须重新确认。

每次生成最多1次模型HTTP请求，无自动付费重试；同输入成功后复用，失败时显示手动重试。检索使用本地BM25，不调用模型或向量服务。经验只提供核对方法，当前材料没有的金额、币种、单号、付款方式和AR/AP仍须留空。运行中任务固定已有经验版本，不自动读取后来新增内容；停用会阻止后续检索，不能撤回已进入上下文的内容。

需要改变费用标准名等确定性执行行为时，使用 **执行规则** 页签，继续经过既有评测与审核发布。参考经验不会自动修改财务规则或模型权重。

## 验证与开发

2026-10-23进化库源码已完成，小范围离线检查 **27 passed**，Vue类型检查及生产构建通过，合成界面验证草稿、确认入库、停用及原有规则入口。未调用真实模型/OCR、未跑全量、未连接正式数据库验证新接口，未启动或重启正式后端。最终检查发现2024已有09:09启动的进程，本次源码尚未由它加载。操作流程、计费边界与限制见[进化库记录](docs/research/experience-library-20261023.md)。

2026-10-23第4/8项的源码修复、MCP/22个项目Skills和真实开发测量见[本轮记录](docs/research/extraction-harness-4-8-20261023.md)。最终少量离线定向检查18项通过；较早在线开发测量2/4完全匹配，修复后未重跑在线、未做独立人工金标，也未重启正式服务。按用户预算要求不再跑全量或批量真实模型测试。

原件评测入口默认离线：`.\backend\python.cmd -m backend.evals.original_extraction --case png-debit-invoice --prepare-only`。它校验原件与历史真实OCR响应哈希并回放解析；不会请求真实OCR或模型。实际模型入口必须显式使用`--online-model`并仅选一个`--case`，不得将离线结果称作在线验收。

命令均从仓库根目录执行；后端单独使用说明见 [backend/README.md](backend/README.md)，前端开发见 [frontend/README.md](frontend/README.md)。

~~~powershell
.\backend\python.cmd -m pip check
.\backend\python.cmd -m pytest -q backend/tests backend/skills

# 前端重新开发/构建时才需要 Node.js
cd frontend
npm ci
npm run build
~~~

Python 直接依赖在 `backend/requirements.txt`，完整锁文件为 `backend/requirements.lock.txt`；前端锁文件为 `frontend/package-lock.json`。所有业务 Skill 均可在宿主外通过自身 CLI 接收 JSON；具体输入/输出与依赖见各自 SKILL.md。

此前真实 Qwen、GaussDB、Redis、官方 Server 和 Vue 生产页已联调，合成 Excel 完成真实模型到人工审批、正式导出，OBS 与指定 OCR 完成原题基础接入；这些历史结果及旧目录迁移仅覆盖原验收版本。本轮职责重构全量回归 **163 passed、43 warnings、4 subtests passed（68.90秒）**；后续配置修复 **40 passed（28.73秒）**。项目外运行时与pip check通过，官方服务四HTTP全200，三个历史任务及原中断保留。证据为 `backend/tests/reports/responsibility-tests.txt`、`responsibility-configuration-tests.txt`、`responsibility-runtime.json` 和 `responsibility-after.json`。详细范围见 [验收记录](docs/acceptance.md)、[恢复说明](docs/recovery.md) 和 [性能记录](docs/performance.md)。

旧 DOC/XLS 已通过项目内 LibreOffice 实际转换；`DOC_CONVERTER` 相对后端根目录解析。Excel 公式缺缓存时重算，Word 提供绑定渲染哈希的 PDF 与内容锚点预览。验证使用明确标注的合成 OLE 文件，移机验证留待交付阶段。长 PDF / 跨页 Word 已有合成合同测试，尚不能据此声称原题长材料准确率或时延达标。最终独立真实金标评测未完成。

## 当前开发阶段

本轮按智能体职责重构后端：`backend/` 直接作为 Python 包，官方入口保持 `backend.agents:make_graph` 和 `backend.api:app`。八个业务 Skill 保留独立包结构，框架装配、工具绑定、校验、版本管理和基础设施各自归位。用户已明确先完成需求，本轮不制作或更新交付包；既有 ZIP、哈希和迁移记录继续保留历史身份。

开发前阅读 [AGENT.md](AGENT.md)，然后查看 [文档导航](docs/README.md) 与 [T01–T33 实施状态](docs/superpowers/plans/2026-10-21-final-development-plan.md)。[补充思考](docs/insights.md)说明业务依据、已实现边界及后续方向。材料仅按本次授权上传至指定 OBS 并交由 OCR 处理，未发送交付邮件、公开发布材料或执行真实财务记账。
