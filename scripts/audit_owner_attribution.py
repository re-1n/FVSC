"""Evaluate frozen F1 cases and explicit-scope S6 regression without generation."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess

from fvsc.ingest.owner_attribution import direct_owner_eligibility, reported_expressions
from fvsc.ingest.source_provenance import ExpressionSpan, SourceAttribution
from fvsc.evaluation.planned_slot_synthesis import FrozenQuestionPlan, PlannedRequirement
from fvsc.evaluation.relation_support_guard import PUBLIC_RELATION_SUPPORT_GUARD
from fvsc.evaluation.reported_attribution_fixtures import cases


def envelope(row: dict) -> SourceAttribution | None:
    if row.get("missing"):
        return None
    spans = []
    for span in row.get("spans", []):
        start = row["text"].index(span["text"])
        spans.append(ExpressionSpan.from_text(
            row["text"], start=start, end=start + len(span["text"]),
            kind=span["kind"], origin_status=span["origin"],
            owner_relation=span["relation"],
            owner_endorsement=span.get("stance", "unresolved"),
        ))
    return SourceAttribution(
        transport_author_role=row["role"], text_origin_status=row["origin"],
        owner_adopted_expression=row.get("adopted", False),
        forwarded=row.get("forwarded", False), expression_spans=tuple(spans),
    )


def counts(rows: list[dict]) -> dict:
    return {
        "total": len(rows), "passed": sum(r["passed"] for r in rows),
        "false_positives": sum(r["actual"] and not r["expected"] for r in rows),
        "false_negatives": sum(r["expected"] and not r["actual"] for r in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    fixture_path = root / "docs/evaluation/owner_attribution_v1_cases.json"
    inputs = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert len(inputs) == len({r["id"] for r in inputs}) == 22
    rows = []
    for row in inputs:
        attribution = envelope(row)
        decision = direct_owner_eligibility(row["text"], attribution)
        reports = reported_expressions("S1", row["text"], attribution)
        for report in reports:
            report.verify(source_label="S1", text=row["text"])
        preserved = (
            len(reports) == row.get("reports", 0)
            and sum(r.owner_endorsement == "endorsed" for r in reports) == row.get("endorsed", 0)
            and all(r.speaker is None for r in reports)
        )
        rows.append({
            **row, "actual": decision.eligible, "decision": asdict(decision),
            "reported_expressions": [asdict(r) for r in reports],
            "passed": decision.eligible == row["expected"] and preserved,
            "annotations_preserved": preserved,
        })
    regression = []
    for case in cases():
        description = f"What did the owner directly state was {case.relation}?"
        plan = FrozenQuestionPlan(case.case_id, (
            PlannedRequirement("R1", description, attribution_scope="direct_owner"),
        ))
        candidate = PUBLIC_RELATION_SUPPORT_GUARD.compile(plan, (case.source,))[0]
        original = PUBLIC_RELATION_SUPPORT_GUARD.compile(FrozenQuestionPlan(case.case_id, (
            PlannedRequirement("R1", description),
        )), (case.source,))[0]
        actual = "S1" in candidate.eligible_source_labels
        regression.append({
            "id": case.case_id, "family": case.family,
            "expected": case.expected_direct_owner_eligibility,
            "actual": actual, "source_scope_actual": "S1" in original.eligible_source_labels,
            "passed": actual == case.expected_direct_owner_eligibility,
            "decisions": [asdict(d) for d in candidate.source_decisions],
        })
    contract = [r for r in rows if not r.get("challenge")]
    challenges = [r for r in rows if r.get("challenge")]
    paths = (
        "docs/evaluation/OWNER_ATTRIBUTION_GATE_V1.md",
        "docs/evaluation/owner_attribution_v1_cases.json",
        "src/fvsc/ingest/owner_attribution.py",
        "src/fvsc/ingest/source_provenance.py",
        "src/fvsc/evaluation/planned_slot_synthesis.py",
        "src/fvsc/evaluation/relation_support_guard.py",
        "src/fvsc/evaluation/planned_slot_runner.py",
        "src/fvsc/evaluation/reported_attribution_fixtures.py",
        "scripts/audit_owner_attribution.py",
    )
    artifact = {
        "audit": "explicit-owner-attribution-v1", "protocol_commit": "2f28378",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "sha256_lf": {p: hashlib.sha256((root / p).read_text(encoding="utf-8").encode("utf-8")).hexdigest() for p in paths},
        "contract": counts(contract), "coverage_challenges": counts(challenges),
        "previous_set_explicit_scope": counts(regression),
        "cases": rows, "regression_cases": regression,
        "scope": "explicit annotation-consuming F1 and six-English-relation S6; no LLM or attribution extractor",
    }
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(artifact, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({k: artifact[k] for k in (
        "contract", "coverage_challenges", "previous_set_explicit_scope",
    )}, indent=2))
    return 0 if all(r["passed"] for r in contract) else 1


if __name__ == "__main__":
    raise SystemExit(main())
