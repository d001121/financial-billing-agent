"""Versioned business corrections and approval bindings, independent of HITL runtime."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256

import simplejson

FIELDS = {
    "document_type": "document_info.document_type", "reference_no": "document_info.reference_no",
    "document_date": "document_info.document_date", "issuer": "transaction_party.issuer",
    "recipient": "transaction_party.recipient", "charge_item": "charge_details.charge_item",
    "amount": "charge_details.amount", "currency": "charge_details.currency",
    "payment_term": "charge_details.payment_term", "accounting_entity": "financial_attributes.accounting_entity",
    "posting_type": "financial_attributes.posting_type", "evidence": "evidence", "creditor": "creditor",
    "debtor": "debtor", "bill_of_lading": "bill_of_lading", "booking_no": "booking_no",
    "container_no": "container_no", "quantity": "quantity", "unit_price": "unit_price",
    "selected_match_id": "selected_match_id",
}


def _error(code, message, **extra):
    return {"code": code, "message": message, "severity": "error", "repairable": False, **extra}


def automatic_stop_question(task: dict) -> dict | None:
    """Expose a concrete existing repair/budget stop as a caller todo."""
    stop = task.get('automatic_stop') or {}
    if stop.get('revision') != task['revision']:
        return None
    issues = (task.get('validation') or {}).get('issues') or []
    details = '；'.join(dict.fromkeys(i['message'] for i in issues
        if i.get('severity') == 'error' and i.get('message')))[:600]
    return dict(action='edit', source='completion', field=None, choices=[],
        summary='自动处理已停止，已有结果待核对',
        question='已保留当前费用和原文证据。' + stop['message'] + '。' +
            (f'当前待核对：{details}。' if details else '') +
            '请对照原文指出要修改的费用和字段，或回复“暂缓”。')


def entity_question(task: dict) -> dict | None:
    """Offer extracted parties for caller selection; never infer the caller's entity."""
    if task.get('accounting_entity') or task.get('status') == 'review_deferred' or not task.get('records'):
        return None
    choices, seen = [], set()
    extraction = task.get('extraction') or {}
    rows = [*task.get('records', []), *task.get('charges', []), *extraction.get('documents', [])]
    for row in rows:
        party = row.get('transaction_party') or {}
        for value in (row.get('creditor'), row.get('debtor'), row.get('issuer'), row.get('recipient'),
                      party.get('issuer'), party.get('recipient')):
            if not isinstance(value, str) or not value.strip():
                continue
            name = value.strip()
            key = ' '.join(name.casefold().split())
            if key not in seen:
                seen.add(key)
                choices.append(name)
    candidates = '\n'.join(f'{i + 1}. {name}' for i, name in enumerate(choices))
    return dict(action='entity', field='accounting_entity', source='completion', choices=choices,
        summary='费用已提取，请在账单助手中确认本次记账公司，再继续判断AR/AP。',
        question='费用和原文已整理好。请确认本次为哪家公司记账，以便判断应收 AR 或应付 AP。\n'
            + (f'材料中识别到以下公司，您可点击候选填入回复：\n{candidates}\n' if choices else
               '材料中尚未识别到可供选择的公司，请回复本次记账公司名称。\n')
            + '也可以回复其他公司名称，或回复“暂缓/跳过/不需要主体”先不指定主体；不会自动替您选择。')


def _path(field):
    if field in FIELDS:
        return FIELDS[field]
    if field in FIELDS.values():
        return field
    raise ValueError("不支持编辑字段：" + str(field))


def _get(record, path):
    current = record
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return deepcopy(current)


def _set(record, path, value):
    parts = path.split(".")
    current = record
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    if parts[-1] in {"amount", "quantity", "unit_price"} and value is not None:
        if isinstance(value, bool):
            raise ValueError("布尔值不能作为金额/数量")
        try:
            value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("金额/数量须为数字") from exc
        if not value.is_finite():
            raise ValueError("金额/数量须为有限数字")
    current[parts[-1]] = deepcopy(value)


