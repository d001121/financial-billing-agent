"""Explainable billing rule support; domain validation remains in existing Skills."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import math


POLICY_VERSION = "3.1.0"
FIELDS = ("reference_no", "charge_item", "amount", "currency")
WEIGHTS = {"field_support": 70, "consistency": 20, "coverage": 10}
CORE_FIELD_WEIGHTS = {"amount": 0.45, "currency": 0.35, "charge_item": 0.20}
DOCUMENT_FIELDS = {"reference_no", "charge_item", "amount", "currency", "payment_term"}
STRUCTURED_KINDS = {"pdf_layout_financial", "ocr_structured", "table", "cell",
                    "xlsx_cell", "docx_table", "pdf_table"}
REQUIRED_CHECKS = ("schema", "coverage", "evidence", "amount", "matching", "update",
                   "posting", "revision", "capability", "budget")
LOCATION_KEYS = ("source_id", "anchor", "quote", "quote_start", "quote_end", "page", "bbox",
                 "sheet", "row", "column", "paragraph", "table", "cell", "attachment_path",
                 "filename", "render_version", "occurrence_id", "source_version", "content_sha256",
                 "value_start", "value_end")
LABELS = {"field_support": "关键字段原文支持", "consistency": "原文约束核对", "coverage": "材料覆盖完整性"}


def _decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _flat(value):
    result = dict(value)
    for key in ("document_info", "charge_details", "financial_attributes", "transaction_party"):
        if isinstance(value.get(key), dict):
            result.update(value[key])
    return result


def _candidate_record(charge, revision):
    """Project a draft for display only; do not decide financial direction."""
    result = deepcopy(charge)
    result.update(revision=charge.get("revision", revision), operation="PENDING_REVIEW")
    for group, names in {
        "document_info": ("document_type", "reference_no", "document_date"),
        "transaction_party": ("issuer", "recipient"),
        "charge_details": ("charge_item", "amount", "currency", "payment_term"),
        "financial_attributes": ("accounting_entity", "posting_type"),
    }.items():
        result[group] = {key: deepcopy(charge.get(key)) for key in names}
    return result


def _policy(options):
    if not isinstance(options, dict) or set(options) - {"weights", "high_threshold", "medium_threshold", "policy_id", "review_threshold"}:
        raise ValueError("options仅支持weights/high_threshold/medium_threshold/policy_id/review_threshold")
    weights = options.get("weights", WEIGHTS)
    if not isinstance(weights, dict) or set(weights) != set(WEIGHTS):
        raise ValueError("weights必须完整提供三个已定义证据组")
    if any(isinstance(value, bool) or not isinstance(value, (int, float, Decimal)) or
           not math.isfinite(float(value)) or value < 0 for value in weights.values()):
        raise ValueError("权重须为有限非负数字")
    if abs(sum(float(value) for value in weights.values()) - 100) > 1e-8:
        raise ValueError("权重之和必须为100")
    high, medium = options.get("high_threshold", 90), options.get("medium_threshold", 65)
    if any(isinstance(value, bool) or not isinstance(value, (int, float, Decimal)) or
           not math.isfinite(float(value)) for value in (high, medium)) or not 0 <= medium < high <= 100:
        raise ValueError("阈值须满足0 <= medium < high <= 100")
    policy_id = options.get("policy_id", "grouped_source_support_v2")
    if not isinstance(policy_id, str) or not policy_id.strip():
        raise ValueError("policy_id必须为非空字符串")
    threshold = options.get('review_threshold', 80)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float, Decimal)) or not math.isfinite(float(threshold)) or not 0 <= threshold <= 100:
        raise ValueError('review_threshold须为0到100的有限数字')
    return {"policy_id": policy_id.strip(), "review_threshold": float(threshold), "weights": {key: float(value) for key, value in weights.items()},
            "high_threshold": float(high), "medium_threshold": float(medium)}


def _review_fields(candidate, fields, refs, issues, cid, threshold):
    """Route observed extraction uncertainty, separately from missing data and gates."""
    assessed, items = [], []
    for field, fact in fields.items():
        present = candidate.get(field) not in (None, '')
        raw = candidate.get('raw_' + field)
        observed_unresolved = not present and isinstance(raw, str) and bool(raw.strip()) and any(
            raw in ref.get('quote', '') for ref in refs)
        if not present and not observed_unresolved:
            continue
        score = fact['score'] if present else 0
        assessed.append((score, CORE_FIELD_WEIGHTS.get(field, 0.1)))
        if score < threshold:
            items.append(dict(charge_id=cid, field=field, score=score,
                value=deepcopy(candidate.get(field)), raw_value=raw,
                reason='原文已有值但尚未能明确解释' if observed_unresolved else '；'.join(fact['reasons'])))
    # Actual arithmetic/party contradictions are uncertainty about an existing
    # value. Missing fields, unavailable checks and infrastructure are not.
    contradictions = {'LINE_ARITHMETIC': 'amount', 'TOTAL_MISMATCH': 'amount',
                      'POSTING_CONFLICT': 'posting_type', 'RECORD_CANDIDATE_CONFLICT': None}
    for error in issues:
        if error.get('charge_id') not in (None, cid) or error.get('code') not in contradictions:
            continue
        field = contradictions[error['code']] or error.get('field')
        if candidate.get(field) in (None, '') or any(item['field'] == field for item in items):
            continue
        if threshold > 0:
            items.append(dict(charge_id=cid, field=field, score=0,
                value=deepcopy(candidate.get(field)), reason=error.get('message', '当前值存在矛盾')))
    weight = sum(value[1] for value in assessed)
    score = round(sum(score * weight for score, weight in assessed) / weight, 2) if weight else None
    return score, items


def _blocking(issue):
    return isinstance(issue, dict) and issue.get("severity", "error") not in {"warning", "info"} and issue.get("blocking") is not False


def _check_state(check, charge_id):
    if not isinstance(check, dict) or not isinstance(check.get("ok"), bool):
        return "unavailable"
    errors = [item for item in check.get("issues", []) if _blocking(item)]
    if any(item.get("charge_id") in (None, charge_id) for item in errors):
        return "failed"
    if check["ok"] and check.get("valid", True) is not False:
        return "passed"
    # Validators operate on all rows; an issue explicitly scoped to another row
    # does not falsify this row's component. Global validation still gates review.
    return "passed" if errors and all(item.get("charge_id") is not None for item in errors) else "failed"


def _refs(check, charge_id):
    if not isinstance(check, dict):
        return []
    rows = check.get("charges", check.get("records", []))
    matches = [row for row in rows if isinstance(row, dict) and row.get("charge_id") == charge_id]
    if len(matches) != 1:
        return []
    return _verified_refs(matches[0].get("evidence", []))


def _verified_refs(raw_refs):
    result, seen = [], set()
    for ref in raw_refs:
        if not isinstance(ref, dict) or ref.get("verified") is not True:
            continue
        start, end = ref.get("quote_start"), ref.get("quote_end")
        if not (ref.get("source_id") and ref.get("anchor") and isinstance(ref.get("quote"), str)
                and ref["quote"] and ref.get("content_sha256") and type(start) is int
                and type(end) is int and 0 <= start < end and end - start == len(ref["quote"])):
            continue
        # Same source text under aliases remains one occurrence. A field-specific
        # association is retained, but never awards a count-based bonus.
        key = (ref["content_sha256"], ref["anchor"], start, end, ref.get("field"), ref.get("line_id"))
        if key not in seen:
            seen.add(key)
            result.append(ref)
    return result


def _same_value(field, a, b):
    if field in ("amount", "quantity", "unit_price"):
        return _decimal(a) is not None and _decimal(a) == _decimal(b)
    return a is not None and b is not None and str(a).strip().casefold() == str(b).strip().casefold()


def _facts(check, charge_id):
    if not isinstance(check, dict) or check.get("field_support_contract") != "source_support_v2":
        return {}
    rows = [row for row in check.get("charges", []) if row.get("charge_id") == charge_id]
    return rows[0].get("field_support", {}) if len(rows) == 1 else {}


def _normalized_amount_matches(check, candidate, record_value, revision):
    """Reuse the current financial Skill's canonicalization, including discounts."""
    if not isinstance(check, dict) or check.get("revision") != revision:
        return False
    rows = [row for row in check.get("normalized_charges", []) if row.get("charge_id") == candidate.get("charge_id")]
    return len(rows) == 1 and _same_value("amount", rows[0].get("input_amount"), candidate.get("amount")) and \
        _same_value("amount", rows[0].get("amount"), record_value)


