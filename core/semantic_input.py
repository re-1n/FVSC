"""
Language-Agnostic Semantic Input Parser

Converts explicit JSON/dict semantic structures to density matrices.
No linguistic parsing required — all semantic relationships are defined explicitly.

Input format:
{
    "Concept_Name": {
        "weight": 1.0,
        "contains": {
            "Concept_Child1": 0.6,
            "Concept_Child2": 0.3,
        }
    }
}

Each concept gets:
- An orthogonal basis vector
- A density matrix constructed from weighted concept vectors
- Nested containers via tensor products
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class SemanticInput:
    """Parsed semantic input structure."""
    concepts: Dict[str, 'ConceptDef']
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SemanticInput':
        """Parse semantic input from dict."""
        concepts = {}
        for name, spec in data.items():
            concepts[name] = ConceptDef.from_dict(name, spec)
        return cls(concepts=concepts)


@dataclass
class ConceptDef:
    """Definition of a single concept with its semantic relationships."""
    name: str
    weight: float = 1.0
    contains: Dict[str, float] = None  # child_name -> weight
    
    def __post_init__(self):
        if self.contains is None:
            self.contains = {}
    
    @classmethod
    def from_dict(cls, name: str, spec: Dict[str, Any]) -> 'ConceptDef':
        """Parse concept definition from dict."""
        weight = spec.get("weight", 1.0)
        contains = spec.get("contains", {})
        return cls(name=name, weight=weight, contains=contains)


class SemanticInputParser:
    """Parse explicit semantic input and construct density matrices."""
    
    def __init__(self, dim: int = 50, basis_generator=None):
        """
        Args:
            dim: Dimensionality of semantic space
            basis_generator: BasisVectorGenerator instance (created if None)
        """
        self.dim = dim
        if basis_generator is None:
            from .basis_vectors import create_basis_generator
            self.basis_gen = create_basis_generator(dim=dim, strategy="random_indexing")
        else:
            self.basis_gen = basis_generator
        
        self._concept_vectors: Dict[str, np.ndarray] = {}
        self._concept_rhos: Dict[str, np.ndarray] = {}
    
    def parse(self, semantic_input: Dict[str, Any]) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
        """Parse semantic input and return (concept_vectors, concept_rhos).
        
        Args:
            semantic_input: Dict with concept definitions
        
        Returns:
            (concept_vectors, concept_rhos) where:
            - concept_vectors: Dict[concept_name -> orthogonal basis vector]
            - concept_rhos: Dict[concept_name -> density matrix]
        """
        parsed = SemanticInput.from_dict(semantic_input)
        
        # Step 1: Assign orthogonal basis vectors to all concepts
        for concept_name in parsed.concepts:
            self._concept_vectors[concept_name] = self.basis_gen.get_vector(concept_name)
        
        # Step 2: Build density matrices (with nested structure via tensor products)
        for concept_name, concept_def in parsed.concepts.items():
            self._concept_rhos[concept_name] = self._build_density_matrix(concept_def, parsed.concepts)
        
        return self._concept_vectors, self._concept_rhos
    
    def _build_density_matrix(self, concept_def: ConceptDef, all_concepts: Dict[str, ConceptDef]) -> np.ndarray:
        """Build density matrix for a concept using weighted outer products.
        
        ρ_concept = w_concept |ψ_concept⟩⟨ψ_concept| + Σ w_i |ψ_i⟩⟨ψ_i|
        
        where w_i are weights from the "contains" relationship.
        """
        # Start with the concept's own vector
        v_self = self._concept_vectors[concept_def.name]
        rho = concept_def.weight * np.outer(v_self, v_self)
        
        # Add weighted components from contained concepts
        for child_name, child_weight in concept_def.contains.items():
            if child_name in self._concept_vectors:
                v_child = self._concept_vectors[child_name]
                rho += child_weight * np.outer(v_child, v_child)
        
        return rho
    
    def build_nested_density_matrix(self, concept_def: ConceptDef, 
                                   all_concepts: Dict[str, ConceptDef],
                                   depth: int = 0, max_depth: int = 3) -> np.ndarray:
        """Build density matrix with recursive nesting via tensor products.
        
        For nested containers, use tensor product to maintain fractal structure:
        ρ_nested = ρ_parent ⊗ ρ_child
        
        This preserves the hierarchical structure in the quantum state.
        """
        if depth >= max_depth or not concept_def.contains:
            # Base case: simple density matrix
            return self._build_density_matrix(concept_def, all_concepts)
        
        # Recursive case: tensor product of parent and children
        v_self = self._concept_vectors[concept_def.name]
        rho_parent = concept_def.weight * np.outer(v_self, v_self)
        
        # Build tensor product with children
        for child_name, child_weight in concept_def.contains.items():
            if child_name in all_concepts:
                child_def = all_concepts[child_name]
                rho_child = self.build_nested_density_matrix(child_def, all_concepts, depth + 1, max_depth)
                
                # Tensor product: ρ_parent ⊗ ρ_child
                # This creates a larger space that preserves both structures
                rho_tensor = np.kron(rho_parent, rho_child)
                rho_parent = child_weight * rho_tensor
        
        return rho_parent
    
    def partial_trace(self, rho: np.ndarray, subsystem_dim: int) -> np.ndarray:
        """Partial trace operation: Tr_B(ρ_AB) to "unfold" a container.
        
        Removes subsystem B, leaving only the reduced density matrix of A.
        Useful for seeing the weighted composition of a container.
        
        Args:
            rho: Density matrix of composite system (A ⊗ B)
            subsystem_dim: Dimension of subsystem B
        
        Returns:
            Reduced density matrix of subsystem A
        """
        dim_a = rho.shape[0] // subsystem_dim
        rho_reduced = np.zeros((dim_a, dim_a), dtype=complex)
        
        for i in range(subsystem_dim):
            # Extract block corresponding to subsystem B state |i⟩
            block = rho[i*dim_a:(i+1)*dim_a, i*dim_a:(i+1)*dim_a]
            rho_reduced += block
        
        return np.real(rho_reduced)


def parse_semantic_input(semantic_input: Dict[str, Any], dim: int = 50,
                        basis_generator=None) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """Convenience function to parse semantic input.
    
    Args:
        semantic_input: Dict with concept definitions
        dim: Dimensionality of semantic space
        basis_generator: Optional custom basis generator
    
    Returns:
        (concept_vectors, concept_rhos)
    """
    parser = SemanticInputParser(dim=dim, basis_generator=basis_generator)
    return parser.parse(semantic_input)
