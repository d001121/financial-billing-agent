---
name: document-extraction
description: 自主阅读整包航运材料，综合正文和附件提取账单字段；短材料批量读，长材料定位扩读，疑点按需OCR或核验，保留可定位原文引用。
metadata:
  version: "2.2.3"
  include_tools: "read_materials read_document_sources save_document_extraction"
---

# 阅读材料并给出账单建议

理解用户目标和已有上下文，选择有帮助的操作，不把下面的说明当固定流水线。

## 推荐过程

1. 新材料先 `intake_documents`；已有成功材料直接复用，不重复接入。
2. 阅读正文和附件，抽出费用候选及原文引用。
3. **先 `save_document_extraction` 保存全部已读费用候选**（通常一次；主控用 `finalize=true` 同时取得证据、金额等校验，专家按获准工具范围保存）。不要逐行调用保存，避免在尚未交齐同一单据的费用/总额时消耗纠错轮次。没有保存候选之前，不要先询问记账主体或 AR/AP，也不要假设调用方能修改还不存在的字段。
4. 候选保存成功后，主体由宿主打开的原生 human review（conversation_review）核对；收付款关系等材料无法确定的信息再用 `ask_user` 询问。
5. 用 `prepare_export` 读取当前 revision 的实际校验并结束；以产物和校验为准。

如果人工回复要求修改字段但还没有候选：先按第 3 步保存候选，再回到回复应用修改，不要直接拒绝或结束。工具报错时先读本 Skill 和错误信息，修正参数或换合规工具重试；不要原样重复失败的调用，也不要因为一次错误就放弃任务。

保存时如果某个引用被拒绝，只按错误纠正一次；仍无支持就留 null 并一句话说明，不要枚举全部 ref，也不要在回复里复述试错过程。每个文件的 `bill_of_lading` 用该文件自己印出的 B/L/Document No.；`EXPORT REFERENCES` 或别处的主单号不是该文件的 B/L 标签，不能把 MBL 号码写给 HBL；找不到该文件自己的号码就留 null。

- 新材料先intake_documents。所有格式形成干净Markdown，短材料直接随工具返回，通常不需要再读文件；长材料留在`/materials/`，用原生grep（字面搜索）和read_file定位，也可read_materials一次读取多个窗口。目录和截断信息会说明还有什么可读。
- 比较邮件正文和附件，理解费用、付款关系、运输编号及不同单据。第一份读到答案后仍参考其余材料；不按附件数量生成账单。资料少就直接读完，长资料围绕表头、明细、总额和跨页续接扩读。不要登记九块或其他固定数量的coverage。
- 本项目没有多模态。PDF有文字层时，财务字段（费用行、金额、币种、数量、单价、单号）优先读`page:N/layout/financial`，其次`page:N/layout`；`page:N/embedded`只用于条款/正文。`ocr_structured`只用于图片/扫描页或交叉核对；OCR与layout冲突时以layout为准，不能把OCR合并的100.00覆盖layout的65.00+35.00。PDF/图片文本不足时，用read_document_sources(method="ocr", source_ids=[...], pages=[...]/frame=...)补读；OCR结构化空字段不代表看到了整张原图；不能确认的内容直说未知，不反复调用同一失败路径。
- 提取真实费用行。原件没有的字段null；有冲突先核对角色和上下文，再判断能否解决。费用名不要混入收款方；`A pay B: H/C $50`表示费用H/C、金额50、A付款B收款，裸$不能唯一确定币种。不要把运输日期、运费条款自动借给另一笔费用。
- 表格整理列可能带入同页表头的币种，`ref_id`只引用其对应的真实原文。费用行未印币种时，另用同一单据中明确印出ISO币种的表头/合计行引用支持`currency`；不能把该费用行引用同时声明支持币种。图片补充全文同理，币种/日期/编号各自引用实际印出它们的行。不要因OCR结构字段为空就忽略原文明确给出的值。
- 单据编号取本单据的Invoice/Reference等真实编号；只有提单号而无账单编号时，`reference_no=null`，提单号放`bill_of_lading`。邮件主题里的PRE-ALERT、订舱等编号不自动等于账单单号，须按该邮件正文和附件的实际标注判断。条款中的条件性收费、取消费、设备罚金和承前转后/合计不是已经发生的独立费用；同名的不同实际费用行仍须分别保留。
- `Free`、`As arranged`等非金额条款不能自行转成0金额费用；仅原文明列数字0的实际费用才记录0。专家已经保存的候选由主控读取并核验，修复时复用原charge_id；省略的字段表示沿用，明确写null才表示清空。
- `document_type` 用原文印出的标题（GENERAL NOTICE / DEBIT NOTE / INVOICE / PRE-ALERT），不要用OCR的fileType代号。`payment_term` 只填原文明确写出的 PP/CC；`C`、`COD`、`PAY IMMEDIATELY` 不是PP/CC，保留原值并留空。签发方/接收方没有原文名称就null，不用发件人、页眉抬头或系统水印顶替。
- 账单日期有值时标明正文的document_date引用；邮件Date只是传输日期。同一份单据会印多个日期（ETA、截止日、生效日、签发日），只能选本单据自己的账单/签发日期，不能选运输节点。原件没给账单日期则留null，不能用邮件时间填满。校验返回`date_candidates`或`BILL_DATE_EVIDENCE_MISMATCH`时，先核对候选行或引用行是否确为账单日期：是则补引用，不是则改值；不要因为缺引用就删除已提取的正确日期。宿主已保存的人工日期更正可以沿用，模型自报确认不能替代。
- 阅读文本中的`[r...]`是引用标识。evidence使用`{"ref_id":"r...","fields":["charge_item","amount"]}`，需要时加币种、收付款方等字段。服务端还原原始文字及位置，模型无需计算偏移或拼接版式引文。同一字段可引用多处相关材料；相关性由Agent结合内容判断。
- 通常一次save_document_extraction保存charges，主控可finalize=true一起核对；documents、totals只在有用时提供，coverage无需填写。遇到反馈只修复具体误读，缺失不当作需要反复提取的错误。完成后prepare_export给出实际结果，剩余歧义随结果展示。

需要进一步方法时读取[长材料阅读](references/markdown-reading.md)、[格式与OCR](references/reading-strategies.md)、[多文件核对](references/cross-file-review.md)、[输出](references/output-contract.md)。工具执行与检索使用原生LangChain/Deep Agents能力。本包scripts只提供材料引用映射和账单数据校验。
