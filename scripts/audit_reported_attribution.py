"""Run the frozen public diagnostic against registered S6, without generation."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import subprocess

from fvsc.evaluation.planned_slot_synthesis import FrozenQuestionPlan, PlannedRequirement
from fvsc.evaluation.relation_support_guard import PUBLIC_RELATION_SUPPORT_GUARD
from fvsc.evaluation.reported_attribution_fixtures import cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixtures = cases()
    assert len(fixtures) == 48
    assert len({item.case_id for item in fixtures}) == 48
    assert set(Counter(item.family for item in fixtures).values()) == {6}
    rows = []
    for item in fixtures:
        item.source.attribution.verify(item.source.text)
        plan = FrozenQuestionPlan(item.case_id, (
            PlannedRequirement("R1", f"What did the owner directly state was {item.relation}?"),
        ))
        prediction = PUBLIC_RELATION_SUPPORT_GUARD.compile(plan, (item.source,))
        actual = "S1" in prediction[0].eligible_source_labels
        expected = item.expected_direct_owner_eligibility
        rows.append({
            **asdict(item), "actual_direct_owner_eligibility": actual,
            "passed": actual == expected,
            "false_positive": actual and not expected,
            "false_negative": expected and not actual,
        })
    root = Path(__file__).resolve().parents[1]
    fingerprints = {}
    for path in (
        "src/fvsc/evaluation/reported_attribution_fixtures.py",
        "src/fvsc/evaluation/relation_support_guard.py",
        "src/fvsc/ingest/source_provenance.py",
        "scripts/audit_reported_attribution.py",
        "docs/evaluation/REPORTED_ATTRIBUTION_AUDIT.md",
    ):
        # Normalize checkout line endings so Windows and Linux hashes agree.
        content = (root / path).read_text(encoding="utf-8").encode("utf-8")
        fingerprints[path] = hashlib.sha256(content).hexdigest()
    families = {}
    for family in sorted({item.family for item in fixtures}):
        subset = [row for row in rows if row["family"] == family]
        families[family] = {
            "total": len(subset),
            **{key: sum(row[key] for row in subset) for key in (
                "passed", "false_positive", "false_negative",
            )},
        }
    artifact = {
        "audit": "public-reported-attribution-v1",
        "evaluation_scope": "S6 candidate eligibility for direct owner assertions; no LLM",
        "promotion_eligible": False,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True,
        ).strip(),
        "python": platform.python_version(),
        "sha256_lf": fingerprints,
        "passed": all(row["passed"] for row in rows),
        "passed_cases": sum(row["passed"] for row in rows),
        "total_cases": len(rows),
        "false_positives": sum(row["false_positive"] for row in rows),
        "false_negatives": sum(row["false_negative"] for row in rows),
        "families": families, "cases": rows,
    }
    # Never replace a previous result.
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(artifact, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(json.dumps({key: artifact[key] for key in (
        "passed_cases", "total_cases", "false_positives", "false_negatives", "families",
    )}, indent=2))
    return 0 if artifact["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
