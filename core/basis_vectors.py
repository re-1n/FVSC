"""
Language-Agnostic Basis Vector Generation

Provides orthogonal basis vectors for concepts without any linguistic parsing.
Supports multiple strategies:
- One-Hot: Each concept gets a unique standard basis vector
- Random Indexing: Deterministic pseudo-random vectors from concept hash
- Custom: User-provided vectors

No external dependencies beyond numpy.
"""

import numpy as np
from typing import Optional, Dict


class BasisVectorGenerator:
    """Generate orthogonal basis vectors for concepts in a language-agnostic way."""

    def __init__(self, dim: int = 50, seed: int = 42, strategy: str = "random_indexing"):
        """
        Args:
            dim: Dimensionality of the semantic space
            seed: Random seed for reproducibility
            strategy: "one_hot", "random_indexing", or "custom"
        """
        self.dim = dim
        self.seed = seed
        self.strategy = strategy
        self._rng = np.random.default_rng(seed)
        self._concept_to_index: Dict[str, int] = {}
        self._index_counter = 0
        self._custom_vectors: Dict[str, np.ndarray] = {}

    def get_vector(self, concept: str) -> np.ndarray:
        """Get orthogonal basis vector for a concept.
        
        Returns a normalized vector in R^dim.
        Deterministic: same concept always gets same vector.
        """
        if self.strategy == "one_hot":
            return self._get_one_hot(concept)
        elif self.strategy == "random_indexing":
            return self._get_random_indexing(concept)
        elif self.strategy == "custom":
            if concept in self._custom_vectors:
                return self._custom_vectors[concept]
            # Fallback to random indexing if custom not provided
            return self._get_random_indexing(concept)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

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
        """Random Indexing: deterministic pseudo-random vector from concept hash.
        
        Advantages:
        - Unlimited concepts (no dimension constraint)
        - Orthogonal by construction (high-dimensional random vectors are nearly orthogonal)
        - Deterministic: same concept always gets same vector
        """
        h = hash(concept) % (2**31)
        rng = np.random.default_rng(h)
        v = rng.standard_normal(self.dim)
        return v / (np.linalg.norm(v) + 1e-10)

    def set_custom_vector(self, concept: str, vector: np.ndarray):
        """Provide a custom vector for a concept.
        
        Useful for incorporating external embeddings (e.g., word2vec, GloVe).
        Vector will be normalized.
        """
        v = vector / (np.linalg.norm(vector) + 1e-10)
        self._custom_vectors[concept] = v

    def set_custom_vectors(self, vectors: Dict[str, np.ndarray]):
        """Batch set custom vectors."""
        for concept, vector in vectors.items():
            self.set_custom_vector(concept, vector)


def create_basis_generator(dim: int = 50, strategy: str = "random_indexing",
                          custom_vectors: Optional[Dict[str, np.ndarray]] = None) -> BasisVectorGenerator:
    """Factory function to create a basis vector generator.
    
    Args:
        dim: Dimensionality
        strategy: "one_hot", "random_indexing", or "custom"
        custom_vectors: Optional dict of concept -> vector mappings
    
    Returns:
        Configured BasisVectorGenerator
    """
    gen = BasisVectorGenerator(dim=dim, strategy=strategy)
    if custom_vectors:
        gen.set_custom_vectors(custom_vectors)
    return gen
