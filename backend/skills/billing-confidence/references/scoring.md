# Grouped source support and conditional review, version 3.1.0

This is an explainable business support index, **not** a calibrated correctness probability. It makes no model/OCR requests and does not approve or post anything. Currency arithmetic and matching remain in billing-reconciliation; all source number/currency semantics and offsets remain in evidence-linking. The host supplies fresh unified validation for the current revision.

## Why this policy changed

The material is global shipping correspondence and bills without a fixed template. Missing reference numbers, quantity or unit price do not establish that a legitimate bill is wrong. A model can invent operands or copy one mistaken OCR value and still produce internally consistent arithmetic. Source read-back, lexical agreement and decimal validity are related observations; scoring them as independent overstates support.

The user's FineReport article recommends OCR + semantic extraction, standardization, business checks and feedback. It provides no fusion formula, calibration dataset or reproducible project accuracy. We apply its strategies to source-backed semantic fields and explicit constraints without imposing supplier templates or filtering long-tail material. Source selection is documented in the project's research note.

## Default fusion

Let A, C and N be **graded** source support for amount, currency and original charge name, each in [0,1]. A supported value starts at 0.85; it gains 0.05 for exactly one target location, 0.10 when the citation is a structured field/table cell, and 0.05 when two or more distinct sources agree. If every citation is an email subject/header while the field belongs to document content, subtract 0.45. Ambiguous values score 0.40 (numeric/format ambiguity) or 0.30 (location/currency ambiguity); contradictory values score 0.10; missing or unavailable values score 0. L is a passed, source-backed line arithmetic check; T is a passed, source-backed total check; V is the existing coverage check (0 or 1).

`S = 70 × (0.45A + 0.35C + 0.20N) + 20 × max(0.5L, T) + 10V`

| Component | Maximum | Meaning |
| --- | ---: | --- |
| field_support | 70 | Amount, explicit currency and original charge name supported by fresh source facts. Read-back and valid currency/amount do not earn duplicate points. |
| consistency | 20 | Maximum of 10 for source-backed line arithmetic and 20 for a distinct declared total. Two views of one invoice never add to 30. |
| coverage | 10 | Current coverage validator passed. This means ranges are accounted for, not proof of semantic recall. |

Weights and thresholds are initial policy choices, not fitted probabilities. `options.weights` can replace the **three** exact keys with finite nonnegative numbers totaling 100. `policy_id`, `high_threshold` (90) and `medium_threshold` (65) are configurable; unknown options are rejected. Policies cannot disable hard gates. The inner field weights remain fixed. Version 1 six-key options are not silently converted.

Missing checks receive zero in the overall support index; its weights are never renormalized. A structured, uniquely located field reaches 1.0; a plain single body line reaches 0.90; a reference supported only by an email subject reaches 0.45 and is routed to review even though the quoted subject does contain it. 100 therefore requires all three core fields at 1.0 plus the constraint and coverage groups. A source-backed bill with no operands or total scores at most 80; a verified distinct total can add the full consistency group without requiring a reference number or operands. Optional reference support remains visible. Task support is the minimum fee score; averaging cannot conceal one weak row.

## Source contract and dependency limits

The current evidence check must expose `field_support_contract: source_support_v2`, current revision, uniquely identified charges and their field_support facts. Facts include the current candidate value, status, reasons and targets. Targets must point into verified references returned by that same check, including hash, anchor, source ID and offsets. Stale or unknown contracts are unavailable instead of falling back to English number parsing.

Numeric comparisons in this package accept **canonical** finite Decimal values only. Global formats, accounting negatives, Unicode digits and ambiguous 1,234 are interpreted once in evidence-linking; raw tokens, candidates and ambiguity are propagated. The model's selected number or a raw verified flag never resolves ambiguity. Name normalization must preserve the original spelling; record/candidate conflicts remain hard gates.

For L, both operands and amount need source support at different physical token offsets. The existing amount check must pass. One token attributed to both unit price and amount cannot supply two fields. No multiplication is implemented here. L earns half a constraint group because it remains a view of the same document.

For T, require one total in the current logical-document/source and currency scope, matched by total index, amount and currency to current total_evidence. Its amount and currency must be supported and the amount check must pass. Its amount token cannot be any cited fee amount token. Labelling a computed sum or the same source token a total earns no bonus. Cross-currency sums, unrelated totals and ambiguous locations cannot earn T. Source role semantics still depend on extraction and independent gold evaluation; these checks cannot prove that no row was missed.

Duplicate hashes/offsets and aliases never earn count bonuses. Scores do not use citation counts, model votes, countries or filenames. Additional documents receive no bonus, so this implementation needs no independence classifier and claims no statistical independence of near-duplicates or copied email text.

## Gates and human review

Quick confirmation is blocked by stale task/record/validation/confirmation; missing or ambiguous core fields; record/candidate disagreements; unavailable/failed required schema, coverage, evidence, amount, matching, update, posting, revision, capability or budget checks; conflicts; unresolved posting direction; PENDING_REVIEW; unsupported cited totals; and other current blocking issues. Correct arithmetic cannot cure an ambiguous currency symbol.

The legacy `review_route` remains an overall-support presentation field. Runtime routing uses `review_required` and `review_items`, not that legacy field. Each existing or cited-but-unresolved field is reviewed if its score is strictly below `review_threshold` (default 80, configurable from 0 to 100). Null/empty values without cited raw observations are excluded, as are unavailable optional operands/totals. Real amount/posting contradictions attach a targeted field item. Current PP/CC source support and validated AR/AP are included when present. `review_score` is the weighted support among observed fields (core amount .45, currency .35, name .20; optional reference/payment/posting .10 each), with task minimum across rows; missing values never receive fabricated high scores. A weak field still triggers review even if the row average exceeds threshold.

The host raises native LangGraph `interrupt()` after scoring only for the targeted items. With no low-confidence existing values and all hard checks passed, automatic verification completes and its exact binding is recorded as `auto_review`, separate from human approval. Missing mandatory financial data or incomplete processing preserves visible editable results without inventing low-confidence tasks or authorizing formal export. Human confirmation never overrides failed financial checks. Edits create revisions and invalidate old bindings. Historical pinned versions retain their prior behavior.

## Framework evidence and validation

Docs MCP /oss/python/langchain/structured-output and Reference MCP ToolStrategy were read before changes: native schema validation, tool calls and structured repair already exist. Docs MCP /langsmith/code-evaluator-sdk and Reference MCP EvaluationResult provide deterministic evaluation protocols, delegating business scores to user functions. The installed LangChain 1.4.6 / Deep Agents 0.7.29 / LangSmith 0.14.11 combination is unchanged. Native Skill loading/execution, hooks, shared budgets and approval remain intact.

The concrete gap is this project's international source semantics and correlated financial-support policy. ToolStrategy and generic trajectory evaluators do not define it. Only domain functions change; no custom Agent loop, Skill runner, judge model or extra online call is introduced. Regression covers international formats, ambiguous readings, operand provenance, reused total tokens, duplicates, wrong currencies, stale facts and portable CLI/native tool use. Independent representative gold labels are still required for accuracy, high-score error rates and threshold calibration.

