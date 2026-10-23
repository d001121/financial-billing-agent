# 航运智能账单助手：最终开发计划

> **供后续开发 Agent 使用：** 按任务执行时使用 `subagent-driven-development` 或 `executing-plans` Skill；先完整阅读根目录 [AGENT.md](../../../AGENT.md)。以下复选框记录实际完成情况，不以文档、目录或配置存在代替验收。

**目标：** 交付可在 Windows x64 解包运行的 Python/LangChain 航运智能账单助手、Vue 工作台、可移植业务 Skills、统一 Hooks、真实服务集成证据与题目要求的 JSON。

**架构：** LangChain `create_agent` 主控，显式组合官方 Todo、SubAgent、Skills、middleware；Deep Agent 作为文档专家。官方 Agent Server 管理运行与框架状态，GaussDB 保存业务事实，Vue 使用配套官方 SDK。领域能力全部归八个业务 Skill，校验按十一类 Hook 统一配置。

**技术栈：** 项目内 `backend/bishi1/` Python 3.13.16、LangChain、Deep Agents、官方 Python Agent Server/FastAPI 扩展、Vue 3/TypeScript/Vite、Qwen、指定 OCR、GaussDB、Redis；新增版本经兼容验证后锁定。

---

## 1. 计划基线与使用方式

- 版本：**1.8，2026-10-21，面向业务用户的前端页面分层**。保留无模板海外提取/v2融合及最终开发基线，逐项记录已验证范围与剩余条件；完整目标不因已有代码或合成回归而自动完成。
- 规则正文：[AGENT.md](../../../AGENT.md)；设计正文：[implementation.md](../../implementation.md)；业务包与 Hook 合同：[skills-and-hooks.md](../../skills-and-hooks.md)；文档核对结果：[文档导航](../../README.md)。本文件是后续开发的统一任务清单。
- **这是开发计划。** 产品运行时由主控使用原生 `write_todos` 动态规划；不得将下面任务编号编译成产品固定 DAG 或另建 PlanService。
- 当前已有backend、Vue、八个业务Skill、十一类Hook、官方运行服务和SQLite检查点；真实服务已跑通合成Excel的人工批准/导出及反馈候选发布/回滚，OBS与原题PDF/图片指定OCR的基础接入已验证。新EML因正文 `$50` 缺币种及收费双方而原生等待输入，正式导出422，未批准。初稿“没有业务实现、T01–T33均未完成”属于历史状态，现以§2.1的逐项状态和证据为准。
- 既有迁移与 MCP 记录见 [portable-environment.md](../../portable-environment.md)；最新验收、恢复与性能分别见 [acceptance.md](../../acceptance.md)、[recovery.md](../../recovery.md)、[performance.md](../../performance.md)，官方组合与缺口见 [实现依据](../../research/implementation-evidence.md)。复选框只归纳这些报告覆盖的范围。

每项任务开始前都执行：读取相关约定和实际状态 → 查询该项操作的 LangChain Docs/API MCP → 核对已安装版本及适用组合 → 配置/组合官方能力 → 最小验证 → 锁定与记录。只有查证官方及其集成不满足具体职责，才可补最小代码；Skill scripts、Hook、模型工厂和薄适配均受此约束。代码编写/运行使用 **stop-that-shit**，前端设计/编写同时使用 **design**。不把插件列为交付程序依赖，不虚称 Guard 已启用。

每项任务通过后勾选任务及步骤，在对应记录中留下输入版本、命令、结果和产物位置；失败保留原因及待解决条件。以下列出的目标文件是职责归属，不能据此预先批量生成空文件或批准自写实现。业务测试围绕可观察结果，避免只复述实现。

## 2. 已核实状态与开发前置条件

| 对象 | 当前事实 | 完成验证的任务 |
| --- | --- | --- |
| 便携环境 | 项目内 Windows x64 Python 与依赖保留；本轮项目外运行时、原生扩展、OBS离线签名与pip check通过，报告为responsibility-runtime.json。旧161项迁移及SDK/MCP报告仅覆盖旧版本，本轮暂不更新交付包；项目内LibreOffice已在开发机实际转换合成DOC/XLS，移机仍待验 | T01；T33当前暂停 |
| 业务依赖 | LangChain 1.4.6/core 1.6.12/OpenAI适配1.7.2、Deep Agents 0.7.29、LangGraph 1.2.16、CLI 0.4.37/API 0.16.2/runtime 0.36.2、langgraph-checkpoint-sqlite 3.1.2、esdk-obs-python 3.26.6及格式/数据库驱动已安装锁定，pip check通过 | T01及对应格式/存储任务 |
| 模型 | 指定Qwen已在真实服务任务中调用；统一工厂关闭思考，HTTP派发检查及共享调用计量有测试，不能推断所有复杂语义场景通过 | T03、T17 |
| OCR | 已获准启用OBS，原题PNG及两份PDF上传/签名下载哈希/OCR通过；data.list结构化映射ready，其中PNG映射为原真实响应回放。新EML三个附件实际自动上传/OCR完成；完整故障、长材料与财务金标仍待验 | T06、T12基础；见obs-ocr-real.json、obs-originals-ocr.json、obs-agent-task.json |
| GaussDB/Redis | 已接入业务条件存储、健康检查及OCR缓存路径；真实运行可用，完整故障/负载与跨存储一致性仍待验 | T05、T08、T30 |
| Vue/官方协议 | Vue 3.5.44、SDK 1.2.5、Vite 8.3.4已锁定；已有人工批准/导出与反馈发布/回滚历史证据。新版总览/大屏/业务/待办/提交/详情/管理页面已实现；最终构建2408 modules、Vite 1.71秒。浏览器主要路径、390×844、菜单及API临时阻断/恢复通过，完整矩阵仍待验，见user-workspace-ui.json | T04、T07、T29 |
| 本地样本 | 四份原件、EML内三个附件出现位置已清点，manifest有来源/哈希；原题financial_ground_truth仍为null，材料已参与开发 | T02、T11；见sample-inventory.md |
| 补充样本 | 合成Excel/DOCX/TIFF、匹配/更新、覆盖及故障样例用于回归；合成二进制OLE DOC/XLS已补齐；真实业务Office/长PDF和独立真实金标仍缺，不能用合成测试代验 | T02、T18–T23、T32 |

本轮按用户批准的设计重构后端职责：`backend/` 直接作为 Python 包，`agents/middleware/tools/hooks/mcp/extensions/harness/api/infrastructure/config` 分别归位，八个业务 Skill 保持包边界。官方入口保持 `backend.agents:make_graph` 与 `backend.api:app`。用户已明确先完成需求，本轮交付制作、更新和迁移暂缓。本轮全量163项回归通过（43 warnings、4 subtests、68.90秒），后续配置修复40项定向通过（28.73秒）；项目外运行时与pip check通过，四HTTP全200及三个历史任务状态保留。报告为 `backend/tests/reports/responsibility-tests.txt`、`responsibility-configuration-tests.txt`、`responsibility-runtime.json` 和 `responsibility-after.json`；下方旧报告仅保留原验收版本身份。

### 2.1 T01–T33 实施验收状态

状态只描述表中证据覆盖的范围。“部分”包含已有代码或部分通过，但任务的组合完成条件仍未全部满足；未勾步骤继续作为剩余要求，不因实现存在而自动勾选。目录调整前的工作目录完整回归为 **161 passed，43 warnings，4 subtests passed，28.81秒**，报告在 `backend/tests/reports/pytest.txt`、`pytest.xml`；OBS候选包迁移回归为 **161 passed，43 warnings，4 subtests passed，41.16秒**，报告在 `backend/tests/reports/app-portability-obs.json`、`app-portability-obs-tests.txt`。subtests单列，SQLite 58个必需基础conformance作为其中1项测试执行，不另相加。此前140等历史批次和旧迁移报告不改写为本轮结果，完整口径见 [acceptance.md](../../acceptance.md)。

