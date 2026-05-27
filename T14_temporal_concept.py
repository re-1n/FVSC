# -*- coding: utf-8 -*-
"""
T14: Temporal Evolution — TemporalConcept Implementation

Extends Concept with time-parameterized density matrices ρ(t).
Tracks eigenvalue trajectories, trace evolution, and semantic drift.

Usage:
    concept = TemporalConcept(term="свобода")
    concept.add_component_temporal(vector, weight, judgment)
    
    # Query temporal properties
    trace_t = concept.trace_at(t)
    eigs_t = concept.eigenvalues_at(t)
    drift = concept.semantic_drift(t1, t2)
    
    # Analyze embodiment and tacit knowledge
    embodiment = concept.embodiment_score()
    tacit = concept.tacit_knowledge_score()
"""

import numpy as np
import time
from dataclasses import dataclass, field
from typing import Optional

# Assume density_core is available
try:
    from core.density_core import Concept, Component, Judgment, von_neumann_entropy
except ImportError:
    from density_core import Concept, Component, Judgment, von_neumann_entropy


@dataclass
class TemporalConcept(Concept):
    """Concept with temporal evolution tracking.
    
    Extends Concept to track ρ(t) — how density matrix evolves through discourse.
    Stores snapshots of ρ, eigenvalues, and trace at each judgment timestamp.
    """
    
    # Temporal tracking
    _rho_snapshots: dict[float, np.ndarray] = field(default_factory=dict, repr=False)
    _eigenvalue_history: dict[float, np.ndarray] = field(default_factory=dict, repr=False)
    _trace_history: list[tuple[float, float]] = field(default_factory=list, repr=False)
    
    # Metadata
    _first_mention_time: Optional[float] = field(default=None, repr=False)
    _last_update_time: Optional[float] = field(default=None, repr=False)
    
    def rho_at(self, t: float) -> Optional[np.ndarray]:
        """Get ρ(t) — exact snapshot or nearest neighbor.
        
        Args:
            t: timestamp (seconds since epoch)
            
        Returns:
            Density matrix at time t, or None if no data.
        """
        if t in self._rho_snapshots:
            return self._rho_snapshots[t]
        
        if not self._rho_snapshots:
            return None
        
        # Find nearest snapshot
        nearest_t = min(self._rho_snapshots.keys(), key=lambda x: abs(x - t))
        return self._rho_snapshots[nearest_t]
    
    def trace_at(self, t: float) -> float:
        """Trace(ρ(t)) — intensity of experience at time t.
        
        Args:
            t: timestamp
            
        Returns:
            Trace value (sum of eigenvalues), or 0.0 if no data.
        """
        rho = self.rho_at(t)
        if rho is None:
            return 0.0
        return float(np.trace(rho))
    
    def eigenvalues_at(self, t: float) -> Optional[np.ndarray]:
        """Eigenvalues λᵢ(t) at time t.
        
        Args:
            t: timestamp
            
        Returns:
            Array of eigenvalues (sorted descending), or None if no data.
        """
        if t in self._eigenvalue_history:
            return self._eigenvalue_history[t]
        
        if not self._eigenvalue_history:
            return None
        
        # Find nearest
        nearest_t = min(self._eigenvalue_history.keys(), key=lambda x: abs(x - t))
        return self._eigenvalue_history[nearest_t]
    
    def semantic_drift(self, t1: float, t2: float) -> float:
        """Measure semantic change between t1 and t2.
        
        Uses Frobenius norm of eigenvalue difference:
            drift = ||λ(t2) - λ(t1)||_F / ||λ(t1)||_F
        
        Interpretation:
            0.0 = no change (stable meaning)
            0.5 = moderate drift (facet reordering)
            1.0+ = major drift (new facets emerge)
        
        Args:
            t1, t2: timestamps
            
        Returns:
            Drift score (non-negative float).
        """
        eigs1 = self.eigenvalues_at(t1)
        eigs2 = self.eigenvalues_at(t2)
        
        if eigs1 is None or eigs2 is None:
            return 0.0
        
        # Pad to same length
        n = max(len(eigs1), len(eigs2))
        e1 = np.pad(eigs1, (0, n - len(eigs1)), mode='constant')
        e2 = np.pad(eigs2, (0, n - len(eigs2)), mode='constant')
        
        norm1 = np.linalg.norm(e1)
        if norm1 < 1e-12:
            return 0.0
        
        return float(np.linalg.norm(e2 - e1) / norm1)
    
    def add_component_temporal(self, vector: np.ndarray, weight: float,
                               judgment: Judgment):
        """Add component and record temporal snapshot.
        
        Extends add_component() with temporal tracking:
        1. Add to components list (with consolidation)
        2. Record ρ(t) snapshot at judgment.timestamp
        3. Compute and store eigenvalues
        4. Record trace value
        
        Args:
            vector: semantic vector (d-dimensional)
            weight: component weight (modality × intensity)
            judgment: source judgment with timestamp
        """
        # 1. Add to components (existing consolidation logic)
        self.add_component(vector, weight, judgment)
        
        # 2. Record temporal metadata
        t = judgment.timestamp
        if self._first_mention_time is None:
            self._first_mention_time = t
        self._last_update_time = t
        
        # 3. Record snapshot at this timestamp
        rho_t = self.rho  # recomputed after add_component
        if rho_t is not None:
            self._rho_snapshots[t] = rho_t.copy()
            
            # 4. Compute eigenvalues (sorted descending)
            eigs = np.linalg.eigvalsh(rho_t)
            eigs = np.sort(eigs)[::-1]  # descending order
            self._eigenvalue_history[t] = eigs
            
            # 5. Record trace
            tr = float(np.trace(rho_t))
            self._trace_history.append((t, tr))
    
    def tacit_knowledge_score(self) -> float:
        """Fraction of concept that is tacit (consolidated, old).
        
        Tacit knowledge = components that are:
        - Old (age > 30 days)
        - Confirmed multiple times (high activation_count)
        - Not recently changed
        
        Interpretation:
            0.0 = all explicit (recent, low confirmation)
            1.0 = all tacit (old, high confirmation)
        
        Returns:
            Score in [0, 1].
        """
        now = time.time()
        tacit_weight = 0.0
        total_weight = 0.0
        
        for c in self.components:
            if c.archived:
                continue
            
            age = now - c.timestamp
            age_days = age / 86400.0
            
            # Tacit factor: increases with age, saturates at 30 days
            tacit_factor = min(1.0, age_days / 30.0)
            
            # Weight by activation count (confirmed many times = more tacit)
            component_tacit = c.weight * c.activation_count * tacit_factor
            tacit_weight += component_tacit
            total_weight += c.weight * c.activation_count
        
        if total_weight < 1e-12:
            return 0.0
        
        return float(tacit_weight / total_weight)
    
    def embodiment_score(self) -> float:
        """How embodied is this concept?
        
        Embodied concepts have:
        - High Trace(ρ(t)) = frequently activated
        - Low entropy S(ρ) = clear, focused meaning
        - Stable eigenvalues = consistent across contexts
        
        Abstract concepts have:
        - Low Trace(ρ(t)) = rarely activated
        - High entropy S(ρ) = ambiguous, polysemous
        - Volatile eigenvalues = meaning shifts
        
        Interpretation:
            0.0 = abstract (low trace, high entropy, volatile)
            1.0 = embodied (high trace, low entropy, stable)
        
        Returns:
            Score in [0, 1].
        """
        if not self._trace_history:
            return 0.0
        
        # 1. Average trace (normalized to [0, 1])
        traces = [tr for _, tr in self._trace_history]
        avg_trace = np.mean(traces)
        max_trace = np.max(traces) if traces else 1.0
        trace_score = min(1.0, avg_trace / max(max_trace, 1.0))
        
        # 2. Entropy (low = embodied)
        rho_n = self.rho_norm
        if rho_n is None:
            entropy_score = 0.0
        else:
            entropy = von_neumann_entropy(rho_n)
            # Normalize: max entropy for d=50 is log(50) ≈ 3.9
            entropy_score = 1.0 - min(1.0, entropy / 4.0)
        
        # 3. Eigenvalue stability (low variance = stable = embodied)
        if len(self._eigenvalue_history) < 2:
            stability_score = 1.0
        else:
            eigs_list = list(self._eigenvalue_history.values())
            # Variance of dominant eigenvalue
            dominant_eigs = [e[0] for e in eigs_list if len(e) > 0]
            if len(dominant_eigs) > 1:
                eig_variance = np.var(dominant_eigs)
                # Normalize: typical variance is ~0.1
                stability_score = 1.0 / (1.0 + eig_variance / 0.1)
            else:
                stability_score = 1.0
        
        # Combine: geometric mean of three factors
        embodiment = (trace_score * entropy_score * stability_score) ** (1/3)
        return float(np.clip(embodiment, 0.0, 1.0))
    
    def intensity_trajectory(self) -> tuple[list[float], list[float]]:
        """Get (times, traces) for plotting.
        
        Returns:
            (times, traces) — lists of timestamps and Trace(ρ(t)) values.
        """
        if not self._trace_history:
            return [], []
        times, traces = zip(*self._trace_history)
        return list(times), list(traces)
    
    def eigenvalue_trajectories(self) -> dict[int, tuple[list[float], list[float]]]:
        """Get eigenvalue trajectories for plotting.
        
        Returns:
            {eigenvalue_index: (times, values), ...}
            E.g., {0: ([t1, t2, ...], [λ₁(t1), λ₁(t2), ...]), ...}
        """
        if not self._eigenvalue_history:
            return {}
        
        times = sorted(self._eigenvalue_history.keys())
        max_eigs = max(len(self._eigenvalue_history[t]) for t in times)
        
        trajectories = {}
        for i in range(max_eigs):
            eig_values = []
            for t in times:
                eigs = self._eigenvalue_history[t]
                eig_values.append(eigs[i] if i < len(eigs) else 0.0)
            trajectories[i] = (times, eig_values)
        
        return trajectories
    
    def time_span(self) -> float:
        """Total time span from first mention to last update (seconds)."""
        if self._first_mention_time is None or self._last_update_time is None:
            return 0.0
        return self._last_update_time - self._first_mention_time
    
    def mention_count(self) -> int:
        """Number of times this concept was mentioned."""
        return len(self._trace_history)
    
    def average_intensity(self) -> float:
        """Average Trace(ρ(t)) across all mentions."""
        if not self._trace_history:
            return 0.0
        traces = [tr for _, tr in self._trace_history]
        return float(np.mean(traces))
    
    def peak_intensity(self) -> float:
        """Maximum Trace(ρ(t))."""
        if not self._trace_history:
            return 0.0
        traces = [tr for _, tr in self._trace_history]
        return float(np.max(traces))
    
    def entropy_evolution(self) -> list[tuple[float, float]]:
        """Get (time, entropy) pairs for plotting.
        
        Returns:
            [(t, S(ρ(t))), ...] sorted by time.
        """
        result = []
        for t in sorted(self._rho_snapshots.keys()):
            rho = self._rho_snapshots[t]
            tr = np.trace(rho)
            if tr > 1e-12:
                rho_norm = rho / tr
                entropy = von_neumann_entropy(rho_norm)
                result.append((t, entropy))
        return result


