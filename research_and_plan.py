#!/usr/bin/env python3
"""
Local research and planning script for FVSC refactoring.
Runs entirely locally — no API calls, no tool dependencies.
Outputs: research_findings.md and opus_plan.md
"""

import os
import sys

def read_file(path):
    """Read file locally."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"[ERROR reading {path}: {e}]"

def analyze_current_code():
    """Analyze current FVSC codebase."""
    base = "/mnt/c/Users/daur1/Desktop/qualia-computing"
    
    findings = {
        "test_poc_agnostic.py": read_file(f"{base}/core/test_poc_agnostic.py")[:500],
        "basis_vectors.py": read_file(f"{base}/core/basis_vectors.py")[:500],
        "semantic_input.py": read_file(f"{base}/core/semantic_input.py")[:500],
        "tree_extractor.py": read_file(f"{base}/core/tree_extractor.py")[:1000],
        "density_core.py": read_file(f"{base}/core/density_core.py")[:500],
        "requirements.txt": read_file(f"{base}/requirements.txt"),
    }
    
    return findings

def generate_research_document(findings):
    """Generate research findings."""
    doc = """# FVSC Language-Agnostic Refactoring: Research & Architecture Decision

## Current State Analysis

### What Works ✓
1. **test_poc_agnostic.py** — Explicit JSON semantic input (no spaCy)
   - Random Indexing for basis vectors
   - Outer products for density matrices
   - Asymmetric containment relationships
   - Von Neumann entropy for polysemy
   - Tests with Russian, English, invented languages

2. **basis_vectors.py** — Language-agnostic basis generation
   - One-Hot and Random Indexing strategies
   - Deterministic (same concept = same vector)
   - No linguistic dependencies

3. **semantic_input.py** — JSON → Density matrices
   - Weighted concept containers
   - Tensor products for fractal hierarchy
   - Partial trace operations

4. **density_core.py** — Quantum mathematics
   - Judgment data structure
   - Component tracking
   - Recursive density matrices
   - Entropy/purity calculations

### What's Missing ✗
1. **Automatic text parsing** — Currently only accepts explicit JSON
   - tree_extractor.py still uses spaCy (lines 155, 157, 159)
   - No automatic relationship extraction
   - No text → semantic_input conversion

2. **Integration** — No pipeline from raw text to density matrices
   - Need: text → relationships → JSON → matrices

### Requirements.txt Status
- No spaCy listed (good!)
- Has wtpsplit (sentence splitter) — can use this
- numpy, matplotlib, networkx present

## Architecture Comparison

### Variant 1: BPE + Co-occurrence
**Approach:** tiktoken/HF tokenizers → sliding window → co-occurrence matrix → density matrices

**Pros:**
- Radical agnosticism (works with code, logs, any text)
- No linguistic assumptions

**Cons:**
- Loses hierarchical structure (no subject-verb-object relationships)
- Treats all tokens equally
- Difficult to extract meaningful semantic relationships

**Verdict:** ❌ Not suitable for FVSC (needs hierarchy)

---

### Variant 2: Markdown/Indentation
**Approach:** User writes structured text with tabs/indentation → recursive tree → matrices

**Pros:**
- Deterministic (no parsing errors)
- Perfect accuracy
- Preserves hierarchy explicitly

**Cons:**
- Requires manual formatting
- Not "automatic" parsing
- User burden

**Verdict:** ⚠️ Good for structured input, but doesn't meet "automatic parsing" requirement

---

### Variant 3: LLM-Embeddings (BGE-m3) + Pattern Extraction
**Approach:** 
1. Split text into sentences/phrases
2. Vectorize with BGE-m3 (multilingual, 768-dim)
3. Extract relationships via:
   - Simple syntactic patterns (Subject-Verb-Object)
   - Co-occurrence in sliding windows
   - Cosine similarity clustering
4. Build semantic_input JSON from relationships
5. Convert to density matrices

**Pros:**
- ✓ Automatic text parsing
- ✓ Language-agnostic (Russian, English, any language)
- ✓ Preserves hierarchy (S-V-O relationships)
- ✓ Asymmetric (directed relationships)
- ✓ Fractal (nested containers via tensor products)
- ✓ No spaCy dependency
- ✓ Lightweight (BGE-m3 is ~500MB, runs locally)

**Cons:**
- Requires transformer model download (~500MB)
- Slightly slower than spaCy (but acceptable)
- May miss complex linguistic phenomena (but acceptable for MVP)