| 任务 | 状态 | 已有证据与剩余项 |
| --- | --- | --- |
| T01 官方组合/依赖 | 已实现且验证 | 原生Agent/Skill/Server已运行；requirements及前端锁文件固定项目版本；后续升级仍需重验组合 |
| T02 样本/金标 | 部分 | `docs/sample-inventory.md`、`backend/evals/datasets/manifest.json`及合成回归存在；原题逐字段财务金标与独立真实最终组未完成 |
| T03 Qwen/关闭思考 | 部分 | 真实Qwen参与Excel任务；`backend/infrastructure/models.py`与`backend/tests/test_host.py`验证请求体/共享预算；全部隐藏路径与schema在线能力未逐项独立验收 |
| T04 Server/Vue | 部分 | 旧页面原生中断/恢复和重启保留历史记录；本次复核useStream/disconnect/join-rejoin且未改SDK执行。新版历史原生中断可水合且日志折叠时仍可见，测试标签API阻断后保留16项旧快照并重试恢复；未回复中断或停后端，全部订阅交错/断线组合仍待验 |
| T05 GaussDB/Redis | 部分 | 真实业务存取/健康检查及OCR缓存接入；全部连接失败、超时和事务回滚矩阵未完成 |
| T06 OCR URL/响应 | 基础合同已验证 | OBS官方SDK上传/3600秒GET签名、下载哈希与原题PDF/PNG真实OCR通过；确认success/data.list原键值映射及来源精度，完整过期/在途/服务故障矩阵仍待验 |
| T07 Vue视觉/交互 | 主要路径通过，完整矩阵待验 | 总览/独立大屏/业务/待办/提交/详情/管理及子页实际打开；筛选往返、原文内容块、确认/导出提示、历史人工请求和390×844布局/菜单通过。完整键盘、长表、视口及失败状态仍待验，见user-workspace-ui.json，旧截图不代验 |
| T08 产物/revision/存储 | 部分 | `backend/infrastructure/repository.py`及host回归覆盖条件写入、并发批次和过期修订；完整副作用/跨存储故障仍待验 |
| T09 原生Skill/CLI | 部分 | host用例验证读取→披露→函数执行；`backend/tests/test_skill_cli.py`验证项目外CLI；pin全部边界、摘要后披露及另一完整宿主未全验 |
| T10 Hook装配 | 部分 | 十一类配置、原生retry/HITL/派发及必需Hook导出阻断有回归；全部顺序/异常组合未全验 |
| T11 来源证据 | 部分 | evidence包覆盖原文回读、版本/重复出现与定位歧义；真实OCR保留原JSON、response_pointer和传输原页/帧，page_index不当物理页；空间坐标及全部格式端到端待验 |
| T12 PDF/图片OCR | 真实基础接入已验证 | PDF/PNG及新EML的JPG/PDF实际上传与OCR完成；原响应、回执和映射保留，TIFF多帧为合成合同覆盖，全部异常与长文档在线条件仍待验 |
| T13 短材料提取 | 部分 | schema、候选与合成Excel路径运行；真实PDF/PNG已有服务费用字段，新EML正文 `$50` 候选缺币种/收费双方而进入awaiting_input；原题逐字段人工金标未完成 |
| T14 金额/标准化 | 部分 | reconciliation包的精确金额、币种、税/折扣及最小CREATE测试；真实全场景财务金标仍待验 |
| T15 JSON导出 | 已实现且验证 | export包/host测试覆盖数组、数字/null、过期/审批/必需Hook阻断；真实服务合成Excel产物见 `backend/examples/synthetic-bills.json` |
| T16 主控/专家闭环 | 部分 | 官方主控/todos/专家组合及任务 `abab67c9-2fe2-44fe-a416-6dbd92058b26` 已批准导出；专家当前保存产物引用，未直接配置设计中的每专家response_format |
| T17 共享预算 | 部分 | 实际HTTP请求计量、父子工具共享预算、禁用/暂停/重试阻断有回归；全部外部/并发/隐藏路径及计时负载未全验 |
| T18 EML/Excel | 部分 | 原题EML正文+三个附件均ready，每附件保留真实OBS/OCR回执；正文币种与收费双方不明，原生补问且正式导出422。合成Excel已导出，完整真实XLS边界与财务金标仍待验 |
| T19 DOC/DOCX | 功能已实现，合成格式验收通过 | 项目内LibreOffice已实际转换二进制DOC；DOCX正文/合并/嵌套/分页表格、渲染hash及证据锚点回归通过。真实业务金标与转换器移机另验 |
| T20 长PDF/覆盖 | 部分 | 分块拥有范围、失败保留、覆盖与逻辑单据回归；长PDF真实OCR/跨页半行在线端到端未验 |
| T21 匹配/重复 | 部分 | 同名多行、多候选、来源重复和冲突确定性测试；真实独立样本及全部组合未验 |
| T22 增量/幂等 | 部分 | 缺失/null/新值、继承、未授权差异与过期revision回归；完整未知副作用恢复矩阵未验 |
| T23 主体/AR/AP | 部分 | 主体切换、关系缺失、Credit Note/PP-CC不猜方向等回归；第三方代收代付真实金标仍待验 |
| T24 人工/审批/控制 | 部分 | 修改/拆删/证据修订、人工值保留、审批失效及原生HITL恢复；全部batched/嵌套/在途控制组合未验 |
| T25 能力热插拔 | 部分 | 新任务固定快照、配置校验/并发原子保存、stdio真实调用及在途实时禁用；当前CAS发布skills v6/0dd7d9b036a29571747e，两新增在线任务固定新版本，旧任务/中断未迁移；全部角色/远端版本回滚和另一完整宿主未验 |
| T26 十一类Hook | 部分 | 配置存在且必需项禁用/过期/校验失败真实阻断；必需集合当前为hooks中的固定REQUIRED常量，独立profile及所有异常/超时/内部请求组合未验 |
| T27 有界纠错 | 部分 | 无进展候选阻断、受影响修订重算与两轮限制已有实现/回归；真实模型两轮失败与定向修复全矩阵未验 |
| T28 跨任务改进 | 部分 | 原生本地LangSmith与UI合成集5/7→7/7、审核发布/回滚；仅主体作用域charge_mapping实际应用，rule/prompt/skill仍为草稿，独立真实最终评测未完成 |
| T29 Vue业务工作空间 | 部分 | 页面路由、列表搜索到详情再返回保留筛选、复核清筛不跳页、EUR金额到mail/body原文、100分确认入口/未审批导出禁用、日志折叠时历史中断可见、管理子页、390×844及API临时阻断恢复均已实测。未提交新任务/审批/回复；完整视口/键盘/长表/订阅与断线矩阵仍待验 |
| T30 重启/恢复 | 部分 | SQLite58项基础conformance、关闭重开HITL、整服务重启及 `backend/tests/reports/server-force-restart.json` 的无在途请求强停后稳定检查点/消息/EML中断保留；断电/在途OCR/全部未知结果未验 |
| T31 性能 | 部分 | 合成Excel单次22模型/19工具、活跃187.387秒；新EML14模型/12工具、活跃163.155237秒；PNG真实OCR12.329秒与PDF请求段31.744/45.816秒均为有限样本，无完整负载P50/P95及长材料压测 |
| T32 独立总验收 | 部分 | 已有离线/真实服务分层证据与验收矩阵；独立真实金标与全部原题/扩展外部验收未完成 |
| T33 交付迁移 | 当前暂停 | 用户已明确先完成需求，本轮不制作、更新或迁移交付包。已有README/截图/补充思考及旧ZIP迁移报告保留历史身份；恢复交付工作后须按当前职责结构重新核验，Office转换器移机及其外部链路仍未验 |

当前实现偏差须继续保持可见：无shell `execute`；专家结构化业务结果经工具产物保存和Hook校验；热更新为新任务快照与在途实时禁用，不自动迁移旧任务；反馈实际应用范围限主体作用域费用映射；必需Hook集合仍由 `backend/hooks/registry.py:REQUIRED` 固定。SQLite通过官方服务的checkpointer生命周期接入现成saver，不在Agent工厂重复注入。dev元数据仍有约10秒刷盘窗口，不能由SQLite基础测试推断跨存储硬崩溃零丢失。

外部条件处理原则：先从题面、现有配置和本机能力自行核实，不再次索取已有密钥。用户已授权OBS自动上传和OCR，直接使用现有.env配置，不再询问是否启用或是否已有文件服务；不得把本地路径提交OCR或超出授权公开发布材料。指定模型无权限或平台组合确实不支持时，提交实际错误和最小替代建议，取得相应选择后再改变方案；独立任务继续推进，模拟响应与真实响应回放均须标明，不能替代新的在线集成证据。

