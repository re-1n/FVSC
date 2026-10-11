"""Cheap Russian morphology-backed judgment extraction.

This adapter restores the whitepaper's exact-relation path without making a
heavy dependency parser canonical. It uses morphology plus explicit local
heuristics, therefore every result is L1, defeasible, source-spanned evidence.
The language-agnostic co-occurrence parser remains available as a fallback and
evaluation arm.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Protocol

from ..semantic import Judgment
from .judgment_events import SourceSpan
from .vault_ingest import SourceDocument


_WORD_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", flags=re.UNICODE)
_SENTENCE_RE = re.compile(r"[^.!?…\n]+(?:[.!?…]+|$)", flags=re.UNICODE)
_NOMINAL_COPULA_RE = re.compile(r"\s+[—–-]\s+(?:это\s+)?", flags=re.IGNORECASE)

_VERB_POS = frozenset({"VERB", "INFN", "PRTS"})
_NOUN_POS = frozenset({"NOUN", "NPRO"})
_ADJECTIVE_POS = frozenset({"ADJF", "ADJS", "PRTF", "PRTS"})
_ARGUMENT_POS = _NOUN_POS | _ADJECTIVE_POS
_CLAUSE_MARKERS = frozenset({"что", "чтобы", "если", "когда", "пока"})
_COORDINATORS = frozenset({"и", "или", "либо", "да"})
_NEGATIONS = frozenset({"не", "ни"})
_SUBJECT_EXCLUSIONS = frozenset({"это", "что", "кто", "он", "она", "они"})

_RELATION_INTENSITY = {
    "требовать": 0.9,
    "нуждаться": 0.8,
    "просить": 0.6,
    "включать": 0.8,
    "содержать": 0.8,
    "иметь": 0.7,
    "являться": 1.0,
    "быть": 0.7,
    "создавать": 0.9,
    "порождать": 0.9,
    "вызывать": 0.8,
    "давать": 0.7,
    "позволять": 0.7,
    "помогать": 0.6,
    "разрушать": 0.8,
    "мешать": 0.7,
    "отрицать": 0.8,
    "любить": 0.7,
    "ненавидеть": 0.9,
    "хотеть": 0.6,
    "думать": 0.5,
    "считать": 0.6,
    "знать": 0.8,
    "делать": 0.6,
    "использовать": 0.7,
    "строить": 0.7,
}

# lemma -> (modality type, weight, propagate outer negation)
_MODAL_ENVELOPES = {
    "знать": ("FACTUAL", 1.0, False),
    "верить": ("EPISTEMIC", 0.5, False),
    "думать": ("EPISTEMIC", 0.5, True),
    "считать": ("EPISTEMIC", 0.6, True),
    "полагать": ("EPISTEMIC", 0.5, True),
    "хотеть": ("DESIDERATIVE", 0.6, False),
    "мечтать": ("DESIDERATIVE", 0.5, False),
    "бояться": ("EPISTEMIC", 0.4, False),
    "сомневаться": ("EPISTEMIC", 0.3, False),
    "надеяться": ("DESIDERATIVE", 0.5, False),
    "мочь": ("EPISTEMIC", 0.5, False),
    "должен": ("DEONTIC", 0.7, False),
    "обязать": ("DEONTIC", 0.7, False),
}
_UNIVERSAL_QUANTIFIERS = {"все": 1.0, "весь": 1.0, "каждый": 1.0, "любой": 0.9}
_EXISTENTIAL_QUANTIFIERS = {"некоторый": 0.7, "какой-то": 0.6, "один": 0.5}
_QUANTIFIER_LEMMAS = frozenset(_UNIVERSAL_QUANTIFIERS) | frozenset(
    _EXISTENTIAL_QUANTIFIERS
)
_HABITUAL_MARKERS = frozenset({"обычно", "часто", "всегда", "иногда", "редко", "порой"})
_EPISODIC_MARKERS = frozenset(
    {"вчера", "сегодня", "завтра", "потом", "тогда", "сейчас", "недавно", "утром", "вечером"}
)


@dataclass(frozen=True)
class MorphAnalysis:
    lemma: str
    pos: str
    grammemes: frozenset[str] = frozenset()
    score: float = 1.0


class Morphology(Protocol):
    version: str

    def analyze(self, word: str) -> MorphAnalysis: ...


class Pymorphy3Morphology:
    """Lazy adapter so importing FVSC does not initialize the dictionary."""

    version = "pymorphy3-v1"

    def __init__(self) -> None:
        try:
            import pymorphy3
        except ImportError as exc:  # pragma: no cover - dependency is installed in CI
            raise RuntimeError(
                "Russian judgment extraction requires pymorphy3; install requirements.txt"
            ) from exc
        self._analyzer = pymorphy3.MorphAnalyzer()

    def analyze(self, word: str) -> MorphAnalysis:
        parsed = self._analyzer.parse(word)[0]
        return MorphAnalysis(
            lemma=str(parsed.normal_form).casefold(),
            pos=str(parsed.tag.POS or ""),
            grammemes=frozenset(str(value) for value in parsed.tag.grammemes),
            score=float(parsed.score),
        )


@dataclass(frozen=True)
class _Token:
    text: str
    lemma: str
    pos: str
    grammemes: frozenset[str]
    score: float
    start: int
    end: int


@dataclass(frozen=True)
class JudgmentCandidate:
    judgment: Judgment
    source_span: SourceSpan


class JudgmentExtractor(Protocol):
    version: str

    def extract(self, document: SourceDocument) -> tuple[JudgmentCandidate, ...]: ...


def _sentence_spans(text: str) -> Iterable[tuple[int, int]]:
    for match in _SENTENCE_RE.finditer(text):
        start, end = match.span()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            yield start, end


def _tokens(text: str, *, offset: int, morphology: Morphology) -> list[_Token]:
    result: list[_Token] = []
    for match in _WORD_RE.finditer(text):
        analysis = morphology.analyze(match.group())
        result.append(
            _Token(
                text=match.group(),
                lemma=analysis.lemma,
                pos=analysis.pos,
                grammemes=analysis.grammemes,
                score=analysis.score,
                start=offset + match.start(),
                end=offset + match.end(),
            )
        )
    return result


def _has_direct_negation(tokens: list[_Token], index: int) -> bool:
    return any(token.lemma in _NEGATIONS for token in tokens[max(0, index - 2) : index])


def _is_argument(token: _Token) -> bool:
    return token.pos in _ARGUMENT_POS and len(token.lemma) >= 2


def _subject(tokens: list[_Token], verb_index: int) -> _Token | None:
    clause_start = max(
        (
            index + 1
            for index, token in enumerate(tokens[:verb_index])
            if token.lemma in _CLAUSE_MARKERS
        ),
        default=max(0, verb_index - 10),
    )
    candidates = [
        token
        for token in tokens[clause_start:verb_index]
        if token.pos in _NOUN_POS and token.lemma not in _SUBJECT_EXCLUSIONS
    ]
    if not candidates:
        return None
    nominative = [
        token
        for token in candidates
        if "nomn" in token.grammemes or token.lemma in {"я", "ты", "мы", "вы"}
    ]
    return (nominative or candidates)[-1]


def _objects(tokens: list[_Token], verb_index: int, subject: _Token) -> list[_Token]:
    candidates: list[_Token] = []
    for token in tokens[verb_index + 1 : min(len(tokens), verb_index + 11)]:
        if token.pos in _VERB_POS:
            break
        if token.lemma in _CLAUSE_MARKERS and candidates:
            break
        if _is_argument(token) and token.lemma != subject.lemma:
            candidates.append(token)
            if token.pos in _NOUN_POS and "nomn" not in token.grammemes:
                break
    if not candidates:
        return []

    primary = next(
        (
            token
            for token in candidates
            if token.pos in _NOUN_POS and "nomn" not in token.grammemes
        ),
        candidates[0],
    )
    result = [primary]
    primary_index = tokens.index(primary)
    for direction in (-1, 1):
        other_index = primary_index + 2 * direction
        coordinator_index = primary_index + direction
        if not (0 <= coordinator_index < len(tokens) and 0 <= other_index < len(tokens)):
            continue
        if tokens[coordinator_index].lemma not in _COORDINATORS:
            continue
        other = tokens[other_index]
        if other.pos in _NOUN_POS and other.lemma != subject.lemma:
            result.append(other)
    return sorted({token.start: token for token in result}.values(), key=lambda token: token.start)


def _modal_context(tokens: list[_Token], verb_index: int) -> tuple[float, str, bool, list[str]]:
    modality = 1.0
    modality_type = "FACTUAL"
    negated = _has_direct_negation(tokens, verb_index)
    chain: list[str] = []

    for index in range(max(0, verb_index - 10), verb_index):
        token = tokens[index]
        envelope = _MODAL_ENVELOPES.get(token.lemma)
        if envelope is None:
            continue
        between = tokens[index + 1 : verb_index]
        has_complement = any(value.lemma in _CLAUSE_MARKERS for value in between)
        has_infinitive = tokens[verb_index].pos == "INFN"
        if not has_complement and not has_infinitive:
            continue
        kind, weight, neg_raising = envelope
        modality *= weight
        modality_type = kind
        outer_negated = _has_direct_negation(tokens, index)
        if outer_negated and neg_raising:
            negated = not negated
            chain.append(f"negation-raised:{token.lemma}")
        elif outer_negated:
            modality *= 0.3
            chain.append(f"rejected-envelope:{token.lemma}")
        chain.append(f"modal-envelope:{token.lemma}")

    return max(0.05, min(1.0, modality)), modality_type, negated, chain


def _condition_context(
    tokens: list[_Token],
    *,
    verb_index: int,
    sentence_text: str,
    sentence_start: int,
) -> tuple[str | None, str | None]:
    if_index = next((index for index, token in enumerate(tokens) if token.lemma == "если"), None)
    if if_index is None or verb_index <= if_index:
        return None, None
    comma_relative = sentence_text.find(",", tokens[if_index].end - sentence_start)
    comma_absolute = sentence_start + comma_relative if comma_relative >= 0 else None
    condition_id = f"{sentence_start}:{tokens[if_index].start}"
    if comma_absolute is None or tokens[verb_index].start < comma_absolute:
        return condition_id, "ANTECEDENT"
    return condition_id, "CONSEQUENT"


def _quantifier_weight(tokens: list[_Token], subject: _Token) -> tuple[float, str | None]:
    subject_index = tokens.index(subject)
    for token in tokens[max(0, subject_index - 2) : subject_index + 1]:
        if token.lemma in _UNIVERSAL_QUANTIFIERS:
            return _UNIVERSAL_QUANTIFIERS[token.lemma], "UNIVERSAL"
        if token.lemma in _EXISTENTIAL_QUANTIFIERS:
            return _EXISTENTIAL_QUANTIFIERS[token.lemma], "EXISTENTIAL"
    return 1.0, None


def _clause_type(tokens: list[_Token], verb: _Token) -> str:
    lemmas = {token.lemma for token in tokens}
    if lemmas & _HABITUAL_MARKERS:
        return "HABITUAL"
    if lemmas & _EPISODIC_MARKERS:
        return "EPISODIC"
    if "past" in verb.grammemes and "perf" in verb.grammemes:
        return "EPISODIC"
    if "past" in verb.grammemes and "impf" in verb.grammemes:
        return "HABITUAL"
    if "pres" in verb.grammemes and "impf" in verb.grammemes:
        return "GENERIC"
    return "UNKNOWN"


def _is_envelope(tokens: list[_Token], verb_index: int) -> bool:
    token = tokens[verb_index]
    if token.lemma not in _MODAL_ENVELOPES:
        return False
    following = tokens[verb_index + 1 : min(len(tokens), verb_index + 11)]
    return any(value.lemma in _CLAUSE_MARKERS for value in following) or any(
        value.pos == "INFN" for value in following
    )


def _confidence(subject: _Token, verb: _Token, object_: _Token) -> float:
    morphology_score = min(subject.score, verb.score, object_.score)
    return max(0.35, min(0.9, 0.55 + 0.35 * morphology_score))


class RussianJudgmentExtractor:
    """Extract source-spanned L1 judgments using Russian morphology."""

    version = "russian-morphology-heuristic-v1"

    def __init__(self, morphology: Morphology | None = None) -> None:
        self.morphology = morphology or Pymorphy3Morphology()

    def extract(self, document: SourceDocument) -> tuple[JudgmentCandidate, ...]:
        candidates: list[JudgmentCandidate] = []
        seen: set[tuple[object, ...]] = set()

        for sentence_start, sentence_end in _sentence_spans(document.text):
            sentence_text = document.text[sentence_start:sentence_end]
            tokens = _tokens(sentence_text, offset=sentence_start, morphology=self.morphology)
            if not tokens:
                continue
            span = SourceSpan.from_document(document, start=sentence_start, end=sentence_end)

            for verb_index, verb in enumerate(tokens):
                if verb.pos not in _VERB_POS or _is_envelope(tokens, verb_index):
                    continue
                subject = _subject(tokens, verb_index)
                if subject is None:
                    continue
                for object_ in _objects(tokens, verb_index, subject):
                    modality, modality_type, negated, chain = _modal_context(tokens, verb_index)
                    condition_id, condition_role = _condition_context(
                        tokens,
                        verb_index=verb_index,
                        sentence_text=sentence_text,
                        sentence_start=sentence_start,
                    )
                    if condition_id is not None:
                        modality = min(modality, 0.4)
                        modality_type = "CONDITIONAL"
                        chain.append("conditional-scope")
                    quantifier_weight, quantifier = _quantifier_weight(tokens, subject)
                    modality = max(0.05, min(1.0, modality * quantifier_weight))
                    if quantifier is not None:
                        chain.append(f"quantifier:{quantifier.lower()}")

                    judgment = Judgment(
                        subject=subject.lemma,
                        verb=verb.lemma,
                        object=object_.lemma,
                        quality="NEGATIVE" if negated else "AFFIRMATIVE",
                        negation_scope=negated,
                        modality=modality,
                        modality_type=modality_type,
                        intensity=_RELATION_INTENSITY.get(verb.lemma, 0.5),
                        timestamp=document.observed_at,
                        source_text=sentence_text,
                        condition_id=condition_id,
                        condition_role=condition_role,
                        interpretation_layer=1,
                        defeasible=True,
                        inference_chain=[self.morphology.version, "heuristic:svo-window", *chain],
                        extraction_confidence=_confidence(subject, verb, object_),
                        clause_type=_clause_type(tokens, verb),
                        semantic_roles={"AGENT": subject.lemma, "PATIENT": object_.lemma},
                        role_intensity=0.5,
                        context_metadata={"extractor": self.version, "quantifier": quantifier},
                    )
                    self._append(candidates, seen, judgment, span)

            self._extract_nominal_copula(
                document=document,
                sentence_text=sentence_text,
                sentence_start=sentence_start,
                tokens=tokens,
                span=span,
                candidates=candidates,
                seen=seen,
            )
            self._extract_adjective_modifiers(
                document=document,
                sentence_text=sentence_text,
                tokens=tokens,
                span=span,
                candidates=candidates,
                seen=seen,
            )

        candidates.sort(
            key=lambda item: (
                item.source_span.start,
                item.judgment.subject,
                item.judgment.verb,
                item.judgment.object,
            )
        )
        return tuple(candidates)

    @staticmethod
    def _append(
        candidates: list[JudgmentCandidate],
        seen: set[tuple[object, ...]],
        judgment: Judgment,
        span: SourceSpan,
    ) -> None:
        key = (
            span.start,
            span.end,
            judgment.subject,
            judgment.verb,
            judgment.object,
            judgment.polarity,
            judgment.condition_role,
        )
        if key not in seen:
            seen.add(key)
            candidates.append(JudgmentCandidate(judgment=judgment, source_span=span))

    def _extract_nominal_copula(
        self,
        *,
        document: SourceDocument,
        sentence_text: str,
        sentence_start: int,
        tokens: list[_Token],
        span: SourceSpan,
        candidates: list[JudgmentCandidate],
        seen: set[tuple[object, ...]],
    ) -> None:
        match = _NOMINAL_COPULA_RE.search(sentence_text)
        if match is None:
            return
        boundary = sentence_start + match.start()
        left = [token for token in tokens if token.end <= boundary and token.pos in _NOUN_POS]
        right = [
            token
            for token in tokens
            if token.start >= sentence_start + match.end() and _is_argument(token)
        ]
        if not left or not right:
            return
        subject, object_ = left[-1], right[0]
        judgment = Judgment(
            subject=subject.lemma,
            verb="cop:это",
            object=object_.lemma,
            modality=1.0,
            intensity=0.7,
            timestamp=document.observed_at,
            source_text=sentence_text,
            interpretation_layer=1,
            defeasible=True,
            inference_chain=[self.morphology.version, "heuristic:nominal-copula"],
            extraction_confidence=max(
                0.5,
                min(0.9, 0.6 + 0.3 * min(subject.score, object_.score)),
            ),
            clause_type="GENERIC",
            semantic_roles={"THEME": subject.lemma, "ATTRIBUTE": object_.lemma},
            role_intensity=0.5,
            context_metadata={"extractor": self.version},
        )
        self._append(candidates, seen, judgment, span)

    def _extract_adjective_modifiers(
        self,
        *,
        document: SourceDocument,
        sentence_text: str,
        tokens: list[_Token],
        span: SourceSpan,
        candidates: list[JudgmentCandidate],
        seen: set[tuple[object, ...]],
    ) -> None:
        for index in range(len(tokens) - 1):
            first, second = tokens[index], tokens[index + 1]
            if first.pos in _ADJECTIVE_POS and second.pos == "NOUN":
                adjective, noun = first, second
            elif first.pos == "NOUN" and second.pos in _ADJECTIVE_POS:
                noun, adjective = first, second
            else:
                continue
            if adjective.lemma in _QUANTIFIER_LEMMAS:
                continue
            negated = _has_direct_negation(tokens, tokens.index(adjective))
            judgment = Judgment(
                subject=noun.lemma,
                verb="amod",
                object=adjective.lemma,
                quality="NEGATIVE" if negated else "AFFIRMATIVE",
                negation_scope=negated,
                intensity=0.5,
                timestamp=document.observed_at,
                source_text=sentence_text,
                interpretation_layer=1,
                defeasible=True,
                inference_chain=[self.morphology.version, "heuristic:adjacent-amod"],
                extraction_confidence=max(
                    0.45,
                    min(0.9, 0.55 + 0.35 * min(noun.score, adjective.score)),
                ),
                clause_type="GENERIC",
                semantic_roles={"THEME": noun.lemma, "ATTRIBUTE": adjective.lemma},
                role_intensity=0.5,
                context_metadata={"extractor": self.version},
            )
            self._append(candidates, seen, judgment, span)


__all__ = [
    "JudgmentCandidate",
    "JudgmentExtractor",
    "MorphAnalysis",
    "Morphology",
    "Pymorphy3Morphology",
    "RussianJudgmentExtractor",
]