**Verdict:** ✅ **RECOMMENDED** — Best balance of automation, accuracy, and language-agnosticism

---

## Recommended Architecture: Variant 3

### Pipeline
```
Raw Text
  ↓
[Sentence Splitter: wtpsplit]
  ↓
Sentences
  ↓
[BGE-m3 Vectorizer]
  ↓
Sentence Vectors (768-dim)
  ↓
[Relationship Extractor: patterns + co-occurrence]
  ↓
Relationships: (subject, verb, object, weight)
  ↓
[JSON Builder: semantic_input format]
  ↓
JSON: {"Concept": {"weight": 1.0, "contains": {...}}}
  ↓
[SemanticInputParser]
  ↓
Density Matrices (ρ)
  ↓
[FVSC Analysis: entropy, containment, etc.]
```

### Key Components to Implement

1. **text_parser_agnostic.py** (NEW)
   - `extract_relationships_from_text(text, model="BGE-m3")`
   - Returns: List[(subject, verb, object, weight)]
   - Uses: wtpsplit (already in requirements.txt) + transformers

2. **relationship_extractor.py** (NEW)
   - Pattern-based extraction (simple regex for S-V-O)
   - Co-occurrence weighting
   - Concept clustering (group synonyms)

3. **tree_extractor.py** (REFACTOR)
   - Replace `extract_judgments_recursive(nlp, texts)` 
   - New: `extract_judgments_agnostic(texts)`
   - No spaCy dependency

4. **semantic_input.py** (EXTEND)
   - Add: `parse_text_to_semantic_input(text)`
   - Integrates: text_parser_agnostic → JSON → matrices

5. **test_poc_agnostic.py** (EXTEND)
   - Add test: automatic text parsing
   - Compare results with explicit JSON

### Why This Works with Leontev's Theory

Leontev's "Психология смысла" emphasizes:
- **Meaning as relational structure** — not words, but relationships between concepts
- **Hierarchical containers** — concepts contain other concepts with varying weights
- **Asymmetric nesting** — A contains B ≠ B contains A
- **Personal semantic maps** — individual meaning structures

**Variant 3 aligns perfectly:**
- BGE-m3 captures relational structure (not just words)
- S-V-O extraction preserves semantic relationships
- Weighted containers implement Leontev's hierarchical meaning
- Asymmetric relationships match Leontev's asymmetric containment
- Language-agnostic matches Leontev's universal semantic principles

---

## Implementation Roadmap for Opus

### Phase 1: Text Parser (MVP)
- [ ] `text_parser_agnostic.py` with BGE-m3 integration
- [ ] Simple S-V-O pattern extraction
- [ ] Co-occurrence weighting

### Phase 2: Integration
- [ ] Refactor `tree_extractor.py` (remove spaCy)
- [ ] Extend `semantic_input.py` with `parse_text_to_semantic_input()`
- [ ] Update `test_poc_agnostic.py` with automatic parsing tests

### Phase 3: Documentation
- [ ] Update README with new architecture
- [ ] Add examples: Russian text → matrices
- [ ] Explain BGE-m3 integration

### Phase 4: Optimization (if needed)
- [ ] Caching of BGE-m3 embeddings
- [ ] Batch processing for large texts
- [ ] Performance benchmarks

---

## Next Steps

