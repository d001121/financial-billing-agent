"""Rule-support regressions using the real existing evidence and amount validators.

Docs MCP: /oss/python/deepagents/skills, /langsmith/code-evaluator-sdk.
Reference MCP: SkillsMiddleware, EvaluationResult. Installed combination:
LangChain 1.4.6, Deep Agents 0.7.29, LangSmith 0.14.11.
Unrelated host gates are fixed fixtures; no model, network or approval is replaced.
"""
from copy import deepcopy
from decimal import Decimal
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest
import simplejson


PACKAGE = Path(__file__).resolve().parents[1]
SKILLS = PACKAGE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


confidence = load("_confidence_under_test", PACKAGE / "scripts" / "skill.py")
financial = load("_confidence_financial_validator", SKILLS / "billing-reconciliation" / "scripts" / "skill.py")
evidence = load("_confidence_evidence_validator", SKILLS / "evidence-linking" / "scripts" / "skill.py")


def refresh(task):
    """Run the unique domain validators; provide fixed unrelated host gate facts."""
    validators = {"evidence": evidence.validate_evidence, "amount": financial.validate_amounts,
                  "matching": financial.validate_matching, "update": financial.validate_updates,
                  "posting": financial.validate_posting}
    checks = []
    for name in confidence.REQUIRED_CHECKS:
        result = validators[name](task) if name in validators else {"valid": True, "issues": []}
        checks.append({"name": name, "ok": result["valid"], **result})
    issues = [item for check in checks for item in check["issues"]]
    task["validation"] = {"revision": task["revision"], "ok": not issues, "issues": issues, "checks": checks}
    return task


def task_for(amount="50", quoted_amount=None, revision=1):
    quoted_amount = amount if quoted_amount is None else quoted_amount
    text = f"INV-1 THC USD {quoted_amount} QTY 2 UNIT {Decimal(amount) / 2}"
    total_text = f"TOTAL USD {amount}"
    charge = {"charge_id": "c1", "source_id": "doc", "document_id": "doc", "line_id": "row-1",
              "reference_no": "INV-1", "charge_item": "THC", "amount": Decimal(amount), "currency": "USD",
              "quantity": 2, "unit_price": Decimal(amount) / 2,
              "creditor": "Carrier", "debtor": "Client", "issuer": "Carrier", "recipient": "Client",
              "evidence": [{"source_id": "doc", "anchor": "p1", "quote": text}]}
    task = {"revision": revision, "accounting_entity": "Client", "existing_records": [],
            "charges": [charge], "sources": [{"source_id": "doc", "status": "ready", "blocks": [
                {"anchor": "p1", "text": text, "page": 1, "authoritative": True, "kind": "table"},
                {"anchor": "p1-total", "text": total_text, "page": 1, "authoritative": True, "kind": "table"}]}],
            "coverage": [{"chunk_id": "chunk-1", "status": "extracted", "charge_ids": ["c1"]}],
            "totals": [{"source_id": "doc", "role": "total", "currency": "USD", "amount": Decimal(amount),
                        "evidence": [{"source_id": "doc", "anchor": "p1-total", "quote": total_text}]}]}
    task["charges"] = evidence.link_evidence(task)["charges"]
    task["records"] = financial.reconcile_charges(task)["records"]
    return refresh(task)


def assess(task):
    result = confidence.assess_confidence(task)
    return result, result["records"][0]


def component(row, name):
    return next(item for item in row["components"] if item["id"] == name)


def test_info_issue_cannot_fail_a_passed_schema_check():
    check = dict(ok=True, valid=True, issues=[dict(code='NOT_INVOICE', severity='info')])
    assert confidence._check_state(check, 'c1') == 'passed'


