"""Deterministic shipping charge rules; no agent execution or model calls."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re

import pycountry

VERSION = "1.4.0"
ALIASES = {
    "handling fee": "Handling Charge", "h/d fee": "Handling Charge",
    "h/c": "Handling Charge", "h/c fee": "Handling Charge",
    "handling charge": "Handling Charge", "doc fee": "Documentation Fee",
    "documentation fee": "Documentation Fee", "thc": "Terminal Handling Charge",
    "terminal handling charge": "Terminal Handling Charge",
    "trucking fee": "Trucking Charge", "trucking charge": "Trucking Charge",
    "customs fee": "Customs Clearance Fee", "customs clearance fee": "Customs Clearance Fee",
    "storage fee": "Storage Charge", "storage charge": "Storage Charge",
}
EDIT_FIELDS = {
    "document_type", "reference_no", "document_date", "issuer", "recipient",
    "charge_item", "amount", "currency", "payment_term", "bill_of_lading",
    "booking_no", "container_no", "quantity", "unit_price", "creditor", "debtor",
}


def issue(code, field, message, charge_id=None, **extra):
    return {"code": code, "field": field, "message": message, "charge_id": charge_id,
            "severity": "error", "repairable": False, **extra}


def unique_issues(issues):
    return list({json.dumps(item, sort_keys=True, default=str, ensure_ascii=False): item
                 for item in issues}.values())


def norm(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def money(value):
    if value is None or isinstance(value, bool):
        raise ValueError("金额缺失或不是数字")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("金额不是有效十进制数字") from exc
    if not result.is_finite():
        raise ValueError("金额必须为有限数字")
    return result


def flatten(record):
    out = {k: deepcopy(v) for k, v in record.items() if k not in {
        "document_info", "transaction_party", "charge_details", "financial_attributes", "audit_trail"}}
    for group in ("document_info", "transaction_party", "charge_details", "financial_attributes"):
        out.update(record.get(group) or {})
    return out


DOCUMENT_TYPES = {
    "email_pre_alert": "Pre-Alert", "pre_alert": "Pre-Alert", "pre-alert": "Pre-Alert",
    "pre alert": "Pre-Alert", "pre-alert email": "Pre-Alert", "pre alert email": "Pre-Alert",
    "arrival_notice": "General Notice", "arrival notice": "General Notice",
    "general_notice": "General Notice", "general notice": "General Notice",
    "pai-cma-notice": "General Notice",
    "pai-zim-notice": "Debit Invoice", "debit_invoice": "Debit Invoice",
    "debit invoice": "Debit Invoice",
    "debit_note": "Debit Note", "debit note": "Debit Note",
    "credit_note": "Credit Note", "credit note": "Credit Note",
}
PAYMENT_TERMS = {"pp": "PP", "prepaid": "PP", "pre-paid": "PP", "cc": "CC", "collect": "CC"}
PAY_RELATION = re.compile(
    r'(?P<payer>[A-Za-z][A-Za-z0-9&.\-]*(?:\s+[A-Za-z][A-Za-z0-9&.\-]*){0,4})\s+'
    r'pay(?:s)?\s+(?P<payee>[A-Za-z][A-Za-z0-9&.\-]*(?:\s+[A-Za-z][A-Za-z0-9&.\-]*){0,4})',
    re.IGNORECASE)


def settle_payment_term(record):
    """Keep only PP/CC that the charge's own evidence actually prints."""
    term = record.get("payment_term")
    if term is None:
        return record, None
    if _human_confirmed(record, "payment_term"):
        return ({**record, "payment_term": PAYMENT_TERMS.get(norm(term), term),
                 "raw_payment_term": record.get("raw_payment_term") or term}, None)
    mapped = PAYMENT_TERMS.get(norm(term))
    quotes = _field_quotes(record, "payment_term") or [
        str(ref.get("quote") or "") for ref in record.get("evidence") or []]
    supported = mapped is not None and any(
        (mapped == "PP" and re.search(r"\bPP\b|PRE-?PAID", quote, re.IGNORECASE))
        or (mapped == "CC" and re.search(r"\bCC\b|COLLECT", quote, re.IGNORECASE))
        for quote in quotes)
    if supported:
        return ({**record, "payment_term": mapped,
                 "raw_payment_term": record.get("raw_payment_term") or term},
                None)
    settled = {**record, "payment_term": None,
               "raw_payment_term": record.get("raw_payment_term") or term}
    return settled, f"原文未给出该费用行的PP/CC付款方式（{term}），已留空待业务确认"


