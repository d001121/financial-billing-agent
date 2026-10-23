import importlib.util
from pathlib import Path
from decimal import Decimal

SPEC = importlib.util.spec_from_file_location("billing_reconciliation_skill", Path(__file__).parents[1] / "scripts" / "skill.py")
skill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill)


def charge(**overrides):
    return {"charge_id": "c1", "source_id": "invoice", "line_id": "row-1", "reference_no": "INV-01",
            "document_type": "Invoice", "issuer": "Carrier", "recipient": "Client", "charge_item": "H/D Fee",
            "amount": "100.10", "currency": "USD", "payment_term": "prepaid",
            "creditor": "Carrier", "debtor": "Client", "evidence": [
                {"source_id": "invoice", "anchor": "p1", "quote": "100.10", "verified": True},
                {"source_id": "invoice", "anchor": "p1", "quote": "PP", "field": "payment_term", "verified": True}],
            **overrides}


def reconcile(charges=None, **more):
    return skill.reconcile_charges({"charges": charges or [charge()], "existing_records": [],
                                    "accounting_entity": "Carrier", "revision": 1, **more})


def test_create_normalizes_and_current_entity_changes_direction():
    result = reconcile()
    row = result["records"][0]
    assert result["valid"]
    assert row["operation"] == "CREATE"
    assert row["charge_details"] == {"charge_item": "Handling Charge", "amount": Decimal("100.10"), "currency": "USD", "payment_term": "PP"}
    assert row["financial_attributes"]["posting_type"] == "AR"
    assert reconcile(accounting_entity="Client")["records"][0]["financial_attributes"]["posting_type"] == "AP"


def test_total_scope_matches_when_only_one_row_has_document_id():
    document = dict(source_id="invoice", document_id="doc-1")
    charge_first = reconcile([charge(amount="245", currency="USD")],
        totals=[dict(source_id="invoice", document_id="doc-1", currency="USD",
                     amount="245", role="total")],
        documents=[document])
    assert not any(i["code"] == "TOTAL_MISMATCH" for i in charge_first["issues"])

    total_first = reconcile([charge(amount="245", currency="USD", document_id="doc-1")],
        totals=[dict(source_id="invoice", currency="USD", amount="245", role="total")],
        documents=[document])
    assert not any(i["code"] == "TOTAL_MISMATCH" for i in total_first["issues"])


def test_printed_heading_with_spaces_normalizes_to_canonical_type():
    for raw, expected in (("DEBIT NOTE", "Debit Note"),
                          ("GENERAL NOTICE", "General Notice"),
                          ("PRE-ALERT EMAIL", "Pre-Alert")):
        row = reconcile([charge(document_type=raw)])["records"][0]
        assert row["document_info"]["document_type"] == expected


def test_explicit_pay_line_fills_payer_and_payee_without_overwriting():
    evidence = [dict(source_id="mail", anchor="mail/body",
                     quote="SHA pay TAR：H/C $50", verified=True)]
    result = reconcile([charge(charge_item="H/C", amount="50", creditor=None, debtor=None,
                               evidence=evidence)], accounting_entity="TARGETING A INC")
    row = result["records"][0]
    assert row["creditor"] == "TAR" and row["debtor"] == "SHA"
    assert row["financial_attributes"]["posting_type"] is None


def test_pay_line_does_not_overwrite_a_human_confirmed_side():
    evidence = [dict(source_id="mail", anchor="mail/body",
                     quote="SHA pay TAR：H/C $50", verified=True)]
    result = reconcile([charge(charge_item="H/C", amount="50", creditor="NEPTUNE", debtor=None,
                               human_confirmed={"creditor": {"revision": 2, "value": "NEPTUNE"}},
                               evidence=evidence)], accounting_entity="NEPTUNE")
    row = result["records"][0]
    assert row["creditor"] == "NEPTUNE" and row["debtor"] == "SHA"