def test_field_support_is_graded_by_evidence_strength():
    fact = {'status': 'supported', 'targets': [{'anchor': 'a'}]}
    header = dict(source_id='mail', anchor='mail/headers', kind='mail_headers',
                  quote='PRE-ALERT SSZSE26093128', field='reference_no')
    score, reasons = confidence._support_grade('reference_no', fact, [header])
    assert score == 45 and any('邮件' in reason for reason in reasons)

    plain = dict(source_id='doc', anchor='a', quote='SSZSE26093128', field='reference_no')
    assert confidence._support_grade('reference_no', fact, [plain])[0] == 90

    structured = dict(source_id='doc', anchor='a', kind='table',
                      quote='SSZSE26093128', field='reference_no')
    assert confidence._support_grade('reference_no', fact, [structured])[0] == 100


def test_unique_document_resolves_source_only_charge_total_scope():
    task = task_for()
    task['charges'][0]['document_id'] = None
    task['documents'] = [dict(source_id='doc', document_id='invoice-one')]
    task['totals'][0]['document_id'] = 'invoice-one'
    task['charges'][0].update(quantity=None, unit_price=None)
    task['records'] = financial.reconcile_charges(task)['records']
    row = assess(refresh(task))[1]
    assert row['signals']['document_total']['status'] == 'passed'


def test_auto_review_does_not_require_optional_template_information():
    task = task_for()
    task['charges'][0].update(reference_no=None, quantity=None, unit_price=None)
    task['records'] = financial.reconcile_charges(task)['records']
    task['totals'] = []
    result = confidence.assess_confidence(refresh(task))
    assert result['score'] == 80  # Preserve the uncalibrated evidence-support score.
    assert result['review_required'] is False
    assert result['review_items'] == []
    assert result['review_score'] == 100


def test_observed_wrong_value_creates_targeted_review_and_preserves_hard_gate():
    task = task_for()
    task['charges'][0]['amount'] = Decimal('500')
    task['records'] = financial.reconcile_charges(task)['records']
    result = confidence.assess_confidence(refresh(task))
    assert result['review_required'] is True
    assert any(item['field'] == 'amount' for item in result['review_items'])
    assert result['blockers']


def test_absent_values_are_not_low_confidence_and_do_not_become_executable():
    task = task_for()
    task['charges'][0].update(amount=None, currency=None)
    task['records'] = financial.reconcile_charges(task)['records']
    result = confidence.assess_confidence(refresh(task))
    assert result['review_required'] is False
    assert result['blockers']  # Required financial data is still unavailable.


def test_review_threshold_is_strict_and_configurable():
    task = refresh(task_for())
    task['options'] = {'review_threshold': 100}
    result = confidence.assess_confidence(task)
    assert result['review_required'] is False
    assert result['policy']['review_threshold'] == 100


def test_present_payment_term_is_checked_but_absence_is_not_a_review_task():
    task = task_for()
    task['charges'][0]['payment_term'] = 'PP'
    text = task['sources'][0]['blocks'][0]['text'] + ' PREPAID'
    task['sources'][0]['blocks'][0]['text'] = text
    task['charges'][0]['evidence'] = [{'source_id':'doc','anchor':'p1','quote':text}]
    task['records'] = financial.reconcile_charges(task)['records']
    good = confidence.assess_confidence(refresh(task))
    assert not good['review_required']
    assert good['records'][0]['fields']['payment_term']['status'] == 'supported'
    task['charges'][0]['payment_term'] = 'CC'
    bad = confidence.assess_confidence(refresh(task))
    assert any(item['field'] == 'payment_term' for item in bad['review_items'])


def test_cited_unresolved_raw_value_is_not_treated_as_absent_information():
    task = task_for()
    text = 'INV-1 THC $1,234'
    task['sources'][0]['blocks'][0]['text'] = text
    task['charges'][0].update(amount=None, currency=None, raw_amount='1,234', raw_currency='$',
        evidence=[{'source_id':'doc','anchor':'p1','quote':text}])
    task['records'] = financial.reconcile_charges(task)['records']
    result = confidence.assess_confidence(refresh(task))
    assert {'amount','currency'} <= {item['field'] for item in result['review_items']}


