from __future__ import annotations

import json

import pytest

from fvsc.evaluation import (
    FrozenCandidate,
    FrozenCandidateSet,
    Stage4hCitationReview,
    Stage4hClaimReview,
    Stage4hModelConfig,
    Stage4hOwnerReview,
    Stage4hRunSpec,
    content_digest,
)


_D = "a" * 64
_E = "b" * 64


def _spec(**changes) -> Stage4hRunSpec:
    values = {
        "gold_sha256": _D,
        "challenge_sha256": _E,
        "corpus_sha256": "c" * 64,
        "case_ids": ("gold-001", "challenge-001"),
        "arms": ("A0", "A1", "A2", "A4"),
        "model": Stage4hModelConfig(
            backend_id="ollama.local",
            model="qwen:test",
            prompt_version="stage4h-v1",
        ),
        "created_at": 1.0,
    }
    values.update(changes)
    return Stage4hRunSpec(**values)


def test_run_spec_is_content_addressed_and_round_trips() -> None:
    spec = _spec()
    encoded = json.dumps(spec.to_dict(), ensure_ascii=False, sort_keys=True)
    loaded = Stage4hRunSpec.from_dict(json.loads(encoded))

    assert loaded == spec
    assert loaded.run_id == spec.run_id
    assert len(spec.run_id) == 64
    assert spec.model.temperature == 0.0
    assert spec.model.seed == 42
    assert spec.model.num_predict == 768
    assert spec.evaluation_mode == "pilot"
    assert spec.explicit_locator_policy == "anchor"
    assert spec.thresholds.max_severe_errors == 0

    changed = dict(spec.to_dict())
    changed["top_k"] = 9
    with pytest.raises(ValueError, match="run_id"):
        Stage4hRunSpec.from_dict(changed)


def test_exclusive_locator_policy_is_validated_and_changes_run_identity() -> None:
    baseline = _spec()
    exclusive = _spec(explicit_locator_policy="exclusive")

    assert "explicit_locator_policy" not in baseline.to_dict()
    assert exclusive.to_dict()["explicit_locator_policy"] == "exclusive"
    assert exclusive.run_id != baseline.run_id
    assert Stage4hRunSpec.from_dict(exclusive.to_dict()) == exclusive

    with pytest.raises(ValueError, match="explicit locator policy"):
        _spec(explicit_locator_policy="guess")


def test_owner_annotation_overlay_is_part_of_new_run_identity_only_when_present() -> None:
    legacy = _spec()
    annotated = _spec(owner_annotation_overlay_id="d" * 64)

    assert "owner_annotation_overlay_id" not in legacy.to_dict()
    assert annotated.to_dict()["owner_annotation_overlay_id"] == "d" * 64
    assert annotated.run_id != legacy.run_id
    assert Stage4hRunSpec.from_dict(annotated.to_dict()) == annotated


def test_run_spec_requires_all_local_arms_and_explicit_a3_scope() -> None:
    with pytest.raises(ValueError, match="missing required arms"):
        _spec(arms=("A0", "A1", "A2"))
    with pytest.raises(ValueError, match="external_reference_scope"):
        _spec(arms=("A0", "A1", "A2", "A3", "A4"))
    with pytest.raises(ValueError, match="only when A3"):
        _spec(external_reference_scope="send selected source bodies")

    enabled = _spec(
        arms=("A0", "A1", "A2", "A3", "A4"),
        external_reference_scope="owner-approved selected source bodies",
    )
    assert "A3" in enabled.arms

    with pytest.raises(ValueError, match="evaluation mode"):
        _spec(evaluation_mode="marketing")
    with pytest.raises(ValueError, match="at least 17"):
        _spec(evaluation_mode="confirmatory")


def test_frozen_candidates_bind_rank_revision_and_method_without_source_text() -> None:
    candidate = FrozenCandidate(
        rank=1,
        source_id="telegram/messages/message-334.json",
        source_revision=_D,
        role="ranked",
        score=0.75,
        evidence_event_ids=(_E,),
    )
    frozen = FrozenCandidateSet.create(
        run_id=_spec().run_id,
        case_id="gold-001",
        arm="A1",
        retrieval_method="lexical-char-tfidf-v1",
        candidates=(candidate,),
    )

    encoded = json.dumps(frozen.to_dict(), ensure_ascii=False)
    assert "Паразиты превращают внимание" not in encoded
    assert FrozenCandidateSet.from_dict(json.loads(encoded)) == frozen

    tampered = frozen.to_dict()
    tampered["candidates"][0]["score"] = 0.80
    with pytest.raises(ValueError, match="candidate_set_id"):
        FrozenCandidateSet.from_dict(tampered)


def test_candidate_context_parent_must_be_frozen_and_ranks_are_contiguous() -> None:
    context = FrozenCandidate(
        rank=2,
        source_id="message-335",
        source_revision=_E,
        role="context",
        expanded_from_source_id="message-334",
    )
    with pytest.raises(ValueError, match="contiguous"):
        FrozenCandidateSet.create(
            run_id=_D,
            case_id="gold-001",
            arm="A1",
            retrieval_method="lexical",
            candidates=(context,),
        )

    orphan = FrozenCandidate(
        rank=1,
        source_id="message-335",
        source_revision=_E,
        role="context",
        expanded_from_source_id="message-334",
    )
    with pytest.raises(ValueError, match="parent"):
        FrozenCandidateSet.create(
            run_id=_D,
            case_id="gold-001",
            arm="A1",
            retrieval_method="lexical",
            candidates=(orphan,),
        )


def test_owner_review_is_separate_content_addressed_claim_and_citation_scoring() -> None:
    citation = Stage4hCitationReview(citation_id=_D, verdict="supports")
    claim = Stage4hClaimReview(
        claim_id=_E,
        verdict="partially_accepted",
        citations=(citation,),
    )
    review = Stage4hOwnerReview.create(
        blind_item_id="c" * 64,
        proposal_id="d" * 64,
        claim_reviews=(claim,),
        meaning_fidelity=3,
        usefulness=4,
        false_owner_attribution=True,
    )

    assert review.severe_error_count == 1
    assert Stage4hOwnerReview.from_dict(review.to_dict()) == review

    tampered = review.to_dict()
    tampered["meaning_fidelity"] = 4
    with pytest.raises(ValueError, match="review_id"):
        Stage4hOwnerReview.from_dict(tampered)


def test_content_digest_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="JSON values"):
        content_digest({"score": float("nan")})