def normalized(record, mapping=None):
    out = flatten(record)
    if out.get("document_type"):
        out["document_type"] = DOCUMENT_TYPES.get(norm(out["document_type"]), out["document_type"])
    out["raw_charge_item"] = out.get("raw_charge_item") or out.get("charge_item")
    configured = {norm(k): v for k, v in (mapping or {}).items()}
    item_key = norm(out.get("charge_item"))
    if item_key in configured:
        out["charge_item"] = configured[item_key]
    elif item_key in ALIASES:
        out["charge_item"] = ALIASES[item_key]
    elif re.search(r"(?<![A-Za-z])H\s*/\s*C(?![A-Za-z])", str(out.get("charge_item") or ""), re.IGNORECASE):
        out["charge_item"] = "Handling Charge"
    out["raw_payment_term"] = out.get("raw_payment_term", out.get("payment_term"))
    terms = {"pp": "PP", "prepaid": "PP", "freight prepaid": "PP", "cc": "CC",
             "collect": "CC", "freight collect": "CC"}
    if out.get("payment_term") is not None:
        out["payment_term"] = terms.get(norm(out["payment_term"]), out["payment_term"])
    if out.get("currency") is not None:
        out["currency"] = str(out["currency"]).strip().upper()
    if out.get("amount") is not None:
        try:
            out["amount"] = money(out["amount"])
            if out.get("line_role") == "discount":
                out["raw_amount"] = out.get("raw_amount", out["amount"])
                out["amount"] = -abs(out["amount"])
        except ValueError:
            pass
    return out


def _rows(payload):
    return payload.get("charges", payload.get("records", []))


