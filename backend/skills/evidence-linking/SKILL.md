---
name: evidence-linking
description: Verify shipping charge citations and international amount/currency source support without fixed templates, retaining original spans, ambiguity and page/cell provenance. Use after extraction and after evidence edits.
metadata:
  version: "2.1.4"
  include_tools: "link_task_evidence"
---

# Evidence read-back

Before saving a repair, `validate_repair({previous,candidate})` reads back both versions against the same current sources. A previously supported field cannot become a nonempty unsupported value through an evidence edit. Reject that candidate atomically and retain the saved facts for review. Explicit null remains null; a different value with actual supporting evidence is allowed. Never restore or invent values automatically.

`documents` header identities are also read back. Each present bill reference, B/L, master B/L, booking or container must be supported by that file's own citations. A shared shipment cannot overwrite one source's printed identifiers with another source's values. Header failures are repairable hard issues. Distinct printed numbers remain distinct, while a genuinely common container can prove transportation association.

The Agent interprets relationships between materials and decides which facts support the candidate. Cross-source citations do not require a separate identity-proof checklist. Preserve each file's printed identifiers and avoid borrowing unrelated financial facts. The validator checks actual references and value support; model-provided verified flags are overwritten. Human edits and exports reuse this validator. `pdf_embedded_text` supports page-based evidence after OCR success; old preview text stays nonauthoritative.

When saved document headers explicitly identify different invoice references, a shared shipment cannot supply the other invoice's amount, currency, quantity, unit price or payment term. These contradictory financial citations fail with CROSS_SOURCE_DOCUMENT_CONFLICT. This checks known conflicts without requiring an identity-proof checklist for every cross-file reference.

Version 1.3 also exposes `payment_term` source facts. Canonical PP accepts actual PP/PREPAID/PRE-PAID text; CC accepts CC/COLLECT. No term is inferred when absent. Existing ambiguity and exact source-offset rules apply to these facts.

Normal extraction copies `ref_id` and `fields` from the material reading. The extraction Skill restores exact source quotes and offsets before this validator runs; no additional model call is needed. For direct portable use call `link_evidence` with `{charges,sources,revision}`. Each source is either `{source_id,text}` or `{source_id,blocks:[{anchor,text,...}]}`. Each charge has restored `evidence:[{source_id,anchor,quote}]`. Read [the contract](references/contracts.md).

Quotes must occur verbatim in one unique referenced block. Missing or ambiguous references fail validation. Do not repair evidence by generating text, page numbers or coordinates. Preserve separate email and attachment occurrences even when underlying content hashes match. Returned links carry the original metadata only when supplied, a content hash, source version, quote offsets and `verified`.

Offsets are determined from exact source text. A unique verbatim quote can be relocated when the model reports an incorrect offset; keep the reported offset and `unique_exact_quote` method in the returned provenance. Repeated quotes still require a correct original offset or a longer unique quote. Failed references return bounded actual `locations` with nearby `context_quote`; use these to select the intended role rather than guessing character counts. No fuzzy text matching or first-occurrence selection is used.

Use native bound tools. The portable CLI `python scripts/skill.py` reads/writes JSON on stdin/stdout. This verifies citation read-back, not whether the model interpreted the business meaning correctly. Persist immutable source content in the host store and recheck current revisions before export.

`validate_evidence` supplies `source_support_v2` facts for billing-confidence: each current candidate's exact value, support/ambiguity, original numeric candidates and real field spans. It accepts unambiguous international decimal/grouping conventions, qualified currency symbols, unique ISO official currency names and the bounded local aliases listed in the contract. A model's expected amount, issuer country or document language never resolves `1,234`, `$`, `¥`, `kr`, `Rs` or `C$` ambiguity. Keep raw source text unchanged; do not repair OCR letters into digits or invent missing currency codes. Provided amount/currency/charge-name values require current supported evidence; unsupported, unavailable or ambiguous facts are hard validation errors, including repeated equal-value locations. Pure `link_evidence` read-back does not substitute for this semantic gate.

For quantity × unit-price support, provide field-specific original quotes for `quantity`, `unit_price` and `amount`. Their `value_start`/`value_end` point to actual raw tokens, allowing the consumer to distinguish separate facts from reuse of the same token. Arithmetic itself remains the billing-reconciliation Skill's responsibility.

`build_preview({source,revision,target:{anchor,quote,field,value}})` provides a read-only original structure view. It resolves saved block/cell anchors and only returns real boxes with explicit coordinate units. Office structure anchors do not imply a physical Word page. Repeated values locate the row instead of guessing a cell. See [preview contract](references/preview.md).
