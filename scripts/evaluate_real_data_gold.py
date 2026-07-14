#!/usr/bin/env python3
"""Compare lexical and judgment retrieval on a private source-cited gold set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Sequence

from fvsc.evaluation import RankedSources, RetrievalEvaluation, evaluate_rankings, load_gold_set
from fvsc.evidence import EvidenceLedger, EvidencePolicy
from fvsc.ingest import (
    JUDGMENT_EVENT_EXTRACTOR,
    RussianJudgmentExtractor,
    load_telegram_export,
)
from fvsc.ingest.document_ingest import build_evidence_batch
from fvsc.retrieval import (
    reciprocal_rank_fusion,
    search_documents,
    search_judgment_evidence,
)


def _metric(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _evaluation_dict(report: RetrievalEvaluation) -> dict:
    return {
        "abstention_accuracy": _metric(report.abstention_accuracy),
        "context_recall_at_k": _metric(report.mean_context_recall_at_k),
        "evaluated_abstention_cases": report.evaluated_abstention_cases,
        "evaluated_answer_cases": report.evaluated_answer_cases,
        "mean_recall_at_k": _metric(report.mean_recall_at_k),
        "mrr_at_k": _metric(report.mean_reciprocal_rank),
        "negative_hits_at_k": report.negative_hits_at_k,
        "per_case": [
            {
                "abstention_correct": item.abstention_correct,
                "case_id": item.case_id,
                "context_recall_at_k": _metric(item.context_recall_at_k),
                "negative_hits_at_k": item.negative_hits_at_k,
                "recall_at_k": _metric(item.recall_at_k),
                "reciprocal_rank": _metric(item.reciprocal_rank),
            }
            for item in report.cases
        ],
        "top_k": report.top_k,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate FVSC source retrieval without persisting private text.",
    )
    parser.add_argument("--telegram", type=Path, required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument(
        "--owner-id",
        action="append",
        required=True,
        help="Raw Telegram owner actor id; repeat for multiple owner identities",
    )
    parser.add_argument("--namespace", default="private-diary")
    parser.add_argument("--timezone", default="Europe/Moscow")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.top_k <= 0 or args.candidate_k < args.top_k:
        raise SystemExit("candidate-k must be >= positive top-k")

    started = time.perf_counter()
    gold = load_gold_set(args.gold)
    export = load_telegram_export(
        args.telegram,
        owner_author_ids=args.owner_id,
        source_namespace=args.namespace,
        display_timezone=args.timezone,
    )
    extractor = RussianJudgmentExtractor()
    batch = build_evidence_batch(
        export.documents,
        judgment_extractor=extractor,
        include_cooccurrence=False,
    )
    ledger = EvidenceLedger(batch.events)
    ingest_seconds = time.perf_counter() - started
    policy = EvidencePolicy(
        source_kinds=frozenset({"owner_reflection"}),
        extractors=frozenset({JUDGMENT_EVENT_EXTRACTOR}),
        derivations=frozenset({"linguistic-judgment"}),
        max_interpretation_layer=1,
    )

    lexical_rankings: list[RankedSources] = []
    judgment_rankings: list[RankedSources] = []
    equal_fusion: list[RankedSources] = []
    lexical_fusion: list[RankedSources] = []
    search_started = time.perf_counter()
    for case in gold.cases:
        lexical_ids = tuple(
            hit.source_id
            for hit in search_documents(
                export.documents,
                case.question,
                top_k=args.candidate_k,
                owner_adopted_only=True,
            )
        )
        judgment_ids = tuple(
            hit.source_id
            for hit in search_judgment_evidence(
                ledger,
                case.question,
                morphology=extractor.morphology,
                policy=policy,
                top_k=args.candidate_k,
            )
        )
        lexical_rankings.append(RankedSources(case_id=case.case_id, source_ids=lexical_ids))
        judgment_rankings.append(RankedSources(case_id=case.case_id, source_ids=judgment_ids))
        equal_fusion.append(
            RankedSources(
                case_id=case.case_id,
                source_ids=tuple(
                    hit.source_id
                    for hit in reciprocal_rank_fusion(
                        {"judgment": judgment_ids, "lexical": lexical_ids},
                        rank_constant=60,
                        top_k=args.candidate_k,
                    )
                ),
            )
        )
        lexical_fusion.append(
            RankedSources(
                case_id=case.case_id,
                source_ids=tuple(
                    hit.source_id
                    for hit in reciprocal_rank_fusion(
                        {"judgment": judgment_ids, "lexical": lexical_ids},
                        weights={"judgment": 1.0, "lexical": 5.0},
                        rank_constant=60,
                        top_k=args.candidate_k,
                    )
                ),
            )
        )
    search_seconds = time.perf_counter() - search_started

    reports = {
        "judgment": evaluate_rankings(gold, judgment_rankings, top_k=args.top_k),
        "lexical": evaluate_rankings(gold, lexical_rankings, top_k=args.top_k),
        "rrf_equal": evaluate_rankings(gold, equal_fusion, top_k=args.top_k),
        "rrf_lexical_5": evaluate_rankings(gold, lexical_fusion, top_k=args.top_k),
    }
    lexical = reports["lexical"]
    promoted = [
        name
        for name, report in reports.items()
        if name != "lexical"
        and (report.mean_reciprocal_rank or 0.0) > (lexical.mean_reciprocal_rank or 0.0)
        and (report.mean_recall_at_k or 0.0) >= (lexical.mean_recall_at_k or 0.0)
        and report.negative_hits_at_k <= lexical.negative_hits_at_k
    ]
    output = {
        "schema_version": 1,
        "corpus": {
            "documents": len(export.documents),
            "exact_events": sum(
                event.extractor == JUDGMENT_EVENT_EXTRACTOR for event in batch.events
            ),
            "gold_cases": len(gold.cases),
            "owner_documents": sum(
                document.source_kind == "owner_reflection" for document in export.documents
            ),
        },
        "arms": {name: _evaluation_dict(report) for name, report in sorted(reports.items())},
        "decision": {
            "promoted_arms": promoted,
            "retrieval_default": "lexical" if not promoted else promoted[0],
            "semantic_superiority_demonstrated": bool(promoted),
        },
        "timing_seconds": {
            "ingest": round(ingest_seconds, 6),
            "search_all_arms": round(search_seconds, 6),
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