def test_normal_high_support_is_explained_and_does_not_mutate_or_approve():
    task = task_for()
    before = deepcopy(task)
    result, row = assess(task)
    assert result["score"] == 100 and row["band"] == "high" and row["eligible_for_quick_confirm"]
    assert result["method"] == "grouped_source_support_v2" and result["calibrated"] is False
    assert result["policy_version"] == "3.1.0" and not row["blockers"]
    assert all(value["status"] == "supported" for value in row["fields"].values())
    assert row["origin"] == "records" and row["record_id"] == row["charge_id"] == "c1"
    assert row["record"] == task["records"][0]
    assert all(target["page"] == 1 for target in row["evidence_targets"])
    assert sum(item["score"] for item in row["components"]) == row["score"]
    assert task == before and "approval" not in task


def test_unavailable_arithmetic_and_total_are_zero_and_produce_medium_support():
    task = task_for()
    task["charges"][0].pop("quantity")
    task["charges"][0].pop("unit_price")
    task["totals"] = []
    refresh(task)
    _, row = assess(task)
    assert row["score"] == 80 and row["band"] == "medium"
    assert not row["eligible_for_quick_confirm"]
    assert row["signals"]["line_arithmetic"]["status"] == "unavailable"
    assert row["signals"]["document_total"]["status"] == "unavailable"
    assert component(row, "consistency")["score"] == 0
    assert not row["blockers"]


def test_absent_declared_total_is_not_inferred_from_computed_sum_or_a_hard_blocker():
    task = task_for()
    task["totals"] = []
    refresh(task)
    assert next(check for check in task["validation"]["checks"] if check["name"] == "amount")["totals"]
    _, row = assess(task)
    assert row["score"] == 90 and row["eligible_for_quick_confirm"]
    assert row["signals"]["document_total"]["status"] == "unavailable"


def test_total_without_source_references_loses_only_its_optional_points():
    task = task_for()
    task["totals"][0]["evidence"] = []
    refresh(task)
    assert task["validation"]["ok"]
    _, row = assess(task)
    assert row["signals"]["document_total"]["status"] == "unavailable"
    assert row["score"] == 90 and not row["blockers"] and row["eligible_for_quick_confirm"]


def test_fabricated_total_matching_line_sum_gets_no_source_support_points():
    task = task_for()
    task["sources"][0]["blocks"][1]["text"] = "TOTAL USD 150"
    task["totals"][0]["evidence"][0]["quote"] = "TOTAL USD 150"
    refresh(task)
    assert not task["validation"]["ok"]  # A matching extracted sum cannot override original 150.
    assert any(i['code'] == 'TOTAL_VALUE_UNSUPPORTED' for i in task['validation']['issues'])
    _, row = assess(task)
    assert component(row, "consistency")["score"] == 0
    assert "amount" in row["signals"]["document_total"]["reason"]
    assert row["blockers"] and not row["eligible_for_quick_confirm"]


@pytest.mark.parametrize("alter", [
    lambda check: check.update(revision=0),
    lambda check: check["total_evidence"][0].update(currency="EUR"),
    lambda check: check["total_evidence"].append(deepcopy(check["total_evidence"][0])),
])
def test_total_requires_unique_fresh_scope_and_currency_result(alter):
    task = task_for()
    check = next(item for item in task["validation"]["checks"] if item["name"] == "evidence")
    alter(check)
    _, row = assess(task)
    assert row["signals"]["document_total"]["status"] == "unavailable"


def test_total_repeated_amount_in_broad_quote_requires_field_specific_location():
    task = task_for()
    text = "SUBTOTAL USD 50 TOTAL USD 50"
    task["sources"][0]["blocks"][1]["text"] = text
    task["totals"][0]["evidence"] = [{"source_id": "doc", "anchor": "p1-total", "quote": text}]
    refresh(task)
    _, row = assess(task)
    assert row["signals"]["document_total"]["status"] == "unavailable"
    task["totals"][0]["evidence"] = [{"source_id": "doc", "anchor": "p1-total", "quote": "TOTAL USD 50",
        "quote_start": text.rindex("TOTAL"), "field": field} for field in ("amount", "currency")]
    refresh(task)
    _, row = assess(task)
    assert row["signals"]["document_total"]["status"] == "passed"
    assert component(row, "consistency")["score"] == 20