## 3. 文件归属

### 本次前端页面重构（T04、T07、T29）

- [x] 使用design与stop-that-shit change，按业务用户路径实现工作总览、独立大屏、账单业务中心、待办复核、独立材料提交页、账单详情和管理中心/能力/经验子页。
- [x] Hash导航可表达页面与状态筛选；KeepAlive按业务中心/待办key缓存同次页面会话内的搜索、主体、排序和分页，整页刷新不承诺恢复局部输入。
- [x] 默认轮询摘要与health，进入详情才读task和资产；列表摘要不覆盖完整费用/来源，详情异步结果按任务和Revision匹配。
- [x] 详情保留官方AgentPanel挂载，中断表单独立显示，计划/工具/专家日志按需展开；当前Revision审批前置提示与后端导出完整校验分别保留。
- [x] 类型检查和Vite生产构建已通过，未新增Agent执行器、SSE状态机或财务计算副本；SDK保持已锁定版本。
- [x] 新版浏览器主要路径验收：总览/大屏/业务/待办/提交/详情/管理及子页、列表详情往返保留筛选、复核清筛不跳页、EUR金额到邮件内容块、确认/导出提示、日志折叠时历史人工请求、390×844与移动菜单，以及测试标签API阻断后的旧快照保留和重试恢复通过；见[原始报告](../../../backend/tests/reports/user-workspace-ui.json)。未审批或回复，未关闭后端；全部空态/失败/视口/键盘/长表与订阅交错矩阵仍待验，历史截图不代验。

### 本轮补充范围（用户项目项3、4、8）

当前skills配置v6：intake1.2.0、extraction1.3.0、evidence1.2.0、reconciliation1.1.0、confidence2.0.0，能力快照0dd7d9b036a29571747e。最终回归353 passed、43 warnings、4 subtests passed（220.45秒），报告为global-confidence-pytest.txt/XML。前端类型检查、构建与v1/v2 SSR通过；真实Qwen/浏览器结果另见acceptance，不替代独立真实金标。v5/234项与R1确认→R2改错/60分/422→R3恢复/100分属于office-confidence历史记录。

### 无模板国际业务优化（v2）

- [x] 经Docs/API MCP确认原生schema、Skills和评估组合；只补国际数字/币种及业务支持度缺口，不新增Agent运行时或依赖。
- [x] 保留raw值、无模板字段作用域、多语言费用名、数字/位置歧义与原文候选；格式解释唯一归evidence包。
- [x] 金额/币种/费用名无支持或歧义进入统一Hook，真实批准/导出接口422；普通词不依模型候选冒充ISO币种。
- [x] 三组融合70/20/10；相关算术/总额取max，复制来源不加分；规范折扣只消费同revision财务事实。
- [x] 前端兼容旧结果，展示核验状态、缺依据原因及原文候选；类型检查/构建/SSR通过。
- [x] 9例确定性合成差分与353项全量回归留档；CAS发布v6，历史任务不迁移。
- [x] v6真实Qwen功能回归：欧洲1234.56/65.44 EUR、CREATE/AP及100分；裸$1,234保持null/PENDING_REVIEW及24分，实际批准/正式导出422。两run success，未自动审批；活跃365.668/325.139秒，不算时延达标。
- [x] 浏览器v2分组说明、块级原文定位及低分复核展示；全14个旧任务及2146个旧发布文件哈希未变，证据见global-confidence系列报告。
- [ ] 独立真实全球材料金标、语种/账单家族分层、阈值校准及高分错误率测量。已有合成/在线功能验收不代替此项。

- [x] Excel/Word现代与旧格式接入、公式重算、原结构锚点及Word派生PDF由document-intake提供；合成OLE及Office格式回归通过，移机留待恢复交付工作。
- [x] 新增独立billing-confidence Skill，复用实时证据/金额/覆盖结果输出分值与扣分，缺总额引用不强制全单审批；明确引用矛盾与其他硬错误继续阻断批准。
- [x] 提供任务绑定的原生工具、只读confidence API、来源preview API，固定任务能力版本，不向历史任务静默注入新规则。
- [x] Vue展示费用及字段分、低分原因、Excel单元格与Word版式/结构原文定位、修订入口及显式确认当前版本；使用真实后端审批/版本合同。
- [x] 完成当前v5的新在线样例及浏览器修改/确认验收：DOC/XLSX各两条CREATE/AP、50/20 USD、100分及校验通过；固定答案UI完成确认→改错/422→改回→重新确认R3。结果写入acceptance及online/ui-final报告；旧版失败仍保留，不代表独立真实金标、长材料负载或全项目验收完成。
- [x] 长材料优化按优先级写入performance、implementation与insights，明确逐块缓存、有界读取、token容量、全局背压、首结果发布等待实现项，不宣称已提速。

这组补充不改变原T01–T33的全量独立金标、故障和交付验收条件。

完整目标树以 [implementation.md §12](../../implementation.md) 为准。任务中的路径均相对项目根目录。

| 位置 | 责任 |
| --- | --- |
| `backend/agents/` | factory与supervisor/document/billing角色组合；各角色agent.py与prompt.md |
| `backend/middleware/` | 官方middleware组合、Skill资源、MCP披露、派发与结果边界 |
| `backend/tools/` | 上下文/人工输入、产物保存和官方Skill工具绑定；领域算法仍归Skill |
| `backend/hooks/registry.py`、`validation.py`、`guards.py` | 校验注册与统一触发；领域算法只在所属Skill保留一份 |
| `backend/mcp/`、`backend/extensions/`、`backend/harness/` | 官方MCP连接/命名、能力/Skill版本、共享派发/预算/计时 |
| `backend/api/` | FastAPI装配、共享HTTP辅助及按职责分组路由 |
| `backend/infrastructure/` | 模型、事务仓储、资产和官方检查点适配 |
| `backend/config/` | 配置schema/校验/事务/提示词解析和agents/mcp/skills/hooks/runtime YAML |
| `backend/skills/<业务包>/{SKILL.md,references/,scripts/}` | 必要领域实现与独立入口；schema/映射按需放包内assets，包内测试随包迁移 |
| `frontend/src/{pages,components,composables,utils,api,styles,types}/` | 页面分层、账单交互、摘要展示、官方SDK与服务端契约，不复制财务规则 |
| `backend/tests/`、`backend/evals/` | 运行集成、跨包行为、固定样例、候选比较和独立评测 |
| `backend/data/`、`backend/.langgraph_api/` | 原件/派生件/业务文件与官方服务生成数据 |
| `backend/scripts/` | 环境、启动、测量与既有交付工具；本轮交付工作暂缓 |

## 4. 逐项开发任务

### T01：确定官方复用组合与新增依赖

**依赖：** 无。**交付位置：** `backend/requirements.txt`、`backend/requirements.lock.txt`、`docs/portable-environment.md`、`docs/development-tools.md`。

- [x] 按职责核对 `create_agent`、Todo、SubAgent/CompiledSubAgent、Skills、Filesystem、摘要、HITL、retry/call-limit、MCP 与 Agent Server 的 Docs/API；必要时用 GitHub MCP 固定源码和测试。
- [x] 选择满足整套组合的稳定发行版本，不盲目升级。Skill tools 需 `deepagents>=0.7.22`，本方案使用 `pinned_skills`，因此候选组合至少满足 **`deepagents>=0.7.23`**；当前安装0.7.29，最低版本不代替全组合验收。
- [x] 经 `./backend/python.cmd -m pip ...` 补充当前切片实际需要的依赖，并保留 `pip check`/安装与迁移记录。官方完整循环和协议未因可选依赖缺失而重写；新增依赖仍须重锁并检查。
- [x] 记录实际安装版本、所查入口、采用组合、最小验证与具体缺口；版本来源为当前requirements/前端锁文件，运行证据见验收记录。

**完成条件：** 原生组件可在便携解释器导入，依赖检查通过；明确待T04运行验证的 Server/Vue组合，没有“网页API存在即本地可用”的声明。

### T02：建立样本清单、标准答案与验收基线

**依赖：** 无，可与T01并行。**交付位置：** `backend/evals/datasets/`、`backend/evals/datasets/manifest.json`、`backend/tests/fixtures/`、`docs/acceptance.md`。

