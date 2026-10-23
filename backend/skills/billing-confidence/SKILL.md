---
name: billing-confidence
description: Assess explainable rule support for shipping billing records using fresh evidence, amount, coverage and conflict validation. Use to help a human decide which original documents to inspect; never treat the score as a correctness probability or approval.
metadata:
  version: "3.1.0"
  include_tools: "assess_task_confidence"
---

# Billing evidence support

Version 3 adds a separate observed-field review policy. `review_threshold` defaults to 80; only an observed value scoring strictly below it adds a targeted `review_items` entry. Missing values and absent optional arithmetic/total checks never create low-confidence tasks. A null normalized amount/currency with an actual cited raw value remains unresolved observed data, not an absent field. `review_score` describes available fields; the existing grouped `score` still describes overall evidence support and is never inflated by missing operands. Payment terms use source facts, AR/AP uses the financial posting validator. The host uses native `interrupt()` only when `review_required` is true and otherwise completes automatic verification. Hard financial checks remain separate and cannot be overridden by either score.

Read [the scoring contract](references/scoring.md) before interpreting results. Call `assess_confidence(payload)` with the current task revision and a **fresh host-generated** validation result, including its detailed `checks`. Keep `charges`, `records`, `sources`, `coverage`, `totals` and `accounting_entity` in the payload. The function is pure, makes no network calls and never modifies input or grants approval.

Each record returns a 0–100 grouped support score, the contributing components, support for reference number/charge name/amount/currency, hard blockers, and source targets the UI can open. Version 3.1 grades **field support** instead of treating every supported value as certainty: a unique, structured/table-cell, non-header citation reaches 100, a plain body line 90, and an email-subject-only citation 45 (routed to review). The grade does not depend on fixed label names such as B/L NUMBER or MBL NO.; those differ per bill and remain the model's semantic decision. 100 therefore requires all core fields at full strength plus the constraint and coverage groups. Version 2 requires the current `source_support_v2` contract from evidence-linking >=1.2.0. It consumes validated field facts, rather than parsing international numbers again. Copying the same source or requesting a second model opinion never earns a bonus.

Default overall support groups are source support 70, constraint consistency 20 and coverage 10. Source read-back, field semantics and valid amounts form one correlated group. Constraint consistency uses the **maximum**, not the sum, of source-backed quantity × unit price (half group) and a distinct declared total in the same document/currency scope (full group). Invented operands and a line amount reused as its own total earn no extra points. A reference number is displayed when present; it is not a mandatory template field.

`calibrated: false` means the number is not an empirical probability of being correct. Unsupported checks score zero; missing checks never renormalize to 100. Missing document totals do not create a hard blocker. A high score cannot override a blocker, failed validation or approval requirements. `signals` explains both constraint checks and `review_route` distinguishes blocked, suggested review and quick confirmation.

The host must resolve this function from the task's pinned Skill release, recompute it after edits, and compare the response revision before displaying it. Historical tasks without this Skill must report unavailable rather than silently loading today's rules. Do not accept a model's claimed confidence or a caller-supplied `verified` flag as evidence.

When no records exist yet, candidates are projected for display with `origin: charges`, `record_id: charge_id`, and `operation: PENDING_REVIEW`; these remain ineligible for quick confirmation. Normal rows have `origin: records`. The `record` field preserves the record displayed alongside its assessment.

Portable CLI: `python scripts/skill.py --input task.json --output confidence.json`; omit the paths or use `-` for stdio. CLI exits zero when assessment completes, even when the result requires review; malformed input exits one with a JSON `CLI_INPUT` issue. The scoring function uses the standard library; the CLI uses `simplejson` to preserve decimal amounts in displayed records.
