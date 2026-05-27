# T14: Temporal Evolution of Density Matrices — Research Summary

**Status:** Research phase (blocks T11, T13)  
**Date:** 2026-05-16  
**Context:** FVSC breakthrough — personality as dynamic system, not static map

---

## 1. Problem Statement

### Current Limitation
- **Static ρ:** Each concept has one density matrix per person, regardless of discourse position
- **Example:** `ρ(свобода)` = same matrix at t=0 (first mention) and t=100 (after 100 messages)
- **Loss:** Cannot capture semantic drift, emotional intensity evolution, tacit knowledge accumulation

### Insight
Personality is a **dynamical system**. Concepts evolve through discourse:
- Early mention: tentative, low intensity
- Repeated confirmation: consolidates, increases trace
- Contradiction: eigenvalue trajectories shift (semantic drift)
- Emotional peaks: Trace(ρ(t)) spikes (intensity of experience)

---

## 2. Mathematical Framework: ρ(t)

### 2.1 Temporal Density Matrix

Instead of static `ρ(concept)`, track **ρ(concept, t)** — a time-parameterized family of density matrices.

```
ρ(свобода, t) : ℝ → ℋ(d)
where ℋ(d) = space of d×d Hermitian matrices
```

**Key properties:**
- `ρ(t)` is Hermitian, positive semi-definite for all t
- `Tr(ρ(t))` = total "mass" or intensity at time t
- Eigenvalues λᵢ(t) trace semantic facets over time
- Eigenvectors vᵢ(t) show how facet directions rotate

### 2.2 Trace as Intensity

**Interpretation:** `Trace(ρ(t))` = intensity of experience at time t

```
dTrace/dt > 0  ⟹  rapid accumulation (emotional peak, active discussion)
dTrace/dt ≈ 0  ⟹  stable understanding (consolidation)
dTrace/dt < 0  ⟹  decay/forgetting (power-law, F3)
```

**Physical analogy:** Like energy in a quantum system — high trace = high "activation energy" of the concept.

### 2.3 Eigenvalue Trajectories as Semantic Drift

Eigenvalues λᵢ(t) track how meaning facets evolve:

```
λ₁(t) = dominant facet intensity
λ₂(t) = secondary facet intensity
...
```

**Semantic drift detection:**
- If λ₁(t₀) ≈ λ₂(t₀) but λ₁(t₁) >> λ₂(t₁): facet consolidation (meaning clarifies)
- If new λ₃(t₁) emerges: new facet discovered (polysemy increases)
- If λᵢ(t) → 0: facet forgotten or archived

**Example:** "свобода" (freedom)
- t=0: λ₁ ≈ 0.3 (political), λ₂ ≈ 0.3 (personal), λ₃ ≈ 0.2 (abstract)
- t=50: λ₁ ≈ 0.6 (political dominates after discussion), λ₂ ≈ 0.2, λ₃ ≈ 0.1
- Semantic drift: political facet strengthened, others weakened

### 2.4 Von Neumann Entropy Over Time

```
S(t) = -Tr(ρ(t) log ρ(t))
```

**Interpretation:**
- S(t) high ⟹ polysemous, ambiguous understanding
- S(t) low ⟹ focused, clear understanding
- dS/dt > 0 ⟹ meaning becoming more ambiguous (new facets)
- dS/dt < 0 ⟹ meaning clarifying (facets consolidating)

---

## 3. Implementation Approach

### 3.1 Data Structure Evolution

**Current (static):**
```python
@dataclass
class Concept:
    term: str
    components: list[Component]  # rank-1 components
    _rho: Optional[np.ndarray]   # single matrix
```

**Proposed (temporal):**
```python
@dataclass
class TemporalConcept:
    term: str
    components: list[Component]  # unchanged — still rank-1
    
    # NEW: temporal tracking
    _rho_snapshots: dict[float, np.ndarray]  # t → ρ(t)
    _eigenvalue_history: dict[float, np.ndarray]  # t → [λ₁, λ₂, ...]
    _trace_history: list[tuple[float, float]]  # [(t, Tr(ρ(t))), ...]
    
    def rho_at(self, t: float) -> Optional[np.ndarray]:
        """Density matrix at time t (interpolated or cached)."""
        
    def trace_at(self, t: float) -> float:
        """Trace(ρ(t)) — intensity at time t."""
        
    def eigenvalues_at(self, t: float) -> np.ndarray:
        """Eigenvalue trajectory at time t."""
        
    def semantic_drift(self, t1: float, t2: float) -> float:
        """Measure how much meaning changed between t1 and t2."""
```