- [x] 盘点 `backend/data/samples/` 的原件及EML内附件，记录文件摘要、出现位置、来源关系、格式和可交付范围；内容摘要与“某封邮件内的出现位置”分别标识。
- [ ] 人工核对现有材料的单据、每条费用、金额/币种、方向及来源，建立可解释标准答案；不能只拿模型生成结果作标签。
- [ ] 补齐 Excel/Word/TIFF、已有账单、更新指令、重复/冲突/同名多行、长PDF跨页与故障样例。可构造有明确答案的测试材料，标记为合成，不能冒充原题真实样本。
- [ ] 按单据家族及近重复附件划分开发/反馈、候选选择回归、最终独立评测三组；记录标签来源和用途，最终组不参与本轮提示词与候选选择。
- [ ] 将原题10项验收与用户扩展要求映射到任务和断言。当前明确答案的关键财务场景要求精确通过；模型指标与性能口径先固定再测量，不事后改口径。

**完成条件：** 清单、答案、划分和缺口可回查；没有把“本地有文件”视为内容已正确提取。缺少某格式原题样本不阻止构造覆盖，但报告须区分真实与合成。

### T03：验证Qwen，并让全部模型请求关闭思考

**依赖：** T01。**交付位置：** `backend/config/settings.py`、`backend/agents/factory.py`、`backend/config/agents.yaml`、`backend/tests/test_model_integration.py`。

- [ ] 先查官方模型集成、`ChatOpenAI`兼容配置、工具绑定及结构化响应能力；模型名称/地址/密钥读取现有 `backend/.env`，禁止输出密钥。
- [ ] 最小真实验证普通调用、工具调用和schema输出，记录可用能力、请求标识和异常，避免凭模型名称假定视觉、窗口或严格JSON支持。
- [ ] 所有主控、子Agent、摘要、评分/优化和结构化修复请求实际携带 `extra_body={"enable_thinking": false}` 对应的Python布尔值；检查实际发往兼容接口的请求体。
- [ ] 建立统一可计量模型配置，附加内部调用也使用它；模拟断言覆盖隐藏路径，真实调用结果与离线测试分别报告。

**完成条件：** 指定账号/模型真实可调用；被采用路径的请求体关闭思考，隐藏请求无旁路。视觉不是默认依赖，不用VLM替代指定OCR。

### T04：打通官方Agent Server与Vue协议

**依赖：** T01。**交付位置：** `backend/langgraph.json`、`backend/agents/factory.py`、`backend/api/app.py`、`frontend/package.json`及锁文件、`frontend/src/components/AgentPanel.vue`、`docs/development-tools.md`。

- [x] 使用design核对本地工具链并建立最小Vue工程；通过Docs/API MCP核实 `@langchain/vue` 的 `useStream`、官方服务自定义HTTP扩展和命令/流合同。
- [x] 成套锁定CLI、`langgraph-api`、inmem runtime、LangGraph、Vue SDK及其共享协议依赖；实际运行范围与缺口见验收记录。
- [x] 用 `create_agent` 注册工具Agent，官方服务管理线程/运行/检查点，HTTP扩展使用业务前缀；启动、流状态、工具调用及原生中断/恢复已有记录。
- [ ] 验证刷新重连、先运行后订阅、正常停机再启动，以及便携Windows实际启动方式。库内部事件版本与外部协议版本分开处理。

**完成条件：** Vue原生SDK直接连接通过；注册Agent不重复注入saver，当前通过官方服务checkpointer生命周期配置现成SQLite saver；没有自写SSE协议、队列或前端Agent状态机。所有故障组合仍按状态表保留待验。

### T05：验证GaussDB、Redis及持久化职责

**依赖：** T01。**交付位置：** `backend/config/settings.py`、`backend/infrastructure/repository.py`、`backend/tests/test_storage_integration.py`、`docs/development-tools.md`。

- [x] 使用已有 `backend/.env` 验证GaussDB认证、驱动、schema访问与必要事务/条件写入；只操作本项目测试记录，不清理或修改无关表。
- [x] 查验Redis认证并用于可选intake/OCR缓存；键含原件哈希、URL/能力版本、响应格式、pointer及非秘密OBS身份，TTL为86400秒，失败回退持久原件/产物，不另建运行队列。
- [x] 明确GaussDB的业务revision/执行事实与官方Server框架状态边界；不把GaussDB当未经验证的Server内部PostgreSQL。
- [ ] 测试连接失败、超时与事务回滚并输出可定位错误，形成驱动及最小操作结果记录。

**完成条件：** 真实认证和必要数据库行为通过；Redis可用及职责有据。端口探测不代替认证或持久性验证。

### T06：落实指定OCR的文件URL与真实响应合同

**依赖：** T02，可与T03–T05并行。**交付位置：** `backend/skills/document-intake/references/intake-contract.md`、`framework-reuse.md`、`backend/tests/reports/obs-ocr-real.json`、`obs-originals-ocr.json`。

- [x] 复核题面POST、`file/task/callBack/taskType`及连接10秒/读取300秒；使用已获准的OBS发布路径，真实下载状态与原件哈希通过。
- [x] 经LangChain Docs/API MCP核对loader/工具/middleware，固定源码确认OBSFileLoader下载职责和JSONLoader通用投影；组合华为官方SDK补最小发布与题面响应合同，具体依据在包内framework-reuse.md。
- [ ] 完成获准PDF/图片的全部错误行为验证。真实PNG和两份PDF的下载、响应状态及data.list已核实并保存；page_index/pages_split不当物理页/坐标，失败合同已有回归，但完整线上故障矩阵尚未完成。
- [ ] 完成全部排队/重试/过期边界。当前原件、切片和附件临派发生成默认3600秒签名，上传回执及失败范围保留；不能据此宣称全部在途/断电组合通过。

**完成条件：** 指定OCR真实返回可处理结果，明确可用来源精度；缺少页码/坐标时不编造。此项未通过不能宣称PDF/图片真实集成完成。

### T07：确定Vue视觉与交互基线

**依赖：** T02、T04。**交付位置：** `docs/ui-design.md`、`frontend/src/styles/`、`frontend/src/pages/`、`frontend/src/components/`。

- [x] 调用design，确定深海军蓝/青绿/暖白排版、间距、颜色语义、表格密度和组件状态；日常业务与管理配置分开。
- [x] 定义并实现总览/大屏、业务/待办列表、独立提交页、账单详情、管理入口及能力/经验子页；费用与原件联动，技术日志折叠不隐藏人工请求。
- [ ] 设计加载、空态、损坏文件、服务失败、待补充、待复核、暂停中/已暂停、版本冲突和不可导出状态；键盘与窄屏仍可操作。
- [x] 用当前真实协议实现页面，记录设计决策与实际截图清单；主要路径及390×844布局见[浏览器报告](../../../backend/tests/reports/user-workspace-ui.json)，合成历史任务仍保留其样例身份。

**完成条件：** 统一tokens及关键状态可审查；费用、证据和运行状态没有三套互相冲突的展示含义。

### T08：建立通用产物、revision、回执与存储合同

**依赖：** T04、T05。**交付位置：** 当前为 `backend/infrastructure/repository.py`、`backend/api/routes/tasks.py`、`backend/tools/artifacts.py`、`backend/infrastructure/assets.py`、`backend/data/`、`backend/tests/test_host.py`；设计期的 `contracts.py`/专名测试文件未单独建立。

- [ ] 查询框架状态/存储已有能力，界定必须独立保存的业务事实；定义task/thread/run关联、不可变原件/派生件、产物引用、问题、revision、能力版本和执行回执。
- [ ] 实现期望版本条件写入、唯一键/事务和审计关联；通用宿主存不透明领域payload，领域字段schema由Skill提供。
- [ ] 区分候选、已校验、待复核、过期与正式导出；记录输入引用及版本，使失效依赖可定位。
- [ ] 验证并发写入一成功一冲突、失败回滚、原件不被覆盖、工具事实与后置Hook结果分别保存。

**完成条件：** HTTP/Agent共用通用存储；业务revision和框架checkpoint职责清楚，不用消息历史代替执行事实。

### T09：验证原生Skill发现、工具绑定与可移植入口

