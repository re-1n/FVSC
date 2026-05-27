# T14: Temporal Evolution — Blockers, Issues, and Design Decisions

**Status:** Research complete, implementation ready, blocked on T11/T13  
**Date:** 2026-05-16

---

## Critical Path Blockers

### 1. T11: Morphological Core (HARD BLOCKER)

**Why it blocks T14:**
- T14 requires accurate message timestamps from Telegram data
- Currently timestamps are not extracted from message metadata
- T11 (pymorphy2 + case grammar) handles the data pipeline and metadata extraction
- Without T11, we have no reliable temporal data

**Status:** Open (high priority)  
**Workaround:** Use synthetic discourse data with simulated timestamps for testing

**Action:** Coordinate with T11 implementation to ensure:
- Message timestamps extracted from Telegram JSON
- Passed through to Judgment objects
- Preserved in SemanticSpace

---

### 2. T13: Frame Extraction (SOFT BLOCKER)

**Why it blocks T14:**
- Current flat S→V→O format cannot represent nested temporal evolution
- Example: "я уверен что свобода важна" (I'm confident that freedom is important)
  - Static ρ: loses modal envelope
  - Temporal ρ(t): can track how confidence and importance evolve separately
- T13 enables frame-level ρ(t) tracking

**Status:** Open (medium priority)  
**Workaround:** Implement T14 for flat judgments first, extend to frames later

**Action:** Design frame-level temporal tracking:
- Each frame has its own ρ(t)
- Modal envelopes modify child frame's modality over time
- Enables tracking "how confident am I becoming about X?"

---

### 3. Telegram Metadata Extraction (HARD BLOCKER)

**Current state:**
- Telegram JSON exports contain `date` field (Unix timestamp)
- Not currently extracted or used
- All Judgment objects get `timestamp=time.time()` (processing time, not message time)

**Required:**
- Parse `date` from Telegram JSON
- Pass to tree_extractor.py
- Set `judgment.timestamp = message_date` (not processing time)

**Status:** Open  
**Workaround:** Manually assign timestamps in test data

---

## Implementation Issues

### Issue 1: Snapshot Storage Memory Overhead

**Problem:**
- Storing full ρ(t) snapshot at every judgment
- For d=50: each snapshot = 50×50 = 2500 floats = 20KB
- 1000 judgments = 20MB per concept
- 100 concepts = 2GB total

**Solutions:**
1. **Sparse snapshots:** Store every Nth judgment (e.g., every 10)
   - Pros: Reduces memory 10×
   - Cons: Loses temporal resolution
   
2. **Incremental storage:** Store only eigenvalues + trace, recompute ρ(t) on demand
   - Pros: 100× memory reduction
   - Cons: Slower queries, need to store component history
   
3. **Compression:** Use low-rank approximation (keep top-k eigenvalues)
   - Pros: 50% memory reduction
   - Cons: Loses information about small eigenvalues

**Recommendation:** Start with solution 1 (sparse snapshots, every 10 judgments), optimize later if needed.

**Implementation:**
```python
def add_component_temporal(self, vector, weight, judgment):
    self.add_component(vector, weight, judgment)
    
    # Only snapshot every N judgments
    if len(self._trace_history) % 10 == 0:
        t = judgment.timestamp
        rho_t = self.rho
        if rho_t is not None:
            self._rho_snapshots[t] = rho_t.copy()
            # ... rest of snapshot logic
```

---

### Issue 2: Eigenvalue Ordering Ambiguity

**Problem:**
- Eigenvalues are unordered (eigensolver returns them in arbitrary order)
- λ₁(t₁) might correspond to different facet than λ₁(t₂)
- Makes trajectory tracking unreliable

**Example:**
```
t₁: λ = [0.6, 0.3, 0.1]  (political, personal, abstract)
t₂: λ = [0.5, 0.4, 0.1]  (abstract, personal, political) — reordered!
```

**Solutions:**
1. **Always sort descending:** λ₁ ≥ λ₂ ≥ λ₃ (current implementation)
   - Pros: Simple, deterministic
   - Cons: Loses facet identity (can't track "political facet" specifically)
   
2. **Track eigenvectors:** Match eigenvectors across time using cosine similarity
   - Pros: Preserves facet identity
   - Cons: Computationally expensive, fragile to numerical errors
   
3. **Hybrid:** Sort by eigenvalue, but track eigenvector direction
   - Pros: Best of both worlds
   - Cons: More complex

**Recommendation:** Use solution 1 (sort descending) for now. Add eigenvector tracking in v2 if needed.

---

### Issue 3: Decay Model Interaction with Temporal Tracking

**Problem:**
- Current F3 (power-law decay) modifies weights dynamically
- ρ(t) computed at time t includes decay
- But decay depends on "now" (current time)
- Makes historical ρ(t) non-reproducible

**Example:**
```
Component added at t=0 with weight w₀
ρ(t=100) computed at "now=100": includes decay factor (1 + 100/τ)^{-0.5}
ρ(t=100) computed at "now=200": includes decay factor (1 + 200/τ)^{-0.5}
Result: ρ(t=100) changes depending on when you query it!
```

**Solutions:**
1. **Snapshot at query time:** Store (t, now, ρ) tuples
   - Pros: Accurate, reproducible
   - Cons: Explodes storage (need snapshot for each (t, now) pair)
   
2. **Freeze decay at snapshot time:** When storing ρ(t), also store "now" value
   - Pros: Reproducible, reasonable storage
   - Cons: Can't recompute with different decay parameters
   
3. **Disable decay for historical analysis:** Use undecayed ρ(t) for temporal tracking
   - Pros: Simple, reproducible
   - Cons: Loses decay information

**Recommendation:** Use solution 2 (freeze decay at snapshot time).

**Implementation:**
```python
@dataclass
class TemporalSnapshot:
    t: float              # judgment timestamp
    now: float            # snapshot time (when ρ was computed)
    rho: np.ndarray       # density matrix
    eigs: np.ndarray      # eigenvalues
    trace: float          # trace value

def add_component_temporal(self, vector, weight, judgment):
    self.add_component(vector, weight, judgment)
    
    t = judgment.timestamp
    now = time.time()
    rho_t = self.rho
    
    snapshot = TemporalSnapshot(
        t=t, now=now, rho=rho_t.copy(),
        eigs=np.linalg.eigvalsh(rho_t),
        trace=np.trace(rho_t)
    )
    self._snapshots[t] = snapshot
```

---

### Issue 4: Visualization Performance

**Problem:**
- Plotting 100 concepts × 1000 timestamps = 100K data points
- Matplotlib struggles with large datasets
- Interactive exploration becomes slow

**Solutions:**
1. **Downsampling:** Plot every Nth point
   - Pros: Fast, simple
   - Cons: Loses detail
   
2. **Aggregation:** Group by time window (e.g., hourly), plot mean/std
   - Pros: Preserves trends, reduces points
   - Cons: Loses individual events
   
3. **Interactive plotting:** Use Plotly or Bokeh
   - Pros: Zoom, pan, hover details
   - Cons: Requires additional dependency

**Recommendation:** Start with downsampling (every 10th point), add Plotly support in v2.

---

## Design Decisions Needed

### Decision 1: Snapshot Frequency

**Options:**
- A) Every judgment (full fidelity, high memory)
- B) Every 10 judgments (balanced)
- C) Every hour (low memory, loses detail)
- D) Adaptive (more frequent during high-activity periods)

