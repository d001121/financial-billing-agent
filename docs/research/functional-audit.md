# 题面逐项核对与控制台实际接入（2026-10-22）

本记录以用户指定的下载目录 HTML 原题为基线，区分原题要求、后续扩展、已实现行为及实际验收范围。题面中的交付邮箱不构成发信授权。本轮没有全量测试、打包、重跑真实账单、代答中断或审批真实账单。

当前发布：skills 配置 **v21**，能力 **c8279edbf4bf6046429c**；document-extraction **2.0.1**、evidence-linking **2.0.1**、feedback-improvement **1.2.0**。正式服务端口2024、PID39940。正常 Ctrl+C 关闭旧服务后重启，33个线程的ID与状态完全一致，GaussDB/Redis健康；[重启回执](../../backend/tests/reports/control-management-restart.json)。旧任务继续使用旧不可变能力，不能用本轮新规则的实现状态推断旧任务已重新提取。

## 1. 原题十项验收

| 原题验收项 | 当前实际实现 | 本轮证据与范围 |
| --- | --- | --- |
| 1. EML正文及附件 | document-intake解析主题/收发件人/编码/正文，递归接入附件和嵌入材料，保留父来源、内容hash和原件；材料包由一个提取Skill综合阅读 | `test_intake.py`、`test_markdown.py`的定向检查通过；真实指定EML历史在线证据另见Codex式提取记录，本轮不重复在线调用 |
| 2. 指定OCR识别PDF/图片 | 通过获准OBS自动上传、临时签名URL调用题面接口；保留原响应、页/帧映射和失败范围。补页继续使用同一OCR，模型只读文本 | 接入/切片/Markdown定向检查通过；历史真实OBS和OCR200见 `obs-originals-ocr.json`、`codex-style-extraction.md`。本轮没有把模拟OCR当作新增在线验收 |
| 3. Excel/Word费用表格 | XLSX工作表/单元格/公式与缓存，DOCX正文/嵌套合并表格按顺序读取；项目内LibreOffice真实转换旧XLS/DOC、重算公式、绑定Word预览版本 | `test_office.py`七项均通过，含真实便携LibreOffice转换。`control-document-functions.xml`中其余历史失败已由后述提取回归闭合。材料为明确合成夹具 |
| 4. 准确提取编号、费用、金额和币种 | 主控自主读干净Markdown、搜索和窗口回读；原生schema约束，原文ref恢复，金额/币种/费用名证据与单据作用域硬校验；国际数字保留原值，歧义不猜 | `control-extraction-evidence-final.xml`17项通过；国际数字/币种等87项在 `control-accuracy-final.xml`中通过。真实准确率仍缺独立人工金标，不能宣称全部原题材料准确提齐 |
| 5. CREATE与UPDATE | billing-reconciliation按单号/费用、提单、订舱、箱号与双方日期金额匹配；唯一命中且有明确修改依据才UPDATE，未授权字段继承原值；逐费用输出 | 财务/导出定向检查通过：仅金额更新、缺失与明确清空区分、多候选拒绝选首条、同名不同费用行保持独立 |
| 6. 主体与AR/AP | 同一收费关系从调用方主体视角判断AR/AP，Credit Note/负数/PP/CC不直接决定方向；已给主体但关系未解决时主控补读或真实中断追问 | 财务定向检查及既有会话目标闭环报告；本轮没有代答真实121d或改变其AR/AP |
| 7. 重复与冲突 | 内容与来源重复、同名真实行、已有记录差异、金额/币种/单据作用域矛盾分别处理；重复无变更NO_CHANGE，冲突保留可编辑提案并禁止直接执行 | `control-financial-harness.xml`财务部分通过；其中旧双侧关联断言已按最新自主判断合同调整，明确不同invoice借财务字段的新断言在17项提取/证据检查中通过 |
| 8. Harness稳定与准确 | 原生规划/委派/工具执行/重试/中断/检查点，统一预算、暂停、版本与必需Hook门禁；同revision保存/人工更正/最终导出核验，保留成功材料避免重做OCR | 本轮动态工具/Hook/专家实际执行及Harness定向检查通过；既有动态规划、人工反馈闭环记录继续适用。正常重启通过；不据此宣称全部断电故障或长材料性能已验收 |
| 9. 五点以上思考 | 本报告§6给出七项与无模板海外业务相关的取舍，并链接落地模块 | 已完成文字与实现对应，不把建议当实测性能 |
| 10. Python/LangChain实现 | Python主控使用LangChain create_agent；Deep Agents原生SkillsMiddleware/SubAgentMiddleware；Vue只展示与调用API；最终输出合法数组JSON，金额为数字、缺失null、ISO币种、保留原名/标准名/证据 | 原生真实专家委派、Skill工具执行、财务导出定向通过；Vue类型和生产构建通过。用户已暂缓ZIP交付，本轮没有打包或发信 |

