"""Runtime: snapshots, persistence, evaluation."""

from .materializer import (
    Contribution,
    DeterministicEvidenceEncoder,
    EvidenceEncoder,
    MaterializedConcept,
    MaterializedSnapshot,
    materialize_ledger,
)
from .snapshots import (
    ConceptChange,
    SemanticSnapshot,
    SnapshotConcept,
    StateDelta,
    apply_delta,
)

__all__ = [
    "ConceptChange",
    "Contribution",
    "DeterministicEvidenceEncoder",
    "EvidenceEncoder",
    "MaterializedConcept",
    "MaterializedSnapshot",
    "SemanticSnapshot",
    "SnapshotConcept",
    "StateDelta",
    "apply_delta",
    "materialize_ledger",
]
