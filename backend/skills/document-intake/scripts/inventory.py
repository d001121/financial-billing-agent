"""Build structural sample inventory without inventing financial ground truth."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

_spec = importlib.util.spec_from_file_location("document_intake_inventory", Path(__file__).with_name("skill.py"))
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
intake_document = _module.intake_document


def build_inventory(input_dir: Path, output_dir: Path) -> dict:
    entries = []
    for path in sorted(input_dir.iterdir()):
        if not path.is_file():
            continue
        result = intake_document(path, output_dir=output_dir / path.stem)
        entries.append({
            "input_file": path.name,
            "status": result["status"],
            "sources": [{
                "name": source["name"],
                "source_id": source["source_id"],
                "content_id": source["content_id"],
                "parent_source_id": source["parent_source_id"],
                "occurrence_id": source["occurrence_id"],
                "size_bytes": source["size_bytes"],
                "format": source["format"],
                "status": source["status"],
                "page_count": source["metadata"].get("page_count"),
                "frame_count": source["metadata"].get("frame_count"),
                "image_dimensions": {key: source["metadata"][key] for key in ["width", "height"] if key in source["metadata"]},
            } for source in result["sources"]],
            "issue_codes": sorted({issue["code"] for issue in result["issues"]}),
            "financial_ground_truth": None,
        })
    return {"schema_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(), "dataset_role": "development_inventory", "data_directory": "笔试题AIAGENT/数据", "label_policy": "Structural facts verified locally; no model-generated financial ground truth. This data is development material, not an independent final holdout.", "entries": entries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    result = build_inventory(args.input_dir, args.output_dir)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