def validate_revision(payload: dict) -> dict:
    issues = []
    if payload.get("expected_revision") != payload.get("revision"):
        issues.append(_error("REVISION_CONFLICT", "内容已被修改，请刷新并查看最新差异", field="revision",
                             actual_revision=payload.get("revision")))
    if not isinstance(payload.get("revision"), int) or isinstance(payload.get("revision"), bool):
        issues.append(_error("REVISION_REQUIRED", "当前revision须为整数", field="revision"))
    ids = [r.get("charge_id") for r in payload.get("records", [])]
    if len(ids) != len(set(ids)) or None in ids:
        issues.append(_error("RECORD_ID_INVALID", "人审费用须具有唯一charge_id", field="records"))
    if not payload.get("reason"):
        issues.append(_error("REVIEW_REASON_REQUIRED", "请提供本次修改依据", field="reason"))
    for operation in payload.get("operations", []):
        if operation.get("op") not in {"set", "delete", "split"}:
            issues.append(_error("REVIEW_OPERATION", "不支持的人工操作", field="operations"))
        if operation.get("charge_id") not in ids:
            issues.append(_error("CHARGE_NOT_FOUND", "费用已不存在或ID无效", charge_id=operation.get("charge_id")))
        if operation.get("op") == "set":
            try:
                _path(operation.get("field"))
            except ValueError as exc:
                issues.append(_error("REVIEW_FIELD", str(exc), field=operation.get("field")))
            if "value" not in operation:
                issues.append(_error("REVIEW_VALUE", "修改须明确提供value，null表示清空", field="value"))
        if operation.get("op") == "split" and (not isinstance(operation.get("value"), list) or len(operation["value"]) < 2):
            issues.append(_error("SPLIT_CHILDREN", "拆分至少提供两条费用字段对象", field="value"))
    return {"valid": not issues, "issues": issues, "revision": payload.get("revision")}


def apply_revision(payload: dict) -> dict:
    """Apply explicit field edits as a new revision and invalidate dependent artifacts."""
    checked = validate_revision(payload)
    if not checked["valid"]:
        return {**checked, "records": deepcopy(payload.get("records", [])), "invalidated": []}
    records = deepcopy(payload["records"])
    revision = payload["revision"] + 1
    history, changed = [], set()
    try:
        for edit in payload.get("operations", []):
            record = next((r for r in records if r["charge_id"] == edit["charge_id"]), None)
            if record is None:
                raise ValueError("同一批操作引用了已删除或已拆分的费用")
            if edit["op"] == "delete":
                history.append({"op": "delete", "before": deepcopy(record), "reason": payload["reason"]})
                records.remove(record)
                changed.add("membership")
            elif edit["op"] == "split":
                children = []
                for index, values in enumerate(edit["value"]):
                    if not isinstance(values, dict) or not values:
                        raise ValueError("拆分费用须提供字段对象")
                    child = deepcopy(record)
                    child["charge_id"] = f"{record['charge_id']}-r{revision}-{index + 1}"
                    child["split_from"] = record["charge_id"]
                    for field, value in values.items():
                        path = _path(field)
                        _set(child, path, value)
                        child.setdefault("human_confirmed", {})[path] = {"revision": revision, "value": _get(child, path)}
                    children.append(child)
                records[records.index(record):records.index(record) + 1] = children
                history.append({"op": "split", "before": record, "after_ids": [r["charge_id"] for r in children],
                                "reason": payload["reason"]})
                changed.add("membership")
            else:
                path = _path(edit["field"])
                before = _get(record, path)
                _set(record, path, edit["value"])
                record.setdefault("human_confirmed", {})[path] = {"revision": revision, "value": _get(record, path)}
                history.append({"op": "set", "charge_id": record["charge_id"], "field": path,
                                "before": before, "after": _get(record, path), "reason": payload["reason"]})
                changed.add(path)
        if "accounting_entity" in payload:
            for record in records:
                path = FIELDS["accounting_entity"]
                before = _get(record, path)
                _set(record, path, payload["accounting_entity"])
                record.setdefault("human_confirmed", {})[path] = {"revision": revision, "value": payload["accounting_entity"]}
                history.append({"op": "set", "charge_id": record["charge_id"], "field": path, "before": before,
                                "after": payload["accounting_entity"], "reason": payload["reason"]})
            changed.add(FIELDS["accounting_entity"])
    except (ValueError, TypeError) as exc:
        return {"valid": False, "issues": [_error("REVIEW_INVALID", str(exc))],
                "records": deepcopy(payload["records"]), "revision": payload["revision"], "invalidated": []}
    if not changed:
        return {"valid": False, "issues": [_error("EMPTY_REVISION", "没有提交人工修改")],
                "records": records, "revision": payload["revision"], "invalidated": []}
    # OCR/source originals are independent and remain reusable. Financial derivatives are not.
    invalidated = ["amounts", "matching", "updates", "posting", "validation", "approval", "export"]
    if "evidence" in changed or "membership" in changed:
        invalidated.append("evidence")
    for record in records:
        record["revision"] = revision
        record["operation"] = "PENDING_REVIEW"
        record["issues"] = [_error("HUMAN_REVALIDATION", "人工修改后须重新进行受影响校验")]
    return {"valid": True, "issues": [], "records": records, "revision": revision,
            "previous_revision": payload["revision"], "invalidated": invalidated, "history": history}


