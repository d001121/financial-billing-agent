import importlib.util
from pathlib import Path
from decimal import Decimal

SPEC = importlib.util.spec_from_file_location("human_review_skill", Path(__file__).parents[1] / "scripts" / "skill.py")
skill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill)


def data(**more):
    return {"records": [{"charge_id": "c1", "charge_details": {"amount": Decimal("10"), "currency": "USD"},
                         "financial_attributes": {"accounting_entity": "Carrier", "posting_type": "AR"},
                         "source_id": "doc", "evidence": [{"source_id": "doc", "quote": "10"}]}],
            "revision": 3, "expected_revision": 3, "reason": "核对原件", "operations": [], **more}


def test_prepare_recalculation_drops_stale_missing_entity_warning():
    records = data()["records"]
    task = {"accounting_entity": "NEPTUNE", "records": records, "revision": 2,
            "issues": [dict(code=None, severity="warning",
                            message="主体accounting_entity未提供，需宿主human review确认")],
            "extraction": {"issues": [dict(code="missing_accounting_entity",
                                           severity="warning", message="主体未提供")]}}
    result = skill.prepare_recalculation({"task": task,
        "review": {"valid": True, "records": records, "revision": 2}})
    assert not any(i.get("code") == "missing_accounting_entity"
                   for i in result["extraction"]["issues"])
    assert not any("accounting_entity" in str(i.get("message") or "")
                   and "未提供" in str(i.get("message") or "")
                   for i in result["issues"])


def test_confirmed_entity_clears_no_accounting_entity_code():
    records = data()['records']
    issue = dict(code='NO_ACCOUNTING_ENTITY', severity='warning', message='accounting_entity 为 null')
    result = skill.prepare_recalculation({'task': dict(accounting_entity='Carrier', records=records,
        revision=3, issues=[issue], extraction={'issues': [issue]}),
        'review': dict(valid=True, records=records, revision=3)})
    assert result['issues'] == result['extraction']['issues'] == []


def test_edit_new_revision_preserves_original_and_invalidates_derivatives():
    original = data(operations=[{"op": "set", "charge_id": "c1", "field": "amount", "value": "12.55"}])
    edited = skill.apply_revision(original)
    assert edited["valid"] and edited["revision"] == 4
    assert edited["records"][0]["charge_details"]["amount"] == Decimal("12.55")
    assert original["records"][0]["charge_details"]["amount"] == Decimal("10")
    assert {"matching", "posting", "approval", "export"} <= set(edited["invalidated"])
    assert "ocr" not in edited["invalidated"]
    recalculation = skill.prepare_recalculation({"task": {"sources": ["original"], "existing_records": []}, "review": edited})
    assert recalculation["charges"][0]["amount"] == Decimal("12.55")
    assert recalculation["sources"] == ["original"]
    assert recalculation["charges"][0]["human_confirmed"]["charge_details.amount"]["revision"] == 4


def test_stale_edits_invalid_values_and_invalid_batch_are_atomic():
    assert not skill.apply_revision(data(expected_revision=2))["valid"]
    original = data(operations=[{"op": "set", "charge_id": "c1", "field": "amount", "value": "12"},
                                {"op": "set", "charge_id": "c1", "field": "currency", "value": "EUR"},
                                {"op": "set", "charge_id": "c1", "field": "amount", "value": "NaN"}])
    result = skill.apply_revision(original)
    assert not result["valid"] and result["records"][0]["charge_details"]["currency"] == "USD"


def test_split_delete_and_entity_are_explicit_changes():
    result = skill.apply_revision(data(operations=[{"op": "split", "charge_id": "c1", "value": [{"amount": "4"}, {"amount": "6"}]}],
                                       accounting_entity="Client"))
    assert result["valid"] and len(result["records"]) == 2
    assert len({r["charge_id"] for r in result["records"]}) == 2
    assert all(r["split_from"] == "c1" for r in result["records"])
    assert all(r["financial_attributes"]["accounting_entity"] == "Client" for r in result["records"])
    deleted = skill.apply_revision(data(operations=[{"op": "delete", "charge_id": "c1"}]))
    assert deleted["valid"] and deleted["records"] == []


def test_approval_binds_complete_args_and_all_versions():
    current = {"revision": 3, "action": "export", "args": {"a": 1, "unchanged": "keep"},
               "tool_version": "1", "rule_version": "1", "skill_versions": {"billing": "1"}}
    approval = {"decision": "approve", "binding": skill.approval_binding(current)}
    assert skill.validate_approval({"current": current, "approval": approval})["valid"]
    for changed in ({"revision": 4}, {"args": {"a": 1}}, {"rule_version": "2"}):
        assert not skill.validate_approval({"current": {**current, **changed}, "approval": approval})["valid"]
    unapproved = skill.validate_approval({**current, "approval": None})
    assert not unapproved["valid"] and {i["code"] for i in unapproved["issues"]} == {"APPROVAL_REQUIRED", "STALE_APPROVAL"}


