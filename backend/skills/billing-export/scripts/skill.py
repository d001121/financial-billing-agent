"""One financial JSON export contract shared by API, tools and CLI."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation

import pycountry
import simplejson

GROUPS = {
    "document_info": ("document_type", "reference_no", "document_date"),
    "transaction_party": ("issuer", "recipient"),
    "charge_details": ("charge_item", "amount", "currency", "payment_term"),
    "financial_attributes": ("accounting_entity", "posting_type"),
}
OPERATIONS = {"CREATE", "UPDATE", "NO_CHANGE", "PENDING_REVIEW"}


def _project(record):
    output = {"operation": record.get("operation", "PENDING_REVIEW")}
    for group, fields in GROUPS.items():
        values = record.get(group, record)
        output[group] = {f: deepcopy(values.get(f)) for f in fields}
    amount = output["charge_details"]["amount"]
    if amount is not None:
        if isinstance(amount, bool):
            raise ValueError("金额不能为布尔值")
        try:
            amount = Decimal(str(amount))
        except (ValueError, InvalidOperation) as exc:
            raise ValueError("金额必须为十进制数字") from exc
        if not amount.is_finite():
            raise ValueError("金额必须有限")
        output["charge_details"]["amount"] = amount
    reasoning = (record.get("audit_trail") or {}).get("ai_reasoning", [])
    if isinstance(reasoning, str):
        reasoning = [reasoning]
    output["audit_trail"] = {"ai_reasoning": reasoning}
    return output


def validate_export(payload: dict) -> dict:
    issues = []
    revision = payload.get("revision")
    expected = payload.get("expected_revision", revision)
    if revision != expected:
        issues.append({"code": "STALE_REVISION", "message": "导出请求版本已过期", "field": "revision"})
    validation_revision = payload.get("validation_revision", revision)
    if validation_revision != revision:
        issues.append({"code": "STALE_VALIDATION", "message": "校验结果不属于当前版本", "field": "validation_revision"})
    if payload.get("approval_revision", revision) != revision:
        issues.append({"code": "STALE_APPROVAL", "message": "审批不属于当前版本", "field": "approval_revision"})
    result = []
    for i, record in enumerate(payload.get("records", [])):
        if record.get("revision", revision) != revision:
            issues.append({"code": "STALE_RECORD", "message": "费用记录不属于当前导出版本", "field": f"records.{i}.revision"})
        try:
            output = _project(record)
        except ValueError as exc:
            issues.append({"code": "EXPORT_AMOUNT", "message": str(exc), "field": f"records.{i}.amount"})
            continue
        if output["operation"] not in OPERATIONS:
            issues.append({"code": "EXPORT_OPERATION", "message": "不支持的操作枚举", "field": f"records.{i}.operation"})
        if not isinstance(output["audit_trail"]["ai_reasoning"], list) or not all(
                isinstance(v, str) for v in output["audit_trail"]["ai_reasoning"]):
            issues.append({"code": "EXPORT_REASONING", "message": "审计依据必须为字符串数组", "field": f"records.{i}.audit_trail"})
        if output["operation"] != "PENDING_REVIEW":
            details, financial = output["charge_details"], output["financial_attributes"]
            if details["amount"] is None or not details["charge_item"]:
                issues.append({"code": "EXPORT_REQUIRED", "message": "可执行费用须有金额及费用名", "field": f"records.{i}.charge_details"})
            if not details["currency"] or not pycountry.currencies.get(alpha_3=details["currency"]):
                issues.append({"code": "EXPORT_CURRENCY", "message": "可执行费用须有ISO币种", "field": f"records.{i}.currency"})
            if financial["posting_type"] not in {"AR", "AP"} or not financial["accounting_entity"]:
                issues.append({"code": "EXPORT_POSTING", "message": "可执行费用须有记账主体及AR/AP", "field": f"records.{i}.financial_attributes"})
            if record.get("issues"):
                issues.append({"code": "EXPORT_UNRESOLVED", "message": "有未解决校验问题的记录不能作为可执行结果", "field": f"records.{i}.issues"})
        result.append(output)
    for error in issues:
        error.update({"severity": "error", "repairable": False})
    return {"valid": not issues, "issues": issues, "records": result, "revision": revision}


def build_export(payload: dict) -> dict:
    """Build the exact top-level array, retaining a validation envelope for callers."""
    result = validate_export(payload)
    if result["valid"]:
        result["json"] = simplejson.dumps(result["records"], ensure_ascii=False, use_decimal=True,
                                          allow_nan=False, indent=2)
    return result


def export_json(payload: dict) -> str:
    result = build_export(payload)
    if not result["valid"]:
        raise ValueError(simplejson.dumps(result["issues"], ensure_ascii=False, use_decimal=True))
    return result["json"]


def main(argv=None):
    """Project one financial export using portable JSON file/stdio IO."""
    import argparse
    from contextlib import ExitStack
    from pathlib import Path
    import sys

    operations = {"export_json": build_export, "build_export": build_export,
                  "validate_export": validate_export}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Input JSON path; omit or use - for stdin")
    parser.add_argument("--output", help="Output JSON path; omit or use - for stdout")
    parser.add_argument("--operation", choices=operations, default="export_json")
    args = parser.parse_args(argv)
    with ExitStack() as stack:
        try:
            source = (stack.enter_context(Path(args.input).open(encoding="utf-8-sig"))
                      if args.input and args.input != "-" else sys.stdin)
            payload = simplejson.load(source, use_decimal=True)
            if not isinstance(payload, dict):
                raise ValueError("Input must be a JSON object")
            result = operations[args.operation](payload)
        except (ValueError, OSError) as exc:
            result = {"valid": False, "issues": [{"code": "CLI_INPUT", "message": str(exc), "severity": "error"}]}
        try:
            destination = (stack.enter_context(Path(args.output).open("w", encoding="utf-8"))
                           if args.output and args.output != "-" else sys.stdout)
            if args.operation == "export_json" and result["valid"]:
                destination.write(result["json"])
            else:
                simplejson.dump(result, destination, use_decimal=True, ensure_ascii=False, allow_nan=False)
            destination.write("\n")
        except OSError as exc:
            print(f"CLI_OUTPUT: {exc}", file=sys.stderr)
            return 1
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