**依赖：** T01、T08。**交付位置：** `backend/tools/skill_bindings.py`、`backend/tools/artifacts.py`、`backend/config/agents.yaml`、首个业务Skill包、`backend/tests/test_skill_contracts.py`。

- [ ] 先查 `SkillsMiddleware`、`SkillToolResolver`、`FilesystemMiddleware`及实际backend；`sources`挂父目录，`include_tools`用空格分隔字符串。
- [ ] 选择一个T11需要的真实证据能力作首个包，使用标准frontmatter及实际引用的references/scripts；普通函数/现成工具经官方工具链执行，不写通用脚本runner。
- [ ] 补齐按需披露、pin、资源读取与工具调用的全部边界；已有读取后披露/函数执行测试，摘要后可用期、pin异常及失配名称仍需逐项核对。工具成功与业务通过分别断言。
- [ ] 验证pin精确匹配已加载元数据、未知/不可读项跳过、内容快照插入及输入键消费清空。消费不删除已插入消息，再pin会追加快照；按实际内容和工具披露判断，不只检查请求字段。
- [x] 在项目宿主外用包内入口运行相同小样例，不导入backend、hooks或开发机路径；声明服务/资源注入和依赖。shell确有需要才另验原生execute及现成隔离backend。

**完成条件：** 第一个包真实可调用、可独立运行，官方加载执行路径有证据；不为满足目录格式复制框架实现。

### T10：建立统一Hook配置及原生装配基础

**依赖：** T08、T09。**交付位置：** `backend/config/hooks.yaml`、`backend/hooks/registry.py`、`backend/hooks/validation.py`、`backend/middleware/`、`backend/tests/test_host.py`；原设计的 `backend/hooks/handlers/` 和专名测试文件未逐一建立。

- [x] 按十一类Hook查官方middleware/触发点并建立配置与结果合同；领域算法位于所属Skill，派发/重试/HITL等复用原生组件。
- [ ] 复用官方动态解析、HITL、ToolRetry、调用限制；验证wrapper外内顺序，使每次实际重试都经过派发检查，策略拒绝不触发网络重试。
- [ ] 验证顺序为固定快照resolver→HITL→ToolRetry→派发校验/实际计量→handler；恢复可能重放HITL外层middleware，handler前不得做不可重复副作用，真实派发预算预留放在审批后且retry内侧。
- [ ] 定义独立ID/版本、事件、顺序、启停、匹配、入口和required profile；只对确有缺口的领域触发补薄接入，没有第二套事件总线。
- [ ] 验证允许/拒绝/补输入实际改变行为，参数修改后二次校验，必需Hook缺失或异常不可正式导出；直接API共用同一入口且不递归触发。

**完成条件：** 拒绝时下游调用次数为0；在途成功回执不因后置观察失败变成可重试副作用。领域算法没有复制到Hook。

### T11：完成来源证据Skill基础

**依赖：** T02、T09、T10。**交付位置：** `backend/skills/evidence-linking/`、`backend/tests/test_evidence_integration.py`。

- [x] 对照官方loader元数据及文件能力，确定需要补充的文件内容标识、出现位置、原件/派生件关系和可回读锚点合同。
- [ ] 提供文件/PDF页块行、EML正文/附件、Excel表行单元格、Word段落/表格内容锚点；字段与费用行能引用多个片段。
- [ ] 保存原文、原值、提取值、标准值及处理版本，不把摘要作为唯一证据；OCR不提供的空间坐标标记缺失。
- [ ] 接入evidence Hook，检验引用不存在、版本不符、原文无法回读、同附件多次出现及派生页映射。

**完成条件：** 从费用字段回到准确原文；内容去重仍保留各出现位置和邮件关联。

### T12：完成PDF/图片指定OCR接入

**依赖：** T06、T10、T11。**交付位置：** `backend/skills/document-intake/`、`backend/tests/test_ocr_pipeline.py`、在线集成记录。

- [x] 先查文档loader、PDF/图像成熟集成和请求适配，仅补指定OCR合同；PDF原生文本仅辅助，真实PDF/PNG及EML附件已调用指定OCR。
- [ ] 完成全部格式真实矩阵。PDF/JPG/PNG与EML附件已实际接入并保留原响应/OBS回执/来源映射；TIFF多帧及切片映射有合成合同，仍需真实TIFF材料。
- [ ] 为网络错误配置有界超时/重试，区分下载失败、HTTP失败、非JSON、服务业务失败、部分页失败和提取失败。
- [x] 固定响应/原真实响应回放与PDF/图片在线验证分开记录；缓存纳入响应格式、pointer、能力版本及非秘密OBS身份，相关变更回归通过。每次接入新建UUID产物目录，不覆盖前次原响应。

**完成条件：** 两类真实材料经指定接口得到可追溯产物；任何失败都有范围和诊断，不能返回空成功。

### T13：完成短材料结构化费用提取

**依赖：** T03、T11、T12。**交付位置：** `backend/skills/document-extraction/`、`backend/skills/document-extraction/assets/`、包内用例。

- [ ] 查询官方结构化输出、模型工具策略及loader合同后，定义单据身份、费用行、数量/单价、金额/币种、税/小计/总计和付款方式schema。
- [ ] 保留原始/标准名称、缺失null、每行独立身份及字段证据；输出候选与问题而非直接宣布可执行账单。
- [ ] 对错误schema、截断、缺行、OCR混淆和低依据结果给出范围与问题；有限修复使用已验证原生策略，计入预算。
- [ ] 用T02短PDF、图片及EML附件的标准答案逐项核对，不以JSON合法代替内容正确。

**完成条件：** 真实短材料的编号、费用、金额、币种及证据正确；无法确定的信息不虚构。

### T14：完成基础标准化、精确金额及校验

**依赖：** T10、T13。**交付位置：** `backend/skills/billing-reconciliation/`、金额/币种/费用映射资源、包内确定性用例。

- [x] 查官方工具、schema/验证及成熟数值库集成后，保存原题费用映射、付款方式和ISO币种资源；歧义符号不自动映射。
- [ ] 精确计算数量×单价、税/折扣及合计，明确舍入、容差、含税/未税与净额规则；分单据及币种核对。
- [ ] 接入amounts和schema Hook，保留OCR纠错原值和可验证依据；总计角色不清楚时进入复核。
- [x] 为首个切片完成“显式空旧账单、唯一费用、主体与交易关系明确”的最小CREATE/AR/AP提案及对应必需校验；缺主体或方向不明仍复核。完整匹配/更新及复杂方向规则在T21–T23扩展。
- [ ] 验证小数精度、不同币种、零/负数、非法数值、税折扣重复计算和数量缺失等结果。

**完成条件：** 财务计算无需在线模型即可复现；金额异常阻止相应正式操作，不静默修数。

### T15：完成题目JSON导出Skill

**依赖：** T08、T10、T11、T14。**交付位置：** `backend/skills/billing-export/`、题目JSON Schema、`backend/tests/test_export_contract.py`。

- [x] 查官方结构化输出和序列化能力后，保留题目顶层数组与核心嵌套字段，支持四类operation及可空字段。
- [x] 验证金额为JSON数字，禁止NaN/Infinity/数字字符串；精确金额序列化不经不受控浮点往返。
- [x] 依据当前revision强制运行当前固定必需Hook集合，区分草稿和正式导出；过期校验/审批及禁用必需Hook阻断导出。独立profile仍属T26剩余项。
- [x] 输出审计引用与短业务依据，日志/状态不混进业务JSON；未知主体/方向和未闭合范围保留复核状态。

**完成条件：** 实际导出可被独立JSON解析及schema校验；关键失败样例无法绕过校验导出为CREATE/UPDATE。

### T16：完成原生主控规划、专家委派与首个端到端闭环

**依赖：** T03、T04、T07、T09–T15。**交付位置：** `backend/agents/factory.py`、`backend/config/agents.yaml`、Vue最小工作台、`backend/tests/test_first_vertical_slice.py`。