def approval_binding(payload: dict) -> dict:
    fields = ("revision", "action", "args", "tool_version", "rule_version", "skill_versions")
    binding = {key: deepcopy(payload.get(key)) for key in fields}
    canonical = simplejson.dumps(binding, sort_keys=True, use_decimal=True, ensure_ascii=False, separators=(",", ":"))
    return {**binding, "digest": sha256(canonical.encode()).hexdigest()}


def review_outcome(payload: dict) -> dict:
    """Separate confidence review, automatic verification and hard financial gates."""
    task, exported = payload['task'], payload['export']
    validation = task.get('validation') or {}
    confidence = validation.get('confidence') or {}
    binding = approval_binding(payload['binding'])
    confirmed = task.get('review_confirmation') or {}
    answer = payload.get('confirmation')
    at = payload.get('at')
    if answer is not None:
        if answer.get('expected_revision') != task['revision']:
            raise ValueError('复核版本已变化')
        if answer.get('decision') not in ('confirm', 'defer'):
            raise ValueError('复核决策须为confirm/defer')
        confirmed = dict(decision=answer['decision'], binding=binding,
                         reason=answer.get('reason') or '调用方对照原件核对当前结果', at=at)
    reviewed = confirmed.get('decision') == 'confirm' and (confirmed.get('binding') or {}).get('digest') == binding['digest']
    needs_review = confidence['review_required'] and not reviewed
    rejected = (task.get('approval') or {}).get('decision') == 'reject'
    deferred = rejected or bool(answer and answer['decision'] == 'defer')
    pending_native = bool(task.get('confidence_interrupt')) and answer is None
    stopped = (task.get('automatic_stop') or {}).get('revision') == task['revision']
    automatic = not stopped and not deferred and not pending_native and not needs_review and validation['ok'] and exported['valid'] and bool(task.get('records'))
    status = 'review_deferred' if deferred else 'awaiting_review' if needs_review or pending_native else 'completed' if automatic else 'completed_with_gaps'
    if task.get('capability', {}).get('config', {}).get('runtime', {}).get('agent_style') == 'codex':
        status = 'completed' if automatic else 'completed_with_gaps'
        needs_review = False
        pending_native = False

    return dict(export=deepcopy(exported), status=status, review_confirmation=confirmed or None,
        auto_review=dict(decision='passed', binding=binding, mode='human_assisted' if reviewed else 'automatic',
                         policy=confidence['policy'], at=at) if automatic else None,
        summary=('本次已暂缓复核，提取结果与原文已保留' if deferred else
                 '修改已保存，请提交核对结果继续自动校验' if pending_native else
                 f"{len(confidence['review_items'])}个已提取字段需要核对" if needs_review else
                 '账单已自动核验完成，可查看原文、修改或导出' if automatic else
                 '提取结果已保存；缺失或未完成项不计为低置信度，当前可查看及修改'))