def _field_refs(refs, field):
    matched = [ref for ref in refs if str(ref.get("field") or "").split(".")[-1] == field]
    return matched or list(refs)


def _header_ref(ref):
    return (str(ref.get("kind") or "") == "mail_headers"
            or str(ref.get("anchor") or "").startswith("mail/headers"))


def _support_grade(field, fact, refs):
    """Grade source support instead of treating every supported value as certainty."""
    status = fact.get("status")
    if status == "ambiguous":
        return 40 if fact.get("ambiguity_kind") == "format" else 30, ["原文存在歧义，尚未唯一解释"]
    if status == "unsupported":
        return 10, ["原文与当前值矛盾或缺少支持"]
    if status != "supported":
        return 0, ["没有可用的当前原文支持"]
    refs = _field_refs(refs, field)
    quality, reasons = 0.85, ["原文值有可回读引用"]
    if len(fact.get("targets") or []) == 1:
        quality += 0.05
        reasons.append("唯一原文位置")
    explicit = any(
        str(ref.get("kind") or "") in STRUCTURED_KINDS
        or ref.get("table") is not None or ref.get("cell") is not None
        for ref in refs)
    if explicit:
        quality += 0.10
        reasons.append("结构化字段或表格单元格")
    sources = {str(ref.get("source_id")) for ref in refs if ref.get("source_id")}
    if len(sources) >= 2:
        quality += 0.05
        reasons.append("多个独立来源一致")
    elif sources:
        reasons.append("仅一个来源")
    if field in DOCUMENT_FIELDS and refs and all(_header_ref(ref) for ref in refs):
        quality -= 0.45
        reasons.append("仅邮件主题/头部支持，未在单据正文核对")
    return round(max(0.0, min(1.0, quality)) * 100), reasons