@pytest.mark.parametrize("label", ["amount", "currency"])
def test_same_scoped_total_quote_supports_both_fields_when_only_one_is_labelled(label):
    task = task_for()
    task["totals"][0]["evidence"][0]["field"] = label
    refresh(task)
    assert task["validation"]["ok"], task["validation"]["issues"]
    _, row = assess(task)
    assert row["signals"]["document_total"]["status"] == "passed"
    assert component(row, "consistency")["score"] == 20
    assert row["score"] == 100 and row["eligible_for_quick_confirm"]


def test_total_fallback_does_not_accept_repeated_values_or_different_scopes():
    task = task_for()
    text = "Total USD 50 | Other USD 50"
    task["sources"][0]["blocks"][1]["text"] = text
    task["totals"][0]["evidence"] = [{"source_id": "doc", "anchor": "p1-total", "quote": text, "field": "amount"}]
    refresh(task)
    _, row = assess(task)
    assert row["signals"]["document_total"]["status"] == "unavailable"
    task["totals"][0]["document_id"] = "other-invoice"
    refresh(task)
    _, row = assess(task)
    assert row["signals"]["document_total"]["status"] == "unavailable"


def test_same_fabricated_evidence_never_gains_support_from_repetition_or_verified_flag():
    task = task_for()
    forged = {"source_id": "doc", "anchor": "p1", "quote": "nonexistent USD 50", "verified": True}
    task["charges"][0]["evidence"] = [forged]
    refresh(task)
    single, row = assess(task)
    task["charges"][0]["evidence"] = [deepcopy(forged) for _ in range(20)]
    refresh(task)
    repeated, duplicate_row = assess(task)
    assert single["score"] == repeated["score"] and row["band"] == "low"
    assert component(duplicate_row, "field_support")["score"] == 0
    assert not duplicate_row["eligible_for_quick_confirm"] and not duplicate_row["evidence_targets"]


def test_same_source_copy_and_repeated_references_do_not_increase_score():
    task = task_for()
    baseline, row = assess(task)
    alias = deepcopy(task["sources"][0])
    alias["source_id"] = "duplicate-doc"
    task["sources"].append(alias)
    ref = deepcopy(task["charges"][0]["evidence"][0])
    # The copy is related by the same invoice, not merely attachment membership.
    task['charges'][0]['source_links'] = [dict(source_id='duplicate-doc', relationship='same_bill',
        identity_field='reference_no', identity_value='INV-1', evidence=[
            dict(source_id=sid, anchor='p1', quote='INV-1') for sid in ('doc', 'duplicate-doc')])]
    task["charges"][0]["evidence"] *= 5
    task["charges"][0]["evidence"].append(dict(ref, source_id="duplicate-doc"))
    refresh(task)
    copied, copy_row = assess(task)
    assert baseline["score"] == copied["score"]
    assert len(copy_row["evidence_targets"]) == len(row["evidence_targets"])


@pytest.mark.parametrize(("amount", "quote", "supported"), [
    ("50", "150", False), ("150", "50", False), ("50", "50", True), ("150", "150", True),
    ("50", "50.00", True),
])
def test_amount_support_uses_decimal_tokens_not_substrings(amount, quote, supported):
    _, row = assess(task_for(amount, quote))
    assert (row["fields"]["amount"]["status"] == "supported") is supported
    assert row["eligible_for_quick_confirm"] is supported