def test_entity_supplement_preserves_partial_extraction_before_records_exist():
    task = dict(revision=2, records=[], accounting_entity='Client', charges=[dict(charge_id='draft',amount=10)],
                sources=[dict(source_id='doc')])
    result = skill.prepare_recalculation(dict(task=task,review=dict(valid=True,records=[],revision=2)))
    assert result['charges'][0]['charge_id'] == 'draft'
    assert result['charges'][0]['accounting_entity'] == 'Client'
    assert result['sources'] == task['sources']


def test_reextraction_preserves_human_value_even_when_model_changes_charge_id():
    edited = skill.apply_revision(data(operations=[{"op": "set", "charge_id": "c1", "field": "amount", "value": "12.55"}]))
    task = {"records": edited["records"], "revision": 4, "history": [edited], "extraction": {"charges": []}}
    fresh = {"charges": [{"charge_id": "new-model-id", "source_id": "doc", "amount": Decimal("999"),
                           "evidence": [{"source_id": "doc", "quote": "10"}]}], "coverage": [], "totals": []}
    result = skill.merge_extraction({"task": task, "result": fresh, "replace": True})
    assert len(result["charges"]) == 1
    assert result["charges"][0]["charge_id"] == "c1"
    assert result["charges"][0]["amount"] == Decimal("12.55")


def test_reextraction_does_not_resurrect_deleted_or_split_parent_rows():
    original = data()
    fresh = {"charges": [{"charge_id": "model-id", "source_id": "doc", "amount": Decimal("10"),
                           "evidence": [{"source_id": "doc", "quote": "10"}]}]}
    deleted = skill.apply_revision({**original, "operations": [{"op": "delete", "charge_id": "c1"}]})
    task = {"records": deleted["records"], "revision": 4, "history": [deleted]}
    assert skill.merge_extraction({"task": task, "result": fresh, "replace": True})["charges"] == []
    split = skill.apply_revision({**original, "operations": [{"op": "split", "charge_id": "c1", "value": [{"amount": "4"}, {"amount": "6"}]}]})
    task = {"records": split["records"], "revision": 4, "history": [split]}
    children = skill.merge_extraction({"task": task, "result": fresh, "replace": True})["charges"]
    assert len(children) == 2 and {c["amount"] for c in children} == {Decimal("4"), Decimal("6")}


def test_batch_merge_preserves_other_chunk_issues_and_does_not_duplicate_totals():
    previous = {"charges": [{"charge_id": "a"}], "coverage": [{"source_id": "doc", "chunk_id": "one", "status": "needs_review"}],
                "totals": [{"source_id": "doc", "currency": "USD", "amount": "10", "role": "total"}],
                "issues": [{"code": "OCR_AMBIGUOUS", "chunk_id": "one", "message": "原文不清晰"},
                           {"code": "COVERAGE_OPEN", "message": "待重算"}]}
    second = {"charges": [{"charge_id": "b"}], "coverage": [{"source_id": "doc", "chunk_id": "two", "status": "extracted"}],
              "totals": [{"source_id": "doc", "currency": "USD", "amount": "12", "role": "total"}], "issues": []}
    merged = skill.merge_extraction({"task": {"extraction": previous, "revision": 1}, "result": second})
    assert len(merged["charges"]) == 2 and len(merged["coverage"]) == 2
    assert len(merged["totals"]) == 1 and merged["totals"][0]["amount"] == "12"
    assert [i["code"] for i in merged["issues"]] == ["OCR_AMBIGUOUS"]


def test_batch_merge_retains_headers_of_documents_without_fees():
    previous = dict(documents=[dict(source_id='a', document_id='a', bill_of_lading='A-1')])
    result = skill.merge_extraction(dict(task=dict(revision=1, extraction=previous),
        result=dict(charges=[], documents=[dict(source_id='b', document_id='b', bill_of_lading='B-1')])))
    assert {r['bill_of_lading'] for r in result['documents']} == {'A-1', 'B-1'}