**Recommendation:** Option B (every 10 judgments)
- Rationale: Balances memory and temporal resolution
- Can be tuned per-concept based on activity level

---

### Decision 2: Interpolation Strategy

**Options:**
- A) Nearest neighbor (use closest snapshot)
- B) Linear interpolation (blend between snapshots)
- C) Spline interpolation (smooth curve)
- D) No interpolation (only query at snapshot times)

**Recommendation:** Option A (nearest neighbor)
- Rationale: Simplest, sufficient for analysis
- Density matrices don't interpolate well anyway (not a vector space)

---

### Decision 3: Decay Model Per-Concept

**Options:**
- A) Global τ (same for all concepts)
- B) Per-concept τ (learned from data)
- C) Adaptive τ (depends on concept activity)

**Recommendation:** Option A initially, upgrade to B in v2
- Rationale: Simpler to implement, sufficient for testing
- Can learn τ from consolidation patterns later

---

### Decision 4: Qualia Quantification Formula

**Current proposal:**
```
qualia_intensity = dTrace/dt + eigenvalue_volatility
```

**Alternative proposals:**
- A) Just dTrace/dt (simpler)
- B) Trace × entropy_change (captures ambiguity)
- C) Machine learning model (trained on annotated data)

**Recommendation:** Option A (just dTrace/dt) for v1
- Rationale: Simplest, interpretable
- Can add entropy_change in v2 if needed

