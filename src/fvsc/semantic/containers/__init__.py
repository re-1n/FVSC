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
from .query import (
    ContainerPath,
    ContainerQueryIndex,
    QueryActivation,
    QueryEdge,
    QueryProjection,
)
from .traversal import (
    BoundedContainerTraversal,
    IndexedActivation,
    IndexedProjection,
    TraversalEdge,
)
from .materializer_fast import (
    FAST_CONTAINER_VERSION,
    materialize_fast_container_ledger,
    signed_permutation_operator,
)

__all__ = [
    "BoundedContainerTraversal",
    "CONTAINER_CORE_VERSION",
    "ContainerActivation",
    "ContainerContribution",
    "ContainerEmbedding",
    "ContainerFacet",
    "ContainerPath",
    "ContainerProjection",
    "ContainerQueryIndex",
    "ContainerSnapshot",
    "FAST_CONTAINER_VERSION",
    "IndexedActivation",
    "IndexedProjection",
    "QueryActivation",
    "QueryEdge",
    "QueryProjection",
    "SemanticContainer",
    "TraversalEdge",
    "materialize_container_ledger",
    "materialize_fast_container_ledger",
    "normalize_context_keys",
    "signed_permutation_operator",
]
