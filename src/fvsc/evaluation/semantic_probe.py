"""Frozen, capacity-only comparison of semantic representation schemas.

The probe starts from public synthetic annotations.  It deliberately excludes text
parsing so that a score measures which annotated facts each schema can retain, not
which parser happens to be better.  Results therefore cannot promote a production
representation without a later extraction and owner-validation experiment.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from ..ingest import SourceDocument
from ..semantic import Judgment
from ..semantic.graph import SemanticGraphView, import_umr_subset


SEMANTIC_PROBE_SCHEMA = "fvsc.semantic-capacity-probe/v1"
MAX_SEMANTIC_PROBE_BYTES = 2 * 1024 * 1024
FactKind = Literal["sentence_edge", "document_edge", "attribute"]
_FACT_KINDS = frozenset({"sentence_edge", "document_edge", "attribute"})


def _nonempty(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


@dataclass(frozen=True, order=True)
class SemanticFact:
    """A node-id-independent fact used only for schema-capacity scoring."""

    kind: FactKind
    subject: str
    predicate: str
    object: str

    def __post_init__(self) -> None:
        if self.kind not in _FACT_KINDS:
            raise ValueError(f"unknown semantic fact kind: {self.kind!r}")
        object.__setattr__(self, "subject", _nonempty(self.subject, field="fact subject"))
        object.__setattr__(self, "predicate", _nonempty(self.predicate, field="fact predicate"))
        object.__setattr__(self, "object", _nonempty(self.object, field="fact object"))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SemanticFact":
        return cls(
            kind=value.get("kind", ""),
            subject=value.get("subject", ""),
            predicate=value.get("predicate", ""),
            object=value.get("object", ""),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "object": self.object,
            "predicate": self.predicate,
            "subject": self.subject,
        }


@dataclass(frozen=True)
class SemanticProbeCase:
    case_id: str
    language_tag: str
    source_text: str
    umr: str
    judgments: tuple[Judgment, ...]
    gold_facts: tuple[SemanticFact, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _nonempty(self.case_id, field="case_id"))
        object.__setattr__(
            self,
            "language_tag",
            _nonempty(self.language_tag, field="language_tag"),
        )
        if not self.source_text:
            raise ValueError("semantic probe source_text must not be empty")
        if not self.umr.strip():
            raise ValueError("semantic probe UMR annotation must not be empty")
        if not self.judgments:
            raise ValueError("semantic probe case must contain judgments")
        if not self.gold_facts:
            raise ValueError("semantic probe case must contain gold facts")
        if len(self.gold_facts) != len(set(self.gold_facts)):
            raise ValueError(f"semantic probe case {self.case_id} has duplicate gold facts")


@dataclass(frozen=True)
class FactScore:
    true_positive: int
    false_positive: int
    false_negative: int

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.0

    def to_dict(self) -> dict[str, int | float]:
        return {
            "f1": self.f1,
            "false_negative": self.false_negative,
            "false_positive": self.false_positive,
            "precision": self.precision,
            "recall": self.recall,
            "true_positive": self.true_positive,
        }


def _scalar_text(value: str | int | float | bool) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def facts_from_graph(graph: SemanticGraphView) -> frozenset[SemanticFact]:
    """Project graph structure to stable concept-level evaluation facts."""
    concepts = {node.node_id: node.concept for node in graph.nodes}
    facts = {
        SemanticFact(
            kind="document_edge" if edge.scope == "document" else "sentence_edge",
            subject=concepts[edge.source_id],
            predicate=edge.relation,
            object=concepts[edge.target_id],
        )
        for edge in graph.edges
    }
    facts.update(
        SemanticFact(
            kind="attribute",
            subject=concepts[attribute.node_id],
            predicate=attribute.name,
            object=_scalar_text(attribute.value),
        )
        for attribute in graph.attributes
    )
    return frozenset(facts)


def facts_from_judgments(judgments: Sequence[Judgment]) -> frozenset[SemanticFact]:
    """Expose only facts structurally guaranteed by the flat Judgment core."""
    facts: set[SemanticFact] = set()
    for judgment in judgments:
        facts.add(SemanticFact("sentence_edge", judgment.verb, "ARG0", judgment.subject))
        facts.add(SemanticFact("sentence_edge", judgment.verb, "ARG1", judgment.object))
        if judgment.polarity < 0.0:
            facts.add(SemanticFact("attribute", judgment.verb, "polarity", "-"))
    return frozenset(facts)


def score_facts(
    predicted: Sequence[SemanticFact] | frozenset[SemanticFact],
    gold: Sequence[SemanticFact] | frozenset[SemanticFact],
) -> FactScore:
    predicted_set = frozenset(predicted)
    gold_set = frozenset(gold)
    return FactScore(
        true_positive=len(predicted_set & gold_set),
        false_positive=len(predicted_set - gold_set),
        false_negative=len(gold_set - predicted_set),
    )


def _judgment(value: Mapping[str, Any]) -> Judgment:
    allowed = {
        "subject",
        "verb",
        "object",
        "quality",
        "negation_scope",
        "modality",
        "modality_type",
    }
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unsupported frozen Judgment fields: {sorted(unknown)}")
    return Judgment(**dict(value))


def load_semantic_probe(path: Path) -> tuple[SemanticProbeCase, ...]:
    """Load a bounded, regular-file-only public probe fixture."""
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"refusing non-regular semantic probe: {source}")
    if source.stat().st_size > MAX_SEMANTIC_PROBE_BYTES:
        raise ValueError("semantic probe exceeds size limit")
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("semantic probe must be valid UTF-8 JSON") from exc
    if not isinstance(raw, dict) or raw.get("schema") != SEMANTIC_PROBE_SCHEMA:
        raise ValueError("unsupported semantic probe schema")
    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("semantic probe cases must be a non-empty array")
    cases: list[SemanticProbeCase] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise ValueError("semantic probe case must be an object")
        raw_judgments = raw_case.get("judgments")
        raw_gold = raw_case.get("gold_facts")
        if not isinstance(raw_judgments, list) or not isinstance(raw_gold, list):
            raise ValueError("semantic probe judgments and gold_facts must be arrays")
        cases.append(
            SemanticProbeCase(
                case_id=raw_case.get("case_id", ""),
                language_tag=raw_case.get("language_tag", ""),
                source_text=raw_case.get("source_text", ""),
                umr=raw_case.get("umr", ""),
                judgments=tuple(_judgment(item) for item in raw_judgments),
                gold_facts=tuple(SemanticFact.from_dict(item) for item in raw_gold),
            )
        )
    case_ids = tuple(case.case_id for case in cases)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("semantic probe case ids must be unique")
    return tuple(cases)


def _mean(values: Sequence[float]) -> float:
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("semantic probe metric values must be finite and non-empty")
    return sum(values) / len(values)


def run_semantic_capacity_probe(cases: Sequence[SemanticProbeCase]) -> dict[str, Any]:
    """Run frozen schema projections and return a deterministic JSON-ready report."""
    if not cases:
        raise ValueError("semantic probe requires at least one case")
    case_reports: list[dict[str, Any]] = []
    totals = {"judgment_core": [0, 0, 0], "umr": [0, 0, 0]}
    macro = {"judgment_core": [], "umr": []}
    for case in cases:
        revision = hashlib.sha256(case.source_text.encode("utf-8")).hexdigest()
        document = SourceDocument.create(
            source_id=f"public/synthetic/{case.case_id}.txt",
            source_revision=revision,
            observed_at=0.0,
            text=case.source_text,
            adapter="semantic-capacity-probe",
        )
        graph = import_umr_subset(
            case.umr,
            document=document,
            language_tag=case.language_tag,
        ).graph
        predictions = {
            "judgment_core": facts_from_judgments(case.judgments),
            "umr": facts_from_graph(graph),
        }
        scores = {
            arm: score_facts(facts, case.gold_facts)
            for arm, facts in predictions.items()
        }
        for arm, score in scores.items():
            totals[arm][0] += score.true_positive
            totals[arm][1] += score.false_positive
            totals[arm][2] += score.false_negative
            macro[arm].append(score.f1)
        case_reports.append(
            {
                "case_id": case.case_id,
                "gold_fact_count": len(case.gold_facts),
                "scores": {arm: score.to_dict() for arm, score in scores.items()},
            }
        )
    summary: dict[str, Any] = {}
    for arm in ("judgment_core", "umr"):
        micro = FactScore(*totals[arm])
        summary[arm] = {
            "macro_f1": _mean(macro[arm]),
            "micro": micro.to_dict(),
        }
    return {
        "assumptions": [
            "synthetic manually annotated cases",
            "text extraction excluded",
            "judgment_core is subject-verb-object plus explicit polarity",
            "scores measure retention of frozen target facts only",
        ],
        "capacity_only": True,
        "case_count": len(cases),
        "cases": case_reports,
        "promotion_eligible": False,
        "schema": SEMANTIC_PROBE_SCHEMA,
        "summary": summary,
    }


__all__ = [
    "FactScore",
    "MAX_SEMANTIC_PROBE_BYTES",
    "SEMANTIC_PROBE_SCHEMA",
    "SemanticFact",
    "SemanticProbeCase",
    "facts_from_graph",
    "facts_from_judgments",
    "load_semantic_probe",
    "run_semantic_capacity_probe",
    "score_facts",
]