- [ ] 再查create_agent、Todo、SubAgent/CompiledSubAgent、create_deep_agent及结构化返回；显式配置主/子模型、工具、Skill、middleware和隔离上下文。
- [ ] 主控补齐主体/材料/旧账单等输入，原生todos随新证据调整；文档专家与核对专家返回带revision/范围/证据的提案。
- [x] 从Vue提交合成Excel，在真实模型/Server中显示计划/委派、费用及证据，经人工批准导出简单CREATE；任务为 `abab67c9-2fe2-44fe-a416-6dbd92058b26`，不能充作原题真实OCR验收。
- [x] 检查父Hook未被假定自动继承、内置general-purpose或递归委派按实际需求关闭、子Agent不直接提交最终记录。

**完成条件：** LangChain真实循环完成工具调用和委派；缺主体时补问、工具失败可见，todo完成不能替代业务验收。

### T17：补齐任务共享预算与harness计量

**依赖：** T10、T16。**交付位置：** `backend/config/runtime.yaml`、通用模型/派发计量装配、`backend/tests/test_shared_budget.py`。

- [ ] 查询官方call-limit/retry/上下文及Deep Agents隐含模型路径；在官方能力基础上只补未覆盖的跨父子共享计量。
- [ ] 约束初始上限：模型24次、工具64次、活跃1200秒、独立文档并发3、每受影响产物纠错2轮；这些是起始配置，评测后可版本化调整。
- [ ] 把摘要、评分、优化、输出修复、内部重试与MCP实际调用纳入对应预算；子委派/重规划不重置。并发派发原子预留用量，避免同时越界。
- [ ] 测试到限禁止新派发、在途结果保留、等待/暂停/排队单独计时；任一分支仍运行计活跃，不累加并行调用时间冒充端到端。

**完成条件：** 请求计数可对账，预算通过执行约束生效；仅提示词限额或外层Agent计数不算完成。

### T18：完成EML与Excel全量接入

**依赖：** T02、T11、T16、T17。**交付位置：** `backend/skills/document-intake/`、相应提取/证据资源、格式测试。

- [ ] 每格式先查询LangChain loader及成熟集成，比较元数据保留和便携依赖；只补具体业务缺口。
- [x] EML读取邮件头、字符编码、正文、HTML/纯文本选择、附件/内嵌图和递归关联；同附件多处出现及损坏附件保留兄弟项已有原题清点/合成回归。
- [x] XLS/XLSX覆盖多个工作表、表头、隐藏行/表标记、合并单元格、重复表头、公式及缓存值缺失；缺缓存通过项目内LibreOffice实际重算，保留公式及重算来源。合成二进制XLS通过。
- [ ] 正文与附件同费用不盲目新增；非账单附件和损坏附件有明确去向。用现有EML与合成Excel答案验证。

**完成条件：** EML内两份PDF及嵌入图可追溯接入，Excel每条有效行有来源；公式/隐藏信息的处理策略可查。

### T19：完成DOC/DOCX与跨页Word

**依赖：** T02、T11、T16、T17。**交付位置：** `backend/skills/document-intake/`、`backend/skills/document-extraction/`、Word证据规则、转换依赖说明。

- [ ] 查询官方Word loaders及Unstructured/Docling等现成集成，实测内容顺序、合并/嵌套表格和运行条件，避免默认自写XML解析器。
- [ ] 为旧DOC确定真实可用转换/读取路径，验证开发机及解包环境；所需外部程序纳入交付或明确安装条件，缺失时返回具体错误。
- [x] DOCX按段落/表格原顺序处理跨页长行、合并/嵌套单元格；内容锚点与渲染PDF哈希绑定，合成回归通过。
- [x] 连续表格、分页符、页眉页脚及转换后表格/费用保留已有合成格式回归；PDF页来自绑定hash的渲染，内容锚点不冒充原页。真实业务跨页语义仍另验。

**完成条件：** DOC、DOCX均有实际样例结果；表格跨页不丢行、不重复，证据能回读；仅支持DOCX不能标记全项完成。

### T20：完成长PDF、跨页续表与覆盖闭合

**依赖：** T12、T13、T17、T18、T19。**交付位置：** `backend/skills/document-intake/`、`backend/skills/document-extraction/`、`backend/skills/evidence-linking/`、长文档测试集。

- [ ] 先核对官方splitter、loader及OCR实际容量；OCR传输切片与模型语义分块分开，保存原页/派生件/单据身份和计划范围。
- [ ] 按身份、表头/列语义和续接证据识别逻辑单据及跨页表格；处理前页半行+后页半行、重复表头、小计、承前/转后、列变化和多单据边界。
- [ ] 为块定义输出拥有范围及只读重叠上下文，预留输入/输出容量；每候选行与所有计划页块记录已提取/非费用/重复指向/复核/失败去向。
- [ ] 测试OCR中间页失败、尾部截断、乱序响应、同名相邻行、跨页身份冲突和预算超限。只重试相关范围，不能重启子Agent重置预算。
- [x] 未闭合范围影响的费用进入PENDING_REVIEW；影响不明则整张逻辑单据复核。合成覆盖测试通过，覆盖100%不替代语义正确率。

**完成条件：** 固定跨页样例费用条数、每行金额及来源全部符合答案；故障范围可见，没有静默截取或重叠重复计费。

### T21：完成已有账单匹配、重复检测及同名多行

**依赖：** T14、T16、T18。**交付位置：** `backend/skills/billing-reconciliation/`、matching Hook配置与用例。

- [ ] 查询官方工具/验证/存储集成后，按题目四级依据匹配，读取输入旧账单JSON或宿主提供的候选快照，不把领域SQL藏在backend。
- [x] 区分文件重复、重复出现、重复提取和真实重复费用；费用行身份不只依赖标准名称，确定性测试保留同名真实行。
- [x] 唯一匹配、无匹配、多候选、强字段冲突分别输出证据和问题；候选按输入快照批量核对。
- [ ] 测试同名不同数量/箱号/税角色、不同币种、EML正文与附件重复、两张票相似字段及相同材料重跑。

**完成条件：** 确认重复输出NO_CHANGE；同名真实多行不误合并，歧义不随意取第一条。

### T22：完成增量更新语义与业务幂等

**依赖：** T08、T21。**交付位置：** `backend/skills/billing-reconciliation/`、`backend/skills/human-review/`相关契约、updates Hook与测试。

- [ ] 先查官方状态更新、结构校验、幂等/持久执行能力，明确它们不自动提供的领域变更语义。
- [x] 区分字段缺失、明确清空、提供新值；没有明确更新依据的差异进入复核，模型null不得覆盖旧值。
- [x] 生成逐字段差异和继承结果；金额单改不改变币种、付款方式或交易方。更新绑定旧记录和期望revision。
- [ ] 对提案接受/导出等本地副作用建立必要幂等键和回执；重复运行/重试不重复保存正式操作。这里只生成账单操作产物，不连接真实财务记账。

**完成条件：** 原题“只更新金额”完整保留其余旧值；冲突写入被拒绝，重复请求无重复变更。

### T23：完成主体、AR/AP、Credit Note与方向歧义

**依赖：** T14、T21、T22。**交付位置：** `backend/skills/billing-reconciliation/`、posting Hook和业务真值用例。

- [ ] 查询官方结构化工具/校验职责后，在Skill中表达主体、签发/接收与收费方向及可验证依据；主体由每次调用方提供。
- [ ] Debit/Credit Note、Invoice、负数、冲销和PP/CC分别结合关系判断，不机械决定或反转AR/AP。
- [x] 主体缺失时主控补问；无法消歧时posting_type为null、问题可定位、operation为PENDING_REVIEW。
- [ ] 对同一材料切换两个主体、第三方代收/代付、Credit Note冲减及主体别名无依据等案例核对标准答案。

**完成条件：** 方向依业务关系且证据完整；主体变更能定位重算范围，不沿用旧审批/结果。

### T24：完成人工修订、审批、暂停与恢复

**依赖：** T08、T10、T16、T22、T23。**交付位置：** `backend/skills/human-review/`、通用HTTP装配、Vue复核组件、`backend/tests/test_human_review.py`。

