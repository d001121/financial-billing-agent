**2026-10-23 最新：置信度改为证据强度梯度，单号不再一律 100。** a5（Pre-Alert）的 `SSZSE26093128` 只由邮件主题支持；旧算法 supported=100、其他=0，故面板只有 0/100。`billing-confidence 3.1.0`：supported 基础 0.85，唯一位置 +0.05，结构化/表格单元格 +0.10（不依赖 `B/L NUMBER`、`MBL NO.` 等固定标签名），两个独立来源 +0.05；仅邮件主题/头部支持且字段应来自正文时 −0.45；ambiguous 0.40/0.30，矛盾 0.10，缺失 0。总分 `field_support` 组改为梯度 `70×(0.45A+0.35C+0.20N)`，100 需三个核心字段都满分且约束/覆盖组通过。`evidence-linking 2.1.3` 把 block 的 `kind`/table/cell 带入引用。`document-extraction 2.2.2` 删除从邮件主题 `PRE-ALERT <token>` 自动填 `reference_no` 的固定规则；单号取哪个号码由模型按材料判断，未提供则 null。a5 离线预览：单号 45 分、进入 review_items，总分 33→22.6。验证：billing-confidence **60 passed**、evidence+confidence **166 passed**、相关套件 **511 passed**、Vue 类型/生产构建通过。历史任务固定旧快照，新任务使用 skills v36；未重跑 OCR/Qwen，未改 a5 历史记录。

**2026-10-23 最新：金额“原文”不再包含相邻数量列。** 金额详情显示“原文 65.00 1.00”：版式财务行为 `rate 65.00 | quantity 1.00 | amount 65.00`，数字正则允许数字间空格，把 `65.00  1.00` 合并成一个无法解释的 token，面板原样展示。`evidence-linking 2.1.2` 改为：空白仅在三位分组（`1 234,56`）时并入同一数字，相邻列拆分；`pdf_layout_financial` 引用按列归属金额/单价/数量（金额取最后三个数字中的最后一个），只有本列能支持该字段，费率与金额相同不再触发“多个原文位置”；观察列表只显示所属列。skills v34。验证：evidence-linking **103 passed**、evidence+confidence **165 passed**、相关套件 **510 passed**。历史任务按固定能力快照继续显示旧结果，需新建任务才使用 v34；未重跑 OCR/Qwen。

**2026-10-23 最新：会话a1 重复费用行与预算耗尽修复。** 会话a1（`ebd6860a`，Debit Note）在 24 次模型调用后 `budget_exhausted`。原因是多次 `save_document_extraction` 以匿名或已失效的 `charge_id` 追加同一费用：同一来源出现 `ch_001..003` 与 `charge-...` 两套行，重复行使 `TOTAL_MISMATCH` 反复出现；同时占位 `document_id=doc_debit_note_001` 与真实 `dc-108478` 并存，把金额拆成两个 scope，重复 totals 也无法去重。`human-review 2.0.6` 在 `merge_extraction` 增加确定性同一性合并（同来源+费用名+金额+币种唯一匹配才复用已保存行 id；line/document 冲突不合并），保留 `document_id`/`line_id`；同一来源只有一个已知 document 时归一占位/缺失的 `document_id`；`save_document_extraction` 的匿名纠错按证据来源计数且只在无新 chunk 时计入 `repair_rounds`。skills v33。验证：human-review **24 passed**，skills/host/conversation/codex/version/config **508 passed**；a1 已保存数据离线回放得到 3 笔费用、1 行 totals、document 统一 `dc-108478`、`TOTAL_MISMATCH` 消失。未重跑 OCR/Qwen，未改 a1 历史记录；a1 仍为 budget_exhausted，需新建任务或由用户决定是否重跑。

**2026-10-23 最新：第4项抽取与第8项Harness修复（源码完成，最终在线未验）。** Codex已配置官方docs-langchain/reference-langchain并实测查询，官方安装器安装22个项目Skills。document-intake1.8.0复用原生RapidOCRBlobParser补图片全文，指定远程OCR仍必需；document-extraction2.2.1修正裸符号币种schema、表头证据、真实费用与条件/Free条款，保持单一提取Skill；human-review2.0.5修同一费用局部修订丢单号（省略保留、显式null清空、换身份不继承）；feedback-improvement1.3.0新增完整行多重集合评分并补关键单据号。skills配置v31/agentsv12/runtimev6。四原件开发标注7笔，未经独立人工批准；修复前真实模型+真实OCR历史回放仅2/4材料包字段全匹配，图片丢编号及EML额外0金额行如实留在回执。用户明确禁止后续全量/批量真实模型测试，随后只做18项小范围离线检查，全部通过；未跑修复后在线回归/全量，未声明总体准确率。评测入口默认离线，真实模型必须显式单case；修复LangSmith异步本地评测意外上传的配置，离线单例验证无LangSmith请求。正式服务只读64线程/0busy、health degraded，按用户指令不处理连接，不重启/发布新能力；历史账单保持原版本。详见[本轮记录](research/extraction-harness-4-8-20261023.md)，下文全量/旧能力/进程记录保留历史范围。

**2026-10-23 最新：会话6账单日期改为模型识别、代码只校验和提示。** 会话6（`30b702ca`，PDF1 General Notice）首次提取为 `document_date=10/19/2026`（抬头日期），但没有 `field=document_date` 的正文引用，`BILL_DATE_EVIDENCE_REQUIRED` 报错后模型把日期删成 null。曾尝试由代码按值自动补证据；由于同一单据印有 ETA、截止日、生效日、签发日，字符串匹配会把错误日期也补成“有依据”，属于用代码替代语义识别，已撤销。`document-extraction 2.1.6` 改为：日期缺正文引用时保留 error，并在 `date_candidates` 返回该值出现的原文行（source/anchor/quote，排除邮件头和结构块），提示模型补引用或改正日期，且明确不要因缺引用删除正确日期；已有日期引用但引用行未印出该值时记 `BILL_DATE_EVIDENCE_MISMATCH`（warning，不阻断）。日期值仍由模型判断；原文找不到该值时只保留原错误。skills 配置 v29。验证：extraction+版本 **59 passed**；会话6真实来源离线回放（读已保存 sources，不重跑 OCR/Qwen）日期保留、未新增证据、返回 3 条候选行；skills/host/codex/conversation/version/config **476 passed**。未修改会话6已保存结果，历史能力不迁移；需新建任务才使用 v29，或由用户在界面修订该单据日期。

**2026-10-23 最新：Redis 暂存 + GaussDB 阶段末持久化。** 任务状态改为写回缓存：`StagedRepository` 读取优先 Redis（未命中回源 GaussDB 并回填），`mutate`/`mutate_fields` 只更新 Redis 并加入 `workorder:tasks:dirty`；在工具调用结束、Agent 本轮结束、人工回复/待答问题、API 请求结束、启动时钟恢复和预算耗尽时 `flush` 一次性写回 GaussDB。新增 `Repository.replace` 做不读旧 payload 的全量写，并以 `app_objects.revision` CAS 防覆盖；Redis 不可用时自动退回直接读写 GaussDB；刷库失败保持 dirty 重试，版本冲突删除落后缓存；缓存 TTL 由 `TASK_CACHE_TTL` 控制（默认 3600 秒）。非 task 记录与审计事件仍直接入库。三处 I/O 修复：`check(..., policy_only=True)` 只读 `control/deleted_at/revision` 投影，需要返回任务的调用保持全量读取；`save_fields_fast` 用 `mutate_fields` 只改选中字段；`validate_and_store(task_id, task=...)` 复用刚保存的内存任务，`settle_saved`/`reconcile_saved` 不再重复整单读取。验证：新增 `test_repository_staging.py` **7 passed**；conversation/host/revision_feedback/task_deletion **126 passed**；`backend/tests` 全量 **243 passed、7 failed**，`backend/skills` **322 passed**；失败均与本轮无关（`test_improvement` 5 项使用 MemoryRepository，因 `payment_term` 规则收紧后评测样本仍断言旧值；`test_task_runtime_streaming` 2 项测试任务缺 `capability`，属既有夹具）。未重启后端、未重跑真实 OCR/Qwen；历史任务与已发布能力不迁移。

**2026-10-23 最新：金额合计范围键修复与窗口错误收口。** 会话5（PDF1 General Notice，245 USD）出现 16 次模型调用、5 次 `read_materials`、3 次 save。根因是 `validate_amounts` 将 `document_id=None` 的费用行与 `document_id=doc_1` 的总额分到不同 scope，产生假的 `TOTAL_MISMATCH`；模型反复读取 PDF/grep 查找差异，最后删除 totals。`billing-reconciliation 1.3.2` 在分组前归一 scope：同一来源只有一个 document 时，缺 `document_id` 的行使用该 document；`validate_amounts` 接受可选 `documents`，`reconcile_charges` 传入当前 documents。`document-extraction 2.1.4` 接受 `start_line=0`（按第1行），未知来源错误列出可用 source_id，行号错误带总行数。skills v27。验证：完整定向 **420 passed**（含金额 scope 正反用例、read_materials 窗口用例）。未跑全量 pytest、未重跑真实 OCR/Qwen；历史任务固定旧能力。

**2026-10-23 最新：intake 清单化与原生 ContextEditing。** `intake_documents` 只返回来源清单（来源、状态、行数、issues）和“用 read_materials 读取正文”的指令，不再展开完整正文；短材料由 `read_materials` 一次读取，只有 `mode=search` 才使用 `/materials/*.md` 的 grep/read_file。四单离线估算 intake 返回块从 9.5k–31.9k 字符降到 260–934 字符。intake 复用键补上 `OCR_RESPONSE_FORMAT` 与 `ocr_text_pointer`。`base_stack` 新增原生 `ContextEditingMiddleware` + `ClearToolUsesEdit(trigger=8000, keep=3, exclude_tools=('save_document_extraction','prepare_export','ask_user'))`，清理较早的 intake/read_file 输出、保留最近 3 条与最新校验结果；材料仍在 `/materials` 和任务产物中。runtime 配置升 v6（新增 `context_edit_trigger`/`context_edit_keep`），skills 仍 v26。验证：intake/host/config 定向 **101 passed**，conversation/host/codex/question-policy/version + 六个 Skill 目录 **372 passed**。未跑全量 pytest、未重跑真实 OCR/Qwen；后端未重启。