def test_pay_line_ignores_a_leading_imperative():
    evidence = [dict(source_id="mail", anchor="mail/body",
                     quote="please pay TAR：H/C $50", verified=True)]
    result = reconcile([charge(charge_item="H/C", amount="50", creditor=None, debtor=None,
                               evidence=evidence)], accounting_entity="TAR")
    row = result["records"][0]
    assert row["creditor"] is None and row["debtor"] is None


def test_one_stated_side_fixes_direction_without_inventing_the_counterparty():
    receivable = reconcile([charge(debtor=None)])
    assert receivable["valid"], receivable["issues"]
    assert receivable["records"][0]["financial_attributes"]["posting_type"] == "AR"
    assert receivable["records"][0]["debtor"] is None

    payable = reconcile([charge(creditor=None)], accounting_entity="Client")
    assert payable["valid"], payable["issues"]
    assert payable["records"][0]["financial_attributes"]["posting_type"] == "AP"
    assert payable["records"][0]["creditor"] is None

    unrelated = reconcile([charge(debtor=None)], accounting_entity="Some Other Co")
    assert unrelated["records"][0]["financial_attributes"]["posting_type"] is None
    assert any(i["code"] == "POSTING_UNRESOLVED" for i in unrelated["issues"])


def test_native_candidate_with_null_raw_name_preserves_original_before_normalizing():
    spec = importlib.util.spec_from_file_location("_reconciliation_extraction_contract",
        Path(__file__).parents[2] / "document-extraction" / "scripts" / "skill.py")
    extraction = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extraction)
    incoming = extraction.ChargeCandidate.model_validate(charge(raw_charge_item=None)).model_dump(mode="python")
    assert incoming["raw_charge_item"] is None
    result = reconcile([incoming])
    assert result["valid"]
    assert result["records"][0]["charge_details"]["charge_item"] == "Handling Charge"
    assert result["records"][0]["raw_charge_item"] == "H/D Fee"
    assert incoming["raw_charge_item"] is None
    assert skill.normalized(charge(raw_charge_item="Original H/D"))["raw_charge_item"] == "Original H/D"


def test_amount_only_update_inherits_missing_fields_and_does_not_mutate_old():
    old = charge(charge_id="old", amount="80.00", payment_term="CC", document_date="2026-10-01")
    incoming = charge(amount="120.25", payment_term=None, document_date=None)
    result = reconcile([incoming], existing_records=[old],
                       update_instructions=[{"target_id": "old", "changes": {"amount": "120.25"}}])
    record = result["records"][0]
    assert result["valid"] and record["operation"] == "UPDATE"
    assert record["document_info"]["document_date"] == "2026-10-01"
    assert record["charge_details"]["payment_term"] == "CC"
    assert old["amount"] == "80.00"


def test_difference_is_not_update_authorization_and_same_is_no_change():
    old = charge(charge_id="old", amount="90")
    assert reconcile(existing_records=[old])["records"][0]["operation"] == "PENDING_REVIEW"
    assert reconcile(existing_records=[charge(charge_id="old")])["records"][0]["operation"] == "NO_CHANGE"


def test_explicit_null_differs_from_omission():
    result = reconcile(existing_records=[charge(charge_id="old")],
                       update_instructions=[{"target_id": "old", "changes": {"amount": None}}])
    assert result["records"][0]["charge_details"]["amount"] is None
    assert not result["valid"]


def test_ambiguous_same_named_existing_rows_are_never_first_match():
    old = [charge(charge_id="old1"), charge(charge_id="old2")]
    result = reconcile(existing_records=old)
    assert result["records"][0]["operation"] == "PENDING_REVIEW"
    assert result["records"][0]["match"]["candidate_ids"] == ["old1", "old2"]
    selected = reconcile([charge(selected_match_id="old2")], existing_records=old)
    assert selected["valid"] and selected["records"][0]["operation"] == "NO_CHANGE"
    assert skill.validate_matching({"charges": [charge(selected_match_id="old2")], "existing_records": old})["valid"]
    assert not skill.validate_matching({"charges": [charge(selected_match_id="other")], "existing_records": old})["valid"]


