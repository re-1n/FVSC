from __future__ import annotations

from fvsc.evidence import EvidenceEvent, EvidencePolicy


def _event(*, kind: str, layer: int = 1, status: str = "unreviewed") -> EvidenceEvent:
    return EvidenceEvent.assertion(
        source_id=f"{kind}.md",
        observed_at=1.0,
        recorded_at=1.0,
        subject="свобода",
        relation="требовать",
        object="ответственность",
        interpretation_layer=layer,
        extractor="fvsc.ingest.judgment",
        extractor_version="1",
        context={
            "derivation": "linguistic-judgment",
            "source_kind": kind,
            "judgment": {"confirmation_status": status},
        },
    )


def test_policy_selects_source_extractor_layer_and_confirmation() -> None:
    policy = EvidencePolicy(
        source_kinds=frozenset({"owner_reflection"}),
        extractors=frozenset({"fvsc.ingest.judgment"}),
        derivations=frozenset({"linguistic-judgment"}),
        confirmation_statuses=frozenset({"confirmed", "unreviewed"}),
        max_interpretation_layer=1,
    )

    assert policy.allows(_event(kind="owner_reflection"))
    assert not policy.allows(_event(kind="unknown"))
    assert not policy.allows(_event(kind="owner_reflection", layer=2))
    assert not policy.allows(_event(kind="owner_reflection", status="rejected"))


def test_policy_fingerprint_is_order_invariant_and_empty_set_denies_all() -> None:
    first = EvidencePolicy(source_kinds=frozenset({"unknown", "owner_reflection"}))
    second = EvidencePolicy(source_kinds=frozenset({"owner_reflection", "unknown"}))

    assert first.fingerprint == second.fingerprint
    assert first.to_dict() == second.to_dict()
    assert not EvidencePolicy(source_kinds=frozenset()).allows(
        _event(kind="owner_reflection")
    )