**2026-10-22 最新：四单结果复核后的确定性收口。** `document-extraction 2.1.3` 从同一来源原文修复缺失或错位的单据头证据（`DOCUMENT_EVIDENCE_REPAIRED`）；PDF B/L 只引用 embedded 但同一文件版式行印有该值时，补入版式证据并撤销 `PDF_IDENTITY_LAYOUT_REQUIRED`；验证器重算并丢弃旧的同类 issue，且对 issue 去重。`billing-reconciliation 1.3.1` 补全空格标题归一（`DEBIT NOTE`→`Debit Note`、`GENERAL NOTICE`→`General Notice`、`PRE-ALERT EMAIL`→`Pre-Alert`），从明确 `A pay B` 原文行补 `debtor=付款方/creditor=收款方`（不覆盖人工确认值），对 issue 去重；`valid` 只由 error 决定，info 不再强制 `PENDING_REVIEW`；`reconcile_saved` 使用本次 evidence-linking 的新 issues，不再沿用旧的顶层校验 issues。`human-review 2.0.3` 在主体已提供后同时清除 extraction 与顶层 `issues` 中的过时主体告警。宿主最终答复在 `validation.ok=false` 时前置“整单校验未通过（N 项错误）”。skills 配置 v26。验证：8 文件定向 **211 passed**（conversation/host/codex/question-policy/version + 三个 Skill），billing-export/billing-confidence/evidence-linking **161 passed**（合计 **372 passed**）；用四单已保存数据离线回放：会话1 `Debit Note`/AR/`CREATE`、会话2 `General Notice`、会话3 `Debit Invoice`、会话44 `Pre-Alert` 且 `creditor=TAR/debtor=SHA`，container 证据不再报错。未跑全量 pytest、未重跑真实 OCR/Qwen；四单仍固定旧能力，需新建任务才使用 v26。

**2026-10-22 最新：签发方水印守卫与角色回复确定性映射。** `document-extraction 2.1.2` 把命中 `Powered by`/`湃乐多`/`Pilot Aiship`/`Pai Aiship` 的 issuer 置 null 并记 `ISSUER_PLATFORM_VENDOR`（warning，原值保留在 issue），费用候选和 `documents` 都处理，页脚平台供应商不再进入主体候选。`billing-reconciliation 1.3.0` 允许单边关系确定方向：主体=已知 creditor → AR，主体=已知 debtor → AP，未知对侧保持 null；双方都缺失或主体不属于任一方仍 `POSTING_UNRESOLVED`；人工确认的 currency/creditor/debtor/payment_term 不再被自动 settlement 清空。`ReplyDecisionMiddleware` 对纯角色回复（“是收款方/付款方/AR/AP”）确定性写入 creditor/debtor 和 posting_type，多费用按 `review_request.charge_id` 或全部记录绑定，0 模型调用；`completion_question` 仅在缺对手方时追问具体付款方/收款方。skills 配置 v25。验证：`test_conversation.py`、`test_skill_versions.py`、billing-reconciliation、document-extraction 定向 **121 passed**（2 warnings），含图级“是收款方”提交 revision 2、全部 AR、无重复待答问题；`test_host.py`、`test_codex_reading.py`、`test_question_policy.py` **68 passed**，合计 7 文件 **189 passed**。未跑全量 pytest、未重跑真实 OCR/Qwen；历史任务能力不迁移，后端需重启后宿主 middleware 才生效。

**2026-10-22 最新：主体补充回到聊天内的人工审核。** 缺主体时先保存候选；保存后 `completion_question` 调用 pinned `human-review.entity_question` 打开原生 `conversation_review`，UI 显示聊天输入框和候选公司；用户回复后由既有 human-review Skill 应用 revision。已完成的 `completed_with_gaps` 任务在打开会话时也会自动打开同一 review；移除“补充记账主体”独立按钮。`AskUserPolicy` 仍禁止在保存前用 `ask_user` 阻塞。验证：conversation/codex/question-policy **56 passed**，host/planning/version **62 passed**；Vue 类型与生产构建通过（`AgentPanel-MRC0DFKO.js`）；后端已停止，未浏览器实测。

**2026-10-22 最新：PDF layout 财务行优先与 OCR/layout 冲突校验。** `document-intake 1.6.1` 从 layout 文本解析 `pdf_layout_financial`，Markdown 按财务行→版式→plain→OCR 排序；`document-extraction 2.1.1` 比较 OCR `chargeList` 与 layout 行，冲突记 `OCR_LAYOUT_CONFLICT`，候选金额只被 OCR 支持时升级为 error；财务字段只引用 OCR 时记 `PDF_LAYOUT_EVIDENCE_REQUIRED`。skills 配置 v24。验证：intake/extraction/version 定向 **105 passed**，排序修正后 extraction/host/codex **113 passed**，conversation **43 passed**，最终版本/新 layout 用例 **4 passed**；未跑全量、未重跑真实 OCR/Qwen。

**2026-10-22 最新：Skill 版本与过期测试收口。** 统一 `skills.yaml` / `SKILL.md` / `scripts/skill.py`：document-intake 1.6.0、document-extraction 2.1.0、evidence-linking 2.1.0、billing-reconciliation 1.2.0，skills 配置 v23；新增 `test_skill_versions.py` 防止三方漂移。更新 document-extraction CLI 的默认 `read_materials`/source 级覆盖断言，缺主体用例改为断言无 interrupt、`PENDING_REVIEW`；`human-review/SKILL.md` 同步“缺主体不自动追问”。验证：版本/CLI/缺主体/document-intake/human-review 定向 **83 passed**（2 warnings、4 subtests），`test_configuration` + `test_host` **95 passed**；未跑全量 pytest，未重跑真实 OCR/Qwen。

**2026-10-22 最新：题面标准自检后的四项修复。** ① EML 裸 `$` 不再猜 USD：`billing-reconciliation 1.2.0` 在匹配前执行 `settle_symbol_currency`（`field=currency` 引文只有符号且无 ISO 代码 → null + `CURRENCY_SYMBOL_AMBIGUOUS`）与 `settle_unbacked_parties`（creditor/debtor 未出现在自身字段引文 → null + `PARTY_UNSUPPORTED`），随后既有 `POSTING_UNRESOLVED` 进入复核。② 补 `H/C → Handling Charge` 映射并保留原始名。③ PNG 无主体不再阻塞：`settle_saved` 在“有候选、无 records”时先 `reconcile_saved`，保证 prepare_export 一定产出账单；新增原生 `AskUserPolicy`（`awrap_tool_call` 短路，Docs MCP 已查证）在主体缺失或无候选时拒绝 `ask_user`；`completion_question` 在调用方未给主体时不再生成实体问题。④ `document-extraction 2.1.0` 补回证据位置字段 schema（None 不落盘）、负/布尔偏移校验、PDF 单据号版式层校验（`PDF_IDENTITY_LAYOUT_REQUIRED`），chunk 覆盖测试改为当前 source 级契约。另按版式核对口径补三条确定性规则：`payment_term` 只保留有原文支持的 PP/CC，`C`/`COD`/`PAY IMMEDIATELY` 置空并保留原值；`document_type` 按印出标题归一（Pre-Alert / General Notice / Debit Invoice / Debit Note）；Pre-Alert 缺失 `reference_no` 时从主题 `PRE-ALERT <编号>` 提取并附正文证据；邮件声明的 MBL 与附件 B/L 不一致时记录 `IDENTITY_CONFLICT`（warning，两者都保留）。

验证：9 文件定向 **386 passed**（`test_host.py`、`test_conversation.py`、`test_question_policy.py` 与 6 个 Skill 测试目录）。真实任务：PNG `65786b80-7d3e-4936-b998-d4d39f15aef1`（主体未传）→ `completed_with_gaps`、2 条 `PENDING_REVIEW`（WHARFAGE ADMINISTRATION FEE 5、WHARFAGE 21.9，币种/主体/方向均 null，无中断）；EML `dd2ad064-a515-4a4a-90b7-b02676dd19fe` → 1 条 `Handling Charge` 50、`Pre-Alert`、`reference_no=SSZSE26093128`、币种/付款方式/方向均 null、`PENDING_REVIEW`。后端重启 PID38236。边界：PNG 的 OCR 响应 `PAI-ZIM-NOTICE` 没有任何币种、日期、签发方或接收方字段，不能凭空补 USD/2025-10-03；未跑全量 pytest；`delivery/harbor-bishi1-windows-x64.zip` 仍是 10-21 旧包，交付前需重打。

**2026-10-22 最新：人工回复实体句与首轮调用上限。** daca（1ea28489，线程 01a162ac）连续三次回复“本次记账主体是NEPTUNE SHIPPING LIMITED。”未生效。轨迹与模型探测确认：一次判定把该句判成 confirm，另一次返回 `apply` 但附带 `posting_type=null`、`payment_term=null` 两个用户未提及的字段；任务有 3 条费用时这些操作没有 charge_id，`apply_revision` 返回 `CHARGE_NOT_FOUND`，回复被记为 completed 但 `applied_revision` 为空，随后又生成同一个主体问题。修复：纯实体句（UI 候选点击生成的 `本次记账主体是X。` 或完整候选名）由宿主确定性解析并直接提交既有 human-review Skill，不调用模型；包含收款/付款角色、金额等混合语义仍交模型。模型返回的未提及 null 字段丢弃，只有用户明确说“没有/留空”才保留；多费用下缺少 charge_id 的操作给出“请指定要修改的费用：…”而不是 CHARGE_NOT_FOUND。runtime v5 新增 `run_model_calls=16`，与 `thread_limit` 合并在同一个原生 `ModelCallLimitMiddleware`（`exit_behavior=end`），单次运行到限后由 after_agent 保存并报告现有产物；旧能力无该键时按 `model_calls - turn_model_calls` 兜底。

验证：`test_conversation.py`+`test_host.py` 97 passed；`test_conversation`、`test_host`、`test_configuration`、`test_codex_reading`、`test_supervisor_planning`、`test_revision_feedback`、`test_workspace_views` 7 文件合计 **168 passed**。新增用例覆盖：多费用实体句图级提交（revision 1→2、0 次模型调用）、模型编造的 null 字段丢弃、显式“留空”保留、角色/混合句不被实体快路径误判、缺 charge_id 的明确报错、单次运行上限与旧能力兜底。后端重启 PID35420，`/api/health` 的 GaussDB/Redis 正常，`/complete-review` 路由仍在，线程 `01a162ac…`=interrupted、`01a1629f…`=idle。真实 daca 仍为 awaiting_input/revision 1，未代提交回复、未改真实账单；未做全量测试或真实 OCR/Qwen 重跑。

**2026-10-22 最新：完成审核与置信度面板稳定性。** 账单在审核后仍可保留空字段收口：`POST /api/tasks/{id}/complete-review` 现在接受 `completed_with_gaps`、`awaiting_review/needs_review/waiting_review/ready_for_review/review_deferred` 这些已提取状态，写入 `review_confirmation(decision=completed_with_gaps)` 并把任务置为 `completed`；处理中、待补充、有待回答 `review_request` 以及 revision 过期会被拒绝，重复提交按当前 revision 幂等返回。前端对应按钮在以上状态显示为主按钮，未提供字段保持 null。此前该路由只存在于源码、运行中的服务未注册（openapi 中缺失），本次重启后才真正可用。

置信度面板此前在 `records` 被下一轮提取短暂清空时整块卸载、随后又出现。`TaskWorkspace` 现在缓存最后一次非空费用列表，仅在任务仍在处理时用于保持所选费用和面板；`useConfidence` 改为请求序号控制，只允许最新请求发布结果，不再要求整个签名逐字未变（该条件会在费用频繁变化时丢弃全部响应，导致分数成批闪现）。

