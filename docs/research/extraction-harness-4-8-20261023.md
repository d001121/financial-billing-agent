# 第4项抽取与第8项Harness：2026-10-23

本轮代码已修改；用户随后要求不再跑全量或批量真实模型测试，最终状态只做少量离线定向检查。下面的在线成绩属于修复前开发测量，不能作为修复后验收。

## MCP、Skills与官方组合

当前客户端为Codex desktop，使用其Codex CLI配置两项官方HTTP服务：`docs-langchain`为`https://docs.langchain.com/mcp`，`reference-langchain`为`https://reference.langchain.com/mcp`。两项均在CLI列表启用；本轮通过FastMCP实际发现工具并查询成功。原有别名保持原状。

已执行官方安装器`npx skills add langchain-ai/langchain-skills --skill '*' --yes`，项目`.agents/skills/`有22份有效SKILL.md，含ecosystem-primer、deep-agents-core、langchain-middleware等；本轮实际读取并使用这些Skill。没有安装另一套Agent运行器。

实现前查证：Docs MCP的`/langsmith/local.mdx`、`/oss/python/langchain/test/unit-testing.mdx`及文档提取/引用搜索；Reference MCP的`aevaluate`、`tracing_context`、`Document`、`add_messages`。实际版本：langchain1.4.6/core1.6.12、community0.4.2、deepagents0.7.30、langgraph1.2.16、langsmith0.14.11、rapidocr3.10.0。

实际组合仍为现有`make_graph`、LangChain create_agent主控、Deep Agents原生专家/Skills/Filesystem、原生retry/call-limit/HITL和检查点。离线评测使用同一图的builder及官方InMemorySaver；这不证明跨重启持久化。评分交LangSmith本地evaluate/aevaluate，不另写Agent循环或通用执行层。

官方Document/引用与状态合并能力不包含本项目的财务字段证据、同名费用行、明细金额或“省略/明确清空/换来源”语义；这些最小领域规则继续放在现有业务Skill。RapidOCRBlobParser未能通过Reference MCP取得对应符号；查过官方加载器文档和已安装community的原生parser源码后直接复用其接口，未自写OCR模型或引入视觉LLM。

## 实际改动

- `document-intake 1.8.0`：图片在指定远程OCR之后可通过原生RapidOCRBlobParser补全文。宿主默认开启，可用`IMAGE_TEXT_OCR_ENABLE=false`关闭；独立CLI默认不变。保存文字产物、哈希、帧、耗时与失败；远程失败时本地文字不能成为成功的权威替代。PNG原件确有USD，而远程结构响应漏掉了它。
- `document-extraction 2.2.1`：明确表头币种需独立真实引用、同名不同费用行保持独立、条件性罚款不作已发生费用、提单号不冒充不存在的账单编号。修正schema仍允许按航线推荐裸$币种的旧矛盾；Free/As arranged不能自行变成0。PDF整理表明确每行ref只引用Original row。
- `human-review 2.0.5`：同一charge_id且来源/单据/行身份未变化时，局部纠正保留省略字段；明确null仍清空。replace控制保留哪些行，不再隐式清空保留行的单据号。换来源/单据/行不会继承旧单号。人工锁/删除/拆分仍优先。
- `feedback-improvement 1.3.0`：旧关键字段评分补上单据号；新增完整行多重集合评分，分别报告完整行精确率/召回率、漏/多行、编号/费用/金额/币种/付款方式，拒绝同名误合并、币种错配与非数字金额。
- 修正既有合成映射标签中没有付款条款却断言PP的样例；明确继承既有PP/CC的两个场景仍保留。修正streaming夹具缺capability问题，没有放松生产检查。

配置为skills v31、agents v12、runtime v6。最终源码未发布到正式服务/未重启，历史能力与账单保持原版本。只读检查正式服务为64线程、0 busy，health为degraded；按用户指示不处理连接问题。

## 原件评测与边界

数据集：`backend/evals/datasets/original-extraction-dev.json`。原PDF页、PNG、EML全文及其两PDF和一JPG附件均已查看；固定输入与六份真实OCR响应的SHA256。预期为四个材料包、七条有数字金额的费用。