def test_multiple_equal_values_need_field_or_line_ownership():
    task = task_for()
    text = "INV-1 THC USD 50\nINV-2 THC USD 50"
    task["sources"][0]["blocks"][0]["text"] = text
    task["charges"][0]["evidence"] = [{"source_id": "doc", "anchor": "p1", "quote": text}]
    refresh(task)
    _, row = assess(task)
    assert row["fields"]["amount"]["status"] == "ambiguous"
    assert not row["eligible_for_quick_confirm"]
    task["charges"][0]["evidence"] = [
        {"source_id": "doc", "anchor": "p1", "quote": value, "quote_start": text.index(value), "field": field}
        for field, value in {"reference_no": "INV-1", "charge_item": "THC", "amount": "50", "currency": "USD"}.items()]
    refresh(task)
    _, resolved = assess(task)
    assert resolved["fields"]["amount"]["status"] == "supported"
    assert resolved["eligible_for_quick_confirm"]


def test_candidate_source_name_support_never_bypasses_record_name_conflict():
    task = task_for()
    # A missing normalization provenance cannot authorize a new name mapping.
    task["records"][0]["raw_charge_item"] = None
    _, row = assess(task)
    assert row["fields"]["charge_item"]["status"] == "supported"
    assert any(item["code"] == "RECORD_CANDIDATE_CONFLICT" and item["field"] == "charge_item"
               for item in row["blockers"])
    assert not row["eligible_for_quick_confirm"]


def test_precise_word_references_resolve_equal_unit_and_line_amounts_without_relaxing_broad_quotes():
    task = task_for("20")
    text = "INV-1 Doc Fee | Quantity 1 | Unit price USD 20 | Amount USD 20"
    task["sources"][0]["blocks"][0]["text"] = text
    charge = task["charges"][0]
    charge.update(charge_item="Doc Fee", raw_charge_item=None, quantity=1, unit_price=Decimal("20"),
                  evidence=[{"source_id": "doc", "anchor": "p1", "quote": text}])
    task["charges"] = evidence.link_evidence(task)["charges"]
    task["records"] = financial.reconcile_charges(task)["records"]
    refresh(task)
    assert not task["validation"]["ok"]
    assert any(issue["code"] == "FIELD_VALUE_AMBIGUOUS" for issue in task["validation"]["issues"])
    _, broad = assess(task)
    assert broad["fields"]["amount"]["status"] == "ambiguous"
    assert broad["fields"]["currency"]["status"] == "ambiguous"
    assert not broad["eligible_for_quick_confirm"]
    assert task["records"][0]["raw_charge_item"] == "Doc Fee"

    task["charges"][0]["evidence"] = [
        {"source_id": "doc", "anchor": "p1", "quote": quote, "field": field,
         "quote_start": text.index(quote), "line_id": "row-1"}
        for field, quote in {"reference_no": "INV-1", "charge_item": "Doc Fee",
                             "amount": "Amount USD 20", "currency": "Amount USD 20"}.items()]
    refresh(task)
    before = deepcopy(task)
    _, precise = assess(task)
    assert precise["score"] == 100 and precise["eligible_for_quick_confirm"]
    assert all(item["status"] == "supported" for item in precise["fields"].values())
    assert task == before


def test_correct_arithmetic_does_not_validate_the_wrong_currency():
    task = task_for()
    task["charges"][0]["currency"] = "EUR"
    task["records"][0]["charge_details"]["currency"] = "EUR"
    task["totals"][0]["currency"] = "EUR"
    refresh(task)
    assert not task["validation"]["ok"]
    _, row = assess(task)
    assert component(row, "consistency")["score"] == 0
    assert row["fields"]["currency"]["status"] in {"unsupported", "unavailable"}
    assert row["review_route"] == "blocked"
    assert not row["eligible_for_quick_confirm"]


