---
name: billing-reconciliation
description: Normalize shipping charges, validate decimal amounts and classify CREATE, UPDATE, NO_CHANGE or PENDING_REVIEW against explicitly supplied existing bills and accounting entity. Use before financial review and export.
metadata:
  version: "1.4.0"
  include_tools: "reconcile_task_charges"
---

# Shipping billing reconciliation

Read [the contracts](references/contracts.md) before using the associated tools. All tools receive one `payload` object. `reconcile_charges` accepts `charges`, explicit `existing_records` (an empty list means none), `accounting_entity`, optional `totals`, `charge_mapping` and `update_instructions`, and `revision`.

Use the runtime's bound tools; do not run arbitrary shell commands or create another agent loop. The portable CLI is `python scripts/skill.py`, reading JSON from stdin and writing JSON to stdout. Install [requirements](requirements.txt) in the host environment.

Preserve each real expense line. Map only the supplied aliases; do not guess currencies. Compare against all records at each matching tier and stop on ambiguity. A difference alone does not authorize UPDATE. An explicit changes object distinguishes omitted fields, null and new values. Direction uses supplied creditor/debtor relationships and the caller's accounting entity; PP/CC, document type and amount sign do not determine AR/AP.

New workbench tasks use automatic history. The host reads persisted projections before reconciliation; `retrieve_history` selects completed/approved, currently validated same-entity records and the existing matching tiers. Do not invent or ask the user to assemble historical JSON. Missing entity waits for the normal entity reply. Read the returned history receipt and candidate matches; a real difference requires the user's explicit update intent. Call `reconcile_task_charges(update_instructions=[...])` with only those changes (target id, or document number and fee name). Failed/stale retrieval cannot authorize CREATE or formal export. Historical UPDATE descendants replace only their exact parent revision; unrelated same-name rows and competing branches remain ambiguous. NO_CHANGE results do not create new baseline rows. See the contracts for provenance and source scope.

Inspect returned `issues` and `records`. Unresolved direction, amounts, source evidence or matching produces PENDING_REVIEW. This skill proposes records; it does not post to a financial system. Source quote read-back is a separate evidence validation and must also run. Run `tests/test_reconciliation.py` for deterministic acceptance scenarios.

`validate_amounts` returns its input `revision` and `normalized_charges` facts from this same financial normalization. Each fact binds the `charge_id`, original flattened `input_amount`, normalized `amount`, `currency` and `line_role`. Consumers must require a fresh passed check, unique current charge identity and matching input/output values before using a fact; the fact is not a separate approval. This permits a positive source discount to correspond to the validated negative financial amount without duplicating the discount rule in confidence scoring. Original numeric/currency strings remain in record provenance.
