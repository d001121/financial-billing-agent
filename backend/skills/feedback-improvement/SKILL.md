---
name: feedback-improvement
description: Preserve explicitly opted-in billing feedback as inactive candidates; measure charge mappings with native local LangSmith experiments, then publish reviewed entity-scoped versions with rollback. Use when a caller asks to retain feedback beyond the current task.
metadata:
  version: "1.4.0"
---

# Reviewed cross-task improvement

## Experience library

The console can summarize a source task's actual corrections with one native structured-output model call. `summary_context` projects bounded history and original source references; `ExperienceDraft` defines the editable card. The host fixes source/task revision and accounting entity. The model cannot choose provenance or widen scope. AI drafts are inactive until a caller explicitly confirms the contents. Missing entity permits a draft but blocks activation. Failures are visible and never replaced by a fabricated AI summary.

When `search_reviewed_experiences` is available, use a specific uncertainty (for example conditional charges or currency symbols) to retrieve at most three approved same-entity lessons. Reference methods and exceptions only; historical amounts, currencies, IDs, parties and AR/AP do not establish current-document facts. A reference is not evidence or an executable rule and does not bypass any existing financial validation. No match means no advice, not an invented fallback.

The host freezes active card revisions in new-task capabilities. Live disabled/revised entries cannot be newly retrieved by an old snapshot; previous returns remain audit history. Cards can be paused, edited as drafts and confirmed again. Native BM25Retriever supplies local ranking with no embedding/model calls. `experience_use` means the tool returned a reference, not that the model adopted it or was correct. Executable mapping publication below remains a separate measured path.

Read [contracts and official evaluation composition](references/contracts.md). A correction changes only its current task unless the caller explicitly chooses `opt_in=true`. `prepare_candidate` records source, scope, proposer, before/after and baseline as an inactive content-addressed artifact. It does not change any running task.

Only `charge_mapping` has an implemented evaluation and activation path. Its scope must be exactly `{"accounting_entity":"..."}`; `before` and `after` are complete custom alias-to-canonical-name snapshots for that entity. Other rule, prompt and Skill proposals remain drafts and cannot evaluate or publish.

Use `evaluate_mapping` with the billing-reconciliation and evidence-linking functions explicitly injected. It runs native `langsmith.evaluate(upload_results=False)` against fixed labeled regression and final datasets, first baseline then candidate. It does not accept claimed pass metrics from the caller or invoke a model. The final set is evaluated only after all regression assertions pass; a final set exposed to a different candidate requires replacement. Missing alias coverage, critical failures, family leakage or stale baselines block release.

`validate_dataset` checks imported human-labeled datasets, unique sample IDs, regression/final separation and explicit synthetic/real labels. The host stores immutable dataset content with enable/disable controls; select it by ID when evaluating. A changed dataset name or version does not make already-exposed final families or identical inputs independent again. This evaluates deterministic financial mappings, not OCR accuracy or prompt/Skill/code evolution. When adding or removing one alias, preserve the entity's other mappings in the complete `after` snapshot; read the active mapping first.

The host stores measured comparisons and final-set consumption. `publish_candidate` requires that stored native comparison, exact content identity, reviewer/reason/approval and expected active version. Store registry changes atomically; resolve versions into new-task capability snapshots. `rollback_candidate` selects an existing immutable version after review. The built-in rollback target is `builtin-v1`. Never rewrite shared code or publish silently.

This package supplies domain metrics, entity mapping resolution and release policy. LangSmith provides the experiment engine; LangChain/Deep Agents provide Agent and Skill execution. Evaluation dependencies are declared in `requirements.txt`; evaluation also requires the two portable sibling Skills, not the backend.

`financial_evaluator` also checks document numbers. `extraction_evaluator` evaluates reference number, charge, numeric amount, currency and payment term against separately reviewed labels. It compares complete row multisets so row order does not matter, two same-name charges cannot merge, and swapped amounts/currencies cannot pass on independent field averages. It reports exactness, precision/recall and missing/extra rows. A real-document development set reviewed by a coding agent is not a human-approved independent final set; preserve that distinction in every report. Use native local LangSmith experiments to run the actual agent; do not feed labels into its prompt or replace its predictions with expected values.

Portable proposal CLI: `python scripts/skill.py --input candidate.json --output result.json`. Omit either path or use `-` for stdin/stdout. JSON numbers remain numeric. Exit 0 means a valid inactive candidate; exit 1 means rejected input. Import the pure functions for evaluation/publication bindings; this CLI never publishes.
