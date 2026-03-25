"""
FVSC Density Matrix Core — Proof of Concept

Recursive density matrices for personal semantic mapping.
Each concept = density matrix (operator of density) in R^d.
Containment, polysemy, and fractal nesting — all from linear algebra.

No external dependencies beyond numpy.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Judgment:
    """A single extracted judgment: Subject → Verb → Object + properties."""
    subject: str
    verb: str
    object: str
    quality: str = "AFFIRMATIVE"      # AFFIRMATIVE | NEGATIVE
    modality: float = 1.0             # FACTUAL=1.0, EPISTEMIC=0.5, etc.
    intensity: float = 0.5
    timestamp: float = 0.0
    source_text: str = ""
    condition_id: Optional[int] = None       # links conditional pairs (if→then)
    condition_role: Optional[str] = None     # "ANTECEDENT" | "CONSEQUENT"
    anomaly_score: Optional[float] = None    # 0.0=normal, 1.0=max anomaly vs existing map


@dataclass
class Component:
    """A rank-1 component of a density matrix, with provenance."""
    vector: np.ndarray                # |v> in R^d
    weight: float
    judgment: Judgment
    timestamp: float = 0.0


@dataclass
class Concept:
    """A concept = density matrix + provenance components."""
    term: str
    components: list[Component] = field(default_factory=list)
    _rho: Optional[np.ndarray] = field(default=None, repr=False)
    _rho_recursive: Optional[np.ndarray] = field(default=None, repr=False)

    @property
    def rho(self) -> np.ndarray:
        """Direct density matrix (from judgments only, no recursion).
        NOT normalized — trace reflects total mass of the concept.
        """
        if self._rho is None:
            self._recompute_rho()
        return self._rho

    @property
    def rho_norm(self) -> np.ndarray:
        """Normalized rho (trace=1) for entropy/purity calculations."""
        r = self.rho
        if r is None:
            return None
        tr = np.trace(r)
        if tr < 1e-12:
            return r
        return r / tr

    @property
    def rho_deep(self) -> np.ndarray:
        """Recursive density matrix (after recursive deepening).
        NOT normalized — trace reflects mass.
        """
        if self._rho_recursive is not None:
            return self._rho_recursive
        return self.rho

    @property
    def rho_deep_norm(self) -> np.ndarray:
        """Normalized recursive rho for entropy/purity."""
        r = self.rho_deep
        if r is None:
            return None
        tr = np.trace(r)
        if tr < 1e-12:
            return r
        return r / tr

    def _recompute_rho(self):
        if not self.components:
            self._rho = None
            return
        d = self.components[0].vector.shape[0]
        rho = np.zeros((d, d))
        for c in self.components:
            v = c.vector.reshape(-1, 1)
            rho += c.weight * (v @ v.T)
        # NO normalization — trace = total mass
        self._rho = rho

    def invalidate(self):
        self._rho = None
        self._rho_recursive = None

    def add_component(self, vector: np.ndarray, weight: float, judgment: Judgment):
        self.components.append(Component(
            vector=vector, weight=weight,
            judgment=judgment, timestamp=judgment.timestamp
        ))
        self.invalidate()


# ---------------------------------------------------------------------------
# Core operations on density matrices
# ---------------------------------------------------------------------------

def trace_inner_product(rho_a: np.ndarray, rho_b: np.ndarray) -> float:
    """Tr(rho_A @ rho_B) — O(d^2) optimized."""
    return float(np.sum(rho_a * rho_b.T))


def containment(rho_a: np.ndarray, rho_b: np.ndarray) -> float:
    """How much does A contain B? = Tr(rho_A @ rho_B) / Tr(rho_A).
    Asymmetric: containment(A,B) != containment(B,A).
    """
    tr_a = np.trace(rho_a)
    if tr_a < 1e-12:
        return 0.0
    return trace_inner_product(rho_a, rho_b) / tr_a


def graded_hyponymy(rho_a: np.ndarray, rho_b: np.ndarray) -> float:
    """Bankova et al. 2019: degree to which A is contained in B.
    hyp(A,B) = 1 - sum(|lambda_i| for lambda_i < 0) / Tr(A)
    where lambda_i are eigenvalues of (B - A).
    """
    diff = rho_b - rho_a
    eigenvalues = np.linalg.eigvalsh(diff)
    negative_sum = sum(abs(lam) for lam in eigenvalues if lam < 0)
    tr_a = np.trace(rho_a)
    if tr_a < 1e-12:
        return 0.0
    return 1.0 - negative_sum / tr_a


def von_neumann_entropy(rho: np.ndarray) -> float:
    """S(rho) = -Tr(rho log rho). Measures polysemy.
    S=0: unambiguous (single facet). S>0: polysemous.
    """
    eigenvalues = np.linalg.eigvalsh(rho)
    eigenvalues = eigenvalues[eigenvalues > 1e-12]
    return float(-np.sum(eigenvalues * np.log(eigenvalues)))


def purity(rho: np.ndarray) -> float:
    """Tr(rho^2). 1=pure/unambiguous, 1/d=maximally ambiguous."""
    return float(np.trace(rho @ rho))


def facets(rho: np.ndarray, threshold: float = 0.05) -> list[tuple[float, np.ndarray]]:
    """Extract meaning facets as eigenvectors of rho.
    Returns [(eigenvalue, eigenvector), ...] sorted by eigenvalue desc.
    Only facets with eigenvalue > threshold are returned.
    """
    eigenvalues, eigenvectors = np.linalg.eigh(rho)
    pairs = []
    for i in range(len(eigenvalues) - 1, -1, -1):
        if eigenvalues[i] > threshold:
            pairs.append((float(eigenvalues[i]), eigenvectors[:, i]))
    return pairs


# ---------------------------------------------------------------------------
# Semantic space — manages concepts and their density matrices
# ---------------------------------------------------------------------------

PRONOUNS = {"я", "ты", "вы", "он", "она", "мы", "они", "оно", "это", "что", "кто",
             "который", "какой", "свой", "себя", "его", "её", "их", "нас", "вас",
             # quasi-pronouns and noise words (no independent semantic content)
             "то", "все", "всё", "всë", "нет", "да", "так", "тут", "там", "вот",
             "ничто", "нечто", "кое-что", "мм", "ну", "ага", "ладно", "окей",
             "целое", "весь", "сам", "такой", "другой", "каждый", "любой"}

# Self-identity verbs: "я являюсь X" → X goes into [self]
SELF_IDENTITY_VERBS = {"являться", "быть", "стать", "становиться", "считать",
                       "казаться", "оказаться", "выглядеть", "представлять"}

# Self-relation verbs: "я хочу X", "я люблю X" → X goes into [self] as relation
SELF_RELATION_VERBS = {"хотеть", "любить", "ненавидеть", "бояться",
                       "уметь", "понимать", "верить", "чувствовать",
                       "ощущать", "стремиться", "нуждаться", "ценить",
                       "предпочитать", "уважать", "презирать",
                       "искать", "ждать", "надеяться", "мечтать"}

SELF_DEPS = {"amod", "cop:это", "nmod:gen"}


class SemanticSpace:
    """The semantic space where concepts live as density matrices."""

    def __init__(self, dim: int = 50, seed_vectors: Optional[dict[str, np.ndarray]] = None,
                 min_components_for_query: int = 2):
        self.dim = dim
        self.concepts: dict[str, Concept] = {}
        self.seed_vectors = seed_vectors or {}
        self.min_components = min_components_for_query
        self._rng = np.random.default_rng(42)
        # Special Self container
        self.self_concept = Concept(term="[self]")

    def get_or_create(self, term: str) -> Concept:
        if term not in self.concepts:
            self.concepts[term] = Concept(term=term)
        return self.concepts[term]

    def get_term_vector(self, term: str) -> np.ndarray:
        """Get a base vector for a term. Uses seed if available, else deterministic hash."""
        if term in self.seed_vectors:
            v = self.seed_vectors[term]
            return v / (np.linalg.norm(v) + 1e-10)
        # Deterministic pseudo-random vector from term hash
        h = hash(term) % (2**31)
        rng = np.random.default_rng(h)
        v = rng.standard_normal(self.dim)
        return v / (np.linalg.norm(v) + 1e-10)

    def _role_transform(self, v: np.ndarray, role: str) -> np.ndarray:
        """Apply a deterministic role-dependent rotation to a vector.
        Different roles (subject, object, verb) get different transformations.
        This breaks symmetry: the same word in subject vs object position
        produces different vectors.
        """
        role_seed = hash(role) % (2**31)
        rng = np.random.default_rng(role_seed)
        # Random orthogonal matrix (deterministic from role)
        M = rng.standard_normal((self.dim, self.dim))
        Q, _ = np.linalg.qr(M)
        rotated = Q @ v
        return rotated / (np.linalg.norm(rotated) + 1e-10)

    def encode_judgment_for_subject(self, j: Judgment) -> np.ndarray:
        """Encode judgment from the SUBJECT's perspective.
        "свобода требует ответственности" -> vector placed in свобода's rho.
        Emphasizes: what is being contained (object) via what relation (verb).
        """
        v_obj = self._role_transform(self.get_term_vector(j.object), "object_in_subject")
        v_verb = self._role_transform(self.get_term_vector(j.verb), "verb_in_subject")

        sign = -1.0 if j.quality == "NEGATIVE" else 1.0
        v = v_obj + sign * j.intensity * v_verb
        return v / (np.linalg.norm(v) + 1e-10)

    def encode_judgment_for_object(self, j: Judgment) -> np.ndarray:
        """Encode judgment from the OBJECT's perspective.
        "свобода требует ответственности" -> vector placed in ответственность's rho.
        Emphasizes: what contains me (subject) via what relation (verb).
        """
        v_subj = self._role_transform(self.get_term_vector(j.subject), "subject_in_object")
        v_verb = self._role_transform(self.get_term_vector(j.verb), "verb_in_object")

        sign = -1.0 if j.quality == "NEGATIVE" else 1.0
        v = v_subj + sign * j.intensity * v_verb
        return v / (np.linalg.norm(v) + 1e-10)

    def _self_type(self, j: Judgment) -> str:
        """Classify a я-judgment. Returns 'identity', 'relation', or 'action'.
        - identity: "я являюсь X", "я свободный" → who I AM
        - relation: "я хочу X", "я люблю X" → what I RELATE to
        - action: "я делаю X" → what I DO (not stored in [self])
        """
        if j.subject.lower() not in ("я", "себя"):
            return "none"
        verb = j.verb.lower()
        if verb in SELF_IDENTITY_VERBS or verb in SELF_DEPS:
            return "identity"
        if verb in SELF_RELATION_VERBS:
            return "relation"
        return "action"

    def _compute_anomaly(self, term: str, v_new: np.ndarray) -> float:
        """How anomalous is v_new relative to existing ρ(term)?

        Returns 0.0 (aligned with existing map) to 1.0 (perpendicular/opposite).
        Returns 0.0 if concept is new or has too few components.
        """
        concept = self.concepts.get(term)
        if concept is None or len(concept.components) < 3:
            return 0.0
        rho_n = concept.rho_norm
        if rho_n is None:
            return 0.0
        # Projection of new vector onto normalized density matrix
        v = v_new.reshape(-1, 1)
        alignment = float(np.sum((v @ v.T) * rho_n.T))  # Tr(|v><v| · ρ_norm)
        return float(np.clip(1.0 - alignment, 0.0, 1.0))

    def materialize_judgment(self, j: Judgment):
        """Process a judgment: create ASYMMETRIC vectors, update density matrices.

        Special handling:
        - Pronouns and noise words are NOT created as regular concepts
        - "Я" as subject:
          - identity ("я являюсь X") → full weight into [self]
          - relation ("я хочу X") → lighter weight into [self]
          - action ("я делаю X") → NOT into [self], only activates object
        - Verbs are also concepts (dual nature)
        - Computes anomaly_score BEFORE adding component (compares with existing ρ)
        """
        w = j.modality * j.intensity
        subj_is_pronoun = j.subject.lower() in PRONOUNS
        obj_is_pronoun = j.object.lower() in PRONOUNS

        # Compute anomaly BEFORE modifying density matrices
        anomaly_scores = []
        if not subj_is_pronoun and j.subject.lower() not in ("я", "себя"):
            v_subj = self.encode_judgment_for_subject(j)
            anomaly_scores.append(self._compute_anomaly(j.subject, v_subj))
        if not obj_is_pronoun:
            v_obj = self.encode_judgment_for_object(j)
            anomaly_scores.append(self._compute_anomaly(j.object, v_obj))
        if anomaly_scores:
            j.anomaly_score = max(anomaly_scores)

        # Skip if both are pronouns/noise
        if subj_is_pronoun and obj_is_pronoun:
            return

        # --- Handle "я" as subject ---
        if j.subject.lower() in ("я", "себя"):
            if obj_is_pronoun:
                return
            self_type = self._self_type(j)
            if self_type == "identity":
                # "я являюсь свободным" → full weight into [self]
                v = self.encode_judgment_for_subject(j)
                self.self_concept.add_component(v, w, j)
            elif self_type == "relation":
                # "я хочу свободу" → lighter weight into [self]
                v = self.encode_judgment_for_subject(j)
                self.self_concept.add_component(v, w * 0.5, j)
            # Always activate the object
            v_for_obj = self.encode_judgment_for_object(j)
            obj_concept = self.get_or_create(j.object)
            obj_concept.add_component(v_for_obj, w * 0.5, j)
            return

        # --- Regular judgment (non-pronoun subject) ---
        if not subj_is_pronoun:
            v_for_subj = self.encode_judgment_for_subject(j)
            subj = self.get_or_create(j.subject)
            subj.add_component(v_for_subj, w, j)

        if not obj_is_pronoun:
            v_for_obj = self.encode_judgment_for_object(j)
            obj_concept = self.get_or_create(j.object)
            obj_concept.add_component(v_for_obj, w * 0.5, j)

        # Verb as concept (dual nature: connector AND container)
        # Verb accumulates contexts — what does "требовать" mean for this person?
        v_verb = self.get_term_vector(j.verb)
        verb_concept = self.get_or_create(j.verb)
        verb_concept.add_component(v_verb, w * 0.2, j)
        verb_concept._is_verb = True  # tag for separate display

    def recursive_deepen(self, iterations: int = 3, alpha: float = 0.7):
        """Recursive deepening: rho(A) = alpha * rho_direct(A) + (1-alpha) * sum(transform(rho(Bi))).
        This makes each concept's density matrix reflect its contents' density matrices.
        """
        terms = list(self.concepts.keys())

        for k in range(iterations):
            for term in terms:
                concept = self.concepts[term]
                rho_direct = concept.rho
                if rho_direct is None:
                    continue

                # Find what this concept contains
                contained = []
                for other_term, other_concept in self.concepts.items():
                    if other_term == term:
                        continue
                    other_rho = other_concept.rho_deep if k > 0 else other_concept.rho
                    if other_rho is None:
                        continue
                    c = containment(rho_direct, other_rho)
                    if c > 0.1:  # threshold
                        contained.append((c, other_rho))

                if not contained:
                    concept._rho_recursive = rho_direct.copy()
                    continue

                # Build recursive component
                rho_recursive = np.zeros_like(rho_direct)
                total_w = 0.0
                for weight, other_rho in contained:
                    rho_recursive += weight * other_rho
                    total_w += weight

                if total_w > 1e-12:
                    rho_recursive /= total_w

                # Blend: alpha * direct + (1-alpha) * recursive
                # NO renormalization — trace reflects mass
                concept._rho_recursive = alpha * rho_direct + (1 - alpha) * rho_recursive

    # -----------------------------------------------------------------------
    # Query operations
    # -----------------------------------------------------------------------

    def _queryable_concepts(self, include_verbs: bool = True) -> list[tuple[str, 'Concept']]:
        """Return concepts with enough components to be meaningful."""
        return [
            (t, c) for t, c in self.concepts.items()
            if len(c.components) >= self.min_components
            and c.rho_deep is not None
            and (include_verbs or not getattr(c, '_is_verb', False))
        ]

    def query_contains(self, term: str, top_k: int = 10) -> list[tuple[str, float]]:
        """What does `term` contain? Uses graded_hyponymy(B, A) —
        'degree to which B is inside A'. Asymmetric by construction.
        Filters out concepts with too few components.
        """
        concept = self.concepts.get(term)
        if concept is None or concept.rho_deep is None:
            return []
        results = []
        for other_term, other_concept in self._queryable_concepts():
            if other_term == term:
                continue
            score = graded_hyponymy(other_concept.rho_deep, concept.rho_deep)
            results.append((other_term, score))
        results.sort(key=lambda x: -x[1])
        return results[:top_k]

    def query_contained_in(self, term: str, top_k: int = 10) -> list[tuple[str, float]]:
        """What contains `term`? Uses graded_hyponymy(A, B) —
        'degree to which A is inside B'. Asymmetric.
        """
        concept = self.concepts.get(term)
        if concept is None or concept.rho_deep is None:
            return []
        results = []
        for other_term, other_concept in self._queryable_concepts():
            if other_term == term:
                continue
            score = graded_hyponymy(concept.rho_deep, other_concept.rho_deep)
            results.append((other_term, score))
        results.sort(key=lambda x: -x[1])
        return results[:top_k]

    def query_facets(self, term: str) -> list[tuple[float, int]]:
        """Get facets of a term. Returns [(weight, facet_index), ...].
        Uses normalized rho for meaningful eigenvalue weights.
        """
        concept = self.concepts.get(term)
        if concept is None or concept.rho_deep_norm is None:
            return []
        f = facets(concept.rho_deep_norm)
        return [(w, i) for i, (w, _) in enumerate(f)]

    def query_polysemy(self, term: str) -> float:
        """How polysemous is a term? 0=unambiguous, >0=polysemous.
        Uses normalized rho.
        """
        concept = self.concepts.get(term)
        if concept is None or concept.rho_deep_norm is None:
            return 0.0
        return von_neumann_entropy(concept.rho_deep_norm)

    def query_similarity(self, term_a: str, term_b: str) -> float:
        """Semantic similarity via trace inner product on normalized rho."""
        a = self.concepts.get(term_a)
        b = self.concepts.get(term_b)
        if a is None or b is None or a.rho_deep_norm is None or b.rho_deep_norm is None:
            return 0.0
        return trace_inner_product(a.rho_deep_norm, b.rho_deep_norm)

    def report(self, term: str):
        """Print a human-readable report for a concept."""
        concept = self.concepts.get(term)
        if concept is None:
            print(f"  '{term}' -- not found")
            return

        rho = concept.rho_deep
        rho_n = concept.rho_deep_norm
        if rho is None:
            print(f"  '{term}' -- no data")
            return

        mass = np.trace(rho)
        print(f"\n  === {term} ===")
        print(f"  Components: {len(concept.components)}")
        print(f"  Mass (trace): {mass:.3f}")
        print(f"  Polysemy (entropy): {von_neumann_entropy(rho_n):.3f}")
        print(f"  Purity: {purity(rho_n):.3f}")
        f = facets(rho_n, threshold=0.02)
        print(f"  Facets: {len(f)}")
        for i, (w, _) in enumerate(f):
            print(f"    facet {i}: weight={w:.3f}")

        contains = self.query_contains(term, top_k=10)
        nouns = [(t, s) for t, s in contains if not getattr(self.concepts.get(t), '_is_verb', False)]
        verbs = [(t, s) for t, s in contains if getattr(self.concepts.get(t), '_is_verb', False)]

        print(f"  Contains (concepts):")
        for other, score in nouns[:5]:
            print(f"    {other}: {score:.3f}")
        if verbs:
            print(f"  Contains (verbs-as-concepts):")
            for other, score in verbs[:3]:
                print(f"    [{other}]: {score:.3f}")

        contained = self.query_contained_in(term, top_k=10)
        nouns_in = [(t, s) for t, s in contained if not getattr(self.concepts.get(t), '_is_verb', False)]
        verbs_in = [(t, s) for t, s in contained if getattr(self.concepts.get(t), '_is_verb', False)]

        print(f"  Contained in (concepts):")
        for other, score in nouns_in[:5]:
            print(f"    {other}: {score:.3f}")
        if verbs_in:
            print(f"  Contained in (verbs):")
            for other, score in verbs_in[:3]:
                print(f"    [{other}]: {score:.3f}")

    def report_self(self):
        """Print report for the [self] container."""
        sc = self.self_concept
        if not sc.components:
            print("\n  === [self] === (empty)")
            return
        sc._recompute_rho()
        rho = sc.rho
        rho_n = sc.rho_norm
        print(f"\n  === [self] (who the person thinks they are) ===")
        print(f"  Self-characterizations: {len(sc.components)}")
        print(f"  Mass: {np.trace(rho):.3f}")
        if rho_n is not None:
            print(f"  Entropy: {von_neumann_entropy(rho_n):.3f}")
            f = facets(rho_n, threshold=0.05)
            print(f"  Facets: {len(f)}")

        print(f"  Source judgments:")
        seen = set()
        for c in sc.components:
            j = c.judgment
            key = f"{j.verb}:{j.object}"
            if key not in seen:
                seen.add(key)
                print(f"    --[{j.verb}]--> {j.object}  | \"{j.source_text[:80]}\"")
                if len(seen) >= 15:
                    break