def prepare_recalculation(payload: dict) -> dict:
    """Restore edited records to extraction candidates without changing source material."""
    task = payload.get("task", {})
    review = payload.get("review", payload.get("revision_result", payload))
    if review.get("valid") is False:
        return {"valid": False, "issues": deepcopy(review.get("issues", [])), "charges": []}
    records = review.get("records", [])
    charges = []
    for record in records:
        # Only the human-review contract's own explicit field paths are unpacked.
        candidate = {k: deepcopy(v) for k, v in record.items() if k not in {
            "document_info", "transaction_party", "charge_details", "financial_attributes", "audit_trail", "issues", "operation"}}
        for field, path in FIELDS.items():
            if "." in path:
                candidate[field] = _get(record, path)
        for path, confirmation in record.get("human_confirmed", {}).items():
            if path in FIELDS.values() and isinstance(confirmation, dict) and "value" in confirmation:
                field = next(key for key, value in FIELDS.items() if value == path)
                candidate[field] = deepcopy(confirmation["value"])
        charges.append(candidate)
    if not records and not task.get('records'):
        # Supplying the entity before reconciliation must retain partial candidates.
        charges = deepcopy(task.get('charges', []))
        for candidate in charges:
            candidate['revision'] = review.get('revision', task.get('revision'))
            candidate['accounting_entity'] = task.get('accounting_entity')
    entity = task.get("accounting_entity")
    entities = {c.get("accounting_entity") for c in charges if c.get("accounting_entity")}
    if len(entities) == 1:
        entity = next(iter(entities))
    result = {"valid": True, "issues": [], "charges": charges, "records": deepcopy(records),
              "revision": review.get("revision", task.get("revision")), "accounting_entity": entity}
    for key in ("existing_records", "update_instructions", "sources", "documents", "totals", "coverage", "chunks", "charge_mapping"):
        if key in task:
            result[key] = deepcopy(task[key])
        elif key in (task.get("extraction") or {}):
            result[key] = deepcopy(task["extraction"][key])
    previous = deepcopy(task.get("extraction") or {})
    # These issues are outputs of deterministic checks, which run again on the
    # reviewed view. Their old values must not veto the newly corrected fields.
    recomputed = {"EXTRACTION_SCHEMA", "EVIDENCE_MISSING", "EVIDENCE_UNREADABLE", "EVIDENCE_AMBIGUOUS",
                  "EVIDENCE_UNVERIFIED", "COVERAGE_OPEN", "COVERAGE_REVIEW", "COVERAGE_UNSPECIFIED",
                  "SOURCE_INCOMPLETE", "BILL_DATE_EVIDENCE_REQUIRED"}
    changed, removed = {}, {}
    for action in review.get("history", []):
        if action.get("op") == "set":
            changed.setdefault(action["charge_id"], set()).add(action["field"])
        elif action.get("op") in {"delete", "split"}:
            removed[action.get("before", {}).get("charge_id")] = action.get("after_ids", [])
    entity_now = task.get("accounting_entity") or result.get("accounting_entity")

    def stale_entity_issue(error):
        if not entity_now:
            return False
        if str(error.get("code", '')).upper() in {'MISSING_ACCOUNTING_ENTITY', 'NO_ACCOUNTING_ENTITY', 'ACCOUNTING_ENTITY_MISSING'}:
            return True
        message = str(error.get("message") or "")
        return "accounting_entity" in message and ("未提供" in message or "未指定" in message)

    remaining = []
    for error in previous.get("issues", []):
        charge_id, field = error.get("charge_id"), error.get("field")
        path = FIELDS.get(field, field)
        if stale_entity_issue(error):
            continue
        if error.get("code") in recomputed or charge_id in removed or path in changed.get(charge_id, set()):
            continue
        remaining.append(error)
    coverage = deepcopy(result.get("coverage", previous.get("coverage", [])))
    for disposition in coverage:
        if "charge_ids" in disposition:
            disposition["charge_ids"] = [replacement for charge_id in disposition["charge_ids"]
                                         for replacement in removed.get(charge_id, [charge_id])]
    current_extraction = {**previous, "revision": result["revision"], "charges": deepcopy(charges),
                          "coverage": coverage, "totals": deepcopy(result.get("totals", [])), "issues": remaining}
    current_extraction.pop("valid", None)
    result.update(extraction=current_extraction, coverage=coverage, evidence=None, coverage_validation=None)
    result["issues"] = [error for error in task.get("issues", [])
                        if not stale_entity_issue(error)]
    if review.get("previous_revision") is not None and previous:
        result["extraction_history"] = [*deepcopy(task.get("extraction_history", [])),
                                        {"revision": review["previous_revision"], "extraction": previous}]
    return result


