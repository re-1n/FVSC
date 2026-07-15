from __future__ import annotations

import hashlib
import json

from fvsc.evaluation import (
    EvidenceRef,
    FrozenCandidate,
    FrozenCandidateBundle,
    FrozenCandidateSet,
    GoldCase,
    Stage4hArmResult,
    Stage4hAttributionReport,
    Stage4hCitationReview,
    Stage4hClaimReview,
    Stage4hGenerationTelemetry,
    Stage4hModelConfig,
    Stage4hOwnerReview,
    Stage4hRunResultBundle,
    Stage4hRunSpec,
    build_blinded_review_pack,
    corpus_digest,
    score_stage4h_attribution,
)
from fvsc.ingest import SourceDocument
from fvsc.interpretation import (
    InterpretationClaim,
    InterpretationProposal,
    SourceCitation,
)


_MODEL_DIGEST = "d" * 64


def _document(index: int) -> SourceDocument:
    text = f"Источник {index} описывает личный смысл и его изменение."
    return SourceDocument.create(
        source_id=f"message-{index}",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=float(index),
        text=text,
        adapter="test",
        source_kind="owner_reflection",
        raw_chars=len(text),
    )


def _case(index: int) -> GoldCase:
    return GoldCase(
        case_id=f"case-{index}",
        title=f"Case {index}",
        question=f"Как меняется смысл {index}?",
        decision="accepted",
        evidence=(EvidenceRef(f"Diary:{index}", f"message-{index}", "primary"),),
        owner_interpretation="Открытая owner-формулировка.",
    )


def _fixture(*, mode: str):
    count = 17 if mode == "confirmatory" else 2
    documents = tuple(_document(index) for index in range(1, count + 1))
    cases = tuple(_case(index) for index in range(1, count + 1))
    model = Stage4hModelConfig(
        backend_id="local.test",
        model="test:model",
        model_digest=_MODEL_DIGEST,
        prompt_version="stage4h-v1",
    )
    spec = Stage4hRunSpec(
        gold_sha256="a" * 64,
        challenge_sha256="b" * 64,
        corpus_sha256=corpus_digest(documents),
        case_ids=tuple(item.case_id for item in cases),
        arms=("A0", "A1", "A2", "A4"),
        model=model,
        created_at=1.0,
        top_k=1,
        prompt_source_cap=1,
        context_depth=0,
        evaluation_mode=mode,
    )
    candidate_sets = []
    results = []
    for case, document in zip(cases, documents, strict=True):
        citation = SourceCitation.from_document(document)
        claim = InterpretationClaim.create(
            text=f"Проверяемый claim для {case.case_id}.",
            citation_ids=(citation.citation_id,),
        )
        for arm in spec.arms:
            candidate_set = FrozenCandidateSet.create(
                run_id=spec.run_id,
                case_id=case.case_id,
                arm=arm,
                retrieval_method=("oracle" if arm == "A2" else f"method-{arm}"),
                candidates=(
                    FrozenCandidate(
                        rank=1,
                        source_id=document.source_id,
                        source_revision=document.source_revision,
                        role="oracle" if arm == "A2" else "ranked",
                    ),
                ),
            )
            candidate_sets.append(candidate_set)
            if arm == "A0":
                results.append(
                    Stage4hArmResult.create(
                        candidate_set=candidate_set,
                        status="extractive",
                        generated_at=2.0,
                        extractive_source_ids=(document.source_id,),
                    )
                )
                continue
            wall = {"A1": 1.0, "A2": 1.2, "A4": 1.5}[arm]
            proposal = InterpretationProposal.create(
                question=case.question,
                answer=f"Ответ {case.case_id}.",
                claims=(claim,),
                citations=(citation,),
                interpretation_layer=3,
                producer=model.backend_id,
                model=model.model,
                prompt_version=model.prompt_version,
                generated_at=3.0 + wall,
                retrieval_method=candidate_set.retrieval_method,
            )
            telemetry = Stage4hGenerationTelemetry(
                backend_id=model.backend_id,
                model=model.model,
                model_digest=model.model_digest,
                prompt_version=model.prompt_version,
                temperature=model.temperature,
                seed=model.seed,
                num_ctx=model.num_ctx,
                source_count=1,
                prompt_chars=100,
                wall_seconds=wall,
                prompt_eval_count=20,
                eval_count=8,
            )
            results.append(
                Stage4hArmResult.create(
                    candidate_set=candidate_set,
                    status="generated",
                    generated_at=3.0 + wall,
                    proposal=proposal,
                    telemetry=telemetry,
                )
            )
    candidate_bundle = FrozenCandidateBundle.create(
        spec=spec,
        candidate_sets=candidate_sets,
    )
    result_bundle = Stage4hRunResultBundle.create(
        spec=spec,
        candidate_bundle=candidate_bundle,
        results=results,
    )
    pack, blind_map = build_blinded_review_pack(
        result_bundle=result_bundle,
        documents=documents,
        blinding_key=b"review-key" * 4,
    )
    return spec, cases, documents, candidate_bundle, result_bundle, pack, blind_map


