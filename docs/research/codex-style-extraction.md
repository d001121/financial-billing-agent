# Codex式提取重构，2026-10-21

用户最新要求：抛弃之前约定的固定读取/核验规则，先对齐Codex处理材料的方法；本项目通过指定OCR代替图像查看。已实际重构主控、文档专家、检验专家与提取Skill，保留LangChain原生执行。

## 对照依据

读取的Codex会话是《整理 AR/AP 费用信息》，thread `01a15e87-95dc-7b20-a0a7-c2304a8cf1f2`。整段130.589秒包含等待用户补充；14条shell命令实际共6.967秒，另有3次图片查看。邮件一次解码、两PDF批量读取，短材料直接综合，没有固定九块覆盖或逐字段重复证明。会话中的SHA为用户授权假定，本项目验证时由调用方明确给定SHA，不能把它说成自动识别出的主体。

旧失败任务`7529697b-f43a-4cc1-9e9a-668f5cecf89c`约620秒、15次模型、14个工具节点，最终触发120图步骤的递归上限。模型约319秒、工具约300秒。已经读过短材料仍被九块coverage/引用重抄/跨来源证明阻断；一次save反馈60,171字符，任务存档576,963字节。图步骤包含middleware步骤，不能等同模型调用数。

## 实现

| 职责 | 当前行为 |
| --- | --- |
| 主控 | 自主选工具，短材料直接综合；长材料搜索定位并扩读；计划和委派按需使用 |
| 文档专家 | 处理具体复杂阅读疑点，避免重读整单和重复表示 |
| 检验专家 | 接收候选与具体问题，核对含义、重复费用和交易方向；有充分上下文可直接返回差异 |
| 单个document-extraction Skill | 分层说明格式/阅读策略，32,000字符内整包批量返回，长包返回清单交给原生grep/read_file或批量窗口 |
| PDF/图片 | 指定OCR返回文本；文字和版式只在有用时补读，成功读取复用 |
| 原文定位 | 阅读时生成稳定ref_id，保存时还原原始quote/offset/页或单元格，不让模型重抄布局文本和偏移 |
| 校验反馈 | 去重，仅返回最多12个实际问题，完整证据和检查保留在业务产物 |
| 完成 | 缺失或歧义保留null/说明，以completed_with_gaps结束；评分不再强制中断。用户仍可看原文并修改 |
| 存储 | 派发/计量读取投影；计数和计时锁行后在数据库内合并小字段，避免传输整个材料存档 |

移除了强制九块/coverage、每字段单独工具回读、固定plan、固定两个专家、PDF编号一律补layout、跨材料双侧身份证明门禁。保留真实引用、金额类型、实际服务失败、版本冲突和暂停检查。题目JSON字段、原件与历史产物仍保留。

使用官方create_agent、TodoListMiddleware、SubAgentMiddleware、SkillsMiddleware、FilesystemMiddleware、StateBackend、ToolRuntime/Command以及Agent Server运行/流式协议。没有新建Agent runner或搜索索引。模型工厂仍实际传enable_thinking=false。新任务graph_recursion_limit=512作为原生图步骤上限，共享24模型/64工具/1200秒预算未提高；这不是通过增加调用次数掩盖重复工作的措施。

本轮通过LangChain Docs与Reference MCP查证了上述原生能力，重点为skills渐进披露、native grep/read_file、CompiledSubAgent和ToolRuntime状态更新。原文引用映射、财务类型和本项目存储投影属于框架未提供的业务/基础设施适配。

## 验证与发布

仅定向测试，未跑全量：16 passed、1条已有langchain.mcp beta warning，7.16秒，见`backend/tests/reports/codex-reading-pytest.xml`。覆盖整包阅读、长材料原生grep/批量窗口、空文件/截断、真实偏移/伪引用拒绝、跨来源引用、反馈去重、主控完整保存并结束、按需检验委派、暂停重试检查、人工修改版本约束、实时启动协议与配置原生发现。

指定EML的既有四来源文字回放一次读全，所有引用逐条与原文偏移一致；没有为此重跑OCR。原生图测试使用合成模型响应，只证明真实工具与middleware调用路径，不证明在线模型准确率。

GaussDB真实回滚探针：1,350,000字节合成存档投影为127字节；投影读取0.0849秒、3次锁行合并更新共0.3818秒。存档和其他字段完整、过期revision被拒绝、事务回滚后合成记录不存在。见`codex-storage-probe.json`。这不是端到端耗时。

发布能力`87974856e3c7561e83cd`，skills配置v19、agents v10、runtime v3。document-intake1.6.0、document-extraction/evidence-linking/human-review2.0.0。旧快照未改写，既有任务未迁移。正常Ctrl+C关闭旧服务，启动PID40408；重启前后29线程ID及状态一致，GaussDB/Redis健康，见codex-restart-before/after.json。

实际在线验证仅新建一单`a0426ed0-218e-4a4e-b0fa-c5e92a605b4d`，材料复用用户指定EML，调用方主体明确SHA。官方运行success，执行116.027秒、排队0.743秒，5次模型/4次工具，无人工中断。三次指定OCR请求均HTTP200，四来源ready。最终1笔H/C、金额50、主体SHA、AP；裸$币种null，单据号/日期/付款方式null，以PENDING_REVIEW建议、completed_with_gaps任务状态结束。八项最终断言通过，见`codex-live-result.json`。

实际路径：intake_documents → save_document_extraction → save_document_extraction（修正）→ prepare_export → 最终回复。首次模型错误地把3份来源头信息也放进charges，并产生一个单据编号原文支持错误；经反馈自行移除这些候选和错误头字段，保留1笔真实费用。没有为了每字段重新读取材料或强制调用专家。这说明自主纠错实际发生，不代表首次提取已经全部准确。

工具回执耗时分别15.986、12.505、12.845、8.974秒，合计50.310秒，保存/最终核验仍有完整业务存储和检查开销。模型首次生成多余字段及再次修正也消耗时间。116秒是单个在线样本，不能证明所有材料都能达到120秒，更未达到20秒目标；未测长材料P50/P95或独立金标准确率。当前需求范围的Codex式阅读/调用重构已经生效，后续速度优化需针对上述实际剩余耗时。