def _origin(record):
    """Stable source-line identity only; financial values never decide an edit's identity."""
    if record.get("source_id") and record.get("line_id"):
        return ("line", str(record["source_id"]), str(record["line_id"]))
    refs = tuple(sorted((str(e.get("source_id")), str(e.get("anchor", "text")),
                         str(e.get("quote_start", "")), str(e.get("quote", "")))
                        for e in record.get("evidence", [])))
    return ("evidence", refs) if refs else ("charge", str(record.get("charge_id")))


def _candidate_id(candidate, index):
    """Use document-extraction's missing-ID convention before indexed merging."""
    basis = f"{candidate.get('source_id')}:{candidate.get('line_id')}:{candidate.get('evidence')}:{index}"
    return "charge-" + sha256(basis.encode()).hexdigest()[:16]


def _amount_key(value):
    if value is None:
        return None
    try:
        return Decimal(str(value)).normalize()
    except (ArithmeticError, InvalidOperation, ValueError):
        return str(value)


def _charge_identity(record):
    """Business identity used only to recognise a re-extracted copy of a saved row."""
    item = " ".join(str(record.get("charge_item") or "").split()).casefold()
    amount = _amount_key(record.get("amount"))
    if not record.get("source_id") or not item or amount is None:
        return None
    return (str(record["source_id"]), item, amount, str(record.get("currency") or "").upper())


def _normalize_document_ids(*parts):
    """One document in a source owns every row that names an unknown document.

    A re-extraction can invent a placeholder document id (``doc_debit_note_1``)
    while the same source's header carries the printed id. Keeping both splits
    the amount scope and makes an otherwise matching total look wrong.
    """
    documents = {}
    for part in parts:
        for document in part.get("documents") or []:
            source_id, document_id = document.get("source_id"), document.get("document_id")
            if source_id and document_id:
                documents.setdefault(str(source_id), set()).add(str(document_id))
    for part in parts:
        for row in [*(part.get("charges") or []), *(part.get("totals") or [])]:
            source_id = row.get("source_id")
            known = documents.get(str(source_id)) if source_id else None
            if known and len(known) == 1:
                only = next(iter(known))
                if str(row.get("document_id") or "") != only:
                    row["document_id"] = only


