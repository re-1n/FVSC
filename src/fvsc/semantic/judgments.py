"""Portable semantic judgment contract.

``EvidenceEvent`` remains canonical memory. A ``Judgment`` is the typed semantic
projection used by linguistic extractors and optional materializers. Keeping the
projection outside the density backend prevents exact subject/relation/object
evidence from depending on a particular local representation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..evidence import EvidenceEvent


JUDGMENT_CONTEXT_SCHEMA = "fvsc.judgment/v1"


@dataclass
class Judgment:
    """One extracted ``subject -> verb -> object`` statement plus context.

    The class deliberately remains mutable because feedback and optional local
    materializers annotate derived judgments. Mutations are never canonical;
    accepted changes are written back as new ledger lifecycle events.
    """

    # Layer 1: syntactic/logical core.
    subject: str
    verb: str
    object: str
    quality: str = "AFFIRMATIVE"
    negation_scope: bool = False
    modality: float = 1.0
    modality_type: str = "FACTUAL"
    intensity: float = 0.5
    timestamp: float = field(default_factory=time.time)
    source_text: str = ""
    condition_id: str | int | None = None
    condition_role: Optional[str] = None
    anomaly_score: Optional[float] = None

    # Interpretation provenance, orthogonal to semantic layers.
    interpretation_layer: int = 0
    defeasible: bool = False
    inference_chain: list[str] = field(default_factory=list)
    extraction_confidence: float = 1.0
    clause_type: str = "UNKNOWN"

    # Layer 2: semantic frame.
    frame_name: Optional[str] = None
    semantic_roles: dict[str, Any] = field(default_factory=dict)
    role_intensity: float = 0.0

    # Layer 3: active polysemic facet.
    facet_id: Optional[int] = None
    polysemy_degree: float = 0.0
    sense_vector: Any | None = None

    # Layer 4: perceptual grounding.
    perceptual_modalities: set[str] = field(default_factory=set)
    perceptual_features: dict[str, Any] = field(default_factory=dict)
    emotion_tags: dict[str, Any] = field(default_factory=dict)

    # Layer 5: pragmatic and historical context.
    context_metadata: dict[str, Any] = field(default_factory=dict)
    historical_variant: Optional[str] = None

    # Layer 6: reflective metaknowledge and owner feedback.
    user_marked_facet: bool = False
    user_confidence: float = 0.0
    confirmation_status: str = "unreviewed"
    context_tags: list[str] = field(default_factory=list)

    @property
    def polarity(self) -> float:
        """Return the ledger polarity implied by quality/negation."""
        return -1.0 if self.quality == "NEGATIVE" or self.negation_scope else 1.0

    def to_evidence_context(self) -> dict[str, Any]:
        """Return the JSON-compatible fields not native to ``EvidenceEvent``.

        ``source_text`` and ``sense_vector`` are intentionally absent. The event
        points to a source revision/span, while vectors are rebuildable local state.
        """
        return {
            "schema": JUDGMENT_CONTEXT_SCHEMA,
            "quality": self.quality,
            "negation_scope": bool(self.negation_scope),
            "modality_type": self.modality_type,
            "condition_id": self.condition_id,
            "condition_role": self.condition_role,
            "anomaly_score": self.anomaly_score,
            "defeasible": bool(self.defeasible),
            "inference_chain": list(self.inference_chain),
            "clause_type": self.clause_type,
            "frame_name": self.frame_name,
            "semantic_roles": dict(self.semantic_roles),
            "role_intensity": float(self.role_intensity),
            "facet_id": self.facet_id,
            "polysemy_degree": float(self.polysemy_degree),
            "perceptual_modalities": sorted(self.perceptual_modalities),
            "perceptual_features": dict(self.perceptual_features),
            "emotion_tags": dict(self.emotion_tags),
            "context_metadata": dict(self.context_metadata),
            "historical_variant": self.historical_variant,
            "user_marked_facet": bool(self.user_marked_facet),
            "user_confidence": float(self.user_confidence),
            "confirmation_status": self.confirmation_status,
            "context_tags": list(self.context_tags),
        }


def judgment_from_event(event: "EvidenceEvent") -> Judgment:
    """Rebuild a derived judgment from an active assertion-like event."""
    if event.event_kind not in {"assertion", "supersession"}:
        raise ValueError("only assertion-like events carry judgments")
    if event.subject is None or event.relation is None or event.object is None:
        raise ValueError("event does not contain a complete judgment")

    raw = event.context.get("judgment", {})
    metadata = raw if isinstance(raw, dict) else {}
    return Judgment(
        subject=event.subject,
        verb=event.relation,
        object=event.object,
        quality=str(
            metadata.get(
                "quality",
                "NEGATIVE" if event.polarity < 0.0 else "AFFIRMATIVE",
            )
        ),
        negation_scope=bool(metadata.get("negation_scope", event.polarity < 0.0)),
        modality=event.modality,
        modality_type=str(metadata.get("modality_type", "FACTUAL")),
        intensity=event.intensity,
        timestamp=event.observed_at,
        condition_id=metadata.get("condition_id"),
        condition_role=metadata.get("condition_role"),
        anomaly_score=metadata.get("anomaly_score"),
        interpretation_layer=event.interpretation_layer,
        defeasible=bool(metadata.get("defeasible", event.interpretation_layer > 0)),
        inference_chain=[str(value) for value in metadata.get("inference_chain", [])],
        extraction_confidence=event.confidence,
        clause_type=str(metadata.get("clause_type", "UNKNOWN")),
        frame_name=metadata.get("frame_name"),
        semantic_roles=dict(metadata.get("semantic_roles", {})),
        role_intensity=float(metadata.get("role_intensity", 0.0)),
        facet_id=metadata.get("facet_id"),
        polysemy_degree=float(metadata.get("polysemy_degree", 0.0)),
        perceptual_modalities=set(metadata.get("perceptual_modalities", [])),
        perceptual_features=dict(metadata.get("perceptual_features", {})),
        emotion_tags=dict(metadata.get("emotion_tags", {})),
        context_metadata=dict(metadata.get("context_metadata", {})),
        historical_variant=metadata.get("historical_variant"),
        user_marked_facet=bool(metadata.get("user_marked_facet", False)),
        user_confidence=float(metadata.get("user_confidence", 0.0)),
        confirmation_status=str(metadata.get("confirmation_status", "unreviewed")),
        context_tags=[str(value) for value in metadata.get("context_tags", [])],
    )


__all__ = ["JUDGMENT_CONTEXT_SCHEMA", "Judgment", "judgment_from_event"]
