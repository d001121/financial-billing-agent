import importlib.util
from pathlib import Path
from decimal import Decimal
import simplejson

SPEC = importlib.util.spec_from_file_location("billing_export_skill", Path(__file__).parents[1] / "scripts" / "skill.py")
skill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill)


def record(**more):
    return {"operation": "CREATE", "charge_item": "THC", "amount": Decimal("1234567890.123456789"),
            "currency": "USD", "accounting_entity": "Client", "posting_type": "AP", **more}


def test_top_level_array_decimal_number_nulls_and_exact_groups():
    wire = skill.export_json({"records": [record()], "revision": 3, "validation_revision": 3})
    assert '1234567890.123456789' in wire and '"1234567890.123456789"' not in wire
    value = simplejson.loads(wire, use_decimal=True)
    assert isinstance(value, list) and value[0]["charge_details"]["amount"] == Decimal("1234567890.123456789")
    assert value[0]["document_info"]["reference_no"] is None
    assert set(value[0]) == {"operation", "document_info", "transaction_party", "charge_details", "financial_attributes", "audit_trail"}


def test_stale_validation_approval_and_bad_amounts_block_export():
    for extra in ({"expected_revision": 1}, {"validation_revision": 1}, {"approval_revision": 1}):
        assert not skill.build_export({"records": [record()], "revision": 2, **extra})["valid"]
    for amount in (True, "NaN", "Infinity", "not a number"):
        assert not skill.validate_export({"records": [record(amount=amount)]})["valid"]
    assert not skill.validate_export({"records": [record(revision=1)], "revision": 2})["valid"]


def test_pending_review_can_preserve_missing_fields_but_executable_cannot():
    assert skill.build_export({"records": [{"operation": "PENDING_REVIEW"}]})["valid"]
    assert not skill.build_export({"records": [{"operation": "CREATE"}]})["valid"]
    assert not skill.build_export({"records": [record(issues=[{"code": "TOTAL_MISMATCH"}])]})["valid"]