def validate_amounts(payload: dict) -> dict:
    """Check finite decimal amounts, currency, arithmetic and declared totals."""
    issues, groups, declared_roles = [], {}, set()
    incoming = _rows(payload)
    charges = [normalized(c, payload.get("charge_mapping")) for c in incoming]
    source_docs = {}
    for document in payload.get("documents", []):
        if document.get("source_id") and document.get("document_id"):
            source_docs.setdefault(str(document["source_id"]), set()).add(str(document["document_id"]))
    for row in [*incoming, *payload.get("totals", [])]:
        if row.get("source_id") and row.get("document_id"):
            source_docs.setdefault(str(row["source_id"]), set()).add(str(row["document_id"]))

    def scope(row):
        """One document in a source makes source and document scopes comparable."""
        document_id = row.get("document_id")
        if document_id:
            return str(document_id)
        source_id = row.get("source_id")
        documents = source_docs.get(str(source_id)) if source_id is not None else None
        if documents and len(documents) == 1:
            return next(iter(documents))
        return str(source_id) if source_id is not None else None

    normalized_charges = [{"charge_id": current.get("charge_id"),
                           "input_amount": flatten(original).get("amount"),
                           "amount": deepcopy(current.get("amount")),
                           "currency": current.get("currency"),
                           "line_role": current.get("line_role", "charge")}
                          for original, current in zip(incoming, charges)]
    for c in charges:
        cid = c.get("charge_id")
        try:
            amount = money(c.get("amount"))
        except ValueError as exc:
            issues.append(issue("INVALID_AMOUNT", "amount", str(exc), cid))
            continue
        currency = c.get("currency")
        if not currency or not pycountry.currencies.get(alpha_3=currency):
            issues.append(issue("INVALID_CURRENCY", "currency", "币种须为明确ISO 4217代码，不能猜测$等符号", cid))
        if c.get("quantity") is not None and c.get("unit_price") is not None:
            try:
                expected = money(c["quantity"]) * money(c["unit_price"])
                if c.get("line_role") == "discount":
                    expected = -abs(expected)
                tolerance = money(payload.get("rounding_tolerance", "0.01"))
                if tolerance < 0 or tolerance > Decimal("0.05"):
                    raise ValueError("舍入容差须介于0和0.05")
                if abs(amount - expected) > tolerance:
                    issues.append(issue("LINE_ARITHMETIC", "amount", "数量×单价与费用金额不符", cid,
                                        expected=str(expected), actual=str(amount)))
            except ValueError as exc:
                issues.append(issue("INVALID_ARITHMETIC", "quantity/unit_price", str(exc), cid))
        key = (scope(c), currency)
        if c.get("line_role", "charge") in {"charge", "tax", "discount"}:
            groups[key] = groups.get(key, Decimal(0)) + amount
            declared_roles.add((key, c.get("line_role", "charge")))
    for adjustment in payload.get("totals", []):
        role = adjustment.get("role", "total")
        key = (scope(adjustment), str(adjustment.get("currency", "")).upper())
        if role in {"tax", "discount"} and (key, role) not in declared_roles:
            try:
                amount = money(adjustment.get("amount"))
                groups[key] = groups.get(key, Decimal(0)) + (-abs(amount) if role == "discount" else amount)
            except ValueError as exc:
                issues.append(issue("INVALID_TOTAL", "totals", str(exc)))
    for total in payload.get("totals", []):
        role = total.get("role", "total")
        if role != "total":
            continue
        key = (scope(total), str(total.get("currency", "")).upper())
        try:
            expected = money(total.get("amount"))
            if key not in groups or abs(groups[key] - expected) > Decimal("0.01"):
                issues.append(issue("TOTAL_MISMATCH", "totals", "同一单据、币种的费用合计与原文总额不符",
                                    expected=str(expected), actual=str(groups.get(key))))
        except ValueError as exc:
            issues.append(issue("INVALID_TOTAL", "totals", str(exc)))
    return {"valid": not issues, "issues": issues, "revision": payload.get("revision"),
            "normalized_charges": normalized_charges,
            "totals": [{"scope_id": k[0], "currency": k[1], "amount": v} for k, v in groups.items()]}


def determine_posting(charge, accounting_entity):
    if not accounting_entity:
        return None, "调用方尚未指定记账主体"
    creditor, debtor = norm(charge.get("creditor")), norm(charge.get("debtor"))
    entity = norm(accounting_entity)
    if creditor and debtor and creditor == debtor:
        return None, "债权人与债务人为同一主体，须人工核实"
    # One stated side is enough to fix the direction: if the caller's entity is
    # the creditor the charge is receivable even when the payer is not yet
    # known, and vice versa. The missing counterparty stays null.
    if creditor and entity == creditor:
        return "AR", "当前主体为该笔费用债权人"
    if debtor and entity == debtor:
        return "AP", "当前主体为该笔费用债务人"
    if not creditor and not debtor:
        return None, "缺少明确债权人/债务人关系，须人工核实"
    return None, "当前记账主体不属于已识别的收费关系"


CURRENCY_SYMBOLS = ("$", "¥", "￥", "€", "£", "₩", "₹")


def _field_quotes(record, field):
    return [str(ref.get("quote") or "") for ref in record.get("evidence") or []
            if str(ref.get("field") or "") == field]


def _human_confirmed(record, field):
    """A current human-confirmed value outranks automated settlement."""
    return any(str(path).split(".")[-1] == field
               for path in (record.get("human_confirmed") or {}))


def _iso_currency_tokens(text):
    tokens = re.findall(r"(?<![A-Za-z])[A-Z]{3}(?![A-Za-z])", text.upper())
    return [token for token in tokens if pycountry.currencies.get(alpha_3=token)]


def settle_symbol_currency(record):
    """A bare currency symbol never authorizes an inferred ISO code."""
    currency = record.get("currency")
    if not currency:
        return record, []
    if _human_confirmed(record, "currency"):
        return record, []
    quotes = _field_quotes(record, "currency")
    if not quotes or any(_iso_currency_tokens(quote) for quote in quotes):
        return record, []
    if not any(symbol in quote for quote in quotes for symbol in CURRENCY_SYMBOLS):
        return record, []
    settled = {**record, "currency": None}
    return settled, [issue("CURRENCY_SYMBOL_AMBIGUOUS", "currency",
        "原文只有货币符号，没有ISO 4217代码；币种留空待复核", record.get("charge_id"))]


