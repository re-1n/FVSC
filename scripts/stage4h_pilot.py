#!/usr/bin/env python3
"""Run and score the source-local Stage 4h controlled attribution pilot."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Iterable, Sequence

from fvsc.evaluation import (
    FrozenCandidateBundle,
    GoldCase,
    Stage4hBlindMap,
    Stage4hCitationReview,
    Stage4hClaimReview,
    Stage4hModelConfig,
    Stage4hOwnerReview,
    Stage4hRunResultBundle,
    Stage4hRunSpec,
    build_blinded_review_pack,
    candidate_bundle_json,
    corpus_digest,
    file_sha256,
    freeze_stage4h_candidates,
    load_gold_set,
    new_blinding_key,
    review_pack_json,
    review_pack_markdown,
    run_local_stage4h,
    score_stage4h_attribution,
)
from fvsc.evaluation.stage4h.contracts import load_run_spec
from fvsc.evidence import EvidenceLedger, EvidencePolicy
from fvsc.ingest import (
    JUDGMENT_EVENT_EXTRACTOR,
    RussianJudgmentExtractor,
    load_telegram_export,
)
from fvsc.ingest.document_ingest import build_evidence_batch
from fvsc.integrations import (
    DEFAULT_OLLAMA_HOST,
    OllamaInterpretationBackend,
)
from fvsc.retrieval import JudgmentSearchIndex, LexicalSearchIndex


PILOT_CASE_IDS = (
    "gold-001",
    "gold-008",
    "gold-010",
    "gold-013",
    "stage4h-challenge-001",
    "stage4h-challenge-002",
)
MAX_LOCAL_ARTIFACT_BYTES = 64 * 1024 * 1024


def _load_json(path: Path) -> dict[str, Any]:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"refusing non-regular Stage 4h artifact: {source}")
    if source.stat().st_size > MAX_LOCAL_ARTIFACT_BYTES:
        raise ValueError(f"Stage 4h artifact exceeds the size limit: {source.name}")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid UTF-8 JSON artifact: {source.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Stage 4h artifact must contain an object: {source.name}")
    return value


def _json_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"


def _atomic_private_write(path: Path, text: str) -> None:
    destination = Path(path)
    if destination.exists():
        if destination.is_symlink() or not destination.is_file():
            raise ValueError(f"refusing unsafe Stage 4h output: {destination}")
        if destination.read_text(encoding="utf-8") == text:
            return
        raise FileExistsError(f"refusing to replace Stage 4h artifact: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.parent.is_symlink():
        raise ValueError(f"refusing symlinked Stage 4h output directory: {destination.parent}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _selected_cases(gold_path: Path, challenge_path: Path) -> tuple[GoldCase, ...]:
    available = {
        case.case_id: case
        for source in (load_gold_set(gold_path), load_gold_set(challenge_path))
        for case in source.cases
    }
    missing = tuple(case_id for case_id in PILOT_CASE_IDS if case_id not in available)
    if missing:
        raise ValueError(f"Stage 4h pilot cases are missing: {missing}")
    return tuple(available[case_id] for case_id in PILOT_CASE_IDS)


def _review_template(pack) -> dict[str, Any]:
    return {
        "instructions": {
            "citation_verdicts": ["supports", "partial", "unsupported"],
            "claim_verdicts": [
                "accepted",
                "partially_accepted",
                "rejected",
                "needs_revision",
            ],
            "meaning_fidelity": "integer 0..4",
            "usefulness": "integer 0..4",
        },
        "pack_id": pack.pack_id,
        "reviews": [
            {
                "abstention_preferable": None,
                "blind_item_id": item.blind_item_id,
                "claim_reviews": [
                    {
                        "citations": [
                            {"citation_id": citation_id, "verdict": None}
                            for citation_id in claim.citation_ids
                        ],
                        "claim_id": claim.claim_id,
                        "verdict": None,
                    }
                    for claim in item.claims
                ],
                "false_owner_attribution": None,
                "forbidden_composite": None,
                "meaning_fidelity": None,
                "missed_context": None,
                "proposal_id": item.proposal_id,
                "unsupported_referent_assumption": None,
                "usefulness": None,
            }
            for item in pack.items
        ],
        "schema_version": 1,
    }


def _load_reviews(path: Path, *, expected_pack_id: str) -> tuple[Stage4hOwnerReview, ...]:
    value = _load_json(path)
    if value.get("pack_id") != expected_pack_id:
        raise ValueError("owner review file does not match the blinded pack")
    raw_reviews = value.get("reviews", [])
    if not isinstance(raw_reviews, list):
        raise ValueError("owner reviews must be an array")
    reviews: list[Stage4hOwnerReview] = []
    for item in raw_reviews:
        if not isinstance(item, dict):
            raise ValueError("each owner review must be an object")
        raw_claims = item.get("claim_reviews", [])
        if not isinstance(raw_claims, list):
            raise ValueError("owner claim_reviews must be an array")
        claim_reviews: list[Stage4hClaimReview] = []
        for raw_claim in raw_claims:
            if not isinstance(raw_claim, dict):
                raise ValueError("each owner claim review must be an object")
            raw_citations = raw_claim.get("citations", [])
            if not isinstance(raw_citations, list):
                raise ValueError("owner citation reviews must be an array")
            claim_reviews.append(
                Stage4hClaimReview(
                    claim_id=raw_claim.get("claim_id", ""),
                    verdict=raw_claim.get("verdict"),
                    citations=tuple(
                        Stage4hCitationReview.from_dict(citation)
                        for citation in raw_citations
                    ),
                )
            )
        reviews.append(
            Stage4hOwnerReview.create(
                blind_item_id=item.get("blind_item_id", ""),
                proposal_id=item.get("proposal_id", ""),
                claim_reviews=tuple(claim_reviews),
                meaning_fidelity=item.get("meaning_fidelity"),
                usefulness=item.get("usefulness"),
                false_owner_attribution=item.get("false_owner_attribution"),
                unsupported_referent_assumption=item.get(
                    "unsupported_referent_assumption"
                ),
                forbidden_composite=item.get("forbidden_composite"),
                missed_context=item.get("missed_context"),
                abstention_preferable=item.get("abstention_preferable"),
            )
        )
    return tuple(reviews)


def _build_indexes(documents, *, extractor: RussianJudgmentExtractor):
    batch = build_evidence_batch(
        documents,
        judgment_extractor=extractor,
        include_cooccurrence=False,
    )
    ledger = EvidenceLedger(batch.events)
    policy = EvidencePolicy(
        source_kinds=frozenset({"owner_reflection"}),
        extractors=frozenset({JUDGMENT_EVENT_EXTRACTOR}),
        derivations=frozenset({"linguistic-judgment"}),
        max_interpretation_layer=1,
    )
    return (
        LexicalSearchIndex(documents, owner_adopted_only=True),
        JudgmentSearchIndex(
            ledger,
            morphology=extractor.morphology,
            policy=policy,
        ),
    )


def _run(args: argparse.Namespace) -> int:
    cases = _selected_cases(args.gold, args.challenge)
    export = load_telegram_export(
        args.telegram,
        owner_author_ids=args.owner_id,
        source_namespace=args.namespace,
        display_timezone=args.timezone,
    )
    documents = export.documents
    extractor = RussianJudgmentExtractor()
    lexical_index, structural_index = _build_indexes(documents, extractor=extractor)

    probe = OllamaInterpretationBackend(
        model=args.model,
        host=args.ollama_host,
        temperature=0.0,
        seed=args.seed,
        num_ctx=args.num_ctx,
    )
    identity = probe.model_identity()
    if identity is None:
        raise RuntimeError(
            "configured Ollama model was not found with a stable local digest; "
            "run `ollama list` and pass the exact installed tag"
        )
    model = Stage4hModelConfig(
        backend_id=probe.backend_id,
        model=args.model,
        model_digest=identity.digest,
        prompt_version=probe.prompt_version,
        temperature=0.0,
        seed=args.seed,
        num_ctx=args.num_ctx,
    )
    spec = Stage4hRunSpec(
        gold_sha256=file_sha256(args.gold),
        challenge_sha256=file_sha256(args.challenge),
        corpus_sha256=corpus_digest(documents),
        case_ids=PILOT_CASE_IDS,
        arms=("A0", "A1", "A2", "A4"),
        model=model,
        created_at=time.time(),
        top_k=10,
        prompt_source_cap=12,
        context_depth=1,
        evaluation_mode="pilot",
    )
    candidate_bundle = freeze_stage4h_candidates(
        spec=spec,
        cases=cases,
        documents=documents,
        lexical_index=lexical_index,
        structural_index=structural_index,
    )
    backend = OllamaInterpretationBackend(
        model=args.model,
        model_digest=identity.digest,
        host=args.ollama_host,
        temperature=0.0,
        seed=args.seed,
        num_ctx=args.num_ctx,
    )
    results = run_local_stage4h(
        spec=spec,
        candidate_bundle=candidate_bundle,
        cases=cases,
        documents=documents,
        backend=backend,
    )
    pack, blind_map = build_blinded_review_pack(
        result_bundle=results,
        documents=documents,
        blinding_key=new_blinding_key(),
    )

    run_dir = args.output_root / spec.run_id
    if run_dir.exists():
        raise FileExistsError(f"Stage 4h run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True, mode=0o700)
    _atomic_private_write(run_dir / "manifest.json", _json_text(spec.to_dict()))
    _atomic_private_write(
        run_dir / "candidates.json",
        candidate_bundle_json(candidate_bundle),
    )
    _atomic_private_write(run_dir / "results.json", _json_text(results.to_dict()))
    _atomic_private_write(run_dir / "blind-map.json", _json_text(blind_map.to_dict()))
    _atomic_private_write(run_dir / "review-pack.json", review_pack_json(pack))
    _atomic_private_write(run_dir / "review-pack.md", review_pack_markdown(pack))
    _atomic_private_write(
        run_dir / "reviews.template.json",
        _json_text(_review_template(pack)),
    )
    summary = {
        "generated_review_items": len(pack.items),
        "model": identity.to_dict(),
        "next": (
            "Copy reviews.template.json to reviews.json, fill every null field while "
            "reading review-pack.md, then run the score subcommand."
        ),
        "run_dir": str(run_dir),
        "run_id": spec.run_id,
    }
    print(_json_text(summary), end="")
    return 0


def _score(args: argparse.Namespace) -> int:
    run_dir = args.run_dir
    spec = load_run_spec(run_dir / "manifest.json")
    if file_sha256(args.gold) != spec.gold_sha256:
        raise ValueError("Gold file digest does not match the Stage 4h manifest")
    if file_sha256(args.challenge) != spec.challenge_sha256:
        raise ValueError("challenge file digest does not match the Stage 4h manifest")
    cases = _selected_cases(args.gold, args.challenge)
    candidate_bundle = FrozenCandidateBundle.from_dict(
        _load_json(run_dir / "candidates.json")
    )
    result_bundle = Stage4hRunResultBundle.from_dict(
        _load_json(run_dir / "results.json")
    )
    blind_map = Stage4hBlindMap.from_dict(_load_json(run_dir / "blind-map.json"))
    pack_value = _load_json(run_dir / "review-pack.json")
    pack_id = pack_value.get("pack_id")
    if not isinstance(pack_id, str):
        raise ValueError("review pack is missing pack_id")
    if blind_map.pack_id != pack_id:
        raise ValueError("blind map does not match the review pack")
    reviews = _load_reviews(args.reviews, expected_pack_id=pack_id)
    report = score_stage4h_attribution(
        spec=spec,
        cases=cases,
        candidate_bundle=candidate_bundle,
        result_bundle=result_bundle,
        blind_map=blind_map,
        reviews=reviews,
    )
    destination = run_dir / "report.json"
    _atomic_private_write(destination, _json_text(report.to_dict()))
    print(
        _json_text(
            {
                "diagnosis": report.diagnosis,
                "promoted_arm": report.promoted_arm,
                "report": str(destination),
                "report_id": report.report_id,
            }
        ),
        end="",
    )
    return 0


def _models(args: argparse.Namespace) -> int:
    backend = OllamaInterpretationBackend(host=args.ollama_host)
    # Keep this command useful for older daemons whose tags omit digest details.
    print(_json_text({"models": list(backend.list_local_models())}), end="")
    return 0


def _parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Run or score the local Stage 4h attribution pilot.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    models = subparsers.add_parser("models", help="list local Ollama model tags")
    models.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    models.set_defaults(handler=_models)

    run = subparsers.add_parser("run", help="freeze and run the six-case local pilot")
    run.add_argument("--telegram", type=Path, required=True)
    run.add_argument("--owner-id", action="append", required=True)
    run.add_argument("--model", required=True)
    run.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--num-ctx", type=int, default=8_192)
    run.add_argument("--namespace", default="private-diary")
    run.add_argument("--timezone", default="Europe/Moscow")
    run.add_argument(
        "--gold",
        type=Path,
        default=root / "private_eval" / "fvsc_gold_001_015.json",
    )
    run.add_argument(
        "--challenge",
        type=Path,
        default=root / "private_eval" / "fvsc_stage4h_challenge_001_002.json",
    )
    run.add_argument(
        "--output-root",
        type=Path,
        default=root / ".fvsc" / "stage4h",
    )
    run.set_defaults(handler=_run)

    score = subparsers.add_parser("score", help="score a fully reviewed blind pack")
    score.add_argument("--run-dir", type=Path, required=True)
    score.add_argument("--reviews", type=Path, required=True)
    score.add_argument(
        "--gold",
        type=Path,
        default=root / "private_eval" / "fvsc_gold_001_015.json",
    )
    score.add_argument(
        "--challenge",
        type=Path,
        default=root / "private_eval" / "fvsc_stage4h_challenge_001_002.json",
    )
    score.set_defaults(handler=_score)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