def test_partial_document_edit_preserves_omitted_fields_but_allows_explicit_null():
    previous = dict(documents=[dict(source_id='a', document_id='a', container_no='BOX-1', reference_no='INV-1')])
    task = dict(revision=1, extraction=previous)
    result = skill.merge_extraction(dict(task=task, result=dict(documents=[dict(
        source_id='a', document_id='a', reference_no='INV-2')])))
    assert result['documents'][0]['container_no'] == 'BOX-1'
    task['extraction'] = result
    result = skill.merge_extraction(dict(task=task, result=dict(documents=[dict(
        source_id='a', document_id='a', container_no=None)])))
    assert result['documents'][0]['container_no'] is None
    assert result['documents'][0]['reference_no'] == 'INV-2'


def test_partial_charge_correction_preserves_invoice_number_even_when_replacing_membership():
    previous = dict(charges=[dict(charge_id='a', source_id='image', reference_no='ORFR1618731',
        amount=Decimal('5'), currency='USD'), dict(charge_id='b', source_id='image', amount=Decimal('21.9'))])
    for replace in (False, True):
        task = dict(revision=1, extraction=previous)
        result = skill.merge_extraction(dict(task=task, replace=replace,
            result=dict(charges=[dict(charge_id='a', amount=Decimal('6'))])))
        row = next(c for c in result['charges'] if c['charge_id']=='a')
        assert row['reference_no']=='ORFR1618731' and row['currency']=='USD'
        assert row['amount']==Decimal('6')
        assert len(result['charges']) == (1 if replace else 2)
        task['extraction'] = result
        cleared = skill.merge_extraction(dict(task=task, replace=replace,
            result=dict(charges=[dict(charge_id='a', reference_no=None)])))
        assert next(c for c in cleared['charges'] if c['charge_id']=='a')['reference_no'] is None


def test_repeated_extraction_merges_a_saved_row_instead_of_appending_a_duplicate():
    previous = {"charges": [
        dict(charge_id="ch_001", source_id="doc", document_id="doc_1", line_id="1",
             charge_item="HANDLING CHARGE", amount=Decimal("65.0"), currency="USD"),
        dict(charge_id="ch_002", source_id="doc", document_id="doc_1", line_id="2",
             charge_item="4 ADD'L DETENTION FREE TIME CHARGE", amount=Decimal("1310.4"), currency="USD"),
    ]}
    incoming = {"charges": [
        dict(source_id="doc", charge_item="HANDLING CHARGE", amount=Decimal("65.00"), currency="USD",
             creditor="Carrier", debtor="Client",
             evidence=[dict(source_id="doc", anchor="layout", quote="HANDLING CHARGE 65.00", quote_start=0)]),
        dict(source_id="doc", charge_item="4 ADD'L DETENTION FREE TIME CHARGE", amount=Decimal("1310.40"),
             currency="USD", creditor="Carrier", debtor="Client",
             evidence=[dict(source_id="doc", anchor="layout", quote="DETENTION 1,310.40", quote_start=0)]),
    ]}

    merged = skill.merge_extraction({"task": {"revision": 1, "extraction": previous}, "result": incoming})

    assert len(merged["charges"]) == 2
    by_id = {row["charge_id"]: row for row in merged["charges"]}
    assert set(by_id) == {"ch_001", "ch_002"}
    assert by_id["ch_001"]["debtor"] == "Client"
    assert (by_id["ch_001"]["document_id"], by_id["ch_001"]["line_id"]) == ("doc_1", "1")


def test_identical_saved_rows_are_not_collapsed_when_more_than_one_candidate_matches():
    previous = {"charges": [
        dict(charge_id="a", source_id="doc", line_id="1", charge_item="HANDLING CHARGE",
             amount=Decimal("65"), currency="USD"),
        dict(charge_id="b", source_id="doc", line_id="2", charge_item="HANDLING CHARGE",
             amount=Decimal("65"), currency="USD"),
    ]}

    merged = skill.merge_extraction({"task": {"revision": 1, "extraction": previous},
        "result": {"charges": [dict(source_id="doc", charge_item="HANDLING CHARGE",
                                     amount=Decimal("65"), currency="USD")]}})

    assert len(merged["charges"]) == 3


def test_repeated_extraction_with_a_different_document_id_does_not_merge():
    previous = {"charges": [dict(charge_id="a", source_id="doc", document_id="doc_1",
                                 charge_item="HANDLING CHARGE", amount=Decimal("65"), currency="USD")]}

    merged = skill.merge_extraction({"task": {"revision": 1, "extraction": previous},
        "result": {"charges": [dict(source_id="doc", document_id="doc_2",
                                     charge_item="HANDLING CHARGE", amount=Decimal("65"), currency="USD")]}})

    assert len(merged["charges"]) == 2