- [ ] 再查HITL四类决定、batched/per_call、嵌套中断、状态更新及原生恢复协议，分别建费用编辑和工具审批请求。
- [ ] 支持金额/币种/主体修改、拆行、删除误提取、选择匹配、补证据；期望revision条件写入新版本，保存人工确认字段与修改理由。
- [ ] 由Skill计算影响并重做相关提取/汇总/匹配/AR/AP，旧校验、审批和导出失效；原件OCR不受影响时复用，后续模型不能静默覆盖人工值。
- [x] 审批绑定动作、完整参数与版本，人工修订使旧审批失效；respond只表示人工合成结果，不能当真实工具回执。当前导出审批走业务版本绑定，ask_user使用原生per_call响应。
- [ ] per_call按interrupt ID逐项恢复，提交前验证response_schema。一次多项中一项无效时，其他工具可能已执行：刷新状态/核对回执后只处理未完成项，禁止整批重发。
- [ ] 主动暂停阻止新派发并结算在途结果；恢复在可控边界读取新revision。测试并发编辑冲突、嵌套请求和审批后参数变化。

**完成条件：** 人工修改确实改变后续结果且不丢原始证据；拒绝不执行、过期审批不能复用，界面显示真实暂停状态。

### T25：完成子Agent、MCP/Skill热插拔、版本与回滚

**依赖：** T09、T10、T17、T24。**交付位置：** `backend/config/mcp.yaml`、能力发布存储、`backend/tools/skill_bindings.py`、Vue扩展配置页、扩展集成用例。

- [ ] 先查官方SubAgentMiddleware及动态子Agent能力、内置MCPAdapter连接/发现/刷新和动态middleware、Skills刷新/pin；测试真实本地stdio及受控HTTP测试服务，不仅验证目录可见。
- [ ] 支持添加、测试、发现、启停、更新、加载失败保留上一有效版本；配置身份与服务自报名分开，schema在披露与执行解析两侧一致。
- [ ] 子Agent的注册、模型/工具/Skill配置与启停同属能力发布：使用官方SubAgent机制在安全边界装配新版本，验证新角色真实委派；禁用后阻止尚未派发的委派，在途角色固定版本并结算结果，不自写角色调度器。
- [ ] Skill采用不可变版本目录，父子各自在run之间或after_agent设置skills_metadata=None，下一run重载，不在当前运行中途重载。重载元数据不会替换历史pin消息，再pin只是追加；版本迁移须显式处理旧指令快照并保留审计，不能把两版同时当有效。恢复缺版本时明确迁移/重规划并使受影响审批失效。
- [ ] 禁用后每次真实派发/内部重试重新检查，尚未发出的调用不能执行；旧连接待在途结束释放，已发请求记录真实结果。
- [ ] 验证远端MCP版本能力并声明原地升级限制；单包独立入口及另一官方宿主迁移对比输出/证据，目标宿主另接Hook策略。

**完成条件：** 子Agent、MCP与Skill无需重启整体服务完成新增/禁用/更新/回滚；可看到实际使用版本和调用证据，没有自建角色调度、Skill加载器或MCP执行框架。

### T26：完成十一类Hook的完整拦截验收

**依赖：** T10、T20–T25。**交付位置：** `backend/config/hooks.yaml`、必要薄处理器、`backend/tests/test_hook_contracts.py`。

- [ ] 逐项验收schema、coverage、evidence、amounts、matching、updates、posting、revision、approval、capability、budget；独立启停/顺序/版本和required配置均真实生效。
- [x] 同一Skill唯一校验实现同时经Agent工具、人工API、正式导出调用，已有过期revision/审批与必需Hook阻断测试；完整外部异常组合仍待验。
- [ ] 测试缺失/禁用必需Hook、异常/超时、参数被修改、动态工具/子Agent/重试与Skill内部请求边界；不能只测主控外层。
- [ ] 注入工具成功后观察Hook失败，确认回执不丢、只修后处理；实际阻断后调用计数为0，校验入口无递归。

**完成条件：** 十一类均有可复现成功/拒绝或复核证据，API无旁路；不要求机械生成十一份重复Python实现。

### T27：完成有界纠错与双向反馈

**依赖：** T17、T20、T24、T26。**交付位置：** 相关Skill问题/修复契约、Agent装配与提示、`backend/tests/test_bounded_repair.py`。

- [ ] 查询官方Agent循环、结构化修复及可复用反思/评测组件，复用其执行而不新建循环runner。
- [ ] 将问题编码为字段/范围、原文证据、期望约束、可修复性和影响；主控据此委派定向修复并更新todos，保留候选差异及轮次。
- [ ] 人工修改进入同一依赖重算路径；简单问题由确定性Hook解决，只有确需语义核对时增加独立上下文评审。
- [ ] 验证修复成功、两轮未修复、重复候选/问题、无新证据、需要调用方决定及预算耗尽；无进展提前复核，不能把终止当通过。

**完成条件：** 能返回具体能力修订并复验；全部请求关闭思考且计入共享预算，记录短依据而非内部思维链。

### T28：完成可评测的跨任务改进

**依赖：** T02、T25、T27。**交付位置：** `backend/skills/feedback-improvement/`、`backend/evals/`、候选/发布配置及Vue入口。

- [ ] 先查官方evals/OpenEvals/LangMem及候选优化能力，优先组合适用组件，不默认自写优化器。
- [ ] 用户明确选择沉淀后生成候选映射/规则/提示/Skill；保存来源、适用范围和旧新差异，当前任务修改不自动改全局。
- [x] 在固定合成映射集用原生本地LangSmith比较baseline和候选，报告关键断言并阻断退步；界面验证5/7→7/7。此步骤不代表独立真实最终评测通过。
- [ ] 评测通过后显式审核发布并可回滚，在途任务固定版本；最终独立组不参与候选选择，后续使用其反馈时记录用途改变。

**完成条件：** 一次可复现的反馈→候选→比较→拒绝/审核发布→回滚演示；没有静默改业务代码或模型权重训练声明。

### T29：完成Vue业务工作空间与全部交互状态

**依赖：** T07、T16、T20、T24–T28。**交付位置：** `frontend/src/`、前端交互/端到端测试、真实截图。

- [x] 使用design和stop-that-shit实现总览、大屏、业务中心、待办、独立材料提交及管理页面，Hash导航与列表缓存已落盘，类型检查和生产构建通过。
- [x] 上传/URL/主体/旧账单表单与材料/费用/证据联动代码保留；原生计划/委派/进度仍由官方SDK管理，AgentPanel持续挂载且中断表单不随日志折叠。
- [ ] 接入人工修改、差异/冲突、待补充、工具审批、暂停/恢复、草稿/正式JSON、扩展启停与候选发布；按钮均调用真实后端。
- [x] 原件、辅助预览/待OCR与人工revision可区分；不支持精确坐标时使用真实文本/页锚点，不伪造高亮位置。
- [ ] SDK负责流与运行状态，业务快照按revision查询；处理刷新、断线、重连、过期编辑与部分完成，避免把草稿标成已校验。
- [ ] 验证键盘操作、长表滚动/按需加载和主要视口，提供稳定演示路径及实际截图。
- [x] 补充新版导航、详情往返、管理子页、原文内容块与人工请求入口的浏览器验收，并验证390×844、移动菜单及测试标签API阻断恢复；见[浏览器报告](../../../backend/tests/reports/user-workspace-ui.json)。本轮未进行新任务到审批导出的写入流程，旧Office/置信度截图不作为新页面证据。

**完成条件：** 评审者可从界面完成题目核心流程并定位证据/修改后果，所有关键状态可理解且可操作。

### T30：完成断线、重启及未知副作用恢复

**依赖：** T24–T29。**交付位置：** `backend/tests/test_recovery.py`、`docs/recovery.md`、实际故障记录。

- [ ] 再查所锁官方Server的持久化、订阅重放及中断合同；区分普通正常重启、强制终止/硬崩溃和外部动作结果未知。
- [ ] 分别在运行启动/订阅交错、OCR在途、子Agent中断、人工修订后、工具成功后Hook失败等位置注入故障并恢复同任务。
- [ ] 核对thread/checkpoint、业务revision、能力版本、人工请求、回执及预算；已成功动作不重发，未知结果先核对，不能把本地状态改写当远端回滚。
- [ ] 记录本地dev刷盘可能丢失的范围及界面提示；强持久化若需官方standalone的PostgreSQL/Redis及许可/平台条件，明确列为部署升级，不默认自写GaussDB saver。

**完成条件：** 正常重启能按保存状态续跑，硬崩溃结果和限制实测；不宣称开发服务零丢失或端到端exactly-once。

### T31：完成长材料性能与时延体验验证