def merge_extraction(payload: dict) -> dict:
    """Merge extraction batches while preserving explicit field locks and line membership edits."""
    task = payload.get("task", {})
    incoming = deepcopy(payload.get("result", {}))
    previous = deepcopy(task.get("extraction") or {})
    _normalize_document_ids(previous, incoming)
    current = prepare_recalculation({"task": task, "review": {"valid": True, "records": task.get("records", []),
                                                               "revision": task.get("revision")}})["charges"]
    protected = {r["charge_id"]: r for r in current if r.get("human_confirmed") or r.get("split_from")}
    deleted_ids, deleted_origins = set(), set()
    for revision in task.get("history", []):
        for action in revision.get("history", []):
            if action.get("op") in {"delete", "split"}:
                before = action.get("before", {})
                deleted_ids.add(before.get("charge_id"))
                deleted_origins.add(_origin(before))
    base = [] if payload.get("replace") else deepcopy(previous.get("charges", []))
    # replace selects list membership. A correction to the same row still
    # preserves fields omitted by the model; only an explicit null clears one.
    prior_by_id = {c.get('charge_id'): c for c in previous.get('charges', []) if c.get('charge_id')}
    for index, candidate in enumerate(base):
        if not candidate.get("charge_id"):
            candidate["charge_id"] = _candidate_id(candidate, index)
    by_id = {c.get("charge_id"): c for c in base}
    previous_origins = {}
    identity_index = {}
    for candidate in base:
        previous_origins.setdefault(_origin(candidate), []).append(candidate["charge_id"])
        identity = _charge_identity(candidate)
        if identity:
            identity_index.setdefault(identity, []).append(candidate["charge_id"])
    protected_origins = {}
    for record in protected.values():
        protected_origins.setdefault(_origin(record), []).append(record)
    incoming_ids = set()
    for index, candidate in enumerate(incoming.get("charges", [])):
        cid, origin = candidate.get("charge_id"), _origin(candidate)
        if cid in deleted_ids or origin in deleted_origins:
            continue
        if not cid:
            previous_ids = [identity for identity in previous_origins.get(origin, []) if identity not in incoming_ids]
            if origin[0] != "charge" and len(previous_ids) == 1:
                cid = previous_ids[0]
            else:
                # A re-extraction that omits line_id/charge_id describes the same
                # saved row when source, item, amount and currency all match exactly
                # one existing row. Never merge when the match is ambiguous.
                identity = _charge_identity(candidate)
                matches = []
                for identity_id in identity_index.get(identity, []) if identity else []:
                    saved = by_id.get(identity_id) or {}
                    if identity_id in incoming_ids:
                        continue
                    if (candidate.get("document_id") and saved.get("document_id")
                            and candidate["document_id"] != saved["document_id"]):
                        continue
                    if (candidate.get("line_id") and saved.get("line_id")
                            and candidate["line_id"] != saved["line_id"]):
                        continue
                    matches.append(identity_id)
                if len(matches) == 1:
                    cid = matches[0]
                else:
                    candidate_index = index
                    cid = _candidate_id(candidate, candidate_index)
                    while cid in incoming_ids or cid in by_id:
                        candidate_index += max(1, len(base), len(incoming.get("charges", [])))
                        cid = _candidate_id(candidate, candidate_index)
            candidate["charge_id"] = cid
        elif cid not in by_id:
            # A stale or re-invented id for a row that was already saved is still
            # that row when the business identity matches uniquely.
            identity = _charge_identity(candidate)
            matches = []
            for identity_id in identity_index.get(identity, []) if identity else []:
                saved = by_id.get(identity_id) or {}
                if identity_id in incoming_ids or identity_id not in by_id:
                    continue
                if (candidate.get("document_id") and saved.get("document_id")
                        and candidate["document_id"] != saved["document_id"]):
                    continue
                if (candidate.get("line_id") and saved.get("line_id")
                        and candidate["line_id"] != saved["line_id"]):
                    continue
                matches.append(identity_id)
            if len(matches) == 1:
                cid = matches[0]
                candidate["charge_id"] = cid
        prior = prior_by_id.get(cid, {})
        if prior and all(not candidate.get(key) or not prior.get(key) or
                         candidate[key] == prior[key] for key in ('source_id', 'document_id', 'line_id')):
            candidate = {**prior, **candidate}
            # The row's line/document identity defines which charge it is; an
            # omitted identity in a correction must not erase the saved link.
            for key in ('charge_id', 'source_id', 'document_id', 'line_id'):
                if not candidate.get(key) and prior.get(key):
                    candidate[key] = prior[key]
        locked = protected.get(cid)
        if (locked is None and len(protected_origins.get(origin, [])) == 1
                and protected_origins[origin][0]["charge_id"] not in incoming_ids):
            locked = protected_origins[origin][0]
        if locked:
            candidate["charge_id"] = locked["charge_id"]
            candidate["human_confirmed"] = deepcopy(locked.get("human_confirmed", {}))
            for path, confirmation in locked.get("human_confirmed", {}).items():
                if path in FIELDS.values() and isinstance(confirmation, dict) and "value" in confirmation:
                    field = next(k for k, value in FIELDS.items() if value == path)
                    candidate[field] = deepcopy(confirmation["value"])
            for key in ("split_from", "selected_match_id"):
                if key in locked:
                    candidate[key] = deepcopy(locked[key])
            protected[candidate["charge_id"]] = candidate
        by_id[candidate.get("charge_id")] = candidate
        incoming_ids.add(candidate["charge_id"])
    for cid, candidate in list(by_id.items()):
        if (cid in deleted_ids or _origin(candidate) in deleted_origins) and cid not in protected:
            del by_id[cid]
    by_id.update(protected)
    combined = {**previous, **incoming, "charges": list(by_id.values())}
    if not payload.get("replace"):
        documents = {(d.get('source_id'), d.get('document_id')): d for d in previous.get('documents', [])}
        for document in incoming.get('documents', []):
            key = (document.get('source_id'), document.get('document_id'))
            documents[key] = {**documents.get(key, {}), **document}
        combined['documents'] = list(documents.values())
        dispositions = {}
        for row in [*previous.get("coverage", []), *incoming.get("coverage", [])]:
            key = row.get("chunk_id") or (row.get("source_id"), row.get("anchor", "text"))
            dispositions[key] = row
        combined["coverage"] = list(dispositions.values())
        totals = {}
        for row in [*previous.get("totals", []), *incoming.get("totals", [])]:
            key = (row.get("source_id"), row.get("document_id"), row.get("currency"), row.get("role", "total"))
            totals[key] = row
        combined["totals"] = list(totals.values())
        touched_chunks = {c.get("chunk_id") for c in incoming.get("coverage", []) if c.get("chunk_id")}
        touched_ids = {c.get("charge_id") for c in incoming.get("charges", []) if c.get("charge_id")}
        recomputed = {"COVERAGE_OPEN", "COVERAGE_REVIEW", "COVERAGE_UNSPECIFIED", "SOURCE_INCOMPLETE", "EVIDENCE_MISSING", "EXTRACTION_SCHEMA",
                      "PDF_IDENTITY_LAYOUT_REQUIRED", "ASSET_NOT_READ", "SOURCE_NOT_READ", "BILL_DATE_EVIDENCE_REQUIRED"}
        retained = []
        for error in previous.get("issues", []):
            if error.get("code") in recomputed or error.get("chunk_id") in touched_chunks or error.get("charge_id") in touched_ids:
                continue
            retained.append(error)
        combined["issues"] = list({_digest_issue(e): e for e in [*retained, *incoming.get("issues", [])]}.values())
    combined["revision"] = task.get("revision")
    return combined