验证：`test_host.py` 54 passed（新增完成审核的已提取状态受理/幂等、处理中与待回答问题拒绝三项）；`test_conversation.py`+`test_workspace_views.py` 42 passed；Vue 类型检查与生产构建通过（`index-j8OiT12T.js`、`TaskWorkspace-Ctuquc9t.js`）。浏览器在 2024 的构建产物实测任务 1231（版本 2、63/100）：`完成审核` 为主按钮，置信度面板 6 个字段在 26 次采样/13 秒内未卸载；用过期 revision 探测路由返回 409 且未改数据。后端重启 PID 29228，`/api/health` 的 GaussDB/Redis 正常，线程 `01a1629f…`、`01a162ac…` 仍为 idle/interrupted，未代为点击完成审核或改动真实账单。未做全量测试或真实 OCR/Qwen 重跑。

**2026-10-22 最新：主体由会话确认，核对与证据合并。** 提交页移除记账主体输入，先读取材料并保存费用，再由账单助手询问公司；候选只取已保存文档/费用中的公司事实，点击填入聊天草稿，发送后才通过既有人审Skill生成新revision并重算AR/AP，可自填或暂缓，不自动指定主体。主动修改主体同样提供候选。缺主体的结束检查复用原生interrupt/Command及固定human-review2.0.2；旧快照不迁移。覆盖旧“缺主体可不问便结束”的交互约定，原件未提供的普通可选字段仍留null。

账单核对采用一张卡：费用表、所选费用置信度、原文及原件定位、修订入口；参考材料收在卡内，取消独立证据侧栏。展示合并重复原文，默认两处，其余展开，不改原始引用或评分算法。会话定向20项、Vue类型/最终生产构建通过（2501 modules、Vite1.03秒、index-D0ZuYs_R.js）；隔离真实原生服务+合成模型验证主体选择→回复→revision1到2→AP，未代答真实账单。skills配置v22，能力7f0d339560e7dc403618；正常重启PID35060，33线程ID/状态相同，GaussDB/Redis健康。未做全量测试、打包或真实OCR/Qwen整单重跑。详见docs/research/entity-choice-and-bill-review.md及entity-choice-*回执。以下记录保留历史范围。

## 2026-10-22 最新：题面逐项完善与管理功能实际验收

当前正式发布skills配置v21、能力c8279edbf4bf6046429c，document-extraction2.0.1/evidence-linking2.0.1/feedback-improvement1.2.0。Skill导入注册/资源/启停/移除、MCP新增/发现/真实调用/禁用、Hook执行和新增专家原生委派，以及费用映射标注导入→真实LangSmith对照评测→审核发布→新任务映射解析→回滚均有执行证据。Loop当前可发布范围是主体作用域费用映射；其他prompt/rule/Skill草稿未实现评测发布。修复邮件日期证据和不同invoice财务字段混用，保留无模板自主跨文件判断。

最后管理/改进21项通过；提取/证据17项通过；Office真实旧XLS/DOC转换和公式/预览验证通过。分批检查有重叠，不宣称全量总数；初始失败和对应最终回归逐项保留。最终Vue类型/构建通过（2501 modules、Vite1.13秒、index-qOZNjC0L.js），隔离管理页面操作及console无错误。正常Ctrl+C重启正式2024服务PID39940，33线程ID与状态一致，GaussDB/Redis健康，新管理API可用；未修改/回复/审批真实账单，隔离2025已停止。完整题面矩阵、官方MCP依据、回执和限制见[逐项核对报告](research/functional-audit.md)、[最后管理检查](../backend/tests/reports/control-management-last.xml)、[提取证据检查](../backend/tests/reports/control-extraction-evidence-final.xml)、[重启完整性](../backend/tests/reports/control-management-restart.json)。

真实识别准确率/误漏识率缺独立人工金标，长材料P50/P95和20秒目标未验收；7例合成费用映射实验不是OCR准确率。没有全量测试、打包或本轮真实OCR/Qwen整单重跑。以下记录为历史版本范围。

2026-10-22 会话布局修正：移除账单详情中残留的“补充记账主体”黄条，待补充问题在账单助手内作为消息展示；仅真实待回复/提交期间显示底部聊天输入框和“发送”按钮，继续使用既有原生中断与回复API。助手面板按视口固定高度（桌面上限640px、窄屏上限580px、最小360px），标题/输入区固定，计划、消息和问题在同一内部区域滚动；展开记录不改变面板尺寸。保留向上阅读和回到最新消息。Vue类型与生产构建通过（2494 modules、Vite1.12秒、index-DRqTUL6_.js），当前真实待回复账单的桌面/390px检查通过，无页面错误；只填写后清空测试文字，未发送、修改或审批账单，未做全量测试。截图与回执见backend/tests/reports/conversation-fixed-{desktop,mobile}.jpg、conversation-fixed-ui.json。前端dist已生效，后端无需重启。

2026-10-22 主控动态闭环：按本机 Codex 源码职责对齐。主控使用原生 TodoListMiddleware/write_todos 按轮规划与阶段更新，工具/子Agent结果交回主控验收，再决定补读、修正、委派、询问或结束；不增加自定义runner、强制工具选择或独立反思模型。codex风格的prepare_export不再return_direct，保存/最终工具返回实际verification评分与缺口；漏调最终工具时，既有TaskOutcome通过原生after_agent/jump_to=model回传未见核验，同revision再写入不能沿用旧回执。规则支持分不是统计正确率，缺信息不强制复核。40项定向测试通过（1 warning、12.29秒），未做全量测试、真实OCR/Qwen重跑或20秒性能验证。见docs/research/supervisor-dynamic-planning.md及backend/tests/reports/supervisor-loop-pytest.xml；服务状态见backend/tests/reports/supervisor-loop-restart.json。以下旧交互/进程记录保留历史范围。

2026-10-22 当前实现：账单处理采用Codex式会话，只有真实人工中断显示内联输入框；原生线程的主体/费用修改、拆分/删除及针对性复核入口转到会话，用户只需自然语言。原生HITL与middleware复用，字段修改交给现有human-review Skill，新revision后重新核验，不能默认批准。32项定向测试通过，Vue类型/生产构建通过（2494 modules，Vite0.961秒，index-BShsDezv.js）；隔离真实Agent Server+合成模型/材料/存储的浏览器验证两轮回复、revision1→3、刷新恢复、结束隐藏输入框及无审核弹窗。未做全量测试或真实OCR/Qwen语义复测。详见[会话审核架构与验证](research/conversation-review.md)、backend/tests/reports/conversation-pytest.xml及conversation-ui.json；当前进程/32线程保留见conversation-restart.json。以下旧表单及进程数字保留历史身份。
# 构建与验收记录

2026-10-22 最新：发送稳定与主体关系目标。账单助手不再按streamEpoch整体销毁；用户原话点击发送即显示，发送中禁用输入框、受理后隐藏已答问题，重接按官方Vue响应式threadId处理并保留最后展示投影。新轮通过REST runs显式input，真实中断仍resume，修复旧interrupt map造成的空跑与人工修订永久禁用。已有主体但当前财务Hook的POSTING_UNRESOLVED/CONFLICT尚未解决，结束边界进入具体关系问答；缺可选信息与明确暂缓不强制追问，置信度不是目标完成判据。新任务human-review2.0.1/skills配置v20，旧快照不改。31项定向测试通过（9.42秒，1 warning），Vue类型/构建通过（2495 modules、1.08秒、index-BYNGcjdS.js）。隔离原生服务+合成模型/存储、reply延迟3秒，验证立即回显、自动追问、刷新恢复、两轮修改revision1→3/AP及结束隐藏输入框；金额65与原件100的合成缺口保留，非整单财务验收。真实121d只恢复原待修订会话，未代答/审批/重跑真实OCR或Qwen。截图与最终重启状态见backend/tests/reports/conversation-goal-*，详见[架构及范围](research/conversation-review.md)；未做全量测试。

2026-10-22 金额原文小数位：121d（30722983-bd0b-4237-8657-42fd9bbe0eb6）保存raw_amount=245.0000，数值245；旧两位小数显示导致245.00。费用表及原件预览标题现在保留与当前值相同的普通十进制原文；不一致时显示当前值，缺值不使用旧原文填充。9项定向检查覆盖四位尾零、修改金额、零、负数、超过六位小数、无原文、无效原文与空值。Vue类型/生产构建通过（2495 modules，Vite969ms，index-Bv6FmwlO.js），真实页面费用表和预览均显示245.0000，revision仍为1。没有提取重跑、人工回复、修改账单或全量测试。历史模型消息保持原文。截图：[费用表](../backend/tests/reports/amount-source-precision-table.jpg)、[原件预览](../backend/tests/reports/amount-source-precision.jpg)。

## 2026-10-22 Harness人工反馈闭环

人工修订进入同线程Agent下一轮，真实中断/暂停/预算不足分别处理；确认字段、删除拆分、旧revision与正式审批/导出保护继续生效。成功解析与补读产物直接复用；启动失败可继续，API受理不能将快速完成回写成运行中。27项定向测试通过（1 warning、10.01秒），Vue类型与生产构建通过（2418 modules、Vite1.06秒，index-BCMdTNjk.js）。未做全量测试。服务正常重启PID42500，32个原有线程ID与状态一致，GaussDB/Redis健康。见[架构说明](research/harness-revision-feedback.md)、[定向测试](../backend/tests/reports/harness-feedback-pytest.xml)、[重启回执](../backend/tests/reports/harness-feedback-restart.json)。真实vsdv续跑回执为backend/tests/reports/harness-feedback-live.json，其结果与合成关系测试分别记录。

# 2026-10-21 最新：Codex式自主提取

已重构主控/文档专家/检验专家及单个提取Skill，取消九块覆盖、固定核验链和评分强制中断；短材料批量返回，长材料原生搜索定位，原文引用由工具恢复。新能力87974856e3c7561e83cd（skills v19、agents v10、runtime v3）已经发布。16项定向验证通过（7.16秒），真实GaussDB投影/小字段更新回滚验证通过，正常重启后29个既有线程状态不变，PID40408服务健康。仅跑一单真实指定EML：116.027秒、5次模型/4次工具、3次OCR请求200，最终1笔H/C50、AP、币种null，无人工中断，8项结果断言通过。首次混入单据头后自行纠正，20秒目标仍未达成。未运行全量测试。完整证据与性能边界见[详细记录](research/codex-style-extraction.md)；下文发布、流程及测试成绩均为历史范围。

## 实时执行过程链路修复（2026-10-21，覆盖下节仅模拟结论）

生产后台旧协议运行没有向Vue订阅提供原生工具/消息事件，导致用户只见等待提示。本轮已改为官方commands/run.start完整v2输出，并处理页面在首检查点前打开时的idle订阅竞态。保留reject及sync默认值；升级时须复核内部durability兼容键。19项定向回归通过、Vue类型/最终生产构建通过（2418 modules、1.07秒）。独立真实官方服务+最终生产Vue（模型/材料/业务GET为明确合成数据，协议帧无拦截注入）观察47条messages、2 started/2 finished、29次界面更新，验证无需手动刷新、回复逐步追加、展开工具更新、结束折叠与刷新恢复；390px无横向溢出、无页面异常。真实旧失败任务已确认停止转圈，显示停止摘要并保留14条既有调用。详见[查证与验证](research/agent-activity-streaming.md)、[真实回执](../backend/tests/reports/agent-activity-native.json)与[回归XML](../backend/tests/reports/agent-activity-streaming-pytest.xml)。

