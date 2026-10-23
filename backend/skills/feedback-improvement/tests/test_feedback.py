import importlib.util
from pathlib import Path
import subprocess
import sys

import simplejson

SPEC = importlib.util.spec_from_file_location("feedback_improvement_skill", Path(__file__).parents[1] / "scripts" / "skill.py")
skill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(skill)


def candidate():
    return skill.prepare_candidate({"opt_in": True, "kind": "charge_mapping", "source": {"task_id": "t1", "revision": 3},
                                    "scope": {"accounting_entity": "Carrier"}, "proposed_by": "reviewer", "before": {},
                                    "after": {"H/D Fee": "Handling Charge"}, "base_version": "v1"})["candidate"]


def comparison(proposal, **extra):
    metrics = {m["key"]: True for m in skill.financial_evaluator({"records": []}, {"records": []})}
    cases = [{"case_id": "reg1", "family_id": "regdoc1", "dataset_role": "regression", "baseline": metrics, "candidate": metrics},
             {"case_id": "final1", "family_id": "finaldoc1", "dataset_role": "final", "baseline": metrics, "candidate": metrics}]
    return skill.compare_candidate({"candidate_id": proposal["candidate_id"], "content_digest": proposal["content_digest"],
                                    "evaluations": cases, **extra})


def test_opt_in_candidate_and_no_silent_release():
    assert not skill.prepare_candidate({"opt_in": False})["valid"]
    proposal = candidate()
    assert proposal["status"] == "candidate"
    result = skill.publish_candidate({"candidate": proposal, "comparison": comparison(proposal)["comparison"],
                                      "registry": {"active_version": "v1", "versions": []}, "expected_active_version": "v1"})
    assert not result["valid"] and result["registry"]["active_version"] == "v1"


def test_critical_regression_leakage_or_missing_metrics_blocks_publication():
    proposal = candidate()
    metrics = {m["key"]: True for m in skill.financial_evaluator({"records": []}, {"records": []})}
    bad = {**metrics, "charge_details_amount": False}
    cases = [{"case_id": "reg1", "family_id": "same", "dataset_role": "regression", "baseline": metrics, "candidate": bad},
             {"case_id": "final1", "family_id": "same", "dataset_role": "final", "baseline": metrics, "candidate": {}}]
    result = comparison(proposal, evaluations=cases)
    assert not result["valid"]
    assert {"CRITICAL_REGRESSION", "EVALUATION_LEAKAGE", "CRITICAL_METRICS_MISSING"} <= {i["code"] for i in result["issues"]}
    assert not comparison(proposal, final_used_for_selection=True)["valid"]


def test_reviewed_published_content_is_fixed_and_can_roll_back():
    proposal = candidate()
    measured = {**comparison(proposal)["comparison"], "engine": "langsmith-local", "baseline_version": "v1",
                "dataset_digest": "test-measured-dataset", "final_evaluated": True}
    args = {"candidate": proposal, "comparison": measured,
            "review": {"approved": True, "reviewer": "r", "reason": "verified", "candidate_id": proposal["candidate_id"]},
            "registry": {"active_version": "v1", "versions": [{"version": "v1"}],
                         "final_uses": {"test-measured-dataset": proposal["content_digest"]}}, "expected_active_version": "v1"}
    published = skill.publish_candidate(args)
    assert published["valid"]
    changed = {**proposal, "after": {"THC": "WRONG"}}
    assert not skill.publish_candidate({**args, "candidate": changed})["valid"]
    rolled = skill.rollback_candidate({"registry": published["registry"], "target_version": "v1",
                                       "expected_active_version": published["published_version"],
                                       "review": {"approved": True, "reviewer": "r", "reason": "restore"}})
    assert rolled["valid"] and rolled["registry"]["active_version"] == "v1"
    proposal["after"]["H/D Fee"] = "changed by caller"
    assert published["registry"]["versions"][-1]["candidate"]["after"]["H/D Fee"] == "Handling Charge"


def test_amount_or_direction_error_cannot_hide_behind_average_score():
    expected = {"records": [{"operation": "CREATE", "charge_details": {"amount": 10, "currency": "USD"},
                            "financial_attributes": {"accounting_entity": "A", "posting_type": "AR"}}]}
    actual = {"records": [{"operation": "CREATE", "charge_details": {"amount": 100, "currency": "USD"},
                          "financial_attributes": {"accounting_entity": "A", "posting_type": "AP"}, "evidence": ["real"]}]}
    metrics = {m["key"]: m["score"] for m in skill.financial_evaluator(actual, expected)}
    assert metrics["charge_details_amount"] is False and metrics["financial_attributes_posting_type"] is False


def test_only_entity_scope_has_a_supported_mapping_execution_context():
    args = {**candidate(), "opt_in": True, "scope": {"issuer": "Carrier"}}
    assert "MAPPING_SCOPE" in {i["code"] for i in skill.prepare_candidate(args)["issues"]}


def test_entity_mapping_chain_uses_complete_snapshots_and_rollback():
    registry = skill.initial_registry()
    registry["versions"] += [
        {"version": "a1", "previous_version": "builtin-v1", "candidate": {
            "kind": "charge_mapping", "scope": {"accounting_entity": "A"}, "after": {"X": "X fee", "Y": "Y fee"}}},
        {"version": "b1", "previous_version": "a1", "candidate": {
            "kind": "charge_mapping", "scope": {"accounting_entity": "B"}, "after": {"B": "B fee"}}},
        {"version": "a2", "previous_version": "b1", "candidate": {
            "kind": "charge_mapping", "scope": {"accounting_entity": " A "}, "after": {"Y": "New Y fee"}}}]
    registry["active_version"] = "a2"
    assert skill.resolve_mapping(registry, {"accounting_entity": "a"}) == {"Y": "New Y fee"}
    assert skill.resolve_mapping(registry, {"accounting_entity": "B"}) == {"B": "B fee"}
    assert skill.resolve_mapping(registry, {"accounting_entity": "C"}) == {}
    registry["active_version"] = "b1"
    assert skill.resolve_mapping(registry, {"accounting_entity": "A"}) == {"X": "X fee", "Y": "Y fee"}


def test_unimplemented_candidate_kinds_remain_drafts():
    proposal = {**candidate(), "kind": "prompt"}
    result = skill.publish_candidate({"candidate": proposal})
    assert "KIND_DRAFT_ONLY" in {i["code"] for i in result["issues"]}


def test_portable_candidate_cli_files_and_rejection_exit_status(tmp_path):
    script = Path(__file__).parents[1] / "scripts" / "skill.py"
    source, destination = tmp_path / "输入.json", tmp_path / "输出.json"
    payload = {**candidate(), "opt_in": True}
    source.write_text(simplejson.dumps(payload, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run([sys.executable, str(script), "--input", str(source), "--output", str(destination)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert simplejson.loads(destination.read_text(encoding="utf-8"))["candidate"]["scope"] == payload["scope"]
    rejected = subprocess.run([sys.executable, str(script)], input='{"opt_in":false}', capture_output=True, text=True)
    assert rejected.returncode == 1
    assert simplejson.loads(rejected.stdout)["valid"] is False
