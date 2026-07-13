"""ContainerCore — explicit asymmetric recursive containers (experimental, ADR-002).

The evidence ledger remains canonical; containers are a derived, versioned snapshot.
Default retrieval uses the graph baseline; containers are opt-in. Claims of container
superiority are prohibited until C5 validation shows a statistically reliable advantage.
"""

from .core import (
    CONTAINER_CORE_VERSION,
    ContainerActivation,
    ContainerContribution,
    ContainerEmbedding,
    ContainerFacet,
    ContainerProjection,
    ContainerSnapshot,
    SemanticContainer,
    materialize_container_ledger,
    normalize_context_keys,
)

__all__ = [
    "CONTAINER_CORE_VERSION",
    "ContainerActivation",
    "ContainerContribution",
    "ContainerEmbedding",
    "ContainerFacet",
    "ContainerProjection",
    "ContainerSnapshot",
    "SemanticContainer",
    "materialize_container_ledger",
    "normalize_context_keys",
]