无busy时正常Ctrl+C重启当前服务，PID19252；28个既有线程ID/状态相同，GaussDB/Redis健康，[重启回执](../backend/tests/reports/agent-activity-restart.json)。没有全量测试、在线OCR/Qwen重跑或真实账单修改/审批/恢复。旧协议运行不转换，真实提取准确率及时延不是本轮结论。

## 智能体执行时间线（2026-10-21）

账单详情新增持续可见、可折叠的智能体过程：模型公开文本回复、工具调用与实际参数/返回、工具运行及错误状态、原生计划和子智能体独立过程。运行时展开，结束后折叠；工具详情按需渲染、长回复折叠、默认最近12条并可展开早期记录。原生人工补充表单位于折叠区外。命令面板仅显示真实命令工具的参数；当前后端没有因此增加shell工具，模拟execute不代表实际执行了命令。

已先查询LangChain Docs MCP的前端工具与子智能体流指南，以及API Reference MCP的useStream、useMessages、useToolCalls和SubagentDiscoverySnapshot；实际采用@langchain/vue1.2.5及其原生检查点/事件投影。自写范围仅为展示排序、中文标签和Vue界面，不自建SSE、工具装配或运行状态机。模型文本取AIMessage.text，reasoning内容块不显示；未更改模型调用或关闭思考配置。

`npm run build`通过Vue类型检查及Vite生产构建：2418 modules、1.10秒，入口index-CQrGcB1Q.js，AgentPanel-C1wSz1fy.js。独立浏览器使用本地拦截的合成HTTP检查点和官方v2消息/工具事件，12项定向检查通过、无pageerror；涵盖历史恢复、文本增量、工具开始/完成、实际命令参数展示、工具展开状态保留、专家作用域消息与自动收起、长回复/较早记录、人工中断持续可见及390px无文档横向溢出。[报告](../backend/tests/reports/agent-activity-ui.json)、[桌面](../backend/tests/reports/agent-activity-live-desktop.png)、[窄屏](../backend/tests/reports/agent-activity-mobile.png)。这些截图明确使用模拟账单，不作为真实业务识别结果。

未运行全量测试或真实OCR/LLM任务，未创建/修改/审批/恢复真实账单，也未删除材料。现有服务无需重启即可提供新dist；检查期间真实用户列表为空。真实长时间网络中断及多层嵌套专家的完整矩阵不在本轮验证范围。

## 工作台全选与删除（2026-10-21）

账单业务中心及待办列表增加行勾选、当前页全选、跨页全选当前筛选结果、取消选择、单条删除和批量删除。确认窗口列出目标账单，默认焦点在取消；批量部分失败逐条说明，成功项立即移除。删除采用deleted_at标记，不移除原始文件、Agent线程/检查点和管理员追踪，也不改业务revision、结果或审批。原生busy/pending/running时要求先暂停，历史线程/运行404允许清理，真实服务故障不能当作空闲。并发revision或运行标识变化拒绝删除，已删记录不能从用户端打开/恢复或通过原生工具继续派发。

定向执行`backend/tests/test_task_deletion.py`和`test_workspace_views.py`：20 passed、1条已有langchain.mcp beta warning、6.23秒，[XML](../backend/tests/reports/workspace-deletion-pytest.xml)。覆盖保留原件/版本/结果、幂等、旧选择冲突、运行保护、历史原生404、状态服务异常、并发恢复、用户列表隐藏及Trace保留。未运行全量测试、在线OCR或LLM。

最终`npm run build`通过Vue/TypeScript及生产构建，2411 modules、Vite971ms，入口index-UVLjoLSy.js。[模拟浏览器回执](../backend/tests/reports/workspace-delete-ui.json)覆盖12条模拟账单的分页/筛选全选、取消、单删、批量部分失败、刷新不复现、旧在途轮询不复现及390px移动端窗口；[桌面截图](../backend/tests/reports/workspace-delete-final-desktop.png)、[移动截图](../backend/tests/reports/workspace-delete-mobile.png)。所有浏览器写入均拦截在模拟API，没有修改真实账单。

真实GaussDB使用独立临时kind及强制回滚事务核验：较新的已删记录不占LIMIT名额，Trace默认查询仍能保留历史；合成行全部回滚。首次在线查询暴露openGauss对AND与JSON操作符的优先级差异，已用显式括号修复并重新验证。官方服务正常Ctrl+C重启加载新版，PID908；26个既有线程ID和状态一致、数据库/Redis健康、27条现存用户账单保持可见、DELETE接口已加载。[服务/数据库回执](../backend/tests/reports/workspace-delete-restart.json)。没有删除真实任务、原件或历史线程，没有变更Skill发布版本。

## 当前发布：文本 OCR 与 Markdown 定位（2026-10-21）

用户最新明确项目没有多模态。现已移除新版本提取包的read_image/read_pdf_page与view_source_image披露；原PDF按指定页切单页PDF提交题面OCR，不渲染图片给模型。图片按帧使用同一OCR接入；保存原页/帧、原始响应、Markdown与真实原文偏移。空OCR不当无费用，已有成功补读复用，单页成功不把旧多页失败洗成完成；旧能力及历史任务保持原样。

CAS发布skills v18/agents v9，接入1.5.0/提取1.7.0，能力7cd94124068b95ff201e；[发布回执](../backend/tests/reports/text-only-ocr-publication.json)。宿主同步原生StateBackend目录/按行回读，简单任务减少委派往返与重复正文/schema/证据输出；仍是一个提取Skill，全部来源都需检查。

本轮定向测试16 passed、2 warnings、7.26秒，[测试XML](../backend/tests/reports/text-only-ocr-targeted.xml)；另配置提示冻结/附件并发2项通过，[XML](../backend/tests/reports/markdown-config-targeted.xml)。响应均为受控合成；不表示在线识别准确率或20秒整单达标。按用户要求未跑全量、未完整重跑新版指定EML。长表逐行覆盖、真实语义角色及端到端速度仍按原验收待实测。

服务正常Ctrl+C停止并以相同官方入口选项启动，PID24616，数据库/Redis健康；25个既有线程ID及状态一致，[重启回执](../backend/tests/reports/text-only-ocr-restart.json)。第一次健康检查曾有数据库旧连接失效，重启后恢复。本轮没有新建业务任务、代答中断或审批真实账单。实现与参考会话比较见[研究记录](research/markdown-text-only-extraction.md)。以下章节均为历史发布及其验证范围。

## 当前发布及完整验证的未通过项（2026-10-21）

最新skills v17/agents v8、document-extraction1.6.4/human-review1.1.3，能力7e98a1650f2a80341eee；[发布回执](../backend/tests/reports/single-skill-warning-publication.json)。提取仍为一个Skill，没有任何格式包。完整验证进一步暴露schema把所有issues都判为失败：BILL_DATE_MISSING warning和NO_INVOICE_REFERENCE info也会触发HOOK_REJECTED。已先用测试复现失败，再将判定改为仅error拒绝（缺severity默认error），保留所有说明，不降级真实冲突。相关156项回归通过、2 warnings、29.87秒，[XML](../backend/tests/reports/single-skill-warning-pytest.xml)。纯Skill发布无宿主代码改动，不另行重启，历史任务仍固定旧能力。

最新版完整原EML验证实际在1.6.3能力e6d88ea2ed7e8fcd6dde下运行任务746914ee-4775-414e-acc4-68300058cba3，最终budget_exhausted/run error，24模型/24工具，活跃732.93秒、采集终点墙钟815.56秒；未重置预算。[完整结果](../backend/tests/reports/single-skill-final-eml-result.json)、[逐项断言](../backend/tests/reports/single-skill-final-eml-verification.json)均保留。

已核验：4来源/9块闭合、一笔H/C50、SHA付款/TAR收款、币种null/raw $、账单日期/编号/付款方式及邮件传输双方没有误填；两PDF均text/layout补读，原图实际查看，主分提单自身B/L、订舱及收发货人、金额与HBL原件定位正确。初次生成的空占位费用被校验拒绝并移除。未通过：HBL仍把EXPORT REFERENCES的OOLU4055331281写为明确master_bill_of_lading；最后证据Hook结果虽通过，但顶层evidence投影和仅币种中断流程没有完成，断言3项失败。不能将引用存在视为编号语义角色正确，也不能把运行到预算上限算成完整通过。

1.6.4仅针对已复现warning误阻断补修并通过相关回归，未再次跑整单OCR/Agent。剩余重点为编号语义、减少无效纠错/重复读取、共享预算与时延，最终真实验收尚未完成。没有修改真实账单、回复人工中断或审批；本轮未改前端、未制作交付包。当前服务PID42484，最后一次重启24个既有线程状态一致，数据库/Redis健康。下节为日期修正阶段的历史发布与验证范围。

## 日期归属修正及当时验证（2026-10-21，历史）

当前skills v16/agents v8、document-extraction1.6.3/human-review1.1.3，能力e6d88ea2ed7e8fcd6dde；[发布回执](../backend/tests/reports/single-skill-date-publication.json)。同一个document-extraction Skill内仍按清点→读取/补读→提取→全部材料比较→验证/输出递进选择；未增加任何格式Skill。沿用原生SkillsMiddleware、标准多模态工具和既有schema/evidence Hook，无额外循环。日期归属补充在原Skill，邮件头不能作为费用账单日期唯一依据，缺失仍为null，不新增人工补信息请求；用户已保存的明确日期修订保留，模型自报human_confirmed不能放行。

最后相关回归为155 passed、2 warnings、40.55秒，[XML](../backend/tests/reports/single-skill-date-pytest.xml)，覆盖提取、人审、宿主、配置与CLI。早先399全量及之后100/140定向均为历史验证范围，不能把它们相加或宣称本版全量重跑。未新增依赖、未改前端或制作交付包。

上版完整真实EML任务1f202de0-825c-4561-87cd-ad677234f311实际检查4来源、9块，产出一笔H/C50，SHA付款/TAR收款，currency=null/raw_currency=$；两PDF均主动补读text/layout，MBL B/L HZMHK331281、订舱4055331281、HBL B/L SSZSE26093128、收发货人均符合原件，HBL出口参考号没有伪装成明确主单号。原图经工具实际送达后由Agent确认宣传内容，无费用。证据回读valid=true，金额与HBL原件定位均成功，原生复核只有currency，未代答、修订或审批。[完整断言报告](../backend/tests/reports/single-skill-eml-verification.json)中仅no_fabricated_optional_fields=false：模型误把邮件Date写入费用document_date。因此该次不能标为全量原件验收通过。22模型/25工具，活跃558.64秒，采集终点墙钟649.83秒；不以本样例推导统计准确率或承诺时延达标。

该失败触发本版日期校验。原邮件的[定向真实模型报告](../backend/tests/reports/bill-date-scope-live-verification.json)实际1次模型、关闭思考：document_date/issuer/recipient均null，旧邮件日期候选被新校验拒绝；但裸模型仍把$猜成USD，原报告passed=false保留。随后复用既有evidence Hook的实际validate_evidence确认FIELD_VALUE_AMBIGUOUS硬阻断，[校验回执](../backend/tests/reports/bill-date-scope-live-guard-final-verification.json)无额外模型调用。不能把link_evidence仅定位成功当字段语义校验通过；最初验证脚本误用该入口的失败也保留。此为日期定向回归与币种门禁验证，**不是新版整单Agent/OCR重跑**；完整新版真实流程及时延优化仍待验。