def _support(field, candidate, facts, refs, available):
    """Consume source semantics from evidence-linking; never parse original money here."""
    value = candidate.get(field)
    if value is None or value == "":
        return {"score": 0, "status": "missing", "reasons": ["当前字段缺失；未按模板补填"]}, []
    fact = facts.get(field, {})
    if not available or not refs or not _same_value(field, fact.get("value"), value):
        return {"score": 0, "status": "unavailable", "reasons": ["没有与当前候选一致的原文语义校验结果"]}, []
    keys = {(ref["content_sha256"], ref["quote_start"], ref["quote_end"], ref["source_id"], ref["anchor"]) for ref in refs}
    targets = [{key: deepcopy(target[key]) for key in LOCATION_KEYS if key in target} | {"field": field}
               for target in fact.get("targets", []) if isinstance(target, dict) and
               (target.get("content_sha256"), target.get("quote_start"), target.get("quote_end"),
                target.get("source_id"), target.get("anchor")) in keys]
    status = fact.get("status", "unavailable")
    if status not in {"supported", "unsupported", "ambiguous", "missing", "unavailable"}:
        status = "unavailable"
    if status == "supported" and not targets:
        status = "unavailable"
    score, graded_reasons = _support_grade(field, {**fact, "status": status, "targets": targets}, refs)
    reasons = graded_reasons if status == "supported" else deepcopy(fact.get("reasons") or ["原文支持不可用"])
    result = {"score": score, "status": status, "reasons": reasons}
    for key in ("observations", "ambiguity_kind"):
        if key in fact:
            result[key] = deepcopy(fact[key])
    return result, targets


def _token_locations(targets):
    return {(t["content_sha256"], t["anchor"], t["value_start"], t["value_end"])
            for t in targets if type(t.get("value_start")) is int and type(t.get("value_end")) is int
            and t["quote_start"] <= t["value_start"] < t["value_end"] <= t["quote_end"]}