**依赖：** T17、T20、T29、T30。**交付位置：** `backend/evals/performance/`、`docs/performance.md`、版本化运行参数。

- [ ] 固定机器、网络、材料页数/费用密度、并发及缓存条件，分别测短文档、长PDF、Word/Excel与混合附件。
- [ ] 记录受理、首个可验证结果、状态展示、最终完成及P50/P95；区分排队、活跃、人工等待和暂停，不用首token替代有效结果。
- [ ] 验证正常负载受理P95目标≤1秒、状态到前端P95目标≤1秒、控制落盘后新派发阻断目标1秒；最终时延同时报告OCR/模型实际占比。
- [ ] 只针对瓶颈优化缓存、批量候选、并发、受限CPU执行与官方服务背压；人工只改局部时不全篇OCR/重跑。测试多任务互不阻塞。

**完成条件：** 有真实测量、资源与调用量报告；目标未达到时写明实际值和原因，不能把设计目标复制成结果。

### T32：完成独立最终评测及总验收

**依赖：** T02、T18–T31。**交付位置：** `backend/evals/reports/`、`docs/acceptance.md`、最终测试记录。

- [ ] 固定代码、依赖、Skill/Hook/规则/模型配置版本，执行开发回归与在线集成；真实调用与固定响应回放分开报告。
- [ ] 在未参与本轮候选生成/选择的最终组评测字段准确性、费用行完整性/重复、匹配、误新增/误更新、AR/AP及来源；报告分母、失败例与覆盖。
- [ ] 核对原题10项及用户所有扩展要求，关键财务断言逐项通过，不以平均分掩盖关键退步；覆盖闭合、恢复与热插拔另有行为断言。
- [ ] 修复发现的问题并运行受影响回归；如用最终组反馈继续优化，记录用途改变，并为下一次独立测量准备新样本。

**完成条件：** 验收矩阵逐项指向代码、样例/命令、结果与证据；真实服务未通过项明确列缺口，不能用模拟PASS封口。

### T33：完成面试交付、便携打包与迁移验证

**当前暂停：** 用户已明确本轮先完成需求。以下保留后续交付目标，本次职责重构不执行打包、重包或交付迁移。

**依赖：** T32。**交付位置：** `README.md`、`docs/portable-environment.md`、`docs/insights.md`、实际启动/构建/打包入口及最终ZIP。

- [x] README首屏展示用途、架构图、快速启动、演示步骤和真实截图；列八个Skill、十一类Hook、官方复用依据、外部服务条件和实际验收结果。
- [x] 至少写六点有依据的补充思考：长材料完整性、证据与财务精度、更新意图/幂等、人工版本与恢复、可插拔边界、时延与改进评测；逐点区分已实现、限制和建议。
- [x] 完成Vue生产构建，运行可使用随包dist；打包包含 `backend/bishi1/`、源码、锁文件、Skill资源、配置及用户要求保留的 `backend/.env`，排除 `.build/`、缓存和无须交付的原件。运行时ZIP不冒充完整应用包。
- [ ] 选择含中文/空格的不同目录解压，从项目外工作目录启动；验证相对入口、二进制依赖、必要DOC转换程序、文件处理、前端、数据库/OCR及一次导出。构建/启动命令以实测写入README。
- [x] 核对交付清单、样例授权与外部运行条件，完整ZIP位置为 `delivery/harbor-bishi1-windows-x64.zip`，大小/哈希见同名 `.package.json`。邮件发送、公开发布、真实财务系统写入不在本计划授权内。

**完成条件：** 不依赖开发机绝对路径、其他项目node_modules或Codex插件；评审者按README可运行完整应用，迁移证据与已知条件齐全。

新结构完整候选包已在中文空格目录、项目外工作目录通过迁移验收：161 passed、43 warnings、4 subtests passed（61.19秒），运行时/原生扩展/OBS SDK离线签名/pip check/真实MCP均通过；四HTTP全200、健康ok，三个任务的checkpoint/消息/原中断保留且未resume，旧EML原件哈希及已批准两条CREATE/AP（20、50）导出一致，.env未改、在线模型请求0。本轮证据为 `backend/tests/reports/app-portability-structure.json`、`app-portability-structure-tests.txt`，候选包103181917字节、SHA-256 `81c666aaedf6fe4514287c09c34d21c292423fccc9ca61ccc9e9ccb967591260`；标准名交付包已收录本轮文档和报告，最终大小/哈希以delivery同名.package.json为准。必要DOC转换程序迁移仍待验，上方完整迁移步骤继续保持未勾选。

目录调整前OBS候选包迁移结果见 `backend/tests/reports/app-portability-obs.json`、`app-portability-obs-tests.txt`：解包到 `.build/迁移 空格-2e9fd76f/`，项目外运行时/SDK离线签名/依赖/MCP及161项回归通过（43 warnings、4 subtests、41.16秒），2025端口四个HTTP入口均200、健康ok。三个任务的同checkpoint/消息/原中断状态保留且未resume，旧EML原件哈希及已批准两条CREATE/AP导出一致；.env未变、在线模型请求0、迁移Server已停止。报告对应候选包102877154字节、SHA-256 `c8e08c09c4018042d718961be9e446b221ec2421c9b3759bc93ddb1848563a78`，不冒充最终标准名重包哈希。旧 `backend/tests/reports/app-portability.json` 仅保留140项历史证据。上方含必要DOC转换的完整迁移步骤仍未勾；指定OCR基础链路已有真实验证，真实DOC、长材料、独立真实金标和生产强恢复等边界仍未通过。

## 5. 执行次序与里程碑

任务编号用于追踪，实际只在依赖满足后开始。可并行：T01/T02；T03/T04/T05/T06；T18/T19；T21–T23与不冲突的格式补齐；末期文档素材可随通过任务积累，但最终打包必须等待总验收。共享模型/Hook/存储装配由一位开发者集中修改，独立Skill可分工，避免同文件竞争。

| 里程碑 | 通过条件 | 用户可见结果 |
| --- | --- | --- |
| M1 基础条件 | T01–T06 | 真实模型/OCR/数据库证据与官方前后端协议可用 |
| M2 首个闭环 | T07–T16 | Vue处理一份真实材料、费用/证据/校验及JSON |
| M3 题目完整业务 | T17–T23 | 全格式、长跨页、匹配/增量/重复/AR/AP |
| M4 扩展与人工闭环 | T24–T29 | 人工纠错、动态能力、十一类Hook、纠错/候选发布 |
| M5 交付验收 | T30–T33 | 恢复与性能实测、独立评测、完整便携ZIP |

## 6. 需求覆盖索引

| 需求 | 主要任务 |
| --- | --- |
| Python/LangChain真实Agent、Plan与专职协作 | T01、T03、T04、T09、T16 |
| EML及递归附件 | T02、T11、T12、T18 |
| 指定OCR、PDF/图片/TIFF | T06、T11–T13 |
| Excel、DOC/DOCX | T18、T19 |
| 长PDF、跨页续表/半行、跨页Word、覆盖 | T11、T19、T20 |
| 提取字段、标准化、金额/币种/税/总计 | T13、T14 |
| 已有账单、重复、同名多行、增量更新 | T21、T22 |
| 调用方主体、AR/AP、Credit Note | T16、T23 |
| 合法JSON、null/数字、证据/依据 | T11、T15 |
| Skill业务封装、官方加载执行、跨宿主复用 | T09–T15、T18–T25、T28 |
| 子Agent、MCP/Skill热插拔与版本/回滚 | T25 |
| 十一类独立Hook、同一算法及API等价 | T10、T14、T21–T26 |
| 人工编辑/拆行/证据/主体、审批及暂停恢复 | T24、T29、T30 |
| harness、共享预算、有界纠错、无进展 | T08、T10、T17、T20、T26、T27 |
| loop改进、候选评测/审核发布/回滚 | T02、T28、T32 |
| Vue体验、重连、时延/并发/局部复用 | T04、T07、T16、T29–T31 |
| 独立评测、补充思考、ZIP便携交付 | T02、T32、T33 |

计划完成的标志仍是T33交付及其前置任务全部验收通过。当前已有可运行实现和部分真实服务证据，尚未达到全部任务的完整完成条件；未通过项按 §2.1 保留，不以文档同步或合成PASS封口。