def test_stale_saved_charge_id_is_merged_into_the_existing_row():
    previous = {"charges": [dict(charge_id="ch_001", source_id="doc", document_id="doc_1",
                                 line_id="1", charge_item="HANDLING CHARGE",
                                 amount=Decimal("65"), currency="USD")]}
    incoming = {"charges": [dict(charge_id="charge-stale-id", source_id="doc",
                                 charge_item="HANDLING CHARGE", amount=Decimal("65.0"),
                                 currency="USD", debtor="Client")]}

    merged = skill.merge_extraction({"task": {"revision": 1, "extraction": previous},
                                     "result": incoming})

    assert len(merged["charges"]) == 1
    row = merged["charges"][0]
    assert (row["charge_id"], row["document_id"], row["line_id"]) == ("ch_001", "doc_1", "1")
    assert row["debtor"] == "Client"


def test_unknown_document_id_is_normalized_to_the_single_source_document():
    previous = dict(documents=[dict(source_id="doc", document_id="DC-1")],
                    totals=[dict(source_id="doc", document_id="dc-1", currency="USD",
                                 amount=Decimal("10"), role="total")])
    incoming = dict(
        documents=[dict(source_id="doc", document_id="DC-1")],
        charges=[dict(charge_id="c1", source_id="doc", document_id="doc_placeholder",
                      charge_item="Fee", amount=Decimal("10"), currency="USD")],
        totals=[dict(source_id="doc", document_id="DC-1", currency="USD",
                     amount=Decimal("10"), role="total")])

    merged = skill.merge_extraction({"task": {"revision": 1, "extraction": previous},
                                     "result": incoming})

    assert merged["charges"][0]["document_id"] == "DC-1"
    assert len(merged["totals"]) == 1


def test_changed_charge_source_does_not_inherit_unrelated_invoice_fields():
    previous = dict(charges=[dict(charge_id='a', source_id='old', reference_no='OLD-1', currency='USD')])
    for key in ('source_id', 'document_id', 'line_id'):
        old = dict(previous['charges'][0], **{key:'old'})
        result = skill.merge_extraction(dict(task=dict(revision=1, extraction=dict(charges=[old])),
            replace=True, result=dict(charges=[dict(charge_id='a', **{key:'new'}, amount=5)])))
        assert 'reference_no' not in result['charges'][0]