def _arithmetic_support(candidate, facts, refs, available, amount_targets):
    if candidate.get("quantity") is None or candidate.get("unit_price") is None:
        return False, "原文未提供数量或单价；合法费用无需补齐模板字段"
    locations = [_token_locations(amount_targets)]
    for field in ("quantity", "unit_price"):
        fact, targets = _support(field, candidate, facts, refs, available)
        if fact["status"] != "supported":
            return False, f"{field}缺少唯一原文支持；模型填写后算术自洽不加分"
        locations.append(_token_locations(targets))
    if any(not location for location in locations) or any(
            locations[i] & locations[j] for i in range(3) for j in range(i + 1, 3)):
        return False, "数量、单价和金额须分别定位到原文中的不同数值字段"
    return True, "数量、单价、金额分别获原文支持，并复用确定性金额核对；同源约束仅计半组分"


def _scope(payload, row):
    if row.get('document_id'):
        return str(row['document_id'])
    sid = row.get('source_id')
    documents = {str(r['document_id']) for r in [*payload.get('documents', []),
        *payload.get('charges', []), *payload.get('totals', [])]
        if r.get('source_id') == sid and r.get('document_id')}
    return next(iter(documents)) if len(documents) == 1 else str(sid) if sid is not None else None


def _total_support(payload, check, scope, currency):
    """Require fresh read-back of a unique declared total, not a computed sum."""
    totals = [(index, row) for index, row in enumerate(payload.get("totals", []))
              if row.get("role", "total") == "total" and
              _scope(payload, row) == scope and row.get("currency") == currency]
    if not totals:
        return False, "没有当前范围的原文总额；计算出的合计不等于原文总额"
    if len(totals) != 1:
        return False, "当前范围存在多个声明总额，缺少唯一总额关联"
    if not isinstance(check, dict) or check.get("revision") != payload.get("revision") or \
            payload.get("validation", {}).get("revision") != payload.get("revision"):
        return False, "没有当前版本的总额证据回读结果"
    index, total = totals[0]
    verified = [row for row in check.get("total_evidence", []) if isinstance(row, dict) and
                type(row.get("total_index")) is int and row["total_index"] == index and
                row.get("role", "total") == "total" and
                _scope(payload, row) == scope and row.get("currency") == currency and
                _decimal(row.get("amount")) == _decimal(total.get("amount"))]
    if len(verified) != 1:
        return False, "当前证据校验没有唯一关联的总额原文"
    if check.get("field_support_contract") != "source_support_v2":
        return False, "没有当前版本的总额语义支持结果"
    row = verified[0]
    refs = _verified_refs(row.get("evidence", []))
    for field in ("amount", "currency"):
        fact, targets = _support(field, total, row.get("field_support", {}), refs, True)
        if fact["status"] != "supported":
            return False, f"总额{field}缺少唯一的当前原文支持"
        if field == "amount":
            total_locations = _token_locations(targets)
            if not total_locations:
                return False, '总额缺少独立数值位置'
            for charge in check.get("charges", []):
                if _scope(payload, charge) != scope:
                    continue
                locations = _token_locations(charge.get("field_support", {}).get("amount", {}).get("targets", []))
                if total_locations & locations and not locations - total_locations:
                    return False, "总额与费用金额复用了同一原文数值；缺少另列的原文总额约束"
    return True, "总额金额和币种均有当前原文支持，按逻辑单据及币种核对；与行算术取较强项，不重复累加"


def _band(score, policy):
    return "high" if score >= policy["high_threshold"] else "medium" if score >= policy["medium_threshold"] else "low"