@pytest.mark.parametrize("change", [
    lambda task: task["charges"][0].update(unit_price="30"),
    lambda task: task["totals"][0].update(amount="150"),
])
def test_real_amount_and_total_mismatch_results_are_hard_gates(change):
    task = task_for()
    change(task)
    refresh(task)
    _, row = assess(task)
    assert not row["eligible_for_quick_confirm"]
    assert {item["code"] for item in row["blockers"]} & {"LINE_ARITHMETIC", "TOTAL_MISMATCH"}


def test_unknown_checks_do_not_substitute_for_missing_known_checks():
    task = task_for()
    next(check for check in task["validation"]["checks"] if check["name"] == "amount")["name"] = "model_confidence"
    task["model_confidence"] = 1.0
    _, row = assess(task)
    assert component(row, "consistency")["score"] == 0
    assert any(item["code"] == "CHECK_UNAVAILABLE" and item["field"] == "amount" for item in row["blockers"])
    assert not row["eligible_for_quick_confirm"]


@pytest.mark.parametrize("change", [
    lambda task: task["validation"].update(revision=0),
    lambda task: task["records"][0].update(revision=0),
    lambda task: task["records"][0].update(human_confirmed={"charge_details.amount": {"revision": 0, "value": "50"}}),
    lambda task: task["records"][0]["financial_attributes"].update(accounting_entity=None),
    lambda task: task["records"][0]["charge_details"].update(amount="150"),
])
def test_staleness_missing_entity_and_record_candidate_conflict_never_quick_confirm(change):
    task = task_for()
    change(task)
    _, row = assess(task)
    assert row["blockers"] and not row["eligible_for_quick_confirm"]


def test_coverage_conflict_is_a_hard_gate_even_when_a_custom_policy_scores_high():
    task = task_for()
    task["validation"]["issues"] = [{"code": "COVERAGE_OPEN", "message": "page 2 not processed"}]
    task["validation"]["ok"] = False
    task["options"] = {"high_threshold": 50, "medium_threshold": 20, "policy_id": "review-policy-a"}
    result, row = assess(task)
    assert row["band"] == "high" and not row["eligible_for_quick_confirm"]
    assert result["policy_id"] == "review-policy-a"


def test_candidate_fallback_projects_draft_without_inventing_direction_or_approval():
    task = task_for()
    task["records"] = []
    result, row = assess(task)
    assert row["origin"] == "charges" and row["record_id"] == row["charge_id"] == "c1"
    assert row["record"]["charge_details"]["amount"] == Decimal("50")
    assert row["record"]["financial_attributes"]["posting_type"] is None
    assert row["record"]["operation"] == "PENDING_REVIEW"
    assert not result["eligible_for_quick_confirm"]


def test_task_score_uses_weakest_row_and_never_averages_away_a_problem():
    task = task_for()
    first = task["records"][0]
    second = deepcopy(first)
    second.update(charge_id="c2", evidence=[])
    task["charges"].append(dict(deepcopy(task["charges"][0]), charge_id="c2", evidence=[]))
    task["records"].append(second)
    refresh(task)
    result = confidence.assess_confidence(task)
    assert result["score"] == min(row["score"] for row in result["records"])
    assert result["score"] < result["records"][0]["score"] and not result["eligible_for_quick_confirm"]


@pytest.mark.parametrize("raw", ["1.234,56", "1,234.56", "1 234,56", "1\u202f234,56", "١٬٢٣٤٫٥٦", "１，２３４．５６"])
def test_global_raw_numbers_support_canonical_amount_without_locale_or_template(raw):
    task = task_for("1234.56")
    text = f"INV-1 THC USD {raw} QTY 2 UNIT 617.28"
    task["sources"][0]["blocks"][0]["text"] = text
    task["charges"][0].update(raw_amount=raw, evidence=[{"source_id": "doc", "anchor": "p1", "quote": text}])
    task["sources"][0]["blocks"][1]["text"] = f"TOTAL USD {raw}"
    task["totals"][0]["evidence"][0]["quote"] = f"TOTAL USD {raw}"
    refresh(task)
    result, row = assess(task)
    assert task["validation"]["ok"], task["validation"]["issues"]
    assert row["fields"]["amount"]["status"] == "supported"
    assert row["score"] == 100 and row["review_route"] == "quick_confirm"
    assert result["calibrated"] is False


