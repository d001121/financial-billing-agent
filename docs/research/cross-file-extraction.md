# 全材料提取与跨来源补充

日期：2026-10-21。用户要求同一次提交为一个账单任务，正文与全部附件共同参考，缺字段时回看其他材料；不同真实账单仍在任务下分别输出。

## 最新：同一个提取 Skill 内递进执行

当前版本为skills v17/agents v8，document-extraction1.6.4/human-review1.1.3，能力7e98a1650f2a80341eee。保留一个提取Skill，在其中通过原生工具进行渐进读取。1.6.3完整原EML任务746914ee-4775-414e-acc4-68300058cba3已跑完，4来源/9块、一笔50、日期/邮件双方null、原图查看、PDF正文/版式与预览均核验；但24模型/24工具后budget_exhausted（活跃732.93秒，观察墙钟815.56秒），HBL出口参考号仍被误填为明确主单号，顶层证据投影/中断未收尾，最终断言3项失败。没有手工修订该任务、重置预算或声称通过。随后1.6.4修复warning/info在schema中误当失败的确定性问题，156项相关回归通过（2 warnings、29.87秒），未再跑整单。语义角色与预算/时延仍是未完成验收。

前序1.6.2样本曾闭合4来源/9块，原图、编号、金额、证据与预览定位通过，只有币种原生中断；仍误用了邮件Date，断言1项失败。为此1.6.3在现有提取Skill的schema校验加入BILL_DATE_EVIDENCE_REQUIRED：EML费用日期须有正文/明确same_bill材料的字段引用，邮件头不支持该字段；未提供值不报错，宿主已保存的人工日期修订可保留，模型自报确认无效。human-review按当前结果重算该错误，宿主仅传入已保存records作为确认依据。

官方依据复核Docs MCP structured-output中Pydantic Field描述与验证、已查Reference tool签名；框架处理schema/工具与反馈，账单日期与邮件传输日期的业务归属不属于通用框架能力，因此最小校验留在现有Skill，不新建日期Skill或运行层。1.6.3阶段155项相关回归通过，2 warnings、40.55秒。真实邮件的单次定向create_agent/ToolStrategy回归日期/传输双方为null；裸模型仍猜USD，既有validate_evidence以币种歧义拒绝，报告分别保留成功范围和失败范围。完整重跑失败与1.6.4补修见本节首段及docs/acceptance.md。下文为此前发布过程。

2026-10-21当前发布为skills v15/agents v7，document-extraction1.6.2，能力9bf7eb03b9aafc32824d。仍只使用一个提取Skill，没有PDF/图片/Office格式包。新增view_source_image绑定工具：任务source_id→现有Skill read_image→LangChain标准多模态ToolMessage；content_and_artifact将可见原图与来源哈希/帧/转换回执分开。宿主不接收模型任意路径、不新增模型循环，实际解释仍由当前文档Agent完成并计入共享预算。

官方依据：本轮通过Docs MCP核对 `/oss/python/deepagents/skills` 的三级披露与步骤/决策条件、建议合并相关能力；`/oss/python/langchain/tools#return-multimodal-content`、`/oss/python/langchain/messages` 的image/base64/mime_type；Reference MCP已读取 `langchain_core.tools.convert.tool` 的content_and_artifact签名，安装组合langchain1.4.6/core1.6.12/openai1.7.2/deepagents0.7.29。框架提供媒体传递、工具运行及Skill披露；本项目仅补不可变原件hash、任务绑定、帧选择和存储回执。图片传递成功不代表识别成功，视觉文字不冒充逐字OCR证据。

真实能力验证：qwen3.8-max通过同一模型工厂、enable_thinking=false，分别接受HumanMessage图片与原生工具image结果，各1次开发探测调用；两次均描述出金门大桥宣传横幅，未见费用或金额。独立报告为source-image-model-probe.json与source-image-tool-model-probe.json，不将这2次无任务探测计入正式任务时延或冒充完整Agent验收。当前140项相关回归通过（2 warnings、56.15秒），XML为single-skill-vision-pytest.xml，涵盖跨任务来源拒绝、多帧/hash、原生ToolMessage及既有PDF/配置/CLI。服务正常Ctrl+C重启为PID28076，23个既有线程ID及状态相同，数据库/Redis健康。新建指定EML验证任务1f202de0-825c-4561-87cd-ad677234f311，正式结果另见验收记录。

上轮任务5682145c-538b-48c5-ba10-09ebc36f56b2最终awaiting_review、17次模型/20次工具、活跃453.03秒。虽已正确提取MBL B/L HZMHK331281、订舱4055331281和HBL B/L SSZSE26093128，但图片未能目视判断，存在COVERAGE_OPEN/COVERAGE_REVIEW；最终还留有2处EVIDENCE_UNREADABLE及HBL出口参考号语义问题，未通过完整原件验收。此失败记录保留，不因新版本发布改写旧任务。下文为此前实现历史。

