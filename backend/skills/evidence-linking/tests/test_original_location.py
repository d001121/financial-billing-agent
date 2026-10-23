import importlib.util
from pathlib import Path

SPEC=importlib.util.spec_from_file_location("skill", Path(__file__).parents[1]/"scripts"/"skill.py")
skill=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(skill)

def test_pdf_original_location_matches_fields_when_visual_order_differs():
    report=Path(__file__).parents[3]/"tests"/"reports"/"original-location-real.json"
    if not report.is_file():
        return
    import json
    from backend.infrastructure.assets import asset_file
    task=json.loads(report.read_text(encoding="utf-8"))
    source=next(s for s in task["sources"] if s.get("format")=="pdf")
    evidence=next(e for e in task["records"][0]["evidence"] if e.get("field")=="amount")
    result=skill.build_preview(dict(source=source, records=task["records"], revision=task["revision"], original_path=str(asset_file(source)), target=dict(anchor=evidence["anchor"], quote=evidence["quote"], field="amount", value="245.0000", charge_id=task["records"][0]["charge_id"])))
    assert result["original"]["status"]=="located"
    assert result["original"]["locations"][0]["page"]==1
    assert result["original"]["locations"][0]["boxes"]
