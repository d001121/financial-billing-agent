# Official reuse and domain release contract

## Reviewed reference experiences (1.4.0, 2026-10-23)

The runtime configuration `use_reviewed_experiences` is a persisted global usage switch (default true, runtime v7). The existing versioned configuration API saves it with compare-and-swap. Disabled snapshots contain no experience cards; tools are omitted when disabled at construction and recheck the live switch before retrieval. Task context reports zero eligible references while disabled. Summarization, stored cards and executable mapping releases remain available. Re-enabling never adds later cards to an old snapshot, and disabling cannot retract content already in model context.

Reference experiences are separate from executable mapping candidates. `ExperienceDraft` defines title, problem, applicability, recommendation, exceptions and keywords. `summary_context(task,note)` projects bounded actual correction history, current rows and source quotes, and explicitly declares clipping. The host binds source task/revision, accounting entity and digest. Historical financial values never become current defaults.

Native `BaseChatModel.with_structured_output(..., method='function_calling', include_raw=True)` provides schema parsing. Native `langchain_community.retrievers.BM25Retriever` owns ranking; `rank-bm25==0.2.2` is installed and declared. The Skill only supplies Chinese/English tokenization, normalized exact accounting scope, active-state/keyword-overlap eligibility and at most three returned cards. There is no embedding API or separate search engine. The installed integration emits a community-package deprecation warning; offline checks cover the actual path.

HTTP prefix `/api/improvements/experiences`:

- `GET ""`: `{experiences,references}` with actual retrieval receipts.
- `POST /summarize`: `{task_id,expected_revision,note?,retry_failed?}` returns `{experience,reused}`. Each attempt permits one model HTTP request, configured timeout45 seconds/output1600 tokens, thinking disabled, and no automatic retries. Identical successful context/prompt reuses the draft. Failed jobs require `retry_failed:true`; running duplicates return409. Source revision changes during generation are rejected. Summary jobs store separate cumulative call/token usage.
- `PATCH /{id}`: `expected_revision` plus editable card fields; source and entity cannot be supplied. Active cards must be paused first. Editing clears review and returns to draft.
- `POST /{id}/review`: `{expected_revision,action:'activate'|'pause',approved:true?}`. Activation requires explicit confirmation, an undeleted source and a known entity. The workspace has no authenticated identity provider; review truthfully records a local action with identity null.

New task snapshots freeze active card contents/versions. Native `search_reviewed_experiences(query)` uses the task entity, pinned Skill/cards, and checks live active state/version. Each returned card creates a deduplicated `experience_use` receipt keyed by task/revision/card/version. Retrieval does not prove adoption or accuracy. Pausing cannot retroactively remove advice already returned to an agent.

Offline verification:9 experience tests plus18 existing focused checks passed (27 total), including native structured output using `httpx.MockTransport`; no real provider/OCR or production database mutations. Online summary quality and task effectiveness remain unmeasured. Abrupt process termination can leave a job running; automatic recovery is not implemented.

## Existing mapping release contract

Checked through LangChain Docs/API MCP on 2026-10-21:

- `https://docs.langchain.com/langsmith/local`: native `evaluate/aevaluate(upload_results=False)` returns local results and uploads neither application nor evaluator traces.
- `https://docs.langchain.com/langsmith/read-local-experiment-results`: iterate native ExperimentResults and read `run`, `example`, and `evaluation_results.results`.
- `https://docs.langchain.com/langsmith/code-evaluator-sdk`: code evaluators compare outputs/reference_outputs and return scores.
- API `langsmith.evaluation._runner.evaluate`, source commit `ae1299ba7a6a80911d0349cdf35b8e4ee234a15d`: `data`, `evaluators`, `max_concurrency`, `blocking`, `upload_results`, `disable_evaluator_tracing`.
- `https://docs.langchain.com/oss/python/deepagents/skills`: Skill discovery/tool execution stays with native middleware.

Installed and exercised here: Python 3.13.16, langchain 1.4.6, deepagents 0.7.29, langsmith 0.14.11, simplejson 4.2.0. The official engine does not define this exercise's accounting assertions, opt-in, entity scope, version registry or review gates. This package implements only those domain policies; LangSmith provides the experiment runtime. It does not implement an Agent runner, evaluation scheduler or model training.

## Candidates and mapping snapshots

`prepare_candidate(payload)` requires `opt_in=true`, `kind`, `source`, `scope`, `proposed_by`, different `before`/`after`, and `base_version`. Source is bound by the HTTP host to the actual task/revision, task capability version and a digest of task artifacts; client-provided source claims are not trusted.