实现入口在 `backend/skills/{document-intake,document-extraction,evidence-linking,billing-reconciliation,billing-confidence,human-review,billing-export,feedback-improvement}/`。领域代码仍随Skill迁移；宿主没有另建提取流水线或Skill执行器。

## 2. 本轮补齐的管理操作

入口：用户页右上角“控制台”→“Skill与工具管理”或“经验与规则”。只有配置文件已写入不足以判定成功，本轮同时检查了原生执行和禁用后行为。

| 能力 | 页面与API实际操作 | 执行证据 |
| --- | --- | --- |
| Skill | 新增已安装包、ZIP导入、配置编辑、资源正文预览、启停、移除注册；冲突时提示重新载入 | 隔离页面实际导入→停用→启用→查看scripts资源→移除；HTTP测试再由原生SkillsMiddleware渐进披露并通过LangChain真实执行新增函数 |
| Skill包契约 | 检查SKILL.md、references/scripts目录、名称、路径、大小及工具schema；纯说明包无需空的skill.py；声明include_tools须有绑定或已注册MCP前缀 | 未绑定工具拒绝；原生发现正确；未指定工具别名时采用函数原名；保存配置失败撤回本次安装；拒绝覆盖现存同名包 |
| MCP | 新增/编辑/启停/移除连接；真实连接测试、工具发现和输入schema展示；填写参数实际试调用 | 原生 `langchain.mcp.MCPAdapter`+FastMCP stdio发现calculate，真实19+23=42；禁用后调用409且执行回执仍只有一条；不可达服务502并保留原配置 |
| Hook | 新增/编辑/启停/移除非必需校验，统一配置和优先级；原生Hook保留固定绑定；必需Hook不能通过停用放行正式产物 | 合成AUDIT_REJECT Hook实际进入统一校验；禁用后不再执行该可选校验；必需Hook门禁、派发/重试检查另有定向证据 |
| 专家Agent | 新增专家、配置prompt/类型/Skill及启停；主控仍由LangChain编排 | 合成模型通过原生SubAgentMiddleware的task工具，实际委派新增audit-expert并收到其唯一回执，不是只检查配置列表 |
| Trace | 原生检查点的调用路径、耗时回执、模型/工具计数、修订/确认/等待口径 | 生产API沿用当前线程只读投影；无独立金标时准确率、误识率和漏识率保持null，避免显示虚构指标 |

Skill移除仅移除注册，不删除不可变历史版本。存在Agent/Hook依赖时服务端拒绝损坏引用，须先调整引用。禁用对尚未派发的调用生效，不能撤回已发出的远端请求；重新启用或换版本由新能力快照使用，历史任务不静默升级。

本项目没有预配置用户的外部业务MCP，正式列表为空是实际状态；没有把测试calculate服务留在正式配置中。真实stdio路径已验证，特定外部HTTP服务的认证、业务schema和服务端版本仍要在接入时实际测试。

## 3. 可运行的自进化loop

本轮实际闭环是**主体作用域的费用名称映射改进**：

1. 用户明确选择沉淀某任务的反馈，记录来源task/revision、主体、提出者、原完整映射及候选完整映射。
2. 导入人工标注JSON，明确合成/真实材料、标注依据、regression/final用途、case及family身份；可选择、下载、启用和禁用数据集。
3. 使用原生LangSmith `evaluate(upload_results=False)`运行当前与候选两版，真实调用证据/金额/财务Skill函数；API不接受客户端自填通过率。
4. 回归先通过，才使用独立最终集；同单据家族或相同输入跨集、重复消费最终集、别名未覆盖、关键字段退步均拒绝发布。重命名数据集不恢复其独立性。
5. 审核人填写理由并确认发布，CAS核对基线与完整候选摘要；新任务能力快照读取新映射，当前任务不被悄悄修改。
6. 审核后回滚至既有版本；禁用feedback-improvement后禁止新候选/评测/发布，但历史读取与恢复回滚仍可用。