用户明确否决按PDF/图片/Office拆格式Skill；未创建这些包。document-extraction1.6.0的SKILL.md提供任务步骤，在同一目录按需读取reading-strategies/cross-file-review/output-contract三个reference。复核Docs MCP `/oss/python/deepagents/skills` 与API SkillsMiddleware，沿用Deep Agents0.7.29三级披露及metadata.include_tools工具关联；没有新Skill加载器、执行器、Agent循环或工作流图。

document-intake1.4.0宿主先用ocr_only保留指定OCR及预览，默认Python接口full兼容旧调用。Agent发现OCR缺内容、标签/列歧义后，在同一个提取Skill里调用read_document_sources选择text/layout和原页。PDFPlumberLoader来自官方社区集成，已安装langchain-community0.4.2、pdfplumber0.11.10；当前API MCP未收录此符号，已核对实际安装源码/签名，不能由搜索未命中推导“官方没有”。Loader没有页选择参数，复用pypdf切选定页后映射回原页。业务补充只包含本项目OCR完成范围、不可变原件hash和来源保存合同，通用读取复用库。

宿主不接受模型任意文件路径；只绑定当前任务来源/资产。补读同步sources及intake.sources，重建整个材料包的chunks，失效旧证据/财务/核验/导出，保留已有候选和原始OCR。重复表示不新增费用；新增块有覆盖义务。覆盖检查新增ASSET_NOT_READ/SOURCE_NOT_READ，防止提齐第一份文件后遗漏其他提交。evidence-linking1.4.2保留唯一逐字引文的实际定位及reported_quote_start，重复引文仍要求真实位置，错误回执提供候选位置供Agent定向修正。

已完整回归398项及4项子测试，228.48秒；pip check通过，锁文件已更新。配置skills13、agents6，能力d2bcb79a60b6e3bcaac2。离线测试不代表统计准确率；真实EML结果和应用状态见docs/acceptance.md。本节之后为早期排查/发布历史，版本、进程和测试数不代表当前状态。

真实首轮d0a1b46e-8b96-4d05-9e24-240c4c9c22f8已主动为两份PDF选择text补读；随后误将图片传给PDF补读工具，ValueError终止运行。已用Docs MCP tools/error-handling及Reference ToolException核对原生纠正机制，宿主绑定采用ToolException与handle_tool_error=True，来源/格式/页码等可纠正错误返回error ToolMessage；不另写重试或错误运行时，未知异常/网络/策略拒绝不在此捕获。修改后46项宿主测试通过，包含错误状态及材料未变断言。首轮错误报告保留，不把它算最终成功；从同一开发任务检查点续跑仍累计原任务预算且不重复OCR。

## 定位结果

截图对应历史任务1fc2152a-1fe0-4020-919d-3caf83fd6819，实际只包含PDF示例账单1.pdf，金额245；并非PDF 示例账单2.pdf。诊断保存在backend/tests/reports/pdf2-before-task.json（文件名为诊断初期命名，内容不是PDF2）。历史任务只读，未修订/审批/迁移。

document-intake此前已读到PDF原生全文，却只保存为authoritative=false的native_preview；document-extraction过滤预览，实际只见指定OCR的结构化JSON。服务省略币种、日期等键后，模型看不到原件里已有的信息。材料包共享上下文此前仅覆盖邮件正文/头，其他来源只有文件名和chunk引用，没有批次间的字段缺口摘要。证据回读也只验证字符串存在，未强制跨来源账单作用域。

## 官方能力与最小缺口

本轮实际查阅LangChain Docs MCP及Reference MCP，安装组合仍为langchain1.4.6、langgraph1.2.16、deepagents0.7.29。沿用本会话已读的SkillsMiddleware、RecursiveCharacterTextSplitter和Document依据。

| 操作 | 官方依据 | 采用方式及业务缺口 |
| --- | --- | --- |
| 专家协作 | /oss/python/langchain/multi-agent/subagents；deepagents.SubAgentMiddleware签名 | 原生隔离专家、主控委派、共享任务工具/持久产物；不自建同级消息总线或Agent循环 |
| 提供源材料/前序事实 | /oss/python/deepagents/context-engineering，tool prompts/runtime context | 原生工具参数/结果传递上下文，复用已有prepare/read/save；材料关联与费用字段缺口属于业务数据 |
| PDF读取/分块 | /oss/python/langchain/knowledge-base#load-and-split-a-pdf、Document/RecursiveCharacterTextSplitter | 继续组合现有pypdf和官方分块器，不自写PDF解析器；新增表示的OCR就绪和来源页/hash属于接入合同 |
| schema/证据关联 | 官方structured output、SkillsMiddleware | Pydantic描述跨来源关联提案；官方框架不提供航运账单身份/币种作用域判定，在业务Skill补最小校验 |