def test_missing_relationship_credit_note_and_collect_never_guess_direction():
    result = reconcile([charge(document_type="Credit Note", amount="-10", payment_term="CC", creditor=None)])
    assert result["records"][0]["financial_attributes"]["posting_type"] is None
    assert result["records"][0]["operation"] == "PENDING_REVIEW"


def test_decimal_totals_currency_and_nonfinite_guard():
    assert skill.validate_amounts({"charges": [charge(amount="0.3", quantity="3", unit_price="0.1")]})["valid"]
    assert not skill.validate_amounts({"charges": [charge(amount="NaN")]})["valid"]
    assert not skill.validate_amounts({"charges": [charge(currency="$")]})["valid"]
    assert not skill.validate_amounts({"charges": [charge()], "totals": [{"source_id": "invoice", "currency": "USD", "amount": "999"}]})["valid"]
    assert not skill.validate_amounts({"charges": [charge(amount=True)]})["valid"]


def test_same_named_real_lines_stay_distinct_but_repeated_source_claims_review():
    result = reconcile([charge(), charge(charge_id="c2", line_id="row-2")])
    assert len(result["records"]) == 2 and all(r["operation"] == "CREATE" for r in result["records"])
    duplicate = reconcile([charge(), charge(charge_id="c2", source_id="other_invoice")])
    assert all(r["operation"] == "PENDING_REVIEW" for r in duplicate["records"])


def test_existing_scope_must_be_explicit_and_total_lines_are_not_charges():
    result = skill.reconcile_charges({"charges": [charge()], "accounting_entity": "Carrier"})
    assert not result["valid"]
    assert reconcile([charge(line_role="total")])["records"] == []


def test_unverified_evidence_or_incomplete_source_makes_proposals_pending():
    bad = charge(evidence=[{"source_id": "invoice", "anchor": "p1", "quote": "100.10", "verified": False}])
    assert reconcile([bad])["records"][0]["operation"] == "PENDING_REVIEW"
    result = reconcile(sources=[{"source_id": "invoice", "status": "partial"}])
    assert not result["valid"] and result["records"][0]["operation"] == "PENDING_REVIEW"
    assert not skill.reconcile_charges({"charges": [], "existing_records": [], "sources": [{"source_id": "invoice", "status": "failed"}]})["valid"]


def test_separate_logical_invoices_in_one_pdf_have_separate_totals():
    result = skill.validate_amounts({"charges": [charge(document_id="inv-1", amount="10"),
                                                  charge(document_id="inv-2", amount="20")],
                                    "totals": [{"source_id": "invoice", "document_id": "inv-1", "currency": "USD", "amount": "10"},
                                               {"source_id": "invoice", "document_id": "inv-2", "currency": "USD", "amount": "20"}]})
    assert result["valid"] and len(result["totals"]) == 2


def test_explicit_tax_discount_roles_count_once_and_carry_forwards_do_not_count():
    payload = {"charges": [charge(amount="100"), charge(charge_id="discount", amount="10", line_role="discount")],
               "totals": [{"source_id": "invoice", "currency": "USD", "role": "tax", "amount": "5"},
                          {"source_id": "invoice", "currency": "USD", "role": "discount", "amount": "10"},
                          {"source_id": "invoice", "currency": "USD", "role": "carry_forward", "amount": "100"},
                          {"source_id": "invoice", "currency": "USD", "role": "total", "amount": "95"}]}
    assert skill.validate_amounts(payload)["valid"]


def test_amount_validation_exposes_current_discount_normalization_without_mutating_source():
    source = charge(amount="50", currency="usd", line_role="discount", quantity="2", unit_price="25",
                    raw_amount="50", raw_currency="usd", raw_quantity="2", raw_unit_price="25")
    result = skill.validate_amounts({"revision": 7, "charges": [source], "totals": [
        {"source_id": "invoice", "currency": "USD", "role": "total", "amount": "-50"}]})
    assert result["valid"] and result["revision"] == 7
    assert result["normalized_charges"] == [{"charge_id": "c1", "input_amount": "50", "amount": Decimal("-50"),
                                               "currency": "USD", "line_role": "discount"}]
    assert source["amount"] == "50" and source["currency"] == "usd"
    assert result["normalized_charges"][0]["amount"] != Decimal("-60")
    record = reconcile([source])["records"][0]
    assert record["charge_details"]["amount"] == Decimal("-50")
    for field in ("raw_amount", "raw_currency", "raw_quantity", "raw_unit_price"):
        assert record[field] == source[field]