@pytest.mark.parametrize("expected", ["1234", "1.234"])
def test_same_raw_number_has_two_readings_even_if_model_arithmetic_agrees(expected):
    task = task_for(expected)
    text = "INV-1 THC USD 1,234"
    task["sources"][0]["blocks"][0]["text"] = text
    task["charges"][0].update(raw_amount="1,234", evidence=[{"source_id": "doc", "anchor": "p1", "quote": text}])
    refresh(task)
    _, row = assess(task)
    assert row["fields"]["amount"]["status"] == "ambiguous"
    assert row["fields"]["amount"]["observations"]
    assert row["review_route"] == "blocked" and not row["eligible_for_quick_confirm"]
    assert any(issue["code"] == "FIELD_VALUE_AMBIGUOUS" for issue in task["validation"]["issues"])


def test_internal_arithmetic_without_source_operands_never_earns_constraint_points():
    task = task_for()
    text = "INV-1 THC USD 50"
    task["sources"][0]["blocks"][0]["text"] = text
    task["charges"][0]["evidence"] = [{"source_id": "doc", "anchor": "p1", "quote": text}]
    task["totals"] = []
    refresh(task)
    _, row = assess(task)
    assert row["score"] == 80 and not row["blockers"]
    assert row["signals"]["line_arithmetic"]["status"] == "unavailable"
    assert "原文" in row["signals"]["line_arithmetic"]["reason"]
    assert row["review_route"] == "review_suggested"


def test_two_correlated_arithmetic_checks_use_max_not_sum():
    both = task_for()
    _, both_row = assess(both)
    no_line = deepcopy(both)
    no_line["charges"][0].pop("quantity")
    no_line["charges"][0].pop("unit_price")
    refresh(no_line)
    _, total_row = assess(no_line)
    assert both_row["score"] == total_row["score"] == 100
    assert component(both_row, "consistency")["score"] == component(total_row, "consistency")["score"]
    assert both_row["fusion"]["duplicate_bonus"] is False


def test_declared_total_reusing_same_physical_amount_cannot_be_extra_evidence():
    task = task_for()
    task["totals"][0]["evidence"] = deepcopy(task["charges"][0]["evidence"])
    refresh(task)
    _, row = assess(task)
    assert row["signals"]["document_total"]["status"] == "unavailable"
    assert "同一原文" in row["signals"]["document_total"]["reason"]
    assert row["score"] == 90


def test_extra_total_citation_does_not_hide_independent_line_amount_support():
    task = task_for()
    check = next(row for row in task['validation']['checks'] if row['name'] == 'evidence')
    total = check['total_evidence'][0]
    check['charges'][0]['field_support']['amount']['targets'].extend(
        deepcopy(total['field_support']['amount']['targets']))
    _, row = assess(task)
    assert row['signals']['document_total']['status'] == 'passed'


def test_equal_word_cell_text_at_distinct_anchors_is_not_the_same_physical_token():
    task = task_for()
    blocks = [{"anchor": anchor, "text": text, "table": 1, "cell": index}
              for index, (anchor, text) in enumerate([
                  ("id", "INV-1"), ("fee", "THC"), ("currency", "USD"),
                  ("line-amount", "50"), ("total-amount", "50")])]
    task["sources"][0]["blocks"] = blocks
    task["charges"][0].update(quantity=None, unit_price=None, evidence=[
        {"source_id": "doc", "anchor": anchor, "quote": text, "field": field}
        for anchor, text, field in [("id", "INV-1", "reference_no"), ("fee", "THC", "charge_item"),
                                    ("currency", "USD", "currency"), ("line-amount", "50", "amount")]])
    task["totals"][0]["evidence"] = [
        {"source_id": "doc", "anchor": "total-amount", "quote": "50", "field": "amount"},
        {"source_id": "doc", "anchor": "currency", "quote": "USD", "field": "currency"}]
    refresh(task)
    _, row = assess(task)
    assert task["validation"]["ok"], task["validation"]["issues"]
    assert row["signals"]["document_total"]["status"] == "passed"
    assert row["score"] == 100 and row["eligible_for_quick_confirm"]