### 3.2 Timestamp Field in Judgment

**Current:**
```python
@dataclass
class Judgment:
    timestamp: float = field(default_factory=time.time)  # already exists!
```

**Good news:** Timestamp already in Judgment (v0.5.3). But currently:
- Not consistently set from Telegram message dates
- Not used in temporal analysis

**Action:** Ensure `tree_extractor.py` sets `judgment.timestamp` from message metadata.

### 3.3 Incremental Updates

**Strategy:** Don't recompute entire ρ(t) history on each new judgment. Instead:

```python
def add_component_temporal(self, vector: np.ndarray, weight: float, 
                           judgment: Judgment):
    """Add component and update temporal snapshots."""
    
    # 1. Add to components list (existing logic)
    self.add_component(vector, weight, judgment)
    
    # 2. Invalidate cached ρ (existing)
    self.invalidate()
    
    # 3. NEW: Record snapshot at judgment.timestamp
    t = judgment.timestamp
    rho_t = self._compute_rho_at(t)
    self._rho_snapshots[t] = rho_t
    
    # 4. NEW: Compute eigenvalues at this time
    eigs = np.linalg.eigvalsh(rho_t)
    self._eigenvalue_history[t] = eigs
    
    # 5. NEW: Record trace
    self._trace_history.append((t, np.trace(rho_t)))
```

**Complexity:** O(d²) per judgment (eigendecomposition), acceptable for d=50.

### 3.4 Visualization Ideas

#### 3.4.1 Trace Over Time
```
Intensity(свобода)
    ↑
    |     ╱╲      ╱╲
    |    ╱  ╲    ╱  ╲
    |   ╱    ╲  ╱    ╲
    |__╱______╲╱______╲___→ time
    
    Peaks = emotional intensity
    Plateaus = consolidation
    Decay = forgetting
```

**Implementation:** Plot `trace_history` as line graph with timestamps.

#### 3.4.2 Eigenvalue Trajectories
```
λ₁(t) ─────────────────  (dominant facet)
λ₂(t) ─ ─ ─ ─ ─ ─ ─ ─  (secondary)
λ₃(t) · · · · · · · · ·  (tertiary)

Crossing points = facet reordering
New emergence = polysemy increase
Decay to zero = facet forgotten
```

**Implementation:** Stacked area chart or multi-line plot.

#### 3.4.3 Semantic Drift Heatmap
```
Concepts × Time matrix:
         t₀   t₁   t₂   t₃   t₄
свобода  0.2  0.4  0.6  0.5  0.3
любовь   0.1  0.2  0.3  0.5  0.7
истина   0.3  0.3  0.3  0.4  0.4

Color intensity = Trace(ρ(t))
Shows which concepts are "hot" at which times.
```

**Implementation:** Matplotlib heatmap with temporal axis.

#### 3.4.4 Phase Space Trajectory
```
Project ρ(t) onto first 2 principal components:
    
    PC2 ↑
        |    ●(t₀)
        |   ╱
        |  ●(t₁)
        | ╱
        |●(t₂)
        |
    ────┼────→ PC1
        
Trajectory shows semantic evolution in reduced space.
```

**Implementation:** PCA on vectorized ρ(t), plot trajectory.

---

## 4. How This Captures Qualia, Tacit Knowledge, Embodiment

### 4.1 Qualia (Subjective Experience)

**Problem:** Static ρ cannot distinguish:
- "I understand X" (stable, low trace)
- "I'm experiencing X intensely" (high trace, rapid change)

**Solution:** Trace(ρ(t)) captures **intensity of experience**.

```
Qualia ≈ dTrace/dt + eigenvalue_volatility

High dTrace/dt = emotional peak (qualia present)
Low dTrace/dt = intellectual understanding (qualia absent)
```

**Example:** "свобода" (freedom)
- Intellectual discussion: Trace grows slowly, eigenvalues stable
- Personal crisis: Trace spikes, eigenvalues oscillate (qualia: anguish)

### 4.2 Tacit Knowledge (Polanyi's "Know More Than We Can Say")