最终正常Ctrl+C重启为PID42484，24个既有线程ID及状态不变，数据库/Redis健康，[重启报告](../backend/tests/reports/single-skill-date-restart-check.json)。历史任务及已发布快照未改。下节为上版发布与原图能力验证范围。

## 单Skill递进读取与原图检查（2026-10-21）

当前发布skills v15/agents v7，document-extraction1.6.2，能力9bf7eb03b9aafc32824d；[发布回执](../backend/tests/reports/single-skill-vision-publication.json)。提取仍为一个Skill，SKILL.md安排递进步骤，references按需加载，原生工具提供PDF正文/版式补读与图片查看，不新增格式Skill或Agent循环。工具接收任务source_id，原图通过标准多模态ToolMessage传给文档Agent；帧、hash、转换和传输回执独立保存，传输不等于识别。

相关回归140 passed、2 warnings、56.15秒，[XML](../backend/tests/reports/single-skill-vision-pytest.xml)。qwen3.8-max经同一模型工厂关闭思考，分别通过用户图片与工具图片两次真实探测，均辨认为宣传横幅且未见费用；报告为[source-image-model-probe](../backend/tests/reports/source-image-model-probe.json)和[source-image-tool-model-probe](../backend/tests/reports/source-image-tool-model-probe.json)。这是开发能力探测，不是独立准确率或全流程验收。当前未增加依赖，沿用之前pip check成功记录。

正常Ctrl+C关闭旧PID41596再启动PID28076，[重启核对](../backend/tests/reports/single-skill-vision-restart-check.json)中23线程ID及状态不变，数据库/Redis健康。未回复或审批历史任务，旧能力不迁移，未改前端、未重建交付包。

上轮真实任务5682145c-538b-48c5-ba10-09ebc36f56b2最终awaiting_review、17模型/20工具、活跃453.03秒。MBL B/L、订舱及HBL B/L已修正，但仍有图片覆盖未完成、2处EVIDENCE_UNREADABLE及出口参考语义问题，未通过完整原件断言；[保留结果](../backend/tests/reports/adaptive-extraction-eml-v2-result.json)。新的指定EML开发任务1f202de0-825c-4561-87cd-ad677234f311正在独立验证，结果另补。下节为上轮发布范围。

## 单个提取 Skill 递进读取（2026-10-21，最新）

最新发布skills v14/agents v6，能力e371ce97eb6401be6056；document-extraction1.6.1、human-review1.1.2，其他版本见[回执](../backend/tests/reports/adaptive-extraction-role-publication.json)。普通PDF文字派生的运输编号必须提供对应字段的版式引文；此检查不自动替换成某个期望编号，也不保证语义必然正确。完整回归[最终日志](../backend/tests/reports/adaptive-extraction-final-pytest.txt)实际399 passed、44 warnings、4 subtests passed，232.15秒；其后最后的修复合并逻辑由[100项定向测试](../backend/tests/reports/adaptive-extraction-role-final.txt)覆盖，未宣称400项全量已跑。

首轮原件任务d0a1b46e-8b96-4d05-9e24-240c4c9c22f8主动补读两PDF正文，但误把图片送PDF工具而中止。宿主改用原生ToolException/handle_tool_error=True后，正常Ctrl+C重启PID41596，22线程状态不变，数据库/Redis正常；同一开发任务从检查点恢复，预算保留8模型/10工具起点，无需重跑OCR。最终17模型/21工具、活跃476.92秒，只有币种中断，但MBL/HBL角色仍错误，原件断言失败。该结果保留于adaptive-extraction-eml-v1-result.json，不算通过。新版5682145c-538b-48c5-ba10-09ebc36f56b2重新验证，结果将在结束后补充。

按用户纠正保留document-extraction一个提取Skill，不新增格式Skill。SKILL.md安排清点、按需读取、提取、全部文件比较、验证/统一输出；references提供格式策略、跨文件作用域和输出合同，Agent使用原生资源/工具选择步骤。read_document_sources只接收当前任务来源和text/layout/原页/原因，不接受任意路径；补读不重复OCR，保存原页/hash并同步intake，重建全材料chunks。未接入的提交文件及遗漏来源不能通过覆盖检查。唯一逐字引文可自动重新定位；重复引文不随意选第一个。

完整后端命令 `./backend/python.cmd -m pytest backend/skills backend/tests -q --junitxml=backend/tests/reports/adaptive-extraction-pytest.xml` 实际398 passed、44 warnings、4 subtests passed，228.48秒；[日志](../backend/tests/reports/adaptive-extraction-pytest.txt)。定向7项通过，包括原EML中MBL列关系、指定原页映射、hash变化拒绝、补读保存和全部材料分块。`pip check`实际No broken requirements found，requirements.lock.txt已刷新。langchain-community0.4.2/pdfplumber0.11.10固定安装；社区集成包的停止主动维护警告保留，未将其作为Agent编排层。

CAS发布skills v13、agents v6，能力d2bcb79a60b6e3bcaac2；[回执](../backend/tests/reports/adaptive-extraction-publication.json)。旧任务及已发布快照不修改。本轮未改前端或制作交付包，真实新EML的运行和字段结果另列下方，不以离线回归替代。

更新：2026-10-21。最新单Skill验证见上节；下文374/361及更早成绩保留历史范围，不相加为独立用例或准确率。用户已明确先做需求，暂不处理交付包。

## 条件复核、主体提交与完整表单（2026-10-21，当前版本）

已有提取字段分数严格低于配置阈值才触发原生人工中断，默认80；未提供字段和缺少可选算术/总额不算低置信度。有原文但无法解释的金额/币种仍需定向复核。正常结果自动核验结束，auto_review和人工approval分开保存；缺少财务必需信息保留completed_with_gaps可编辑结果，禁止正式导出，不能将其伪装为成功账单。用户仍可随时查看六字段、分数、提取原文、原件定位并修订。修订重算当前版本、失效旧核验，不重复OCR。官方能力及业务边界见[实施记录](research/conditional-confidence-review.md)。

主体弹窗区分运行中、策略拦截和真实版本冲突；提交前读取最新版本，检测所改字段，真正冲突在窗口内对照并明确选择保留输入。不会将所有409永久锁成不可提交。更多信息按每项费用纵向分组，弹窗可滚动、按钮可达。

| 验证 | 实际结果 |
| --- | --- |
| 全量后端 | `./backend/python.cmd -m pytest backend/skills backend/tests -q --junitxml=backend/tests/reports/conditional-review-pytest.xml`：374 passed、43 warnings、4 subtests passed，126.21秒；[TXT](../backend/tests/reports/conditional-review-pytest.txt)/[XML](../backend/tests/reports/conditional-review-pytest.xml) |
| 原生Agent中断 | 隔离存储及固定模型HTTP，实际create_agent、interrupt、Command和检查点；低分金额中断、过期答复再中断、更正恢复不重新提取、after_agent最终核验、缺字段不转人审、自动核验直接导出均覆盖。不是本轮真实模型/OCR准确率 |
| 前端构建 | vue-tsc及Vite成功，2411 modules、Vite1.10秒，入口index-bXBaz-K0.js；[日志](../backend/tests/reports/conditional-review-build.txt) |
| 主体页面提交 | 明确合成任务9c05b673-f550-42dc-b88c-a114891bcf7a，模拟预算耗尽且缺主体；浏览器补充Synthetic Client后revision1→2、AP、completed，auto_review=automatic、approval=null，模型调用保持24次，正式导出按钮启用；[结果](../backend/tests/reports/conditional-review-browser-result.json) |
| 页面完整性与原文 | 实际查看真实历史任务的纵向更多信息、主体弹窗填写/取消；字段未横向截断，提交按钮可达。点击50.00打开mail/body并显示对应50及原件下载入口，定位为邮件内容块。真实账单未提交、未审批；[页面报告](../backend/tests/reports/conditional-review-ui.json)，截图为conditional-review-fields.png、conditional-review-entity.png及conditional-review-source.png |
| 应用与持久化 | 最初Stop-Process重启被自动策略拒绝且未执行。随后核实独立控制台及无busy，改用Ctrl+C触发正常关闭；15秒等待曾超时，随后确认进程/监听退出才启动新版PID36640。重启前后18个线程ID及状态无差异，[核对](../backend/tests/reports/conditional-review-restart-check.json)；数据库/Redis健康 |
| 版本发布 | skills v8/runtime v2，能力3d1f75d53d4d20188672；[发布回执](../backend/tests/reports/conditional-review-publication.json)。旧release未改，历史任务不自动迁移 |

本轮没有代用户确认真实账单、提交财务系统或调用OCR/在线模型；合成任务明确标记并保留验收记录。原生低分复核的后端恢复已运行，浏览器低分表单的端到端恢复、完整窄屏/键盘/并发交互矩阵仍未全验。未制作交付包。

## 用户核对收敛为六字段（2026-10-21，上一轮前端）

应用 `design` 与 `stop-that-shit change`。仅调整用户展示与交互；取消内部问题收件箱、原始校验页签、问题数量和扣分/阻断重复列表，默认表格只保留 AR/AP、单据编号、费用名称、金额、币种、付款方式及置信度/修改操作。其他业务字段在“更多信息”，修订中的交易双方与日期默认折叠。处理中及部分候选结果不提前要求最终核对或确认，真实原生补充表单保持挂载。缺少非必填单号/付款方式不增加错误。

最终 `npm.cmd run build` 退出0，vue-tsc和Vite通过，2411 modules、Vite 1.15秒，入口 `index-Pjg7CCsV.js`。浏览器记录见 [bill-review-ui.json](../backend/tests/reports/bill-review-ui.json)，六字段截图 `bill-review-six-fields.jpg`。实际验证100分和24分历史合成账单、真实在途任务的部分提取展示、原生历史中断、修订表单打开/取消、原件窗口与未审批正式导出禁用。本轮未提交账单修订、审批、回复或发布配置；后端规则、Skill快照和评分结果未更改，未重跑后端全量。没有将界面简化视作绕过财务校验。

框架依据复用并实际复核 Docs MCP 的 `frontend/structured-output`、`frontend/human-in-the-loop` 和 Reference MCP 的 `@langchain/vue.UseStreamReturn`：`isLoading`期间显示处理中，真实`interrupt`独立展示，保持官方订阅/恢复；安装版本仍1.2.5。这里只修改业务状态和已有评分的展示，没有新建Agent执行层或财务算法。

## 面向业务用户的页面重构（2026-10-21）

前端已拆成工作总览、独立大屏、账单业务中心、待办复核、独立材料提交、账单详情和管理中心；能力配置与经验规则各有管理子页。使用 `design`、`stop-that-shit change`，原生Vue订阅/中断组合先经LangChain Docs/API MCP复核。最终 `npm.cmd run build` 退出0，包含vue-tsc与Vite生产构建，2408 modules，Vite构建段1.71秒。

在实际生产 `/app/` 完成浏览器检查，记录为 [user-workspace-ui.json](../backend/tests/reports/user-workspace-ui.json)：