def test_human_evidence_correction_refreshes_extraction_for_hooks_and_reconciliation():
    candidate = {"charge_id": "c1", "source_id": "doc", "line_id": "row1", "reference_no": "I1",
                 "charge_item": "Doc Fee", "amount": Decimal("10"), "currency": "USD",
                 "creditor": "Carrier", "debtor": "Client", "evidence": []}
    source = {"source_id": "doc", "name": "invoice", "status": "ready", "format": "xlsx",
              "blocks": [{"anchor": "p1", "text": "Doc Fee USD 10", "authoritative": True}]}
    old_issue = {"code": "EVIDENCE_MISSING", "field": "evidence", "charge_id": "c1",
                 "message": "missing", "severity": "error"}
    original = data(sources=[source], existing_records=[], accounting_entity="Carrier",
                    extraction={"charges": [candidate], "coverage": [{"source_id": "doc", "anchor": "p1",
                        "status": "extracted", "reason": "all", "charge_ids": ["c1"]}], "issues": [old_issue], "valid": False},
                    evidence={"issues": [old_issue]},
                    operations=[{"op": "set", "charge_id": "c1", "field": "evidence",
                                 "value": [{"source_id": "doc", "anchor": "p1", "quote": "Doc Fee USD 10", "verified": True}]}])
    original["records"][0].update({k: v for k, v in candidate.items() if k not in {"amount", "currency", "charge_item", "reference_no"}})
    original["records"][0]["charge_details"]["charge_item"] = "Doc Fee"
    original["records"][0]["document_info"] = {"reference_no": "I1"}
    edited = skill.apply_revision(original)
    recalculated = skill.prepare_recalculation({"task": original, "review": edited})
    current = {**original, **recalculated}
    assert recalculated["extraction"]["revision"] == 4
    assert recalculated["extraction"]["charges"][0]["evidence"][0]["quote"] == "Doc Fee USD 10"
    assert recalculated["extraction"]["issues"] == [] and recalculated["evidence"] is None
    assert "valid" not in recalculated["extraction"]
    assert recalculated["extraction_history"][-1]["extraction"] == original["extraction"]
    for name, function_name in (("document-extraction", "validate_extraction"), ("billing-reconciliation", "reconcile_charges")):
        path = Path(__file__).parents[2] / name / "scripts" / "skill.py"
        spec = importlib.util.spec_from_file_location("review_interop_" + name.replace("-", "_"), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = getattr(module, function_name)(current)
        assert result["valid"], result["issues"]
        if "records" in result:
            assert result["records"][0]["operation"] == "CREATE"
    assert original["extraction"]["issues"] == [old_issue]


def test_recalculation_retains_unresolved_other_fields_and_updates_split_coverage():
    original = data(extraction={"charges": [], "coverage": [{"source_id": "doc", "anchor": "p1",
                        "status": "extracted", "reason": "all", "charge_ids": ["c1"]}],
                    "issues": [{"code": "OCR_AMBIGUOUS", "charge_id": "c1", "field": "currency"},
                               {"code": "OCR_AMBIGUOUS", "charge_id": "c1", "field": "amount"}]},
                    operations=[{"op": "set", "charge_id": "c1", "field": "amount", "value": "12"}])
    edited = skill.apply_revision(original)
    current = skill.prepare_recalculation({"task": original, "review": edited})
    assert [i["field"] for i in current["extraction"]["issues"]] == ["currency"]
    assert current["extraction"]["charges"][0]["amount"] == Decimal("12")
    split = skill.apply_revision({**original, "operations": [{"op": "split", "charge_id": "c1", "value": [{"amount": "4"}, {"amount": "6"}]}]})
    split_view = skill.prepare_recalculation({"task": original, "review": split})
    assert split_view["coverage"][0]["charge_ids"] == [r["charge_id"] for r in split["records"]]
    assert split_view["extraction"]["issues"] == []


def test_cli_file_contract_and_stdin_compatibility(tmp_path):
    import subprocess
    import sys
    import simplejson

    script = Path(__file__).parents[1] / "scripts" / "skill.py"
    payload = data(operations=[{"op": "set", "charge_id": "c1", "field": "amount", "value": "12.55"}])
    input_path, output_path = tmp_path / "input.json", tmp_path / "output.json"
    input_path.write_text(simplejson.dumps(payload, use_decimal=True), encoding="utf-8")
    result = subprocess.run([sys.executable, "-B", str(script), "--input", str(input_path), "--output", str(output_path)],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0 and not result.stdout and not result.stderr
    output = simplejson.loads(output_path.read_text(encoding="utf-8"), use_decimal=True)
    assert output["records"][0]["charge_details"]["amount"] == Decimal("12.55")
    payload["expected_revision"] = 2
    result = subprocess.run([sys.executable, "-B", str(script)], input=simplejson.dumps(payload, use_decimal=True),
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 1 and not result.stderr
    assert simplejson.loads(result.stdout)["issues"][0]["code"] == "REVISION_CONFLICT"


def test_missing_ids_preserve_two_rows_and_stay_stable_across_batch_order_changes():
    first = {"source_id": "doc", "line_id": "row1", "amount": Decimal("10"), "evidence": []}
    second = {"charge_id": None, "source_id": "doc", "line_id": "row2", "amount": Decimal("20"), "evidence": []}
    merged = skill.merge_extraction({"task": {"revision": 1}, "result": {"charges": [first, second]}})
    identities = {c["line_id"]: c["charge_id"] for c in merged["charges"]}
    assert len(merged["charges"]) == 2 and len(set(identities.values())) == 2 and all(identities.values())
    updated = skill.merge_extraction({"task": {"revision": 1, "extraction": merged},
        "result": {"charges": [{**second, "amount": Decimal("21")}, {**first, "amount": Decimal("11")}]}})
    assert len(updated["charges"]) == 2
    assert {c["line_id"]: c["charge_id"] for c in updated["charges"]} == identities
    assert {c["line_id"]: c["amount"] for c in updated["charges"]} == {"row1": Decimal("11"), "row2": Decimal("21")}


def test_missing_ids_never_collapse_another_row_or_overwrite_human_lock():
    edited = skill.apply_revision(data(operations=[{"op": "set", "charge_id": "c1", "field": "amount", "value": "12.55"}]))
    task = {"revision": 4, "records": edited["records"], "history": [edited], "extraction": {"charges": []}}
    incoming = [{"charge_id": None, "source_id": "doc", "amount": Decimal("999"),
                 "evidence": [{"source_id": "doc", "quote": "10"}]},
                {"charge_id": None, "source_id": "other", "line_id": "row2", "amount": Decimal("20"), "evidence": []}]
    merged = skill.merge_extraction({"task": task, "result": {"charges": incoming}, "replace": True})
    assert len(merged["charges"]) == 2
    by_id = {c["charge_id"]: c for c in merged["charges"]}
    assert by_id["c1"]["amount"] == Decimal("12.55")
    assert len(by_id) == 2 and None not in by_id