**Problem:** Static ρ treats all components equally. Cannot distinguish:
- Explicit knowledge (recent, high confidence)
- Tacit knowledge (old, consolidated, low-confidence but deeply embedded)

**Solution:** Temporal structure reveals **consolidation depth**.

```
Tacit knowledge = old components with high activation_count
                  (confirmed many times, low recent change)

Explicit knowledge = recent components with low activation_count
                     (just learned, high recent change)
```

**Implementation:**
```python
def tacit_knowledge_score(self, concept: TemporalConcept) -> float:
    """How much of this concept is tacit (consolidated)?"""
    now = time.time()
    tacit = 0.0
    for c in concept.components:
        age = now - c.timestamp
        if age > 30 * 86400:  # older than 30 days
            tacit += c.activation_count * (1 + age / (30*86400)) ** 0.5
    return tacit / sum(c.activation_count for c in concept.components)
```

### 4.3 Embodiment (Grounding in Experience)

**Problem:** Static ρ is abstract. Cannot distinguish:
- Conceptual knowledge (abstract, high entropy)
- Embodied knowledge (grounded in experience, low entropy, high trace)

**Solution:** Temporal trace + entropy trajectory reveals **embodiment**.

```
Embodied concept:
- High Trace(ρ(t)) = frequently activated
- Low S(t) = clear, focused meaning
- Stable eigenvalues = consistent across contexts

Abstract concept:
- Low Trace(ρ(t)) = rarely activated
- High S(t) = ambiguous, polysemous
- Volatile eigenvalues = meaning shifts with context
```

**Example:** "рука" (hand) vs "справедливость" (justice)
- "рука": high trace, low entropy, stable eigenvalues → embodied
- "справедливость": low trace, high entropy, volatile eigenvalues → abstract

---

## 5. Connection to Dynamical Systems Theory

### 5.1 Differential Equations for ρ(t)

**Liouville-von Neumann equation** (quantum mechanics):
```
dρ/dt = -i[H, ρ]
where [H, ρ] = H·ρ - ρ·H (commutator)
```

**Interpretation for FVSC:**
- H = "semantic Hamiltonian" (encodes concept interactions)
- ρ(t) = semantic state evolving under discourse dynamics
- Commutator = how concepts interfere with each other

**Simplified classical version** (Lindblad master equation):
```
dρ/dt = Σᵢ (Lᵢ·ρ·Lᵢ† - ½{Lᵢ†·Lᵢ, ρ})
where Lᵢ = Lindblad operators (dissipation channels)
```

**In FVSC context:**
- Lᵢ = discourse events (new judgments, contradictions, confirmations)
- Dissipation = power-law decay (F3)
- Coherence = semantic stability

### 5.2 Attractors and Fixed Points

**Fixed point:** ρ* such that dρ/dt = 0
- Interpretation: stable understanding (no new information)
- In practice: eigenvalues constant, trace constant

**Attractor:** ρ(t) → ρ* as t → ∞
- Interpretation: concept converges to stable meaning
- Example: "свобода" after long discussion settles on dominant facet

**Bifurcation:** Small change in discourse causes qualitative shift in ρ(t)
- Example: New facet emerges (eigenvalue ordering changes)
- Interpretation: semantic crisis or breakthrough

### 5.3 Lyapunov Exponents

**Measure of sensitivity to initial conditions:**
```
λ_Lyapunov = lim(t→∞) (1/t) log ||δρ(t)|| / ||δρ(0)||
```

**Interpretation:**
- λ > 0: chaotic semantic evolution (sensitive to discourse details)
- λ = 0: stable semantic evolution (robust to perturbations)
- λ < 0: dissipative (converges to attractor)

**In FVSC:** High λ for emotionally charged concepts, low λ for stable beliefs.

### 5.4 Phase Transitions

**Analogy to statistical mechanics:**
- Temperature ↔ discourse intensity (Trace(ρ(t)))
- Phase transition ↔ semantic shift (eigenvalue reordering)
- Order parameter ↔ dominant eigenvalue λ₁(t)

**Example:** "я" (self-concept)
- Low discourse intensity: fragmented self (high entropy)
- High discourse intensity: unified self (low entropy, λ₁ dominates)
- Phase transition: moment when self-concept crystallizes

---

## 6. Blockers and Dependencies

### 6.1 Hard Blockers

