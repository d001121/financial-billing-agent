# Financial export contract

Checked LangChain structured-output Docs/API MCP 2026-10-21. Native `ToolStrategy` and provider structured output constrain model schemas, but they do not implement this exercise's financial JSON projection, Decimal wire representation or business revision bindings. This package provides only those domain requirements. Official tool loading remains SkillsMiddleware (metadata.include_tools in deepagents >=0.7.22).

- https://docs.langchain.com/oss/python/langchain/structured-output
- https://docs.langchain.com/oss/python/deepagents/skills
- API `langchain.ToolStrategy`, source commit `84ba23c414eca6bf6f6ebd1394a3006378113540`.
- https://docs.python.org/3/library/decimal.html

The top-level array contains operation; document_info(document_type/reference_no/document_date); transaction_party(issuer/recipient); charge_details(charge_item/amount/currency/payment_term); financial_attributes(accounting_entity/posting_type); audit_trail(ai_reasoning string array). Operations are CREATE, UPDATE, NO_CHANGE and PENDING_REVIEW. Reasons describe short auditable business facts, never internal thought traces.

`validate_export(payload)` returns validation/projection, `build_export(payload)` adds exact JSON only on success, and `export_json(payload)` returns the array string or raises ValueError. simplejson(use_decimal=True,allow_nan=False) preserves decimals as JSON numbers. Booleans, NaN and Infinity cannot pass as amounts. Stale revision/validation/approval bindings fail. Missing optional approval_revision means the caller does not require separate tool approval; the host policy decides when approval is required. The host must retrieve actual current revisions and run evidence/amount/matching/posting hooks; this local pure function does not claim external concurrency control.

## Standalone CLI

`python scripts/skill.py --input input.json --output output.json` preserves the default `export_json` wire format: a successful top-level financial JSON array. Omit paths or use `-` for stdin/stdout. `--operation build_export` and `--operation validate_export` instead output their existing validation envelopes. The input root is a UTF-8 JSON object; file input accepts a BOM. All paths preserve Decimal as JSON numbers. A rejected export or malformed/unreadable input produces a `valid=false` issue envelope and exits 1, never a successful financial array. Successful operations exit 0; an unwritable output exits 1 with a stderr diagnostic.

Docs MCP `/oss/python/deepagents/skills` and API `SkillsMiddleware`/`FilesystemMiddleware` were rechecked against deepagents 0.7.29. Native components already provide skill discovery, disclosure and execution; they do not implement this exercise's file IO or financial projection. The CLI uses `argparse` and the existing pure functions only. It does not create an agent runner or grant shell capability to non-sandbox backends.

## Verified runtime, 2026-10-21

Actual project runtime: Python 3.13.16; langchain 1.4.6; deepagents 0.7.29; langchain-text-splitters 1.1.3; pydantic 2.14.1; simplejson 4.2.0; pycountry 26.2.16; langsmith 0.14.11. Package lookup and native splitter/schema execution succeeded through `./python.cmd`. The six business packages jointly pass 38 deterministic pytest cases. This is offline domain verification, not a live OCR/model accuracy claim. Host Skill metadata names refer to the actual bound host tools; Python functions and stdin/stdout CLIs remain the portable package interface.