def test_normalized_amount_facts_use_flattened_current_input_and_ignore_claimed_facts():
    source = charge(amount="999", charge_details={"amount": "50", "currency": "usd"})
    result = skill.validate_amounts({"revision": 4, "charges": [source],
        "normalized_charges": [{"charge_id": "c1", "input_amount": "999", "amount": "-60"}]})
    assert result["valid"] and result["revision"] == 4
    assert result["normalized_charges"] == [{"charge_id": "c1", "input_amount": "50", "amount": Decimal("50"),
                                               "currency": "USD", "line_role": "charge"}]


def test_failed_amount_validation_never_claims_normalization_passed():
    result = skill.validate_amounts({"revision": 8, "charges": [charge(amount="invalid")]})
    assert result["revision"] == 8 and not result["valid"]
    assert any(issue["code"] == "INVALID_AMOUNT" for issue in result["issues"])
    assert result["normalized_charges"][0]["input_amount"] == "invalid"
    assert result["normalized_charges"][0]["amount"] == "invalid"


def test_hc_alias_maps_to_handling_charge_and_keeps_the_raw_name():
    row = reconcile([charge(charge_item="H/C")])["records"][0]
    assert row["charge_details"]["charge_item"] == "Handling Charge"
    assert row["raw_charge_item"] == "H/C"


def test_any_hc_phrase_maps_to_handling_charge():
    row = reconcile([charge(charge_item="Carrier Free H/C")])["records"][0]
    assert row["charge_details"]["charge_item"] == "Handling Charge"
    assert row["raw_charge_item"] == "Carrier Free H/C"


def test_symbol_only_currency_is_nulled_and_pending():
    incoming = charge(evidence=[{"source_id": "mail", "anchor": "mail/body", "field": "currency",
                                 "quote": "SHA pay TAR：H/C $50", "verified": True}])
    row = reconcile([incoming])["records"][0]
    assert row["charge_details"]["currency"] is None
    assert row["operation"] == "PENDING_REVIEW"
    assert any(issue["code"] == "CURRENCY_SYMBOL_AMBIGUOUS" for issue in row["issues"])


def test_party_absent_from_its_field_quote_is_dropped_and_posting_stays_open():
    incoming = charge(creditor="TAR", debtor="湃乐多（上海）航运科技有限公司",
        evidence=[{"source_id": "mail", "anchor": "mail/body", "field": "debtor",
                   "quote": "To: li <li@pltplt.com>", "verified": True}])
    row = reconcile([incoming], accounting_entity="湃乐多（上海）航运科技有限公司")["records"][0]
    assert row["financial_attributes"]["posting_type"] is None
    assert row["operation"] == "PENDING_REVIEW"
    assert any(issue["code"] == "PARTY_UNSUPPORTED" for issue in row["issues"])


def test_payment_term_keeps_only_evidenced_pp_or_cc():
    cod = reconcile([charge(payment_term="COD")])["records"][0]
    assert cod["charge_details"]["payment_term"] is None
    assert cod["raw_payment_term"] == "COD"
    assert cod["operation"] == "CREATE"
    inferred = reconcile([charge(payment_term="PP", evidence=[
        {"source_id": "invoice", "anchor": "p1", "quote": "245.0000 USD", "verified": True}])])["records"][0]
    assert inferred["charge_details"]["payment_term"] is None
    assert inferred["raw_payment_term"] == "PP"


def test_document_type_uses_the_printed_heading():
    assert reconcile([charge(document_type="email_pre_alert")])["records"][0]["document_info"]["document_type"] == "Pre-Alert"
    assert reconcile([charge(document_type="arrival_notice")])["records"][0]["document_info"]["document_type"] == "General Notice"
    assert reconcile([charge(document_type="Debit Note")])["records"][0]["document_info"]["document_type"] == "Debit Note"
