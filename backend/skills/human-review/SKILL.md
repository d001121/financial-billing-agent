---
name: human-review
description: Apply explicit human billing edits, deletes and splits as new revisions, retain original values and invalidate derived checks, approvals and exports. Validate exact versioned tool approval bindings separately from business edits.
metadata:
  version: "2.0.7"
---

# Human business revision

An actual Harness stop (no progress, repair limit, evidence regression or shared run budget) preserves saved facts and is surfaced by `automatic_stop_question(task)` as a concrete review todo, after any missing-entity/AR/AP question. It is not approval. Reply or defer through the existing native interrupt and revision tools; missing values stay null.

When the caller has not supplied an accounting entity, read and save the materials first. After candidates/records exist, ask which company the caller is accounting for, offering only extracted issuer/recipient/creditor/debtor names as choices. `entity_question(task)` builds that domain question from saved facts; it never chooses a default, interprets a human reply, or runs an Agent. The host surfaces its choices through native interrupt payloads and the reply is handled in chat. Even one candidate requires an explicit reply. A different company or explicit defer is allowed. On selection, apply an entity revision and recalculate AR/AP through the existing financial rules, preserving OCR and evidence. Historical releases without this function retain their pinned behavior.

If a human reply supplies an entity or a field edit before any extraction candidate or record exists, do not report it as an invalid revision and lose the answer. Return an actionable error telling the Agent to save candidates through the document-extraction Skill first, then re-apply the reply; the Agent owns the retry. `apply_revision` itself only edits saved records.

Extraction batch merging retains `documents` (including headers from files without fees) by source/document identity. Fee edits/recalculation preserve this source context; it is not additional expense evidence or authorization to overwrite human-confirmed values.

`review_outcome({task,export,binding,confirmation?,at})` consumes fresh confidence and validation facts. With runtime.agent_style=codex, extraction finishes with the saved result and explicit gaps: `completed` for verified results, otherwise `completed_with_gaps`. A confidence score or absent value does not interrupt the Agent run. The user can inspect original material and edit the result afterward. Historical legacy tasks retain their pinned review behavior. Automatic verification is recorded separately from human `approval`; it is never reported as a human action. `validate_approval` accepts a current automatic binding or explicit human approval while the host reruns required financial Hooks. Field edits invalidate the old binding and recompute. Supplying the entity before records exist retains extracted candidates.

The saved extraction status is not the Agent's completion decision. If a supplied accounting entity still produces `POSTING_UNRESOLVED` or `POSTING_CONFLICT`, resolve the existing evidence or ask the caller about the entity's role/relationship and wait for the reply. An absent optional field or a confidence score alone does not require this question. If the caller explicitly states who pays/receives this fee, revise that fee's `debtor`/`creditor` through `apply_revision`, preserving the actual human reply and original source evidence; editing `posting_type` alone does not establish a relationship. Do not guess that a third party is an alias or agent of either source party. An explicit defer ends the clarification without approval. The Harness consumes pinned financial Hook facts and uses native interrupt/resume for this stop check; this Skill does not implement an Agent loop.

Use `apply_revision` with `{records,revision,expected_revision,reason,operations,accounting_entity?}`. Read [contracts](references/contracts.md). Operations are `{op:"set",charge_id,field,value}`, `{op:"delete",charge_id}` or `{op:"split",charge_id,value:[{field:value},...]}`. Null explicitly clears a field. Financial amount, party, entity, evidence and selected_match_id edits are supported. Split needs at least two field objects; it preserves a parent link and creates new child IDs.

A successful edit creates revision+1, retains before/after history and human_confirmed values, marks financial results pending and invalidates dependent financial checks, approval and export. Re-run applicable hooks and reconciliation, preserving confirmed fields. Source OCR remains unchanged. Reject stale expected_revision and show the host's latest diff.

Call `prepare_recalculation({task,review})` to replace the current extraction view for that revision before rerunning checks; it preserves the prior view and unresolved unrelated issues. For portable execution, `python scripts/skill.py --input input.json --output output.json` calls the same revision function. Omit either path or use `-` for stdin/stdout. Check both the exit code and `valid` in the JSON result.

`merge_extraction` preserves omitted fields when correcting the same charge ID and source/document/line identity. Explicit null clears a field. `replace=true` selects which rows remain; it does not implicitly clear omitted fields on retained rows. A changed source/document/line identity does not inherit unrelated prior fields. Human locks, deletes and splits continue to take precedence.

Business edits are not tool approvals. The host uses native HumanInTheLoopMiddleware/Command to pause and resume, and must bind an approval to revision, action, complete args, tool_version, rule_version and skill_versions. `edited_action.args` completely replaces parameters; retain untouched parameters explicitly. `respond` does not prove execution. Use `validate_approval` for bindings and real tool receipts for execution facts. This skill implements no interruption runner or checkpointer.