隔离页面已实测：导入7例合成标注→选择数据集→创建Document Charge映射候选→基线5/7、候选7/7→审核发布→API确认有效映射改变→审核回滚builtin-v1→禁用/启用数据集。基线与候选每例均有原生run_id。[页面/API回执](../../backend/tests/reports/control-management-ui.json)、[发布时的有效映射](../../backend/tests/reports/control-ui-published-mapping.json)。这7例不衡量OCR或大模型的真实识别准确率。

修改一个别名时先读取该主体的完整映射，合并变化再提交；新增/删除一个条目不能顺带抹掉其他自定义条目。prompt/rule/Skill类型仍只能保留草稿，不提供未实现的自动评测/发布承诺；本项目没有模型权重自训练或自动代码改写。

## 4. 本轮准确性修复

- **账单日期证据**：填写document_date须引用正文中的真实日期，不能拿EML邮件头Date代填；原文没有则null。人工已实际保存的同charge日期更正可以保留，模型自报human_confirmed不算人工事实。
- **不同单据的财务字段**：已知documents头中的reference_no明确不同时，不得从另一单据借金额、币种、数量、单价、付款方式；返回 `CROSS_SOURCE_DOCUMENT_CONFLICT`并使该引用未通过。共享提单关系仍可以支持运输字段，不恢复用户已取消的双侧身份DAG。
- **全部材料比较**：read_materials保留本次全部来源清单和内容。第一份提齐字段也要检查其他材料；接入失败/尚未接入资产保持阻断。按用户最新Codex式合同，不重新要求每个字符块都提交覆盖账本。
- **国际数字与币种**：保留已有欧洲/印度分组、Unicode数字、括号负数及ISO证据检查；裸$、¥、模糊三位分隔不凭模型猜测，错误费用名不能被正确金额掩盖。合计按单据及币种作用域核对，算术规则复用唯一Decimal实现。

## 5. 定向验证与实际限制

| 回执 | 结果与解释 |
| --- | --- |
| `control-management-final.xml` | 52通过：当时的管理、配置、改进定向检查；不作为后续变更全部重跑的宣称 |
| `control-management-last.xml` | 最后21通过、91条依赖Beta/弃用警告：完整管理扩展和改进HTTP测试，包括畸形标注提前拒绝、禁用Skill仍可回滚、不可达MCP诊断、新Hook、新专家真实执行 |
| `control-extraction-evidence-final.xml` | 最终17通过：日期、全部材料、精确Markdown/EOF、明确不同单据的财务引用及证据检查 |
| `control-document-functions.xml` | 40通过、2条初始失败；邮件日期缺口已修，旧强制逐块coverage期望已按当前合同调整，两者均在最终17项通过；Office真实转换部分无失败 |
| `control-financial-harness.xml` | 43通过、1条初始旧关联约束失败；更新为明确不同invoice作用域冲突后由最终17项验证，不恢复旧关联DAG |
| `control-accuracy-final.xml` | 87通过、1条MCP故障诊断失败；发现FastMCP实际使用httpx2及close再抛错，修复后 `control-mcp-failure-final.xml`和最后21项均通过 |
| 前端 | `npm run build`含vue-tsc通过，2501 modules、Vite1.13秒、`index-qOZNjC0L.js`；仅有已有大chunk提示 |
| 页面 | 隔离真实配置/MCP/LangSmith操作通过，console errors=[]；最终构建重载与空MCP状态检查通过；任务及持久层为明确合成MemoryRepository |
| 正式服务 | 2024正常重启、33线程ID/状态一致、健康与新管理API可用；隔离2025服务已停止，测试临时根已清理 |

这些检查存在重叠，不相加为一个虚构全量通过数。原始初始失败报告保留，最终修复结果以上述对应回归为准。浏览器早期Chrome原生confirm阻塞自动化，本轮移除确认改为页面内区域，并在IAB完成真实点击验收；没有通过脚本模拟确认。