def settle_unbacked_parties(record):
    """Drop a party value that its own field evidence does not contain."""
    settled, notes = dict(record), []
    for field in ("creditor", "debtor"):
        value = settled.get(field)
        if not value or _human_confirmed(record, field):
            continue
        quotes = _field_quotes(record, field)
        if not quotes:
            continue
        needle = str(value).strip().casefold()
        if any(needle in quote.casefold() for quote in quotes):
            continue
        settled[field] = None
        notes.append(issue("PARTY_UNSUPPORTED", field,
            f"{field}未出现在该字段的原文引用中；留空待复核", record.get("charge_id")))
    return settled, notes


def settle_relationship(record):
    """Fill a missing direction from an explicit "A pay B" source line."""
    if record.get("creditor") and record.get("debtor"):
        return record, None
    for ref in record.get("evidence") or []:
        quote = str(ref.get("quote") or "")
        match = PAY_RELATION.search(quote)
        if not match:
            continue
        payer, payee = match.group("payer").strip(), match.group("payee").strip()
        if not payer or not payee or norm(payer) == norm(payee):
            continue
        if norm(payer) in {"please", "kindly", "to", "must", "will", "should", "payment"}:
            continue
        settled, notes = dict(record), []
        if not settled.get("creditor") and not _human_confirmed(record, "creditor"):
            settled["creditor"] = payee
            notes.append(f"原文“{quote.strip()}”表明{payee}收款")
        if not settled.get("debtor") and not _human_confirmed(record, "debtor"):
            settled["debtor"] = payer
            notes.append(f"原文“{quote.strip()}”表明{payer}付款")
        if notes:
            return settled, "；".join(notes)
    return record, None


def validate_posting(payload: dict) -> dict:
    issues = []
    for original in _rows(payload):
        c = flatten(original)
        posting, reason = determine_posting(c, payload.get("accounting_entity", c.get("accounting_entity")))
        if posting is None:
            issues.append(issue("POSTING_UNRESOLVED", "posting_type", reason, c.get("charge_id")))
        elif c.get("posting_type") not in (None, posting):
            issues.append(issue("POSTING_CONFLICT", "posting_type", "AR/AP与明确收费关系不符", c.get("charge_id")))
    return {"valid": not issues, "issues": issues}


def _same(a, b, fields):
    try:
        return all(a.get(f) is not None and b.get(f) is not None and
                   (money(a[f]) == money(b[f]) if f == "amount" else norm(a[f]) == norm(b[f])) for f in fields)
    except ValueError:
        return False


def find_matches(charge, existing):
    levels = [
        ("reference", ("reference_no", "charge_item")),
        ("bill_of_lading", ("bill_of_lading", "charge_item", "currency")),
        ("booking", ("booking_no", "charge_item", "currency")),
        ("container", ("container_no", "issuer", "recipient", "document_date", "amount")),
    ]
    for level, keys in levels:
        matches = [r for r in existing if _same(charge, r, keys)]
        if matches:
            return level, matches
    return None, []


def resolve_matches(charge, existing):
    level, matches = find_matches(charge, existing)
    issues = []
    if charge.get("selected_match_id") is not None:
        selected = [r for r in matches if str(r.get("charge_id", r.get("id"))) == str(charge["selected_match_id"])]
        if len(selected) == 1:
            matches = selected
        else:
            issues.append(issue("INVALID_MATCH_SELECTION", "selected_match_id", "所选账单不在当前候选集合内", charge.get("charge_id")))
    return level, matches, issues