def _digest_issue(error):
    return simplejson.dumps(error, sort_keys=True, use_decimal=True, ensure_ascii=False)


def validate_approval(payload: dict) -> dict:
    """Check exact replacement args and revision/version binding; do not resume a graph."""
    current = approval_binding(payload.get("current", payload))
    approved = payload.get("approval") or {}
    automatic = payload.get('auto_review') or {}
    if not approved and automatic.get('decision') == 'passed':
        approved = dict(decision='approve', binding=automatic.get('binding'))
    issues = []
    if approved.get("decision") != "approve":
        issues.append(_error("APPROVAL_REQUIRED", "当前版本尚未通过自动核验或人工确认"))
    if (approved.get("binding") or {}).get("digest") != current["digest"]:
        issues.append(_error("STALE_APPROVAL", "版本、工具、规则或完整参数发生变化，须重新审批"))
    if not all(current.get(k) is not None for k in ("revision", "action", "args", "tool_version", "rule_version", "skill_versions")):
        issues.append(_error("INCOMPLETE_BINDING", "审批缺少动作、完整参数或版本绑定"))
    return {"valid": not issues, "issues": issues, "binding": current}


def main(argv=None):
    """Apply one explicit revision using JSON files or compatible stdin/stdout."""
    import argparse
    from contextlib import ExitStack
    from pathlib import Path
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Input JSON path; omit or use - for stdin")
    parser.add_argument("--output", help="Output JSON path; omit or use - for stdout")
    args = parser.parse_args(argv)
    with ExitStack() as stack:
        try:
            source = (stack.enter_context(Path(args.input).open(encoding="utf-8-sig"))
                      if args.input and args.input != "-" else sys.stdin)
            payload = simplejson.load(source, use_decimal=True)
            if not isinstance(payload, dict):
                raise ValueError("Input must be a JSON object")
            result = apply_revision(payload)
        except (ValueError, OSError) as exc:
            result = {"valid": False, "issues": [_error("CLI_INPUT", str(exc))]}
        destination = (stack.enter_context(Path(args.output).open("w", encoding="utf-8"))
                       if args.output and args.output != "-" else sys.stdout)
        simplejson.dump(result, destination, use_decimal=True, ensure_ascii=False, allow_nan=False)
        destination.write("\n")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