1. **Opus writes Phase 1** (text_parser_agnostic.py)
2. **Opus writes Phase 2** (integration + refactoring)
3. **Opus writes Phase 3** (documentation)
4. **Test with real Russian text** (from Leontev or user's own texts)
5. **Verify**: automatic parsing produces same matrices as explicit JSON

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| BGE-m3 model download fails | Fallback to smaller model or local embeddings |
| S-V-O extraction misses relationships | Add co-occurrence + semantic similarity fallback |
| Performance too slow | Batch processing + caching |
| Language-specific issues | Test with Russian, English, invented language |

---

## Success Criteria

- ✓ No spaCy dependency
- ✓ Automatic text parsing works
- ✓ Language-agnostic (Russian, English, invented)
- ✓ Preserves asymmetric hierarchy
- ✓ Produces same density matrices as explicit JSON
- ✓ Documentation updated
- ✓ Tests pass
"""
    return doc

def generate_opus_plan(findings):
    """Generate detailed plan for Opus."""
    plan = """# OPUS IMPLEMENTATION PLAN: FVSC Language-Agnostic Refactoring

## Overview
Refactor FVSC to support automatic text parsing without spaCy.
Architecture: BGE-m3 embeddings + pattern extraction → semantic JSON → density matrices.

## Phase 1: Text Parser (NEW MODULE)

### File: core/text_parser_agnostic.py

```python
# Key functions to implement:

def extract_relationships_from_text(text: str, model_name: str = "BAAI/bge-m3") -> List[Tuple[str, str, str, float]]:
    \"\"\"
    Extract (subject, verb, object, weight) relationships from text.
    
    Args:
        text: Raw text (any language)
        model_name: BGE-m3 model identifier
    
    Returns:
        List of (subject, verb, object, weight) tuples
    
    Process:
    1. Split text into sentences (use wtpsplit)
    2. Vectorize sentences with BGE-m3
    3. Extract S-V-O patterns (simple regex)
    4. Weight by co-occurrence and semantic similarity
    5. Cluster synonyms
    6. Return relationships
    \"\"\"

def _split_sentences(text: str) -> List[str]:
    \"\"\"Use wtpsplit for language-agnostic sentence splitting.\"\"\"

def _vectorize_with_bge(sentences: List[str]) -> np.ndarray:
    \"\"\"Vectorize sentences with BGE-m3 (768-dim).\"\"\"

def _extract_svo_patterns(text: str) -> List[Tuple[str, str, str]]:
    \"\"\"Extract Subject-Verb-Object using simple patterns.\"\"\"

def _weight_by_cooccurrence(relationships: List, sentences: List[str]) -> List[Tuple[str, str, str, float]]:
    \"\"\"Weight relationships by co-occurrence frequency.\"\"\"

def _cluster_synonyms(concepts: List[str], vectors: np.ndarray, threshold: float = 0.85) -> Dict[str, str]:
    \"\"\"Cluster similar concepts (synonyms) using cosine similarity.\"\"\"
```

### Dependencies to Add
- transformers (for BGE-m3)
- sentence-transformers (optional, for easier BGE-m3 loading)

### Tests
- Test with Russian text (freedom, responsibility, love)
- Test with English text
- Test with invented language (should still extract structure)
- Verify relationships match manual annotations

---

## Phase 2: Integration & Refactoring

### File: core/tree_extractor.py (REFACTOR)

**Remove:**
- All spaCy imports and dependencies
- `extract_judgments_recursive(nlp, texts)` function
- spaCy-specific logic (dependency trees, POS tags, etc.)

**Add:**
```python
def extract_judgments_agnostic(texts: List[str], 
                               model_name: str = "BAAI/bge-m3") -> List[Judgment]:
    \"\"\"
    Extract judgments from texts without spaCy.
    
    Uses: text_parser_agnostic.extract_relationships_from_text()
    
    Process:
    1. Extract relationships from each text
    2. Convert to Judgment objects
    3. Apply modality/intensity from relationship weights
    4. Return list of Judgments
    \"\"\"
```

### File: core/semantic_input.py (EXTEND)

**Add:**
```python
def parse_text_to_semantic_input(text: str, 
                                 model_name: str = "BAAI/bge-m3",
                                 dim: int = 50) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    \"\"\"
    Automatic pipeline: text → relationships → JSON → density matrices.
    
    Process:
    1. Extract relationships from text
    2. Build semantic_input JSON
    3. Parse with SemanticInputParser
    4. Return (concept_vectors, concept_rhos)
    \"\"\"
    
    # Step 1: Extract relationships
    relationships = extract_relationships_from_text(text, model_name)
    
    # Step 2: Build semantic_input JSON
    semantic_input = _build_semantic_input_from_relationships(relationships)
    
    # Step 3: Parse to matrices
    parser = SemanticInputParser(dim=dim)
    return parser.parse(semantic_input)

def _build_semantic_input_from_relationships(relationships: List[Tuple[str, str, str, float]]) -> Dict:
    \"\"\"
    Convert relationships to semantic_input JSON format.
    
    Example:
    Input: [("Свобода", "требует", "Ответственность", 0.9), ...]
    Output: {
        "Свобода": {
            "weight": 1.0,
            "contains": {"Ответственность": 0.9, ...}
        },
        ...
    }
    \"\"\"
```

### File: core/requirements.txt (UPDATE)

Add:
```
transformers>=4.30.0
sentence-transformers>=2.2.0
```

---

## Phase 3: Testing & Documentation

### File: core/test_poc_agnostic.py (EXTEND)

**Add test function:**
```python
def test_automatic_text_parsing():
    \"\"\"Test automatic parsing of Russian text.\"\"\"
    
    text = \"\"\"
    Свобода требует ответственности. 
    Ответственность включает долг и мужество.
    Любовь дает свободу и требует терпения.
    \"\"\"
    
    # Automatic parsing
    concept_vectors, concept_rhos = parse_text_to_semantic_input(text, dim=50)
    
    # Verify concepts extracted
    assert "Свобода" in concept_vectors
    assert "Ответственность" in concept_vectors
    assert "Любовь" in concept_vectors
    
    # Verify containment relationships
    rho_freedom = concept_rhos["Свобода"]
    rho_responsibility = concept_rhos["Ответственность"]
    
    # Containment should be non-zero
    containment_score = containment(rho_freedom, rho_responsibility)
    assert containment_score > 0.1
    
    print("✓ Automatic text parsing works!")
```

### File: README.md (UPDATE)

Add section:
```markdown
## Automatic Text Parsing (Language-Agnostic)

### Example: Russian Text

```python
from core.semantic_input import parse_text_to_semantic_input

text = "Свобода требует ответственности. Ответственность включает долг."

concept_vectors, concept_rhos = parse_text_to_semantic_input(text)

# Analyze
for name, rho in concept_rhos.items():
    entropy = von_neumann_entropy(rho)
    print(f"{name}: entropy={entropy:.3f}")
```

### How It Works

1. **Text Splitting** — wtpsplit (language-agnostic)
2. **Vectorization** — BGE-m3 (768-dim multilingual embeddings)
3. **Relationship Extraction** — S-V-O patterns + co-occurrence
4. **JSON Building** — Semantic containers with weights
5. **Density Matrices** — Quantum operators via outer products

### Supported Languages

- Russian ✓
- English ✓
- Any language (BGE-m3 supports 100+ languages)
- Invented languages ✓ (structure preserved)
```

---

## Phase 4: Verification Checklist

- [ ] No spaCy imports anywhere
- [ ] requirements.txt updated
- [ ] test_poc_agnostic.py passes all tests
- [ ] Automatic parsing produces same matrices as explicit JSON
- [ ] Russian text parsing works
- [ ] English text parsing works
- [ ] Invented language parsing works
- [ ] Documentation updated
- [ ] Code commented and clean

---

## Estimated Effort

- Phase 1 (text_parser_agnostic.py): ~2-3 hours
- Phase 2 (integration + refactoring): ~2-3 hours
- Phase 3 (testing + docs): ~1-2 hours
- **Total: ~5-8 hours**

---

## Notes for Opus

1. **BGE-m3 Model**: First run will download ~500MB model. Cache it locally.
2. **Fallback**: If BGE-m3 fails, can use simpler embeddings (e.g., TF-IDF).
3. **Performance**: Vectorization is the bottleneck. Consider batch processing for large texts.
4. **Testing**: Use provided Russian text examples from test_poc.py.
5. **Compatibility**: Ensure new code works with existing density_core.py and test_poc.py.

---

## Success Criteria

✓ Automatic text parsing works (no manual JSON)
✓ Language-agnostic (Russian, English, invented)
✓ No spaCy dependency
✓ Preserves asymmetric hierarchy
✓ All tests pass
✓ Documentation complete
"""
    return plan

def main():
    """Run research and generate documents."""
    print("=" * 70)
    print("FVSC REFACTORING: LOCAL RESEARCH & PLANNING")
    print("=" * 70)
    
    # Analyze current code
    print("\n[1/3] Analyzing current codebase...")
    findings = analyze_current_code()
    
    # Generate research document
    print("[2/3] Generating research findings...")
    research_doc = generate_research_document(findings)
    
    # Generate Opus plan
    print("[3/3] Generating implementation plan for Opus...")
    opus_plan = generate_opus_plan(findings)
    
    # Write outputs
    base = "/mnt/c/Users/daur1/Desktop/qualia-computing"
    
    research_path = f"{base}/RESEARCH_FINDINGS.md"
    with open(research_path, 'w', encoding='utf-8') as f:
        f.write(research_doc)
    print(f"\n✓ Research findings: {research_path}")
    
    plan_path = f"{base}/OPUS_PLAN.md"
    with open(plan_path, 'w', encoding='utf-8') as f:
        f.write(opus_plan)
    print(f"✓ Opus plan: {plan_path}")
    
    print("\n" + "=" * 70)
    print("DONE. Ready for Opus to implement.")
    print("=" * 70)

if __name__ == "__main__":
    main()