def test_reference_and_operands_are_optional_for_a_template_free_bill_with_real_total():
    task = task_for()
    task["charges"][0].update(reference_no=None, quantity=None, unit_price=None)
    task["records"][0]["document_info"]["reference_no"] = None
    refresh(task)
    _, row = assess(task)
    assert row["fields"]["reference_no"]["status"] == "missing"
    assert row["score"] == 100 and not row["blockers"]
    assert row["eligible_for_quick_confirm"]


def test_legacy_or_forged_field_facts_cannot_replace_current_contract():
    task = task_for()
    check = next(check for check in task["validation"]["checks"] if check["name"] == "evidence")
    check.pop("field_support_contract")
    task["charges"][0]["model_confidence"] = 1
    _, row = assess(task)
    assert row["fields"]["amount"]["status"] == "unavailable"
    assert row["review_route"] == "blocked"


def test_dollar_symbol_never_inherits_usd_from_a_separate_total():
    task = task_for()
    text = "INV-1 THC $50 QTY 2 UNIT 25"
    task["sources"][0]["blocks"][0]["text"] = text
    task["charges"][0]["evidence"] = [{"source_id": "doc", "anchor": "p1", "quote": text}]
    refresh(task)
    _, row = assess(task)
    assert row["fields"]["currency"]["status"] in {"unsupported", "ambiguous"}
    assert row["review_route"] == "blocked"


def test_discount_sign_comes_from_financial_normalization_not_a_second_scoring_rule():
    task = task_for()
    task["charges"][0]["line_role"] = "discount"
    task["sources"][0]["blocks"][1]["text"] = "TOTAL USD (50)"
    task["totals"][0].update(amount=Decimal("-50"), evidence=[{
        "source_id": "doc", "anchor": "p1-total", "quote": "TOTAL USD (50)"}])
    task["records"] = financial.reconcile_charges(task)["records"]
    refresh(task)
    _, row = assess(task)
    assert task["validation"]["ok"], task["validation"]["issues"]
    assert row["record"]["charge_details"]["amount"] == Decimal("-50")
    assert row["score"] == 100 and not row["blockers"]
    task["records"][0]["charge_details"]["amount"] = Decimal("-60")
    _, changed = assess(task)
    assert any(item["code"] == "RECORD_CANDIDATE_CONFLICT" for item in changed["blockers"])
    assert changed["review_route"] == "blocked"


def test_native_tool_binding_and_cli_work_outside_the_project(tmp_path):
    from langchain.tools import tool
    native = tool("assess_confidence")(confidence.assess_confidence)
    task = task_for()
    expected = confidence.assess_confidence(task)
    assert native.invoke({"payload": task}) == expected
    source, destination = tmp_path / "输入.json", tmp_path / "评分.json"
    source.write_text(simplejson.dumps(task, use_decimal=True), encoding="utf-8-sig")
    result = subprocess.run([sys.executable, "-B", str(PACKAGE / "scripts" / "skill.py"),
        "--input", str(source), "--output", str(destination)], cwd=tmp_path,
        capture_output=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "" and result.stderr == ""
    assert simplejson.loads(destination.read_text(encoding="utf-8"), use_decimal=True) == expected
    malformed = subprocess.run([sys.executable, "-B", str(PACKAGE / "scripts" / "skill.py")],
        cwd=tmp_path, input="{", capture_output=True, encoding="utf-8", timeout=20)
    assert malformed.returncode == 1 and simplejson.loads(malformed.stdout)["issues"][0]["code"] == "CLI_INPUT"
