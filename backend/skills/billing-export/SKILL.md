---
name: billing-export
description: Validate and serialize the exact shipping exercise JSON array with numeric decimal amounts, nulls, operation enums, accounting direction and concise audit reasons. Use on the current validated billing revision.
metadata:
  version: "1.0.0"
  include_tools: "prepare_export"
---

# Financial JSON export

Read [the contract](references/contracts.md). Call `build_export` with `{records,revision,expected_revision,validation_revision,approval_revision?}`. Check `valid` before consuming `json`. The output JSON is a top-level array with only the six exercise groups; internal evidence, issues and identifiers remain in the host audit store.

Amounts must stay JSON numbers. Use `export_json` or the envelope's pre-serialized `json`; do not convert Decimal through binary float or default=str. Null is legal for genuinely absent fields. CREATE/UPDATE/NO_CHANGE require amount, charge name, ISO currency, accounting entity and AR/AP, with no unresolved issues. An explicit PENDING_REVIEW may retain missing values and must be displayed as requiring human attention.

Run all applicable current-revision hooks before calling this serializer. The host must atomically check current revision; a client-supplied matching number is not proof. This function performs no financial posting or approval. Portable CLI: `python scripts/skill.py < input.json`, writing only the exact array to stdout, errors to stderr through ordinary exceptions.