# ============================================================================
# Utility functions for temporal analysis
# ============================================================================

def compare_concepts_temporal(concept1: TemporalConcept, concept2: TemporalConcept,
                              t1: float, t2: float) -> dict:
    """Compare two concepts at two different times.
    
    Args:
        concept1, concept2: TemporalConcepts to compare
        t1, t2: timestamps
        
    Returns:
        Dictionary with comparison metrics:
        - trace_ratio: Trace(c1, t1) / Trace(c2, t1)
        - drift_c1: semantic drift of c1 from t1 to t2
        - drift_c2: semantic drift of c2 from t1 to t2
        - embodiment_c1, embodiment_c2: embodiment scores
        - tacit_c1, tacit_c2: tacit knowledge scores
    """
    return {
        'trace_ratio': concept1.trace_at(t1) / max(concept2.trace_at(t1), 1e-12),
        'drift_c1': concept1.semantic_drift(t1, t2),
        'drift_c2': concept2.semantic_drift(t1, t2),
        'embodiment_c1': concept1.embodiment_score(),
        'embodiment_c2': concept2.embodiment_score(),
        'tacit_c1': concept1.tacit_knowledge_score(),
        'tacit_c2': concept2.tacit_knowledge_score(),
    }


def identify_semantic_crises(concept: TemporalConcept, 
                             drift_threshold: float = 0.5) -> list[tuple[float, float, float]]:
    """Identify moments of high semantic drift (crises/breakthroughs).
    
    Args:
        concept: TemporalConcept to analyze
        drift_threshold: minimum drift to flag as crisis
        
    Returns:
        List of (t1, t2, drift) tuples where drift > threshold.
    """
    times = sorted(concept._eigenvalue_history.keys())
    crises = []
    
    for i in range(len(times) - 1):
        t1, t2 = times[i], times[i + 1]
        drift = concept.semantic_drift(t1, t2)
        if drift > drift_threshold:
            crises.append((t1, t2, drift))
    
    return crises


def identify_consolidation_periods(concept: TemporalConcept,
                                   drift_threshold: float = 0.1,
                                   min_duration: float = 3600.0) -> list[tuple[float, float]]:
    """Identify periods of semantic stability (consolidation).
    
    Args:
        concept: TemporalConcept to analyze
        drift_threshold: maximum drift to count as stable
        min_duration: minimum duration in seconds
        
    Returns:
        List of (t_start, t_end) tuples for consolidation periods.
    """
    times = sorted(concept._eigenvalue_history.keys())
    periods = []
    current_start = None
    
    for i in range(len(times) - 1):
        t1, t2 = times[i], times[i + 1]
        drift = concept.semantic_drift(t1, t2)
        
        if drift < drift_threshold:
            if current_start is None:
                current_start = t1
        else:
            if current_start is not None:
                duration = t1 - current_start
                if duration >= min_duration:
                    periods.append((current_start, t1))
                current_start = None
    
    # Handle final period
    if current_start is not None:
        duration = times[-1] - current_start
        if duration >= min_duration:
            periods.append((current_start, times[-1]))
    
    return periods