---

## Testing Strategy

### Unit Tests

```python
def test_temporal_concept_creation():
    """Test TemporalConcept initialization."""
    
def test_add_component_temporal():
    """Test snapshot creation on component addition."""
    
def test_rho_at_interpolation():
    """Test nearest-neighbor interpolation."""
    
def test_semantic_drift_calculation():
    """Test drift metric."""
    
def test_embodiment_score():
    """Test embodiment calculation."""
    
def test_tacit_knowledge_score():
    """Test tacit knowledge calculation."""
```

### Integration Tests

```python
def test_synthetic_discourse():
    """Generate synthetic discourse with timestamps, verify eigenvalue tracking."""
    
def test_visualization_generation():
    """Test all visualization functions produce valid plots."""
    
def test_memory_usage():
    """Verify memory overhead is acceptable."""
```

### Validation Tests (Once T11 Complete)

```python
def test_real_telegram_data():
    """Test on real Telegram data with extracted timestamps."""
    
def test_semantic_drift_detection():
    """Verify drift detection identifies real semantic shifts."""
    
def test_embodiment_vs_abstract():
    """Verify embodied concepts score higher than abstract ones."""
```

---

## Validation Criteria

### Correctness
- [ ] Eigenvalue trajectories are monotonic (no sudden jumps)
- [ ] Trace(ρ(t)) is non-negative
- [ ] Entropy S(ρ(t)) is non-negative
- [ ] Embodiment score in [0, 1]
- [ ] Tacit knowledge score in [0, 1]

### Performance
- [ ] Snapshot creation < 10ms per judgment
- [ ] Query rho_at(t) < 1ms
- [ ] Visualization generation < 5s for 100 concepts

### Usability
- [ ] Plots are readable and informative
- [ ] Metrics are interpretable
- [ ] API is intuitive

---

## Open Research Questions

1. **Optimal decay model:** Should τ be per-concept? Per-context?
2. **Eigenvalue matching:** How to track individual facets across time?
3. **Qualia formula:** Is dTrace/dt + eigenvalue_volatility correct?
4. **Embodiment metric:** Should it include other factors (e.g., context diversity)?
5. **Semantic crisis detection:** What drift threshold indicates a real crisis?
6. **Consolidation dynamics:** How long does consolidation take? Is it exponential or power-law?

---

## Next Steps

### Immediate (Can Start Now)
1. Implement TemporalConcept class ✓ (done)
2. Implement visualization functions ✓ (done)
3. Create synthetic discourse generator (TODO)
4. Write unit tests (TODO)

### Blocked by T11
1. Extract Telegram timestamps
2. Test on real data
3. Validate embodiment/tacit knowledge metrics

### Blocked by T13
1. Implement frame-level ρ(t)
2. Track modal envelope evolution
3. Analyze nested semantic drift

### Future (v2+)
1. Eigenvector tracking for facet identity
2. Plotly interactive visualization
3. Per-concept decay learning
4. Semantic crisis detection algorithm
5. Consolidation dynamics analysis

---

## References

### Temporal Dynamics
- Strogatz, S. H. (2015). "Nonlinear Dynamics and Chaos." Westview Press.
- Hirsch, M. W., Smale, S., & Devaney, R. L. (2013). "Differential Equations, Dynamical Systems, and an Introduction to Chaos." Academic Press.

### Memory and Consolidation
- Anderson, J. R. (1993). "Rules of the Mind." Lawrence Erlbaum Associates.
- McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). "Why there are complementary learning systems in the hippocampus and neocortex." Psychological Review, 102(3), 419.

### Quantum Dynamics
- Preskill, J. (2015). "Quantum Computation." Caltech lecture notes.
- Lindblad, G. (1976). "On the generators of quantum dynamical semigroups." Communications in Mathematical Physics, 48(2), 119-130.
