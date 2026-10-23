# Extraction contract 2.1.4

Version 2.1.4 makes `read_materials` window errors actionable: `start_line=0` is treated as line 1, and an unknown source lists the valid source ids together with the file's line count. This removes the repeated invalid-window retries seen when a model used zero-based lines or mistyped a source id.

Version 2.1.3 repairs document-header evidence from the same source: an identity value (`reference_no`, `bill_of_lading`, `master_bill_of_lading`, `booking_no`, `container_no`) whose existing quote is missing the value or is not found in its referenced block is replaced by the actual line that prints it, reported as `DOCUMENT_EVIDENCE_REPAIRED`. A PDF B/L whose candidate only cited the embedded layer is accepted and supplemented with the layout line when that layout text prints the same value; otherwise `PDF_IDENTITY_LAYOUT_REQUIRED` remains. Duplicate issue objects are collapsed.

Version 2.1.2 rejects a footer/platform vendor as the issuer. A charge or document `issuer` containing `湃乐多`, `Pilot Aiship`, `Pai Aiship` or `Powered by` is cleared and reported as `ISSUER_PLATFORM_VENDOR` (warning, original value retained in the issue). Such a watermark is not a printed issuer and must not become a candidate accounting entity. Issuer, recipient, creditor and debtor remain independent facts; clearing one never fills another by inference.

SKILL.md is the single entry. Native SkillsMiddleware handles progressive disclosure and tool exposure. Native StateBackend, grep and read_file handle material files. Native SubAgentMiddleware provides optional specialist delegation. No custom runner, mandatory plan or fixed block workflow is introduced.

`read_materials({sources, windows?, max_chars?})` returns a manifest and all short material together. Default limit is 32,000 characters (including citation markers), configurable from 1,000 to 64,000. Large bundles return mode=search and no hidden full text; use native grep/read_file or batch windows `{source_id,start_line,end_line}`. Each window declares actual end_line, next_line and truncation. An exhausted character budget never means the remaining file was read.

Every original span has a deterministic `r...` ID derived from source occurrence, anchor, original offsets and quote. Native material files and batch windows contain these IDs. Supply evidence=[{ref_id,fields:[...]}]; validate_extraction restores exact source quotes and offsets. A quote may support several fields. Unknown IDs fail validation. Legacy source_id/anchor/quote inputs remain supported. IDs are references, not semantic correctness scores.

Use charges for real expense lines. Null means absent or unresolved. Decimal values must be finite; booleans are rejected. Preserve raw numeric strings when available. documents and totals are optional useful facts, not a second complete extraction requirement. coverage remains a compatibility field; no nine-block or chunk-completion gate applies. validate_coverage reports actual incomplete OCR/ingestion and submitted assets not read.

The Agent compares file meaning, identifiers, dates, amount roles and duplicated descriptions. It decides whether sources support the same fee. There is no mandatory source_links proof graph or layout-for-every-identifier rule. Exact original support and source membership are still checked. Repeated read/representation calls are useful only when they resolve a concrete question.

PDF/图片缺口使用read_document_sources(method="ocr")读原页/帧。PDF文字与版式按需辅助。OCR失败或空结构化费用列表不等于文件无费用；无法确认时保留缺口。补读成功更新Markdown及引用；未变化的原文引用保持稳定。

PDF有版式财务行时，`pdf_layout_financial`是财务字段的首选表示：它保留原始layout行，并提供解析后的`rows`（description/amount/currency/rate/quantity/pc）。`pdf_layout_text`用于上下文和单据身份，`pdf_embedded_text`只用于条款/正文，`ocr_structured`用于图片/扫描页或交叉核对。`validate_extraction`会比较OCR费用行与layout行：行数或金额不一致记`OCR_LAYOUT_CONFLICT`（warning；若候选金额只被OCR支持则升级为error），财务字段只引用OCR时记`PDF_LAYOUT_EVIDENCE_REQUIRED`。冲突时以layout行拆分和金额为准，不静默采用OCR的合并行。

Portable CLI: `python scripts/skill.py --input input.json --output output.json` defaults to read_materials. Explicit operations include read_materials, validate_extraction, validate_coverage, supplement_pdf and historical prepare_extraction. Input/output are UTF-8 JSON; no path means stdio. The portable adapter calls the same business functions, without exposing image tools or another Agent loop.

Framework evidence checked 2026-10-21 through LangChain Docs/API MCP: `/oss/python/deepagents/skills`, `/oss/python/deepagents/subagents`, `/oss/python/langchain/tools`, SkillsMiddleware, FilesystemMiddleware, ToolRuntime, SubAgentMiddleware. Installed Deep Agents 0.7.29 / LangChain 1.4.6. These provide execution/disclosure/search; original billing span mapping and finite monetary schema remain this portable business package's responsibility.