def retrieve_history(payload: dict) -> dict:
    """Select usable same-entity historical rows using the existing match tiers.

    The host supplies persisted task projections, never model-authored history.
    Accepted UPDATE descendants supersede their exact parent; independent rows
    and competing update branches remain separate candidates for review.
    """
    task = payload['task']
    entity = norm(task.get('accounting_entity'))
    rows, scanned = {}, 0
    if entity:
        for previous in payload.get('historical_tasks', []):
            scanned += 1
            validation = previous.get('validation') or {}
            if (previous.get('id') == task.get('id') or previous.get('deleted_at')
                    or previous.get('status') not in {'completed', 'approved'}
                    or norm(previous.get('accounting_entity')) != entity
                    or validation.get('ok') is not True
                    or validation.get('revision') != previous.get('revision')
                    or (previous.get('approval') or {}).get('decision') == 'reject'):
                continue
            for record in previous.get('records', []):
                row = normalized(record, task.get('charge_mapping'))
                if (row.get('operation') not in {'CREATE', 'UPDATE'} or not row.get('charge_id')
                        or row.get('revision', previous['revision']) != previous['revision']
                        or norm(row.get('accounting_entity')) != entity):
                    continue
                source = dict(task_id=previous['id'], revision=previous['revision'], charge_id=row['charge_id'])
                key = (source['task_id'], source['revision'], source['charge_id'])
                row['history_identity'] = row.get('history_identity') or f"{previous['id']}:{row['charge_id']}"
                row['history_source'] = source
                row['charge_id'] = 'history-' + sha256(json.dumps(key).encode()).hexdigest()[:24]
                rows[key] = row
        superseded = set()
        for row in rows.values():
            parent = row.get('history_match') or {}
            key = (parent.get('task_id'), parent.get('revision'), parent.get('charge_id'))
            if key in rows and rows[key]['history_identity'] == row['history_identity'] and key != (
                    row['history_source']['task_id'], row['history_source']['revision'], row['history_source']['charge_id']):
                superseded.add(key)
        baseline = [row for key, row in rows.items() if key not in superseded]
    else:
        baseline = []
    selected = {}
    for raw in _rows(task):
        _, matches = find_matches(normalized(raw, task.get('charge_mapping')), baseline)
        for row in matches:
            selected[row['charge_id']] = row
    candidates = [selected[key] for key in sorted(selected)]
    binding = dict(revision=task['revision'], accounting_entity=entity, existing_records=candidates)
    digest = sha256(json.dumps(binding, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()
    return dict(existing_records=deepcopy(candidates), history_lookup=dict(
        status='searched' if entity else 'waiting_entity', revision=task['revision'],
        accounting_entity=entity, scanned_tasks=scanned, eligible_records=len(baseline),
        candidate_count=len(candidates), digest=digest,
        sources=[deepcopy(row['history_source']) for row in candidates]))


def _history_issues(payload):
    if payload.get('history_mode') != 'automatic':
        return []
    receipt = payload.get('history_lookup') or {}
    if (receipt.get('status') != 'searched' or receipt.get('revision') != payload.get('revision')
            or receipt.get('accounting_entity') != norm(payload.get('accounting_entity'))):
        return [issue('HISTORY_NOT_SEARCHED', 'match', '当前主体和版本尚未完成历史账单检索')]
    current = payload.get('current_history_lookup')
    if current is not None and current.get('digest') != receipt.get('digest'):
        return [issue('HISTORY_STALE', 'match', '历史候选已变化，请重新核对后确认或导出')]
    return []


def _reused_matches(matches):
    owners = {}
    for match in matches:
        if len(match['candidates']) == 1:
            owners.setdefault(str(match['candidates'][0]), []).append(match['charge_id'])
    return [issue('MATCH_REUSED', 'match', '多条新费用指向同一历史费用，需核对行身份', charge_id)
            for ids in owners.values() if len(ids) > 1 for charge_id in ids]


def validate_matching(payload: dict) -> dict:
    issues, matches = _history_issues(payload), []
    if "existing_records" not in payload:
        issues.append(issue("EXISTING_UNSPECIFIED", "existing_records", "须显式提供旧账单列表，空列表表示没有旧账单"))
    old = [normalized(c, payload.get("charge_mapping")) for c in payload.get("existing_records", [])]
    for raw in _rows(payload):
        c = normalized(raw, payload.get("charge_mapping"))
        level, found, selection_issues = resolve_matches(c, old)
        issues.extend(selection_issues)
        matches.append({"charge_id": c.get("charge_id"), "level": level,
                        "candidates": [r.get("charge_id", r.get("id")) for r in found]})
        if len(found) > 1:
            issues.append(issue("AMBIGUOUS_MATCH", "match", "同级匹配有多个候选，不能自动选择第一条", c.get("charge_id")))
    issues.extend(_reused_matches(matches))
    return {"valid": not issues, "issues": issues, "matches": matches}


def _instruction(c, old, instructions, rules=None):
    found = []
    for directive in instructions:
        if directive.get("target_id") is not None:
            hit = str(directive["target_id"]) == str(old.get("charge_id", old.get("id")))
        else:
            hit = bool(directive.get("reference_no") and directive.get("charge_item")) and (
                norm(directive["reference_no"]) == norm(c.get("reference_no")) and
                norm(normalized(directive, rules).get("charge_item")) == norm(c.get("charge_item")))
        if hit:
            found.append(directive)
    return found


def validate_updates(payload: dict) -> dict:
    issues = []
    for directive in payload.get("update_instructions", []):
        changes = directive.get("changes")
        if not isinstance(changes, dict) or not changes:
            issues.append(issue("EMPTY_UPDATE", "update_instructions", "更新指令须包含非空changes对象"))
        elif set(changes) - EDIT_FIELDS:
            issues.append(issue("INVALID_UPDATE_FIELD", "changes", "更新包含不支持的字段",
                                fields=sorted(set(changes) - EDIT_FIELDS)))
        if not directive.get("target_id") and not (directive.get("reference_no") and directive.get("charge_item")):
            issues.append(issue("UPDATE_TARGET_MISSING", "update_instructions", "更新须指定target_id或单据号和费用名"))
    return {"valid": not issues, "issues": issues}


def _nested(c, operation, entity, posting, reasons, revision):
    result = {
        "charge_id": c.get("charge_id"), "revision": revision, "operation": operation,
        "document_info": {k: c.get(k) for k in ("document_type", "reference_no", "document_date")},
        "transaction_party": {k: c.get(k) for k in ("issuer", "recipient")},
        "charge_details": {k: c.get(k) for k in ("charge_item", "amount", "currency", "payment_term")},
        "financial_attributes": {"accounting_entity": entity, "posting_type": posting},
        "audit_trail": {"ai_reasoning": reasons},
    }
    for key in ("source_id", "document_id", "line_id", "evidence", "creditor", "debtor",
                "bill_of_lading", "booking_no", "container_no", "quantity", "unit_price",
                "raw_charge_item", "raw_payment_term", "raw_amount", "raw_currency", "raw_quantity", "raw_unit_price",
                "human_confirmed", "line_role", "selected_match_id", "history_identity", "history_match"):
        if key in c:
            result[key] = deepcopy(c[key])
    return result


def reconcile_charges(payload: dict) -> dict:
    """Normalize, uniquely match and propose CREATE/UPDATE/NO_CHANGE or review."""
    revision = int(payload.get("revision", 1))
    entity = payload.get("accounting_entity")
    rules = payload.get("charge_mapping")
    existing = [normalized(r, rules) for r in payload.get("existing_records", [])]
    instructions = payload.get("update_instructions", [])
    update_check = validate_updates(payload)
    upstream_issues = [*payload.get("evidence_issues", []), *payload.get("coverage_issues", []), *_history_issues(payload)]
    for result_key in ("extraction", "evidence", "coverage_validation"):
        if result_key == "evidence" and "evidence_issues" in payload:
            continue
        if isinstance(payload.get(result_key), dict):
            upstream_issues.extend(payload[result_key].get("issues", []))
    for source in payload.get("sources", []):
        ranges = (source.get("metadata") or {}).get("ocr_ranges", []) + (source.get("metadata") or {}).get("ocr_frames", [])
        if source.get("status") in {"waiting_url", "partial", "failed"} or any(r.get("status") != "ready" for r in ranges):
            upstream_issues.append(issue("SOURCE_INCOMPLETE", "sources", "原始材料存在未完成的解析/OCR范围",
                                         source_id=source.get("source_id")))
    upstream_issues = [i for i in upstream_issues if isinstance(i, dict) and i.get("severity") != "warning" and i.get("blocking") is not False]
    upstream_issues = unique_issues(upstream_issues)
    issues, records = [*update_check["issues"], *deepcopy(upstream_issues)], []
    for index, raw in enumerate(_rows(payload)):
        c = normalized(raw, rules)
        for key in ('history_identity', 'history_match', 'history_source'):
            c.pop(key, None)  # derived from persisted candidates, never extraction input
        if not c.get("charge_id"):
            signature = json.dumps({"source": c.get("source_id"), "line": c.get("line_id"),
                                    "evidence": c.get("evidence"), "index": index}, sort_keys=True, default=str)
            c["charge_id"] = "charge-" + sha256(signature.encode()).hexdigest()[:16]
        reasons, local = [], []
        if c.get("line_role", "charge") not in {"charge", "tax", "discount"}:
            continue  # totals and repeated headers are never charge rows
        c, currency_notes = settle_symbol_currency(c)
        c, party_notes = settle_unbacked_parties(c)
        c, relationship_reason = settle_relationship(c)
        if relationship_reason:
            reasons.append(relationship_reason)
        c, term_reason = settle_payment_term(c)
        if term_reason:
            reasons.append(term_reason)
        local.extend(currency_notes)
        local.extend(party_notes)
        level, matches, selection_issues = resolve_matches(c, existing)
        local.extend(selection_issues)
        if c.get("selected_match_id") is not None and not selection_issues:
            reasons.append("调用方明确选择了已验证候选账单")
        operation = "CREATE"
        if "existing_records" not in payload:
            local.append(issue("EXISTING_UNSPECIFIED", "existing_records", "旧账单范围尚未明确", c["charge_id"]))
        if len(matches) > 1:
            operation = "PENDING_REVIEW"
            local.append(issue("AMBIGUOUS_MATCH", "match", "多个旧账单满足同级条件", c["charge_id"]))
        elif matches:
            old = matches[0]
            directives = _instruction(c, old, instructions, rules)
            if len(directives) > 1:
                local.append(issue("AMBIGUOUS_UPDATE", "changes", "命中多条更新指令", c["charge_id"]))
            elif len(directives) == 1 and update_check["valid"]:
                changes = directives[0]["changes"]
                merged = deepcopy(old)
                merged.update(changes)  # missing key inherits; null explicitly clears
                merged["charge_id"] = c["charge_id"]
                merged["evidence"] = deepcopy(c.get("evidence", []))
                merged["source_id"] = c.get("source_id", old.get("source_id"))
                candidate = normalized(merged, rules)
                different = any(candidate.get(k) != old.get(k) for k in changes)
                c = candidate
                operation = "UPDATE" if different else "NO_CHANGE"
                reasons.append("明确更新指令仅修改指定字段，其余继承旧账单" if different else "明确更新值与旧账单一致")
            else:
                comparable = EDIT_FIELDS
                differences = [k for k in comparable if c.get(k) is not None and c.get(k) != old.get(k)]
                if differences:
                    local.append(issue("UPDATE_NOT_AUTHORIZED", "changes", "存在差异但没有明确更新指令", c["charge_id"], fields=differences))
                else:
                    inherited = deepcopy(old)
                    inherited.update({k: v for k, v in c.items() if v is not None})
                    c = inherited
                    operation = "NO_CHANGE"
                    reasons.append("唯一匹配且已提供字段没有变化")
            reasons.append("旧账单匹配层级：" + str(level))
            if old.get('history_source'):
                c['history_match'] = deepcopy(old['history_source'])
                c['history_identity'] = old['history_identity']
        else:
            reasons.append("在调用方提供的旧账单范围中未找到匹配费用")
        posting, explanation = determine_posting(c, entity)
        reasons.append(explanation)
        if not posting:
            local.append(issue("POSTING_UNRESOLVED", "posting_type", explanation, c["charge_id"]))
        for field in ("charge_item",):
            if not c.get(field):
                local.append(issue("REQUIRED_FIELD", field, "费用名缺失", c["charge_id"]))
        local.extend(validate_amounts({"charges": [c]})["issues"])
        if not c.get("evidence"):
            local.append(issue("EVIDENCE_MISSING", "evidence", "费用缺少来源证据", c["charge_id"]))
        elif any(ref.get("verified") is not True for ref in c["evidence"]):
            local.append(issue("EVIDENCE_UNVERIFIED", "evidence", "费用引用尚未通过原文回读校验", c["charge_id"]))
        source_ids = {str(c.get("source_id")), *[str(e.get("source_id")) for e in c.get("evidence", [])]}
        for upstream in upstream_issues:
            if not isinstance(upstream, dict) or upstream.get("severity") == "warning" or upstream.get("blocking") is False:
                continue
            if upstream.get("charge_id") and upstream["charge_id"] != c["charge_id"]:
                continue
            if upstream.get("source_id") and str(upstream["source_id"]) not in source_ids:
                continue
            local.append({**deepcopy(upstream), "charge_id": c["charge_id"]})
        if local:
            local = unique_issues(local)
        if any(i.get('severity', 'error') == 'error' for i in local):
            operation = "PENDING_REVIEW"
        result = _nested(c, operation, entity, posting, reasons, revision)
        result["issues"] = local
        result["match"] = {"level": level, "candidate_ids": [r.get("charge_id", r.get("id")) for r in matches]}
        records.append(result)
        issues.extend(local)
    reused = _reused_matches([dict(charge_id=r['charge_id'], candidates=r['match']['candidate_ids']) for r in records])
    issues.extend(reused)
    for record in records:
        local = [i for i in reused if i['charge_id'] == record['charge_id']]
        if local:
            record['operation'] = 'PENDING_REVIEW'
            record['issues'].extend(local)
    totals_check = validate_amounts({"charges": _rows(payload), "totals": payload.get("totals", []),
                                     "documents": payload.get("documents", [])})
    total_issues = [i for i in totals_check["issues"] if i["code"] in {"TOTAL_MISMATCH", "INVALID_TOTAL"}]
    if total_issues:
        issues.extend(total_issues)
        for record in records:
            record["operation"] = "PENDING_REVIEW"
            record["issues"].extend(total_issues)
    # Identical claims across different source documents need identity evidence;
    # same-name rows within one source are intentionally kept separate.
    for i, left in enumerate(records):
        for right in records[i + 1:]:
            a, b = flatten(left), flatten(right)
            same_claim = _same(a, b, ("reference_no", "charge_item", "currency", "amount"))
            if same_claim and a.get("source_id") != b.get("source_id"):
                for record in (left, right):
                    error = issue("POSSIBLE_DUPLICATE", "match", "不同来源重复描述同一费用，需核实行身份，不能重复新增", record["charge_id"])
                    record["operation"] = "PENDING_REVIEW"
                    record["issues"].append(error)
                    issues.append(error)
    unique = unique_issues(issues)
    return {"valid": not any(i.get("severity", "error") == "error" for i in unique),
            "issues": unique, "records": records, "revision": revision,
            "rule_version": VERSION}


def main(argv=None):
    """Call one existing financial function with portable JSON file/stdio IO."""
    import argparse
    from contextlib import ExitStack
    from pathlib import Path
    import simplejson
    import sys

    operations = {"reconcile_charges": reconcile_charges, "validate_amounts": validate_amounts,
                  "validate_matching": validate_matching, "validate_updates": validate_updates,
                  "validate_posting": validate_posting}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Input JSON path; omit or use - for stdin")
    parser.add_argument("--output", help="Output JSON path; omit or use - for stdout")
    parser.add_argument("--operation", choices=operations, default="reconcile_charges")
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
            simplejson.dump(result, destination, use_decimal=True, ensure_ascii=False, allow_nan=False)
            destination.write("\n")
        except OSError as exc:
            print(f"CLI_OUTPUT: {exc}", file=sys.stderr)
            return 1
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