| 路径 | 实际核验 |
| --- | --- |
| 总览、大屏、业务中心 | 真实任务摘要、状态分布、主体分布与任务创建量；大屏可返回总览，列表搜索、分页和返回详情后筛选保留 |
| 待办与独立提交 | 复核页清除无匹配搜索仍留在复核页；提交页实际展示材料/主体表单，本轮未提交任务 |
| 费用与原文 | 欧洲合成任务显示两条EUR费用、100分；1234.56点击后打开mail/body内容块。确认入口可见，未审批版本正式导出禁用；未点击确认 |
| 人工补充 | 历史中断3676a55e09e11d5d196a6bb08e5b0e48在执行记录折叠时，问题与回复表单仍可见；未回复或恢复 |
| 管理 | 能力页显示skills v6及八包，MCP分区可打开；经验页读取历史候选和builtin-v1；未保存配置或发布规则 |
| 主要窄屏与失败状态 | 390×844的总览/列表/详情无页面横向溢出，菜单Esc关闭及焦点回归；仅测试标签临时阻断API后保留16项旧快照并提示断连，解除后重试恢复；临时网络/viewport设置均已清理 |

最终构建无新增浏览器应用错误。构建中旧标签曾引用已被清理的旧hash懒加载文件，刷新后恢复，报告保留该历史错误。截图为报告同目录 `user-workspace-*.png`；旧工作台截图不代验新版。本轮没有创建任务、调用模型、修订、审批、正式导出或回复历史中断；详情GET沿用既有sync路径，可能同步已有任务状态。全部视口/键盘/超长表格/订阅交错及断线矩阵仍未全验，后端算法及交付包未改。

## 无模板海外提取与融合v2（2026-10-21）

参照文章的OCR与语义提取、标准化、业务核验和人工反馈策略，本轮不采用固定供应商模板，不按国家猜数字或币种，也不采用文章匿名案例百分比。详细来源、官方MCP依据、唯一职责和限制见 [研究记录](research/global-extraction-confidence.md)。

配置经CAS从v5升到v6，能力 `0dd7d9b036a29571747e`；document-extraction1.3.0、evidence-linking1.2.0、billing-reconciliation1.1.0、billing-confidence2.0.0。新任务固定新快照，历史不迁移，发布回执为 [global-confidence-publication.json](../backend/tests/reports/global-confidence-publication.json)。

原文解析统一在evidence包：合法欧洲、印度、Unicode数字和负数，单分隔符三位歧义、币种作用域及真实位置；保留raw值、候选及偏移。普通All/try等词不因模型选择币种而变为ISO依据。金额/币种/费用名无支持或有歧义会使审批及正式导出422。金融规范化和算术仍在财务包，confidence只消费当前revision事实。

v2为 `70×(0.45A+0.35C+0.20N)+20×max(0.5L,T)+10V`：字段来源支持、一致性和覆盖三组，算术与总额取max，重复引用不加分。缺数量单价/总额不重归一化，也不按固定模板判无效；高分仍需明确确认且不能覆盖硬错误。分数未经独立金标校准。

全量命令为 `./backend/python.cmd -B -m pytest -q -p no:cacheprovider --junitxml=backend/tests/reports/global-confidence-pytest.xml backend/tests backend/skills`，最终 **353 passed、43 warnings、4 subtests passed，220.45秒**。警告仍为依赖MCP/LangSmith beta及ast.Str弃用，未扩大依赖。原始 [TXT](../backend/tests/reports/global-confidence-pytest.txt) 与 [JUnit](../backend/tests/reports/global-confidence-pytest.xml) 均保留。覆盖国际格式、畸形token、币种误读、歧义、不真实操作数、总额复用、相同Word单元格不同anchor、折扣规范化、旧revision、CLI及真实API批准/导出门禁。

[9例差分](../backend/tests/reports/global-confidence-comparison.json) 为确定性合成已知答案：欧洲/印度/阿拉伯数值由旧版拒绝改为支持；歧义1,234由旧100可快捷确认改为48.5且硬阻断；模型自填操作数从95改为80建议核对；费用token复用总额失去额外奖励。模型/OCR调用0，无关宿主检查明确使用成功fixture；不能称为独立金标准确率。

前端已通过vue-tsc/Vite构建，SSR验证保存的v1及新v2字段均能显示；增加核验状态、缺依据原因、原文和候选值。

新增真实Qwen任务使用上述v6快照和正常官方Agent Server路径，无OCR、自动批准或真实记账；报告及明确合成断言为 [global-confidence-online.json](../backend/tests/reports/global-confidence-online.json)。

| 合成材料 / task | 终态与核验 | 调用与时延 |
| --- | --- | --- |
| 法英混合邮件、欧洲数值；`b67c94f8-bd37-4c0a-b6a4-33c2b0fc6b3f` | run success、ready_for_review；2条CREATE/AP，1234.56及65.44 EUR，原文总额1300；无单号/数量/单价仍校验通过、支持度100、可显式确认，保持未审批 | API受理1.371秒；21模型/18工具，活跃365.668秒 |
| 裸`$1,234`；`6fd55af7-6dc5-441c-aee7-f0cd7068fdb5` | run success、awaiting_review；保留raw，amount/currency为null，1条PENDING_REVIEW、24分；实际批准和正式导出均422，revision仍1且无审批 | API受理2.894秒；19模型/16工具，活跃325.139秒 |

原生校验反馈曾使欧洲材料初次猜测偏移无法回读，后续关联工具按真实原文重新验证并形成有效引用；未放宽校验接受错误偏移。歧义样例没有替用户猜数值/币种，也未代答历史中断。两份材料均由本轮明确编写并用于功能回归，不是独立真实金标；有限时延仍高，不能宣称提速或P50/P95达标。评分为确定性纯函数，未增加评分模型请求。

浏览器已实际显示欧洲费用100分、无操作数原因、总额通过与三组评分，点击金额打开原邮件并定位mail/body内容块；此EML定位为块级，未宣称金额坐标或像素框。歧义费用显示24分、待复核、空金额及待确认币种；保留修订入口。前端错误日志为空，未点击确认或人工改值；记录为 [global-confidence-ui.json](../backend/tests/reports/global-confidence-ui.json)，截图为 [评分](../backend/tests/reports/global-confidence-score.jpg)、[原文](../backend/tests/reports/global-confidence-source.jpg) 和 [复核](../backend/tests/reports/global-confidence-review.jpg)。

历史保护按全部14个既有task完整对象哈希与2146个已发布文件逐项比较，均未变化；仅新增上述2任务和51个新能力文件。见 [global-confidence-history.json](../backend/tests/reports/global-confidence-history.json) 及同前缀before/after报告。原题OCR、真实长材料、独立全球金标与生产强恢复继续保留待验；本轮未制作交付包。

## 历史Office/v5、置信度与原文复核（2026-10-21）

本轮功能由业务 Skill 提供，宿主仅接线。XLS/XLSX保留工作表/行/单元格、隐藏/合并信息、公式与缓存；缺缓存通过项目内LibreOffice实际重算。DOC实际转换为DOCX；Word按原内容顺序保留段落、嵌套/合并表格与分页提示，可生成绑定转换版本和PDF哈希的只读版式。合成二进制OLE文件及格式答案在 [office fixtures](../backend/tests/fixtures/office/README.md)，不冒充原题真实财务金标。

历史v1 `billing-confidence`使用六项组件40/25/15/10/5/5，供旧快照和以下历史验收使用；当前v2见上节，不重算旧任务。v1的90分也不代表90%正确率。必需Hook否决即使没有issues也会阻断；停用human-review不能继续人工写入。

Vue提供置信度明细和来源抽屉；金额点击定位Excel真实单元格，重复值仅行定位。Word可在派生PDF版式和原结构之间切换；PDF只有真实页映射及唯一文本上下文才高亮金额，无坐标时不伪造框。支持从抽屉进入原有修订，原件独立保留；用户可直接确认当前版本，无须先逐项打开预览。审批绑定revision，修改后重算并使旧审批失效。

首次真实Qwen合成在线验证见 [office-confidence-online.json](../backend/tests/reports/office-confidence-online.json)：DOCX两条费用50/20 USD、原文总额70，23次模型/20次工具、310.677秒活跃，业务ready_for_review；XLSX同额两条提取后24次模型/22次工具、354.990秒活跃，最终说明阶段被预算拦截，业务budget_exhausted。原快照均保留，没有用后续规则重算历史结果。两次观测不是P50/P95或独立准确率测量。正常同值的整行引用误扣分与重复todos调用已据此定位，后续版本另验，不能把这两次结果描述成全部通过。

第二批真实OLE旧格式在线验证固定v4能力：XLS两条费用、100分、无校验错误，17模型/14工具、247.102秒活跃；DOC两条费用被 `TOTAL_VALUE_UNSUPPORTED` 误拦，20模型/17工具、383.992秒活跃。该问题来自同一总额引用只标amount时未复用其中明确的USD，并非原文缺币种；已由evidence-linking 1.1.2与billing-confidence 1.0.2限定在同一总额的已回读引用中修复，显式冲突和跨范围取证仍拒绝。document-extraction 1.2.1同时修复Word整数cell在人工修订后重新校验的类型兼容。配置经CAS发布为v5，能力 `3eb8bfbc62c9d4f41004`；修复前任务保留，修复后另建在线回归。

最终v5在线回归已结束，均关闭思考，无新增OCR请求、审批或真实记账：

| 合成材料 / task | 真实结果 | 调用与活跃时间 |
| --- | --- | --- |
| 二进制DOC / `4308cb47-178b-419a-9c69-e7239c71e5aa` | run success、ready_for_review；两条CREATE/AP，50/20 USD；规则支持度100、无校验错误 | 20模型 / 17工具，425.392秒 |
| XLSX / `a7de4cd4-087f-456d-aada-4cdaa2013cda` | run success、ready_for_review；两条CREATE/AP，50/20 USD；规则支持度100、无校验错误 | 18模型 / 15工具，246.782秒 |

实际响应、固定样例断言、能力版本和调用记录保留在上述在线报告的 `final_regression_tasks`。这是短合成样例的端到端功能验证，耗时仍偏高；不能据两次运行宣称长材料性能、P50/P95或独立真实业务准确率达标。

浏览器完整闭环记录在 [office-confidence-ui-final.json](../backend/tests/reports/office-confidence-ui-final.json)，任务 `bcc84dbf-6915-4faf-baa7-d216804a9426` 明确为合成固定答案，不冒充模型抽取：R1为100分，未打开原件即可直接确认；金额50→60生成R2，60分，旧审批清除，仅出现 `LINE_ARITHMETIC` / `TOTAL_MISMATCH`，批准请求返回422；原件仍50，预览明确提示找不到当前60，不错高亮其他值。改回50生成R3，恢复100分和有效校验，重新确认成功，审批绑定R3。模型/OCR调用均0。金额点击定位Word派生PDF第1页及真实内容锚点，Excel Charges第3行D3定位另有截图。早期 [office-confidence-ui.json](../backend/tests/reports/office-confidence-ui.json) 保留旧schema错误复现，不能用新结果回写。

最终回归期间新增的能力目录独立发布；此前2094个快照文件的整体内容清单哈希保持不变。三个受保护历史任务的revision、checkpoint、消息及原中断比较见 [office-confidence-before.json](../backend/tests/reports/office-confidence-before.json) 与 [office-confidence-after.json](../backend/tests/reports/office-confidence-after.json)，均未代答、续跑或重新审批。