def _reviews(pack, blind_map, scores, *, unsafe_arm=None):
    values = []
    for item in pack.items:
        entry = blind_map.resolve(item.blind_item_id)
        claim_reviews = []
        citations = {citation.citation_id for citation in item.citations}
        for claim in item.claims:
            claim_reviews.append(
                Stage4hClaimReview(
                    claim_id=claim.claim_id,
                    verdict="accepted",
                    citations=tuple(
                        Stage4hCitationReview(
                            citation_id=citation_id,
                            verdict="supports",
                        )
                        for citation_id in claim.citation_ids
                        if citation_id in citations
                    ),
                )
            )
        values.append(
            Stage4hOwnerReview.create(
                blind_item_id=item.blind_item_id,
                proposal_id=item.proposal_id,
                claim_reviews=tuple(claim_reviews),
                meaning_fidelity=scores[entry.arm],
                usefulness=scores[entry.arm],
                false_owner_attribution=entry.arm == unsafe_arm,
            )
        )
    return tuple(values)


def test_pilot_diagnoses_retrieval_gap_but_cannot_promote() -> None:
    spec, cases, _, candidates, results, pack, blind_map = _fixture(mode="pilot")
    reviews = _reviews(pack, blind_map, {"A1": 2, "A2": 4, "A4": 3})

    report = score_stage4h_attribution(
        spec=spec,
        cases=cases,
        candidate_bundle=candidates,
        result_bundle=results,
        blind_map=blind_map,
        reviews=reviews,
    )

    assert report.diagnosis == "retrieval_or_context_selection_failure"
    assert report.promoted_arm is None
    assert report.evaluation_mode == "pilot"
    assert next(item for item in report.arm_summaries if item.arm == "A2").coverage_rate == 1.0
    assert Stage4hAttributionReport.from_dict(
        json.loads(json.dumps(report.to_dict()))
    ) == report


def test_confirmatory_run_can_promote_a4_only_after_all_registered_gates() -> None:
    spec, cases, _, candidates, results, pack, blind_map = _fixture(
        mode="confirmatory"
    )
    reviews = _reviews(pack, blind_map, {"A1": 3, "A2": 4, "A4": 4})

    report = score_stage4h_attribution(
        spec=spec,
        cases=cases,
        candidate_bundle=candidates,
        result_bundle=results,
        blind_map=blind_map,
        reviews=reviews,
    )

    assert report.diagnosis == "structural_retrieval_candidate"
    assert report.promoted_arm == "A4"
    pair = next(item for item in report.paired_summaries if item.right_arm == "A4")
    assert pair.meaning_fidelity_mean_delta == 1.0
    assert pair.meaning_fidelity_ci95_lower == 1.0
    assert pair.latency_multiplier == 1.5


def test_severe_a4_error_blocks_promotion_even_with_higher_fidelity() -> None:
    spec, cases, _, candidates, results, pack, blind_map = _fixture(
        mode="confirmatory"
    )
    reviews = _reviews(
        pack,
        blind_map,
        {"A1": 3, "A2": 4, "A4": 4},
        unsafe_arm="A4",
    )

    report = score_stage4h_attribution(
        spec=spec,
        cases=cases,
        candidate_bundle=candidates,
        result_bundle=results,
        blind_map=blind_map,
        reviews=reviews,
    )

    structural = next(item for item in report.arm_summaries if item.arm == "A4")
    assert structural.false_owner_attribution_count == len(cases)
    assert structural.severe_error_count >= len(cases)
    assert report.promoted_arm is None