API搜索tool得到官方函数说明；按tools.tool/tools.convert.tool定位返回未找到，未把该结果作为“框架没有工具”的证据。当前使用已验证的langchain.tools.tool装饰器及工具schema推导；Reference的SubAgentMiddleware完整签名已读取。没有新增通用runner、middleware或Hook运行机制。

## 实现

- document-intake1.3.1：指定OCR每个范围仍实际调用；成功后将原PDF内嵌全文单独保存为pdf_embedded_text，包含page、source_content_id、extraction_method、ocr_status、ocr_anchor。OCR原JSON和旧native_preview均保留。失败/缺URL不释放正式全文，扫描/部分可搜索页不凭空补字。
- document-extraction1.5.1：所有来源共享有界原文片段和完整chunk引用；已保存候选的document_facts/missing_fields供后续批次查缺。没有费用的提单也保存documents表头与运输事实，通过source_facts和read_task_context.documents共享；摘要不变成新证据。原生工具支持source_id定向回读，完整覆盖仍以全包chunks校验。每条费用必须指定真实主来源；同一document_id出现不同账单编号触发冲突。
- source_links明确区分same_bill与shipment_context，保留双方真实身份引用。same_bill必须基于相同真实单据编号；运输关联只补提单/订舱/箱号等上下文。不能仅因同邮件或同运输就借币种、费用、总额、账单日期或债权债务人。
- evidence-linking1.4.0回读并验证关联身份，覆盖模型传入的verified，越界证据产生硬错误；人工修订/导出复用同一校验。OCR/native重复表示不增加费用或独立置信度，真实同名多行仍独立。
- human-review1.1.1按来源/逻辑单据身份合并各批documents，修订重算保留这些原始上下文。专家提示词最终发布为agents配置v4；skills配置v11，能力50de789075b9c29458c7。业务算法仍在Skill内，宿主只扩展既有原生工具参数及产物存取。历史已发布目录不修改，旧任务固定旧能力。

## 原件核查与验证边界

用户指定的真实EML拆出正文、两份单页PDF（MBL/HBL）、一个宣传JPG。已用pypdf读取嵌入文本、使用捆绑Poppler渲染并逐页查看PDF/JPG。正文有H/C $50；MBL/HBL补充运输身份，两份提单并不各自新增一笔费用，宣传图无费用。现有原件未给这笔H/C提供唯一ISO币种，也未给独立账单编号；不能用目的港或另一张账单补USD，不能把提单号充成发票号。提单运费PREPAID不能自动证明这笔H/C的付款方式。SHA/TAR是原文简称，开发验证主体SHA不代表用户已确认真实法人。

扫描/部分可搜索PDF的指定OCR仍可能省略字段，本轮没有新增/声称完成视觉转录。相同标识字符串是可核验关联依据，语义角色仍由专家按原文解释；本轮回归与一次在线EML不是独立金标准确率或长材料性能评测。

定向测试先复现6项失败，修改后55项通过。新增防串单校验要求置信度“重复原件不加分”样例显式提供同单号关联，未放宽跨来源门禁。最终全量、真实任务与服务应用结果在下方更新。

首次在线验证进一步发现：本次指定OCR对两份PDF返回success=true但字段几乎全部为空（与此前响应不同），不能把服务成功响应等同提取完整。pypdf layout模式在原HBL仅返回938字符，普通模式读取1882字符，后者包含SSZSE26093128/OOLU4055331281/FREIGHT PREPAID/箱号/SHIPPER等字段。已新增原EML附件回归并先复现失败，随后改用pypdf普通模式的完整文本，原文件预览保留版式核对能力；未手写PDF解析器或静默修改已发布1.3.0能力。

最终代码全量384 passed、43 warnings、4 subtests passed，120.66秒，日志cross-file-pytest.txt/XML。未修改前端，本轮不重跑前端构建或把此前浏览器结果当本轮验收。服务无busy时以验证过的独立控制台Ctrl+C正常关闭后启动，最终PID37676；第二次重启前后19个线程ID及状态一致，数据库/Redis健康。原生服务检查见cross-file-final-server/restart-check报告。

首轮在线任务f96455a0-1d6e-4933-bb78-fed9c12bd72e采用中间能力31b49743ef337538dcc0，接入四来源/九块，输出一笔H/C50；只对已有原文$的币种歧义产生原生confidence_review中断，未代答或审批。18次模型/17次工具、活跃345.51秒；这是中间版原件结果，不算最终版时延。最终版任务2a500c84-4709-4363-adde-6ebad113c4c8采用50de789075b9c29458c7，单独记录在cross-file-eml-final-*。