Only `charge_mapping` supports activation. Scope is exactly `{"accounting_entity":"..."}`. Trading-party or document-specific scopes are rejected because this host passes task-level context to mapping resolution. Before/after are string alias to string canonical-name objects. An empty after snapshot removes custom mappings for that entity; the built-in billing rules still apply.

`resolve_mapping(registry,context)` follows `active_version` and `previous_version` until the latest exact whitespace-normalized, case-insensitive accounting entity match. It returns that version's complete `after` snapshot. It does not merge older aliases back in, leak one entity's mappings to another, or select disconnected version branches. Missing/cyclic chains fail visibly. `initial_registry()` provides the built-in `builtin-v1` rollback target.

## Actual experiment and critical assertions

`evaluate_mapping({candidate,registry,dataset}, reconcile=..., link_evidence=..., validate_amounts=...)` imports the official local evaluator and calls actual injected functions from `billing-reconciliation` and `evidence-linking`. These are explicit package dependencies; no backend import or database access is needed. It resolves the baseline/candidate mappings, links evidence, reconciles fees and validates amounts. Each result retains native run/example identities and per-assertion outcomes.

The project dataset `evals/datasets/charge-mapping.json` contains seven hand-authored synthetic fixtures with fixed expected fields. Regression and final families differ. `$ENTITY` is substituted only with the candidate's entity. Coverage includes canonical mapping, same-name distinct rows, amount-only update and payment-term preservation, invalid evidence, amount arithmetic mismatch, repeat/no-change and AP direction. Unknown aliases without labeled fixtures cannot receive an unsupported pass.

Critical assertions separately compare record count, operation, amount, currency, canonical charge name, payment term, entity, AR/AP, evidence presence/validation, amount validation, source/line identity and duplicate side effects. Any candidate failure or missing metric blocks release; an average score cannot hide a financial error. These deterministic evaluations perform no financial side effects; duplicate-side-effect checks here are an assertion on returned experiment data, not a live external financial-system test.

Native execution uses `max_concurrency=0`, `upload_results=False`, `disable_evaluator_tracing=True`. A regression failure prevents final-set exposure. The registry records final dataset digest to candidate content digest; that final dataset cannot assess another candidate as independent evidence. Repeated evaluation of the identical candidate is allowed before publication. Further candidate selection needs a new separately labeled final dataset. Published candidates cannot overwrite their stored comparison by reevaluation.

`compare_candidate` is pure release policy over measured cases, not proof that supplied metrics are genuine. The HTTP API never accepts caller comparison/metric claims. The host invokes `evaluate_mapping` against its fixed dataset and stores only those returned results. Other candidate kinds return `KIND_DRAFT_ONLY`.

## Publication, rollback and HTTP bindings

`publish_candidate` requires candidate, stored comparison, review `{approved:true,reviewer,reason,candidate_id}`, registry and `expected_active_version`. It checks content digest, candidate ID, native experiment engine, current baseline, final evaluation/consumption and expected version. It returns a copied immutable registry version. `rollback_candidate` requires known target, explicit reviewer/reason/approval and expected current version. The host persists each registry mutation atomically under its repository lock; candidates are separate objects and status is derived from published registry versions. Existing task snapshots remain unchanged.

HTTP prefix `/api/improvements`:

- `GET /candidates`: `{candidates:[view],registry}`.
- `POST /candidates`: `{task_id,expected_revision,opt_in,kind,scope,proposed_by,before,after}` returns `{candidate}`.
- `POST /candidates/{id}/evaluate`: empty body or `{}` returns `{candidate,comparison}`. Nonempty claimed results are rejected.
- `POST /candidates/{id}/publish`: `{reviewer,reason,approved:true,expected_active_version}` returns `{candidate,registry,published_version}`.
- `POST /rollback`: `{target_version,reviewer,reason,approved:true,expected_active_version}` returns `{registry}`.

Candidate view includes `id`, `candidate_id`, source/scope/before/after, proposer, baseline, comparison, status, revision and creation time. Revision/release conflicts return 409; unsupported or failing proposals/evaluations return 422. Candidate creation does not modify its source task.

## Verification scope

The native HTTP integration experiment measured baseline **5/7** and candidate **7/7** for `Document Charge -> Documentation Fee`. This is a synthetic domain regression result, not real-document extraction/OCR accuracy or general learning effectiveness. Tests cover rejected client pass claims, inactive kinds, unknown aliases, wrong mappings, final-set reuse, review/version gates, immutable publication, entity isolation, rollback and unchanged in-flight task snapshots. The package CLI supports files/stdin/stdout and rejection exit status independently of the web application.