| Blocker | Reason | Status |
|---------|--------|--------|
| **T11: Morphological core** | Timestamp must come from message metadata; T11 handles data pipeline | Open |
| **T13: Frame extraction** | Temporal evolution of frames (nested ρ(t)) requires frame structure | Open |
| **Telegram metadata** | Need message timestamps; currently not extracted | Open |

### 6.2 Soft Blockers (Can Work Around)

| Issue | Workaround |
|-------|-----------|
| No real temporal data | Use synthetic data: simulate discourse with timestamps |
| Visualization library | Use matplotlib (already available) |
| Eigenvalue tracking overhead | Cache snapshots, don't recompute full history |

### 6.3 Design Decisions Needed

1. **Snapshot frequency:** Store ρ(t) at every judgment, or sample (e.g., every 10 messages)?
   - **Recommendation:** Every judgment (full fidelity), cache aggressively
   
2. **Interpolation:** How to estimate ρ(t) between snapshots?
   - **Options:** Linear interpolation, spline, or just use nearest snapshot
   - **Recommendation:** Nearest snapshot (simpler, sufficient for analysis)
   
3. **Decay model:** Power-law (current F3) or exponential?
   - **Current:** Power-law (ACT-R, Anderson 1993)
   - **Recommendation:** Keep power-law, but make decay_tau per-concept (learned from data)
   
4. **Eigenvalue tracking:** Full eigendecomposition at each t, or incremental?
   - **Current:** Full eigendecomposition
   - **Recommendation:** Full (d=50, so O(d³) ≈ 125K ops, acceptable)

---

## 7. Code Sketch

### 7.1 TemporalConcept Class

```python
@dataclass
class TemporalConcept(Concept):
    """Concept with temporal evolution tracking."""
    
    _rho_snapshots: dict[float, np.ndarray] = field(default_factory=dict)
    _eigenvalue_history: dict[float, np.ndarray] = field(default_factory=dict)
    _trace_history: list[tuple[float, float]] = field(default_factory=list)
    
    def rho_at(self, t: float) -> Optional[np.ndarray]:
        """Get ρ(t) — exact or nearest snapshot."""
        if t in self._rho_snapshots:
            return self._rho_snapshots[t]
        # Find nearest snapshot
        if not self._rho_snapshots:
            return None
        nearest_t = min(self._rho_snapshots.keys(), key=lambda x: abs(x - t))
        return self._rho_snapshots[nearest_t]
    
    def trace_at(self, t: float) -> float:
        """Trace(ρ(t))."""
        rho = self.rho_at(t)
        return np.trace(rho) if rho is not None else 0.0
    
    def eigenvalues_at(self, t: float) -> np.ndarray:
        """Eigenvalues at time t."""
        if t in self._eigenvalue_history:
            return self._eigenvalue_history[t]
        nearest_t = min(self._eigenvalue_history.keys(), 
                       key=lambda x: abs(x - t))
        return self._eigenvalue_history[nearest_t]
    
    def semantic_drift(self, t1: float, t2: float) -> float:
        """Measure semantic change between t1 and t2.
        
        Uses Frobenius norm of eigenvalue difference:
        drift = ||λ(t2) - λ(t1)|| / ||λ(t1)||
        """
        eigs1 = self.eigenvalues_at(t1)
        eigs2 = self.eigenvalues_at(t2)
        if eigs1 is None or eigs2 is None:
            return 0.0
        # Pad to same length
        n = max(len(eigs1), len(eigs2))
        e1 = np.pad(eigs1, (0, n - len(eigs1)))
        e2 = np.pad(eigs2, (0, n - len(eigs2)))
        norm1 = np.linalg.norm(e1)
        if norm1 < 1e-12:
            return 0.0
        return float(np.linalg.norm(e2 - e1) / norm1)
    
    def add_component_temporal(self, vector: np.ndarray, weight: float,
                               judgment: Judgment):
        """Add component and record temporal snapshot."""
        # 1. Add to components (existing consolidation logic)
        self.add_component(vector, weight, judgment)
        
        # 2. Record snapshot at judgment.timestamp
        t = judgment.timestamp
        rho_t = self.rho  # recomputed after add_component
        if rho_t is not None:
            self._rho_snapshots[t] = rho_t.copy()
            eigs = np.linalg.eigvalsh(rho_t)
            self._eigenvalue_history[t] = eigs
            self._trace_history.append((t, float(np.trace(rho_t))))
    
    def tacit_knowledge_score(self) -> float:
        """Fraction of concept that is tacit (consolidated)."""
        now = time.time()
        tacit_weight = 0.0
        total_weight = 0.0
        for c in self.components:
            if c.archived:
                continue
            age = now - c.timestamp
            # Older components with high activation_count = tacit
            tacit_factor = min(1.0, age / (30 * 86400))  # saturate at 30 days
            tacit_weight += c.weight * c.activation_count * tacit_factor
            total_weight += c.weight * c.activation_count
        return tacit_weight / total_weight if total_weight > 0 else 0.0
    
    def embodiment_score(self) -> float:
        """How embodied is this concept?
        High trace + low entropy + stable eigenvalues = embodied.
        """
        if not self._trace_history:
            return 0.0
        
        # Average trace
        avg_trace = np.mean([tr for _, tr in self._trace_history])
        
        # Entropy (use current rho_norm)
        rho_n = self.rho_norm
        if rho_n is None:
            entropy = 0.0
        else:
            entropy = von_neumann_entropy(rho_n)
        
        # Eigenvalue stability (low variance = stable)
        if len(self._eigenvalue_history) < 2:
            eig_stability = 1.0
        else:
            eigs_list = list(self._eigenvalue_history.values())
            eig_variance = np.var([e[0] for e in eigs_list if len(e) > 0])
            eig_stability = 1.0 / (1.0 + eig_variance)
        
        # Combine: high trace, low entropy, high stability
        embodiment = (avg_trace / 10.0) * (1.0 - entropy / 5.0) * eig_stability
        return float(np.clip(embodiment, 0.0, 1.0))
```