标注作者为编码Agent原件核对，未经独立人工批准，且原件参与开发；用途仅development_regression，不是独立最终金标，也不能推出总体准确率。

| 材料包 | 原件预期 | 修复前在线实测 |
| --- | --- | --- |
| Debit Note PDF2 | DC-108478；65、1310.40、35 USD；同名65/35分开 | 三行字段全对；币种引用误用无USD的费用行，证据校验拒绝 |
| General Notice PDF1 | 无独立账单编号；On Carriage Additional - US Em 245 USD | 字段全对；未把条件25/1100/150计费 |
| PNG Debit Invoice | ORFR1618731；WHARFAGE ADMINISTRATION FEE 5、WHARFAGE21.90 USD | USD已提到；后续局部纠正丢失reference_no |
| EML Pre-Alert | SSZSE26093128；Handling Charge50，裸$币种null | 正确50行保留；额外把Carrier Free H/C变成0金额行 |

四份的payment_term预期均为null：COD/C/PAY IMMEDIATELY及另一单据运费条款不等于这笔费用的PP/CC。EML两份PDF附件是提单，未印出另两笔数字金额费用；不能据附件数增加账单。

这次完整在线开发测量是2/4材料包字段完全匹配；不是全部通过。实际墙钟分别64.301、32.795、47.358、70.141秒，模型10/8/9/14次。全部缺调用方主体，故保留PENDING_REVIEW及真实主体中断，没有代答或批准。字段匹配分数不等于业务validation通过。

在线测量使用当前真实文本模型与原生图，但OCR为六份真实历史响应回放，远程OCR请求为0；不能称为新远程OCR端到端测量。正式冷OCR此前208.739338秒的回执仍是历史测量，本轮没有提速证明。

模型wire元数据确认实际请求`enable_thinking=false`且无图片输入。完成测量41次模型HTTP，middleware记录输入867858/输出20232 tokens（含上下文重复，不能直接当费用），另有首个中止探测6次请求；未计算服务商费用。用户要求停止后，没有再运行模型验证。

## 可复现入口与检查

`backend/evals/original_extraction.py`默认只离线解析及真实OCR响应回放；不调用模型。正式资产、数据库、Redis和历史任务不作为可写评测存储；复用既有FakeRepository和独立目录。标签不传给Agent。

```powershell
# 默认离线；也可只选一个材料包
.\backend\python.cmd -m backend.evals.original_extraction --case png-debit-invoice --prepare-only
```

真实模型入口需额外显式传`--online-model`且只能指定一个`--case`；省略case或批量都会拒绝。本轮不再执行它。

LangSmith0.14.11的异步_forward实际强制启用root tracing，首次upload_results=False仍尝试上传并返回401，故该次不能称零网络。最终入口组合原生Client(tracing_sampling_rate=0, auto_batch_tracing=False)与子图tracing_context(enabled=False,parent=False)，本地单例测试拦截所有client.session.request仍保留结果/评分，确认不请求LangSmith。没有修改环境密钥或排查认证连接。

实测回执：

- 原始在线测量：`backend/tests/reports/original-extraction-model-v2/report.json`及每份task/trajectory/receipts。它们保留旧能力4abf7b1828606a2d7b9d的真实失败，未改写成最终版本结果。
- 最终小范围检查：`acceptance-4-8-final-focused.xml`为8 passed/18 deselected（局部字段、换身份、拆分删除等）；`acceptance-4-8-small-checks.xml`为10 passed（评分器、本地无上传、版本一致、原生图片文字与远程失败）。均不调用真实模型/远程OCR。
- 较早定向35 passed；用户停止前全量离线600 passed/1 failed/4subtests，失败为空白图片新增非阻断诊断导致旧断言；已修正并单独复测1 passed。没有宣称修复后全量通过，用户要求后未重跑全量。

第4项补齐了实际发现的币种遗漏、编号丢失及语义约束；第8项有真实原生执行与可重复评分证据。最终在线回归、独立人工金标、长材料规模与20秒时延仍未验收。遵守当前预算，不把少量离线通过或修复前2/4写成最终准确率。