def _dedupe_issues(issues):
    result, seen = [], set()
    for issue in issues:
        key = (issue.get("code"), issue.get("message"), issue.get("charge_id"), issue.get("field"))
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def assess_confidence(payload: dict) -> dict:
    """Score current billing evidence support without changing validation or approval."""
    if not isinstance(payload, dict):
        raise ValueError("payload必须是任务对象")
    for key in ("charges", "records", "sources", "coverage", "totals"):
        if key in payload and (not isinstance(payload[key], list) or any(not isinstance(row, dict) for row in payload[key])):
            raise ValueError(f"{key}必须是对象列表")
    policy = _policy(payload.get("options", payload.get('confidence_options', {})))
    revision = payload.get("revision")
    validation = payload.get("validation") or {}
    if not isinstance(validation, dict):
        raise ValueError("validation必须是对象")
    checks = {}
    duplicate_checks = set()
    definitions = validation.get("checks", [])
    if not isinstance(definitions, list):
        raise ValueError("validation.checks必须是校验结果列表")
    for check in definitions:
        if isinstance(check, dict) and check.get("name") in REQUIRED_CHECKS:
            name = check["name"]
            if name in checks:
                duplicate_checks.add(name)
            checks[name] = check
    global_blockers = []
    if type(revision) is not int or revision < 1:
        global_blockers.append({"code": "INVALID_REVISION", "message": "缺少有效当前任务版本"})
    if validation.get("revision") != revision:
        global_blockers.append({"code": "STALE_VALIDATION", "message": "校验结果不属于当前版本"})
    if validation.get("ok") is not True:
        global_blockers.append({"code": "VALIDATION_FAILED", "message": "当前完整校验未通过，评分不能覆盖校验结果"})
    if duplicate_checks:
        global_blockers.append({"code": "AMBIGUOUS_CHECK", "message": "同名校验重复，不能确定唯一结果"})
    charge_rows = payload.get("charges", [])
    origin = "records" if payload.get("records") else "charges"
    record_rows = payload.get("records") or [_candidate_record(charge, revision) for charge in charge_rows]
    if not record_rows:
        global_blockers.append({"code": "NO_RECORDS", "message": "尚无可评估费用记录"})
    output = []
    for record in record_rows:
        flat = _flat(record)
        cid = record.get("charge_id")
        blockers = deepcopy(global_blockers)
        candidates = [row for row in charge_rows if row.get("charge_id") == cid]
        candidate = _flat(candidates[0]) if len(candidates) == 1 else {}
        if not cid or sum(row.get("charge_id") == cid for row in record_rows) != 1 or len(candidates) != 1:
            blockers.append({"code": "CHARGE_ID_UNRESOLVED", "message": "记录与候选费用缺少唯一charge_id关联"})
        if record.get("revision") != revision or candidate.get("revision", revision) != revision:
            blockers.append({"code": "STALE_RECORD", "message": "费用记录或候选不属于当前版本"})
        states = {name: _check_state(checks.get(name), cid) for name in REQUIRED_CHECKS}
        for name, state in states.items():
            if state != "passed":
                blockers.append({"code": "CHECK_UNAVAILABLE" if state == "unavailable" else "CHECK_FAILED",
                                 "message": f"{name}校验{'不可用' if state == 'unavailable' else '未通过'}", "field": name})
        refs = _refs(checks.get("evidence"), cid)
        if not refs:
            blockers.append({"code": "EVIDENCE_MISSING", "message": "没有当前证据校验生成的可回读引用"})
        fields, targets, field_targets_by_name = {}, [], {}
        facts = _facts(checks.get("evidence"), cid)
        source_available = checks.get("evidence", {}).get("revision") == revision and validation.get("revision") == revision
        for field in FIELDS:
            fields[field], field_targets = _support(field, candidate, facts, refs, source_available)
            field_targets_by_name[field] = field_targets
            targets.extend(field_targets)
            if field in {"amount", "currency", "charge_item"} and fields[field]["status"] != "supported":
                blockers.append({"code": "FIELD_" + fields[field]["status"].upper(),
                                 "message": f"{field}缺少唯一当前原文支持", "field": field})
            if candidate.get(field) is not None and flat.get(field) is not None:
                if field == "amount":
                    same = _decimal(candidate[field]) == _decimal(flat[field]) and _decimal(flat[field]) is not None
                    if not same and states["amount"] == "passed":
                        same = _normalized_amount_matches(checks.get("amount"), candidate, flat[field], revision)
                else:
                    values = {str(flat[field]).strip().casefold()}
                    if field == "charge_item" and flat.get("raw_charge_item"):
                        values.add(str(flat["raw_charge_item"]).strip().casefold())
                    same = str(candidate[field]).strip().casefold() in values
                if not same:
                    blockers.append({"code": "RECORD_CANDIDATE_CONFLICT", "message": f"{field}记录与当前候选不一致", "field": field})
        if candidate.get('payment_term') not in (None, ''):
            fields['payment_term'], payment_targets = _support('payment_term', candidate, facts, refs, source_available)
            targets.extend(payment_targets)
        if flat.get('posting_type') not in (None, ''):
            posting_ok = states['posting'] == 'passed'
            fields['posting_type'] = dict(score=100 if posting_ok else 0,
                status='supported' if posting_ok else 'unsupported',
                reasons=['记账主体和明确交易关系已通过方向校验' if posting_ok else '当前AR/AP与主体及交易关系尚未一致'])
        entity = flat.get("accounting_entity", payload.get("accounting_entity"))
        if not entity:
            blockers.append({"code": "ACCOUNTING_ENTITY_MISSING", "message": "调用方尚未明确当前记账主体"})
        for owner in (record, candidate):
            confirmations = owner.get("human_confirmed") or {}
            if not isinstance(confirmations, dict):
                blockers.append({"code": "HUMAN_CONFIRMATION_UNREADABLE", "message": "人工确认信息格式无效"})
                confirmations = {}
            for path, confirmation in confirmations.items():
                if not isinstance(confirmation, dict) or confirmation.get("revision") != revision:
                    field = path.split(".")[-1]
                    if field in fields:
                        fields[field] = {"score": 0, "status": "stale", "reasons": ["人工确认不属于当前版本"]}
                    blockers.append({"code": "STALE_HUMAN_CONFIRMATION", "message": "人工确认版本已过期", "field": path})
        issues = list(validation.get("issues", [])) + list(record.get("issues", [])) + list(candidate.get("issues", []))
        for check in checks.values():
            issues.extend(check.get("issues", []))
        for issue in issues:
            if _blocking(issue) and issue.get("charge_id") in (None, cid):
                blockers.append({key: deepcopy(issue[key]) for key in ("code", "message", "field", "source_id") if key in issue})
        if record.get("operation") == "PENDING_REVIEW":
            blockers.append({"code": "PENDING_REVIEW", "message": "当前费用仍须人工复核"})
        supported = sum(fields[key]["status"] == "supported" for key in CORE_FIELD_WEIGHTS)
        # Graded field support: a supported value backed only by an email subject
        # or lacking a unique/structured citation no longer earns full weight.
        source_fraction = sum(fields[key]["score"] / 100 * weight
                              for key, weight in CORE_FIELD_WEIGHTS.items())
        arithmetic_supported, arithmetic_reason = _arithmetic_support(candidate, facts, refs, source_available,
                                                                      field_targets_by_name["amount"])
        arithmetic_ready = arithmetic_supported and states["amount"] == states["evidence"] == "passed"
        scope = _scope(payload, candidate if candidate.get('source_id') or candidate.get('document_id') else flat)
        total_supported, total_reason = _total_support(payload, checks.get("evidence"), scope, flat.get("currency"))
        total_ready = total_supported and states["evidence"] == "passed" and states["amount"] == "passed"
        signals = {
            "line_arithmetic": {"status": "passed" if arithmetic_ready else "failed" if arithmetic_supported else "unavailable",
                                "reason": arithmetic_reason if not arithmetic_supported or arithmetic_ready else "原文数值已有支持，但当前金额或证据校验未通过"},
            "document_total": {"status": "passed" if total_ready else "failed" if total_supported else "unavailable",
                               "reason": total_reason if not total_supported or total_ready else "总额原文已有支持，但当前金额或证据校验未通过"},
        }
        # Source read-back, lexical support and amount validity are related facts,
        # so they form one group. Two arithmetic views of that same invoice are
        # also dependent: use the stronger constraint, never add their scores.
        consistency = max(0.5 if arithmetic_ready else 0, 1.0 if total_ready else 0)
        specs = {
            "field_support": (source_fraction, "passed" if supported == 3 else "partial" if supported else "failed",
                              f"{supported}/3核心字段获原文支持；按证据强度梯度计分（金额45%、币种35%、费用名20%）；回读和币种有效性不另重复加分。单号单独展示，不要求固定模板"),
            "consistency": (consistency, "passed" if consistency else "unavailable",
                            "取原文支持的行算术（半组）与分币种总额（整组）的较强项；两项不累加" if consistency else
                            "尚无可核验的源算术约束；缺失检查不得重归一化成满分"),
            "coverage": (int(states["coverage"] == "passed"), states["coverage"], "复用当前覆盖校验，不从已输出记录数量推断完整；覆盖闭合仍不能证明没有语义漏行"),
        }
        components = [{"id": key, "label": LABELS[key], "score": round(policy["weights"][key] * fraction, 2),
                       "max_score": policy["weights"][key], "status": state, "reason": reason}
                      for key, (fraction, state, reason) in specs.items()]
        score = round(sum(component["score"] for component in components), 2)
        blockers = _dedupe_issues(blockers)
        unique_targets = []
        seen_targets = set()
        for target in targets:
            key = (target.get("content_sha256"), target.get("anchor"), target.get("quote_start"), target.get("quote_end"), target["field"])
            if key not in seen_targets:
                seen_targets.add(key)
                unique_targets.append(target)
        band = _band(score, policy)
        review_score, review_items = _review_fields(dict(candidate, posting_type=flat.get('posting_type')), fields,
                                                   refs, issues + blockers, cid, policy['review_threshold'])
        output.append({"charge_id": cid, "record_id": cid, "origin": origin,
                       "record": deepcopy(record), "score": score, "band": band,
                       "eligible_for_quick_confirm": band == "high" and not blockers,
                       "components": components, "fields": fields, "blockers": blockers, "signals": signals,
                       "fusion": {"source_group": "readback+field_semantics+amount_validity",
                                  "constraint_group": "max(line_arithmetic, document_total)", "duplicate_bonus": False},
                       "review_route": "blocked" if blockers else "quick_confirm" if band == "high" else "review_suggested",
                       "review_score": review_score, "review_required": bool(review_items), "review_items": review_items,
                       "evidence_targets": unique_targets})
    score = min((row["score"] for row in output), default=0)
    blockers = _dedupe_issues(global_blockers + [dict(item, charge_id=row["charge_id"])
        for row in output for item in row["blockers"]])
    eligible = bool(output) and all(row["eligible_for_quick_confirm"] for row in output)
    review_items = [item for row in output for item in row['review_items']]
    review_scores = [row['review_score'] for row in output if row['review_score'] is not None]
    return {"revision": revision, "method": "grouped_source_support_v2", "calibrated": False,
            "policy_id": policy["policy_id"], "policy_version": POLICY_VERSION, "policy": policy,
            "score": score, "band": _band(score, policy), "records": output, "blockers": blockers,
            "eligible_for_quick_confirm": eligible,
            "review_score": min(review_scores) if review_scores else None,
            "review_required": bool(review_items), "review_items": review_items,
            "summary": f"规则支持度{score:g}/100，{len(output)}条费用；" +
                       (f"{len(review_items)}个已有值低于复核阈值。" if review_items else "已有值未触发低置信度复核；缺失信息不计入低置信度。") +
                       "分数未经正确率校准。"}


def main(argv=None):
    """Assess one task through portable JSON file/stdio IO."""
    import argparse
    from contextlib import ExitStack
    from pathlib import Path
    import simplejson
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Input JSON path; omit or use - for stdin")
    parser.add_argument("--output", help="Output JSON path; omit or use - for stdout")
    parser.add_argument("--operation", choices=["assess_confidence"], default="assess_confidence")
    args = parser.parse_args(argv)
    success = True
    with ExitStack() as stack:
        try:
            source = stack.enter_context(Path(args.input).open(encoding="utf-8-sig")) if args.input and args.input != "-" else sys.stdin
            result = assess_confidence(simplejson.load(source, use_decimal=True))
        except (ValueError, OSError) as exc:
            success = False
            result = {"valid": False, "issues": [{"code": "CLI_INPUT", "message": str(exc), "severity": "error"}]}
        try:
            destination = stack.enter_context(Path(args.output).open("w", encoding="utf-8")) if args.output and args.output != "-" else sys.stdout
            simplejson.dump(result, destination, use_decimal=True, ensure_ascii=False, allow_nan=False)
            destination.write("\n")
        except OSError as exc:
            print(f"CLI_OUTPUT: {exc}", file=sys.stderr)
            return 1
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