### 7.2 Visualization Functions

```python
def plot_trace_evolution(concept: TemporalConcept, title: str = None):
    """Plot Trace(ρ(t)) over time."""
    import matplotlib.pyplot as plt
    
    if not concept._trace_history:
        print(f"No temporal data for {concept.term}")
        return
    
    times, traces = zip(*concept._trace_history)
    plt.figure(figsize=(10, 4))
    plt.plot(times, traces, marker='o', linestyle='-', linewidth=2)
    plt.xlabel('Time (s)')
    plt.ylabel('Trace(ρ(t))')
    plt.title(title or f'Intensity Evolution: {concept.term}')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    return plt

def plot_eigenvalue_trajectories(concept: TemporalConcept, title: str = None):
    """Plot eigenvalue trajectories λᵢ(t)."""
    import matplotlib.pyplot as plt
    
    if not concept._eigenvalue_history:
        print(f"No eigenvalue data for {concept.term}")
        return
    
    times = sorted(concept._eigenvalue_history.keys())
    max_eigs = max(len(concept._eigenvalue_history[t]) for t in times)
    
    plt.figure(figsize=(10, 6))
    for i in range(min(max_eigs, 5)):  # plot top 5 eigenvalues
        eigs_at_times = [concept._eigenvalue_history[t][i] 
                        if i < len(concept._eigenvalue_history[t]) else 0
                        for t in times]
        plt.plot(times, eigs_at_times, marker='o', label=f'λ_{i+1}(t)')
    
    plt.xlabel('Time (s)')
    plt.ylabel('Eigenvalue')
    plt.title(title or f'Eigenvalue Trajectories: {concept.term}')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    return plt

def plot_semantic_drift_heatmap(space: SemanticSpace, title: str = None):
    """Heatmap: Concepts × Time, color = Trace(ρ(t))."""
    import matplotlib.pyplot as plt
    
    # Collect all timestamps
    all_times = set()
    for concept in space.concepts.values():
        if isinstance(concept, TemporalConcept):
            all_times.update(concept._eigenvalue_history.keys())
    
    if not all_times:
        print("No temporal data")
        return
    
    times = sorted(all_times)
    concepts = [c for c in space.concepts.values() 
               if isinstance(c, TemporalConcept) and c._trace_history]
    
    # Build matrix
    matrix = np.zeros((len(concepts), len(times)))
    for i, concept in enumerate(concepts):
        for j, t in enumerate(times):
            matrix[i, j] = concept.trace_at(t)
    
    plt.figure(figsize=(12, 6))
    plt.imshow(matrix, aspect='auto', cmap='hot', interpolation='nearest')
    plt.colorbar(label='Trace(ρ(t))')
    plt.xlabel('Time')
    plt.ylabel('Concept')
    plt.yticks(range(len(concepts)), [c.term for c in concepts])
    plt.title(title or 'Semantic Drift Heatmap')
    plt.tight_layout()
    return plt
```