自动化报告：[office-confidence-pytest.txt](../backend/tests/reports/office-confidence-pytest.txt)、[JUnit](../backend/tests/reports/office-confidence-pytest.xml)。本轮未新增OCR在线请求，原题OCR结果仍以原报告为准；未制作或迁移交付包。长材料现有能力、具体瓶颈和优先优化项见 [performance.md](performance.md)。

## 已有实现

- 官方 Agent Server / FastAPI 后端，LangChain `create_agent` 主控、原生 Todo 计划和两个专职子 Agent。
- Vue / TypeScript 工作台、官方 `@langchain/vue` 流订阅，以及随包可运行的生产 `dist/`。
- 八个独立业务 Skill、十一类统一管理的 Hook、MCP 配置与工具调用、能力版本快照。
- 原生人工中断、费用修订/删除/拆分、乐观并发控制、当前版本审批和题面 JSON 导出。
- 共享模型/工具/活跃时间预算、有界纠错、SQLite 检查点、GaussDB 业务记录与 Redis 缓存。
- 已获准启用的华为OBS自动上传和临时签名下载，document-intake 1.2.0保留真实题面orderChange响应映射；SDK固定为esdk-obs-python 3.26.6。
- 主体范围的费用映射候选、固定合成评测、人工发布与回滚；其他规则/提示词/Skill 候选保持草稿。
- 项目内 Windows x64 Python 3.13.16 与实际依赖，`backend/python.cmd` 和 `start.cmd`；完整包与迁移结果见 [便携交付](portability.md)。

## 本轮按职责重构

`backend/` 直接作为 Python 包，不再嵌套 `src/backend/`。主控、文档专家和账单专家归 `agents/`，框架组合归 `middleware/`，宿主工具归 `tools/`，校验归 `hooks/`，MCP 连接归 `mcp/`，能力与 Skill 版本归 `extensions/`，共享派发/预算/计时归 `harness/`，HTTP 路由归 `api/`，模型/仓储/资产/检查点归 `infrastructure/`，配置归 `config/`。八个业务包仍在 `skills/`；Vue 独立位于 `frontend/`。

官方入口为 `backend.agents:make_graph` 与 `backend.api:app`，检查点入口为 `./infrastructure/checkpoints.py:checkpointer`。本轮不改写历史业务 revision、审批、检查点、原始响应或已发布 Skill，也不续跑人工中断。本轮结果见 `backend/tests/reports/responsibility-tests.txt`、`responsibility-configuration-tests.txt`、`responsibility-runtime.json` 和 `responsibility-after.json`；以下旧报告保留历史身份。

## 自动化与构建

本轮全量回归可从仓库根目录复现：

```powershell
.\backend\python.cmd -B -m pytest -q -p no:cacheprovider backend/tests backend/skills
```

全量结果为 **163 passed、43 warnings、4 subtests passed（68.90秒）**，原始输出为 [responsibility-tests.txt](../backend/tests/reports/responsibility-tests.txt)。随后修复prompt_file非法形状处理，相关配置、事务与主控定向回归 **40 passed（28.73秒）**，输出为 [responsibility-configuration-tests.txt](../backend/tests/reports/responsibility-configuration-tests.txt)；两批有重叠，不能相加为203个独立测试。

项目外工作目录的私有运行时、原生扩展和OBS离线签名检查通过，pip check通过，记录为 [responsibility-runtime.json](../backend/tests/reports/responsibility-runtime.json)。最终官方Server已启动，`/ok`、`/api/health`、`/app/`、`/api/samples`全部200；三个历史任务保持原checkpoint、19/9/17条消息、原中断、revision 1与control值，未新建或恢复Agent运行。

旧EML原件仍为1,479,995字节，SHA-256 `fad3298ec8fd3da0e092dfbed0a313be28170073f1e01125195a5dfe9b886e58`；已批准导出200、两条CREATE/AP、数字金额20/50，新OBS待补充任务导出422、0条正式records。1166个skills/releases文件及.env哈希不变。核验沿用原有GET导出行为，更新了last_export与审计回执；报告显式记录该事实，没有新task、revision或run。最终状态报告 [responsibility-after.json](../backend/tests/reports/responsibility-after.json) 的 `passed=true`。本轮没有调用在线模型或OCR，没有更新ZIP。

### 上一轮前后端目录集中的历史结果

新结构工作区已完成 **161 passed、43 warnings、4 subtests passed（30.93 秒）** 全量回归，`pip check` 与项目外运行时/SDK 离线签名通过。以 `backend/` 为工作目录启动的官方 Server 四个 HTTP 检查均为 200，健康为 `ok`，4 份原题样本可列出；三个历史任务的 checkpoint、消息数和原中断保留，旧 EML 原件哈希不变，已批准导出仍为 200/两条 CREATE/AP（20、50），OBS 待补充任务导出仍为 422，没有新建运行或恢复中断。 证据为 [pytest-structure.txt](../backend/tests/reports/pytest-structure.txt)、[pytest-structure.xml](../backend/tests/reports/pytest-structure.xml)、[structure-before.json](../backend/tests/reports/structure-before.json) 和 [structure-after.json](../backend/tests/reports/structure-after.json)。 完整候选ZIP另已通过迁移验收，见下文。

目录调整前的结果为 **161 passed, 43 warnings, 4 subtests passed in 28.81s**，退出码0。原始报告：[pytest.txt](../backend/tests/reports/pytest.txt)、[pytest.xml](../backend/tests/reports/pytest.xml)。当时的OBS候选包从迁移目录运行同范围回归，结果为 **161 passed, 43 warnings, 4 subtests passed in 41.16s**，退出码0，原始输出为 [app-portability-obs-tests.txt](../backend/tests/reports/app-portability-obs-tests.txt)。4个subtests按原报告单列，不与161个测试直接相加。警告包括MCP/LangSmith beta与依赖的 `ast.Str` 弃用提示。

覆盖Skill独立CLI、格式读取与切片合同、证据/覆盖/金额/匹配/更新/AR/AP、人工修订、共享预算、重试派发拦截、原生Skills/MCP调用、配置事务、并发快照发布、资产路径迁移与恢复保护。此前新增OBS签名/失败/guard、旧快照桥接、响应映射及缓存隔离等合同。配置验证与事务专项29项已包含在161项内，不重复累计。

官方SQLite conformance的 **58个必需基础检查通过**，报告为 [sqlite-conformance.json](../backend/tests/reports/sqlite-conformance.json)。这些在完整回归中的一个测试内执行，不能另加到161项。

`pip check` 返回 `No broken requirements found`。`backend/requirements.txt` 保存直接依赖，`backend/requirements.lock.txt` 为实际环境 freeze。前端 `npm run build` 已通过 TypeScript/Vue 检查和 Vite 生产构建；依赖固定于 `frontend/package-lock.json`。

## 真实模型与原题接入

Qwen真实请求已成功，请求体实际传递 `enable_thinking: false`；GaussDB和Redis已实连。OBS上传/签名下载与题面OCR的真实请求结果见下文，健康检查不代替这些业务证据。

| 材料与任务 | 实际结果 | 边界 |
| --- | --- | --- |
| 合成 Excel，`abab67c9-2fe2-44fe-a416-6dbd92058b26` | 原生规划、委派、提取、核对，2 条正确 CREATE/AP，50 USD + 20 USD；当前 Revision 1 已人工批准，正式导出成功 | 主体 Demo Trading Ltd，无 OCR；不能代表原题准确率 |
| 原题EML旧任务，`29c0ae9b-f792-4b53-b1f8-2423e72d852f` | 邮件正文与JPG、2 PDF附件共4来源；正文 `$50` 候选曾被标为USD，当前不能视为币种已确认；原生中断请求附件OCR URL | 保留原快照、历史报告及awaiting_input中断，未静默迁移或代答 |
| 原题EML新任务，`edfd9e4f-a0a7-4aa5-9349-07eb29169cc1` | 正文、JPG及两份PDF共4来源均ready，附件真实上传200并保留回执；正文TAR H/C金额50候选的currency/creditor/debtor均null，原生ask_user要求确认 | 演示主体Demo Trading Ltd；业务awaiting_input，未回答或批准，正式导出HTTP 422、0条正式records |

Excel 使用 22 次模型请求、19 次工具派发、187.39 秒活跃时间；首次已验证证据回执距任务创建 62.05 秒。完整记录在 [online-synthetic-task.json](../backend/tests/reports/online-synthetic-task.json)，已批准 JSON 在 [synthetic-bills.json](../backend/examples/synthetic-bills.json)。这是有限样本，不能报告为任务 P50/P95。

新EML线程为 `01a15bf2-5d1a-7697-bd77-ea28c619036e`，固定能力快照 `3beca02d6c12ae032e2c`；原生中断为 `3676a55e09e11d5d196a6bb08e5b0e48`。实际14次模型、12次工具、163.155237秒活跃时间；框架run_status为success，但业务仍awaiting_input。原文 `SHA pay TAR：H/C $50` 不足以确认币种和收费双方，正式导出由schema/amount/posting/approval校验阻断。附件结构化响应的chargeList为空，保留空结果及原件，不能据此保证无费用。完整证据见 [obs-agent-task.json](../backend/tests/reports/obs-agent-task.json)。skills配置已按期望版本经CAS发布为v2，document-intake为1.1.0；旧任务继续原能力，不混入本轮指令。

### OBS与指定OCR的真实样本

用户已明确将OBS开关改为true。自动发布直接使用华为官方SDK，不修改ACL；签名在请求临派发时生成，默认有效3600秒。上传回执保存对象key、内容哈希、字节数、ETag/request_id及原页/帧，不将凭证或签名URL放入任务/模型参数。

| 原题材料 | 实际请求与映射 | 观察到的服务费用字段 |
| --- | --- | --- |
| 图片示例.png | 首次上传200、签名下载200且SHA256一致，题面OCR 200，OCR耗时12.329秒；初次未映射保留partial。后续复用该真实响应，按orderChange映射ready，没有再次在线请求 | WHARFAGE ADMINISTRATION FEE 5.00；WHARFAGE 21.90 |
| PDF 示例账单2.pdf | 实际上传/签名下载哈希/OCR均通过，单页传输，结构化映射ready；下载与OCR请求段31.744秒 | HANDLING CHARGE 100.00；4 ADD'L DETENTION FREE TIME CHARGE 1310.40 |
| PDF示例账单1.pdf | 实际上传/签名下载哈希/OCR均通过，传输原页范围1–3，结构化映射ready；下载与OCR请求段45.816秒 | On Carriage Additional - US Em 245.00 |

首次真实原始证据为 [obs-ocr-real.json](../backend/tests/reports/obs-ocr-real.json)，保留当时的 `partial/ocr_response_unmapped`。后续PDF在线及PNG原响应回放的映射结果为 [obs-originals-ocr.json](../backend/tests/reports/obs-originals-ocr.json)，明确标注 `real_ocr_call` 与 `original_response_replay`。这些是有限样本时延，不构成OCR P50/P95或负载结论；表中金额是服务返回字段，尚不能作为独立人工财务金标。

