"""
Language-Agnostic Basis Vector Generation

Provides basis vectors for concepts without linguistic parsing.
Supports multiple strategies:
- One-Hot: Each concept gets a unique standard basis vector
- Random Indexing: Deterministic pseudo-random vectors from a stable digest
- Custom: User-provided vectors

No external dependencies beyond numpy.
"""

import hashlib
from typing import Dict, Optional

import numpy as np


class BasisVectorGenerator:
    """Generate reproducible basis vectors for concepts."""

    def __init__(self, dim: int = 50, seed: int = 42, strategy: str = "random_indexing"):
        """
        Args:
            dim: Dimensionality of the semantic space
            seed: Namespace seed for reproducibility
            strategy: "one_hot", "random_indexing", or "custom"
        """
        if dim <= 0:
            raise ValueError("dim must be positive")
        if strategy not in {"one_hot", "random_indexing", "custom"}:
            raise ValueError(f"Unknown strategy: {strategy}")
        self.dim = dim
        self.seed = seed
        self.strategy = strategy
        self._concept_to_index: Dict[str, int] = {}
        self._index_counter = 0
        self._custom_vectors: Dict[str, np.ndarray] = {}

    def get_vector(self, concept: str) -> np.ndarray:
        """Get a normalized vector in R^dim for a concept."""
        if self.strategy == "one_hot":
            return self._get_one_hot(concept)
        if self.strategy == "random_indexing":
            return self._get_random_indexing(concept)
        if concept in self._custom_vectors:
            return self._custom_vectors[concept]
        # Fallback to random indexing if custom not provided
        return self._get_random_indexing(concept)

    def _get_one_hot(self, concept: str) -> np.ndarray:
        """One-Hot encoding: each concept gets a unique standard basis vector.

        Limitation: only works for dim >= number of unique concepts.
        """
        if concept not in self._concept_to_index:
            if self._index_counter >= self.dim:
                raise ValueError(
                    f"One-Hot strategy exhausted: {self._index_counter} concepts > dim={self.dim}"
                )
            self._concept_to_index[concept] = self._index_counter
            self._index_counter += 1

        idx = self._concept_to_index[concept]
        v = np.zeros(self.dim)
        v[idx] = 1.0
        return v

    def _get_random_indexing(self, concept: str) -> np.ndarray:
        """Return a stable pseudo-random vector derived from seed and concept.

        High-dimensional random vectors are approximately, not exactly,
        orthogonal. SHA-256 is used instead of Python's process-randomized
        ``hash()`` so vectors are stable across restarts and machines.
        """
        digest = hashlib.sha256(f"{self.seed}:{concept}".encode("utf-8")).digest()
        rng_seed = int.from_bytes(digest[:8], "little", signed=False)
        rng = np.random.default_rng(rng_seed)
        v = rng.standard_normal(self.dim)
        return v / (np.linalg.norm(v) + 1e-10)

    def set_custom_vector(self, concept: str, vector: np.ndarray):
        """Provide a custom vector for a concept, normalized to unit length."""
        vector = np.asarray(vector, dtype=float)
        if vector.shape != (self.dim,):
            raise ValueError(f"vector for '{concept}' must have shape ({self.dim},), got {vector.shape}")
        norm = np.linalg.norm(vector)
        if norm < 1e-12:
            raise ValueError(f"vector for '{concept}' must be non-zero")
        self._custom_vectors[concept] = vector / norm

    def set_custom_vectors(self, vectors: Dict[str, np.ndarray]):
        """Batch set custom vectors."""
        for concept, vector in vectors.items():
            self.set_custom_vector(concept, vector)


def create_basis_generator(
    dim: int = 50,
    strategy: str = "random_indexing",
    custom_vectors: Optional[Dict[str, np.ndarray]] = None,
) -> BasisVectorGenerator:
    """Create and optionally populate a basis vector generator."""
    gen = BasisVectorGenerator(dim=dim, strategy=strategy)
    if custom_vectors:
        gen.set_custom_vectors(custom_vectors)
    return gen