---

## 8. Theory Summary

### Key Insights

1. **Personality is a dynamical system:** Concepts evolve through discourse, not static.

2. **Trace(ρ(t)) = intensity:** Captures emotional/experiential dimension missing from static ρ.

3. **Eigenvalue trajectories = semantic drift:** Shows how meaning facets reorder and consolidate.

4. **Temporal structure reveals tacit knowledge:** Old, consolidated components vs. recent, explicit ones.

5. **Embodiment = high trace + low entropy + stable eigenvalues:** Grounded concepts behave differently from abstract ones.

6. **Dynamical systems theory applies:** Liouville-von Neumann equation, attractors, bifurcations, Lyapunov exponents.

### Theoretical Foundations

- **Quantum mechanics:** Liouville-von Neumann equation, density matrix formalism
- **Dynamical systems:** Attractors, bifurcations, phase transitions
- **Cognitive science:** ACT-R (power-law decay), Complementary Learning Systems (consolidation)
- **Phenomenology:** Qualia as intensity, embodiment as grounding
- **Linguistics:** Semantic drift, polysemy evolution

---

## 9. Next Steps

### Immediate (Can Start Now)

1. **Ensure timestamps in Judgment:** Verify `tree_extractor.py` sets `judgment.timestamp` from message metadata
2. **Implement TemporalConcept class:** Add to `density_core.py`
3. **Add visualization functions:** Create `temporal_visualization.py`
4. **Synthetic data test:** Generate discourse with timestamps, verify eigenvalue tracking

### Blocked by T11/T13

1. **Real temporal data:** Need T11 (morphological core) to extract message timestamps reliably
2. **Frame-level temporal evolution:** T13 (frame extraction) enables ρ(t) for nested frames
3. **Discourse dynamics:** T13 enables tracking how frames interact over time

### Research Questions

1. **Optimal snapshot frequency:** Every judgment vs. sampled?
2. **Decay model per-concept:** Should τ be learned from data?
3. **Eigenvalue interpolation:** Linear, spline, or nearest-neighbor?
4. **Qualia quantification:** Is dTrace/dt + eigenvalue_volatility the right formula?

---

## 10. Blockers List

### Critical Path

- [ ] T11: Morphological core (pymorphy2 + case grammar)
- [ ] T13: Frame extraction (nested ρ(t))
- [ ] Telegram metadata extraction (message timestamps)

### Implementation

- [ ] TemporalConcept class in density_core.py
- [ ] Visualization module (temporal_visualization.py)
- [ ] Synthetic discourse generator (for testing)
- [ ] Eigenvalue tracking integration

### Validation

- [ ] Unit tests for ρ(t) computation
- [ ] Visualization tests (plot generation)
- [ ] Synthetic discourse test (verify eigenvalue trajectories)
- [ ] Real data test (once T11 complete)

---

## References

### Quantum Mechanics & Density Matrices
- Preskill, J. (2015). "Quantum Computation." Caltech lecture notes.
- Bengtsson, I., & Życzkowski, K. (2017). "Geometry of Quantum States." Cambridge University Press.

### Dynamical Systems
- Strogatz, S. H. (2015). "Nonlinear Dynamics and Chaos." Westview Press.
- Hirsch, M. W., Smale, S., & Devaney, R. L. (2013). "Differential Equations, Dynamical Systems, and an Introduction to Chaos." Academic Press.

### Cognitive Science
- Anderson, J. R. (1993). "Rules of the Mind." Lawrence Erlbaum Associates.
- McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). "Why there are complementary learning systems in the hippocampus and neocortex." Psychological Review, 102(3), 419.

### Phenomenology & Embodiment
- Merleau-Ponty, M. (1962). "Phenomenology of Perception." Routledge.
- Lakoff, G., & Johnson, M. (1980). "Metaphors We Live By." University of Chicago Press.

### Linguistics
- Fillmore, C. J. (1968). "The Case for Case." In E. Bach & R. T. Harms (Eds.), Universals in Linguistic Theory. Holt, Rinehart and Winston.
- Apresjan, J. D. (1995). "Integral Description of Language and Systemic Lexicography." Oxford University Press.