**尚未验收**：独立真实金标下的字段准确率/误识率/漏识率；长材料及跨页PDF/Word的真实规模分层P50/P95；20秒端到端目标。历史指定EML在线116.027秒是旧能力的实际证据，不能视为v21性能结果。现有合成续页/Office/作用域检查不能替代所有真实跨页语义验收。当前Agent Server为本地开发模式，正常重启通过不等于任意硬崩溃下零损失。

旧 `backend/evals/datasets/manifest.json`保留2026-10-20接入前的开发盘点快照，其waiting_url不再作为当前OCR接入状态；没有将其改造成独立金标或假填财务答案。

## 6. 七项业务与技术思考

1. 全球无模板单据先保留原文和版式锚点，再做语义解释；日期、编号、金额不能用区域或邮件上下文硬补。对应document-intake/extraction/evidence Skills。
2. 一次提交是共同参考的材料包，费用行仍以真实单据身份归属；附件重复与同名真实费用不是一回事。对应来源hash、documents及reconcile。
3. AR/AP是当前主体与收付款关系，不是单据标题分类；主体已给但关系冲突时才针对性问一句。对应posting Hook与原生会话中断。
4. 费用映射可以跨任务复用，但只更新有来源且经评测/审核的作用域；一项修订不应变成全局经验。对应feedback-improvement。
5. 高置信度必须有原文和金额/作用域支撑，统计准确率必须有独立标注；高分不能抵消硬冲突。对应billing-confidence、证据Hook与Trace空指标。
6. 长文优先干净Markdown清单、原生grep定位与有界回读，保留原页锚点和未读/失败范围；并发接入和缓存减少重复工作，不能用省略文件换速度。对应StateBackend、读取工具和OCR产物复用。
7. 人工修订、规则发布、账单执行是不同的事实；分别保存revision、能力版本与审批，才能回滚经验而不篡改历史账单。对应条件事务、不可变release和正式导出门禁。

## 7. 官方查证与最小补充范围

本轮已使用LangChain Docs/API Reference MCP核对以下组合，安装版LangChain1.4.6、Deep Agents0.7.29、FastMCP4.1.2、Agent Server0.16.2：

| 操作 | 官方能力 | 本项目必要补充 |
| --- | --- | --- |
| Skill发现、渐进披露与关联工具 | `SkillsMiddleware`、`FilesystemMiddleware`、`StateBackend`、`metadata.include_tools`；正文 `/oss/python/deepagents/skills.mdx` | 管理员本地ZIP存取、资源预览、配置CAS/依赖校验。官方未知include_tools只记debug，故保存前明确拒绝未绑定工具；不自建runner |
| 工具参数与真实执行 | LangChain `tool`、`create_agent`；原生Skill工具resolver | 绑定包内函数及宿主上下文；缺省name使用真实函数名，不另建执行层 |
| MCP发现/连接/调用 | 内置 `langchain.mcp.MCPAdapter`、FastMCP stdio/http和close | 管理HTTP入口、已注册/启用检查与错误诊断；close和httpx2异常在同一边界处理，不盲重试有副作用工具 |
| 专家委派、Hook | `SubAgentMiddleware`、`CompiledSubAgent`、`AgentMiddleware`及原生工具handler | 领域校验留在Skill，宿主薄装配和配置存储；新增专家测试真实走task工具 |
| 对照评测 | `langsmith.evaluate(upload_results=False)`、Example/reference outputs | 费用映射领域断言、独立集/最终消费规则与版本发布事务；不用自造分数或自建实验引擎 |
| 日期/不同单据财务引用 | `ToolStrategy`（完整符号 `langchain.agents.structured_output.ToolStrategy`）与Pydantic约束输出结构 | 官方结构校验不代替本业务的日期证据/单据归属判断，故只在既有extraction/evidence Skill补领域函数 |
| 重启与状态核对 | Agent Server threads.search、原生检查点；Docs persistence/fault-tolerance | 当前无busy时正常Ctrl+C并核对线程；不引入新调度器，不将RunControl文档推断成已改造本地服务 |

开发时调用MCP查文档的要求不成为产品每单执行依赖。产品的真实管理能力由上述代码、定向检查和页面回执证明。