真实响应为 `success=true`、`data.list`单据对象，adapter逐项保留原JSON键值为 `ocr_structured` 块，保存 `/data/list/<index>` 引用；它没有提供可视为原件逐字转录的完整文本。`page_index/pages_split`尚未核实为物理页/坐标，不据此赋页；单页传输片才依据真实映射设page，三页文件只保留页范围。币种、交易方或财务方向缺失继续复核，不因来源ready推断可入账。

每次intake创建新的UUID产物目录，防止跨任务/重试覆盖原始响应；缓存纳入响应格式、文本pointer、能力版本与非秘密OBS身份。内部上传/OCR前guard复用暂停、revision与Skill/必需Hook启停检查，不把SDK内部HTTP另算独立工具调用；它不撤回在途请求。本轮未覆盖全部在途失败、签名过期、断电及远端未知结果矩阵。

## 人工、扩展与改进闭环

浏览器真实交互已验证：金额 50 改为 51 后生成新 Revision，触发 `LINE_ARITHMETIC` / `TOTAL_MISMATCH` 并阻止正式导出；改回 50 后通过校验。第二浏览器持旧 Revision 提交返回 409、保留输入，没有覆盖新版本。原生 todos、工具、专家及嵌套中断可见，断开/重连后保留同一中断。

原生 Skill 发现、正文读取、工具披露、MCP stdio 工具实调及禁用后的派发阻断均有宿主测试。配置采用 schema、交叉引用、期望版本及原子写入；无效配置保留旧版本。任务发布固定 Skill 内容快照，在途任务不自动切换指令。必需 Hook 集合当前固定在 `backend/hooks/registry.py`，尚未实现完整可配置业务 profile；不能声称任意 Hook 类型都能仅靠 YAML 注册。

合成反馈候选 `candidate-5c5293d634e844452840` 经明确 opt_in 创建，将 `Document Charge` 映射为 `Documentation Fee`，适用主体 `Demo Trading Ltd`。实际本地 LangSmith 评测 baseline 5/7 → candidate 7/7，浏览器人工发布 `v-7b94d50f56172a55` 后回滚至 `builtin-v1`；当前有效版本为 `builtin-v1`，审计保留。固定 final 样例已用于该候选，其他候选不得复用为独立最终证据。该结果不是 OCR 或整体抽取准确率。

浏览器细节及接口见 [ui-design.md](ui-design.md)，原生组合与最小适配依据见 [implementation-evidence.md](research/implementation-evidence.md)。

## 恢复与性能

正常停止重启整 Server，以及在无在途外部操作时强制结束自己的 Server 进程后重启，均保留上述两任务的 checkpoint、消息、todos、批准状态或同一中断 ID，预算未重置。缺检查点恢复请求返回 409，不创建空运行。报告为 [restart-before.json](../backend/tests/reports/restart-before.json)、[restart-after.json](../backend/tests/reports/restart-after.json)、[server-force-restart.json](../backend/tests/reports/server-force-restart.json)。

这是稳定检查点上的进程终止验证；未覆盖断电、未刷盘新线程、OCR 在途或结果未知的远端副作用。GaussDB、SQLite 与 dev 元数据没有跨存储原子事务。详见 [recovery.md](recovery.md)。

每路由预热后顺序采样 10 次、并发 1：任务列表 HTTP P50/P95 为 209.83/231.28 ms，单任务详情含官方 state 为 600.32/857.96 ms。原始样本与测量边界见 [performance.md](performance.md)。未据此推导前端事件到达、任务受理、暂停生效或长材料并发达标。

## 用户与控制台分离、EML材料包（2026-10-21）

- 用户中心以一次提交的一份账单为单位，展示单号、主体、交易方、各条金额和具体待办。使用官方线程批量查询核对中断后，3份历史等待人工的任务不再被旧数据库processing掩盖。详情置顶原生回复表单与问题收件箱，全部结构化业务字段改为表格，金额可以打开原文定位。
- 右上角控制台提供独立管理导航，Skill/工具、经验规则和Trace均能打开。真实Trace读取16份提交：3份有人工作业修订（18.75%，界面18.8%）、3份当前待补充、4份曾确认；历史确认不代表当前revision有效确认。调用路径来自官方检查点，耗时来自已有工具回执，原题邮件路径及document-specialist委派已查看。
- 准确率、误识率、漏识率为null，界面注明未关联金标，不用置信度代替。页面分离未新增账号/RBAC；调用路径明确当前检查点范围，不声称完整专家span树。
- extraction 1.4.0按材料包提供全部来源/父关系/chunk清单及有界共享邮件原文，每批附件获得相同上下文；skills v7、agents v2已CAS发布，能力摘要 `347e46bf7361cfe776d0`。旧任务不迁移、不重评分、不代答。浏览器实际打开旧邮件正文与3份附件清单及MBL PDF原件；本轮没有重跑新版真实EML，不作为提取准确率提升证据。
- 后端全量361 passed、43 warnings、4 subtests passed（126.29秒），报告 [bill-workspace-pytest.txt](../backend/tests/reports/bill-workspace-pytest.txt)及同名XML。其后新增14块跨批共享邮件上下文用例，与5项投影测试6 passed、1 warning（7.86秒）；不宣称新增后的362项全量已执行。最终前端类型检查及构建通过（2411 modules、Vite 1.05秒）。
- 浏览器验收 [bill-workspace-ui.json](../backend/tests/reports/bill-workspace-ui.json)覆盖桌面用户/管理导航、全部字段表格、100分直接确认入口与未审批导出禁用、24分问题收件箱、金额定位mail/body、历史中断表单与附件预览、390×844列表/详情及菜单。未执行审批、修订或回复。原文为块级定位；无对应页证据的PDF不伪造金额高亮。测试标签关闭、临时视口恢复，用户标签展示新版。

## 尚未完成的验收

| 项目 | 当前条件与后续验证 |
| --- | --- |
| 原题完整财务结果与OCR异常矩阵 | PDF/图片/邮件附件已完成真实基础接入；仍需逐字段人工核对、缺失币种/主体处理，以及全部服务业务失败、在途故障和未知结果恢复验收 |
| Office 转换器移机及真实业务金标 | 项目内 LibreOffice 已实际转换合成二进制 OLE DOC/XLS；公式重算及Word PDF渲染离线通过。新转换器尚未移机，真实业务Office金标仍需独立核对 |
| 长 PDF、跨页 Word、TIFF 与旧表格的真实材料 | 已有合成读取、切片与完整性测试；仍需真实材料和人工标准答案核对漏行、重复及跨页语义 |
| 最终独立真实金标 | 目前合成评测不替代按单据家族隔离的真实最终集；未宣称总体准确率 |
| 完整负载与长任务体验指标 | 已有有限单次OCR耗时；尚未完成任务受理/事件到达/暂停生效、三任务并发、OCR P50/P95、长材料内存峰值与吞吐测量 |
| 生产部署与强恢复 | 当前为本机单实例 dev；未完成多实例、断电零丢失及未知外部副作用恢复验收 |

T01–T33各步骤的完成和待验状态见 [最终开发计划](superpowers/plans/2026-10-21-final-development-plan.md)。材料仅按用户授权上传指定OBS并提交OCR；未发送交付邮件、公开发布业务原件或执行真实财务记账。

## 上一轮目录集中后的完整应用迁移（历史）

新结构完整候选包已在中文空格目录、项目外工作目录通过迁移验收：161 passed、43 warnings、4 subtests passed（61.19秒），运行时/原生扩展/OBS SDK离线签名/pip check/真实MCP均通过；四HTTP全200、健康ok，三个任务的checkpoint/消息/原中断保留且未resume，旧EML原件哈希及已批准两条CREATE/AP（20、50）导出一致，.env未改、在线模型请求0。报告为 [app-portability-structure.json](../backend/tests/reports/app-portability-structure.json) 和 [app-portability-structure-tests.txt](../backend/tests/reports/app-portability-structure-tests.txt)。解包目录为 `backend/.build/迁移 空格-80a1e622/`，项目外工作目录为 `backend/.build/app-portability-4fab7cbf05d141028edf90fe65576234/outside cwd/`；基线优先采用包内 `backend/tests/reports/structure-before.json`。

已验候选为 `backend/.build/structure-candidate-v2.zip`，103181917字节，SHA-256 `81c666aaedf6fe4514287c09c34d21c292423fccc9ca61ccc9e9ccb967591260`。该候选哈希不等于最终包哈希；当时的标准名交付包已收录该阶段文档和报告，信息以 `delivery/harbor-bishi1-windows-x64.package.json` 为准。迁移Server PID38080已结束，2025无监听，原件、任务状态和验证日志保留。Windows PowerShell 5.1直接接收接口返回的顶层JSON数组，已核对导出为两条记录。真实DOC、长材料、独立真实金标和生产强恢复等未验边界保持不变。

## 目录集中前的完整应用迁移（历史）

目录调整前OBS候选完整ZIP曾解包到 `.build/迁移 空格-2e9fd76f/`，包含实际 `backend/bishi1/`、OBS SDK、前端dist、源码、配置、.env、原件和检查点；从项目外目录 `.build/app-portability-f8cb14aafcd0497c8d5899f0cb73e37f/outside cwd/` 执行私有运行时、SDK离线签名、依赖检查、真实MCP stdio及全部回归。结果为 **161 passed, 43 warnings, 4 subtests passed in 41.16s**，各项退出码0。

| 已验候选包信息 | 结果 |
| --- | --- |
| 文件 | `delivery/harbor-bishi1-windows-x64-candidate.zip` |
| 字节数 | 102877154 |
| SHA-256 | `c8e08c09c4018042d718961be9e446b221ec2421c9b3759bc93ddb1848563a78` |
| 原始报告 | [app-portability-obs.json](../backend/tests/reports/app-portability-obs.json)、[app-portability-obs-tests.txt](../backend/tests/reports/app-portability-obs-tests.txt) |

迁移后的官方Server在2025端口启动，`/ok`、`/api/health`、`/app/`、`/api/samples`均返回200，业务健康为ok。合成Excel、旧EML和OBS新EML三个任务的同一checkpoint、消息数及各自原中断状态均保留，均为 `Resumed=false`，没有提交恢复命令。旧EML原件回读返回200、1,479,995字节，SHA-256仍为 `fad3298ec8fd3da0e092dfbed0a313be28170073f1e01125195a5dfe9b886e58`；已批准任务正式导出返回200，保留两条CREATE/AP、金额20和50，没有发起新的Agent运行。

验证脚本退出0，`Passed=true`；`backend/.env`未修改，在线模型请求为0。日志目录为 `.build/app-portability-f8cb14aafcd0497c8d5899f0cb73e37f/`；自行创建的迁移Server PID 39040已停止，2025无监听，根项目2024服务仍返回200。上述哈希只对应已验候选包，最终标准名重包信息见 [便携交付](portability.md)。这是当前Windows x64机器上的目录迁移验证，不替代另一台机器、真实DOC转换程序迁移及外部服务的完整部署验收。

OBS接入前的 [app-portability.json](../backend/tests/reports/app-portability.json) 继续保留为140项回归和两个历史任务的迁移证据，不改写为其他批次的161项结果。真实DOC、长材料、独立真实金标和生产强恢复等未验边界保持不变。
