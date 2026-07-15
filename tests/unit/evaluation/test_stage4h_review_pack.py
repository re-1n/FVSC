from __future__ import annotations

import hashlib
import json

import pytest

from fvsc.evaluation import (
    EvidenceRef,
    FrozenCandidate,
    FrozenCandidateBundle,
    FrozenCandidateSet,
    GoldCase,
    Stage4hBlindMap,
    Stage4hGenerationTelemetry,
    Stage4hModelConfig,
    Stage4hReviewPack,
    Stage4hRunResultBundle,
    Stage4hRunSpec,
    Stage4hArmResult,
    build_blinded_review_pack,
    corpus_digest,
    review_pack_markdown,
)
from fvsc.ingest import SourceDocument
from fvsc.interpretation import (
    InterpretationClaim,
    InterpretationProposal,
    SourceCitation,
)


def _document(text="Паразиты захватывают внимание.") -> SourceDocument:
    return SourceDocument.create(
        source_id="message-1",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=1.0,
        text=text,
        adapter="test",
        source_kind="owner_reflection",
        raw_chars=len(text),
    )


def _artifacts(document):
    model = Stage4hModelConfig(
        backend_id="local.test",
        model="test:model",
        model_digest="d" * 64,
        prompt_version="stage4h-v1",
    )
    spec = Stage4hRunSpec(
        gold_sha256="a" * 64,
        challenge_sha256="b" * 64,
        corpus_sha256=corpus_digest((document,)),
        case_ids=("gold-001",),
        arms=("A0", "A1", "A2", "A4"),
        model=model,
        created_at=1.0,
        top_k=1,
        prompt_source_cap=1,
        context_depth=0,
    )
    sets = tuple(
        FrozenCandidateSet.create(
            run_id=spec.run_id,
            case_id="gold-001",
            arm=arm,
            retrieval_method=f"hidden-{arm}",
            candidates=(
                FrozenCandidate(
                    rank=1,
                    source_id=document.source_id,
                    source_revision=document.source_revision,
                    role="oracle" if arm == "A2" else "ranked",
                ),
            ),
        )
        for arm in spec.arms
    )
    candidates = FrozenCandidateBundle.create(spec=spec, candidate_sets=sets)
    citation = SourceCitation.from_document(document)
    claim = InterpretationClaim.create(
        text="Образ связан с захватом внимания.",
        citation_ids=(citation.citation_id,),
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
        wall_seconds=1.0,
    )
    results = []
    for index, candidate_set in enumerate(sets):
        if candidate_set.arm == "A0":
            results.append(
                Stage4hArmResult.create(
                    candidate_set=candidate_set,
                    status="extractive",
                    generated_at=2.0,
                    extractive_source_ids=(document.source_id,),
                )
            )
            continue
        proposal = InterpretationProposal.create(
            question="Какую роль играет образ?",
            answer="Проверяемая интерпретация.",
            claims=(claim,),
            citations=(citation,),
            interpretation_layer=3,
            producer=model.backend_id,
            model=model.model,
            prompt_version=model.prompt_version,
            generated_at=3.0 + index,
            retrieval_method=candidate_set.retrieval_method,
        )
        results.append(
            Stage4hArmResult.create(
                candidate_set=candidate_set,
                status="generated",
                generated_at=3.0 + index,
                proposal=proposal,
                telemetry=telemetry,
            )
        )
    bundle = Stage4hRunResultBundle.create(
        spec=spec,
        candidate_bundle=candidates,
        results=results,
    )
    return spec, bundle


def test_review_pack_hides_arm_model_method_and_telemetry_but_keeps_exact_excerpt() -> None:
    document = _document()
    _, results = _artifacts(document)

    pack, mapping = build_blinded_review_pack(
        result_bundle=results,
        documents=(document,),
        blinding_key=b"k" * 32,
    )

    assert len(pack.items) == 3
    assert {entry.arm for entry in mapping.entries} == {"A1", "A2", "A4"}
    encoded = json.dumps(pack.to_dict(), ensure_ascii=False)
    assert "hidden-A1" not in encoded
    assert "test:model" not in encoded
    assert "wall_seconds" not in encoded
    assert '"arm"' not in encoded
    assert document.text in encoded
    assert Stage4hReviewPack.from_dict(json.loads(encoded)) == pack
    assert Stage4hBlindMap.from_dict(mapping.to_dict()) == mapping
    assert all(mapping.resolve(item.blind_item_id).case_id == item.case_id for item in pack.items)

    markdown = review_pack_markdown(pack)
    assert document.text in markdown
    assert "A1" not in markdown
    assert "meaning fidelity 0–4" in markdown


def test_blind_ids_are_keyed_and_source_revision_is_verified() -> None:
    document = _document()
    _, results = _artifacts(document)
    first, _ = build_blinded_review_pack(
        result_bundle=results,
        documents=(document,),
        blinding_key=b"a" * 32,
    )
    second, _ = build_blinded_review_pack(
        result_bundle=results,
        documents=(document,),
        blinding_key=b"b" * 32,
    )
    assert {item.blind_item_id for item in first.items} != {
        item.blind_item_id for item in second.items
    }

    changed = _document("Изменённый текст.")
    with pytest.raises(ValueError, match="revision"):
        build_blinded_review_pack(
            result_bundle=results,
            documents=(changed,),
            blinding_key=b"a" * 32,
        )


def test_short_blinding_key_is_rejected_without_partial_pack() -> None:
    document = _document()
    _, results = _artifacts(document)
    with pytest.raises(ValueError, match="at least 16 bytes"):
        build_blinded_review_pack(
            result_bundle=results,
            documents=(document,),
            blinding_key=b"short",
        )
