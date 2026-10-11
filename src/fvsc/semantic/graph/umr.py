"""Loss-aware import of the documented UMR text-file subset used by FVSC probes.

The adapter intentionally starts with import only. It accepts UMR token, sentence graph,
alignment, and simple document-triple blocks, binds them to an existing source revision,
and records missing alignments as explicit losses. It does not call a parser model and
does not write to ``EvidenceLedger``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Iterable, Protocol

from ..linguistic import LinguisticFrontendResult, LinguisticToken
from .contracts import (
    RepresentationLoss,
    SemanticAttribute,
    SemanticEdge,
    SemanticGraphView,
    SemanticNode,
)


UMR_SUBSET_EXTRACTOR = "fvsc.umr-subset-import"
UMR_SUBSET_VERSION = "1"

_BLOCK_RE = re.compile(r"(?m)^#{80}\s*$")
_SENTENCE_ID_RE = re.compile(r"(?m)^#\s*::\s*snt(?P<index>\d+)\s*$")
_WORDS_RE = re.compile(r"(?m)^Words:\s*(?P<words>.*)$")
_ALIGNMENT_RE = re.compile(r"^\s*(?P<node>[^:#\s]+)\s*:\s*(?P<ranges>.*?)\s*$")
_RANGE_RE = re.compile(r"^(?P<start>\d+)-(?P<end>\d+)$")
_DOCUMENT_TRIPLE_RE = re.compile(
    r"\(\s*(?P<source>[^\s():]+)\s+:(?P<relation>[^\s():]+)\s+"
    r"(?P<target>[^\s():]+)\s*\)"
)
_PENMAN_TOKEN_RE = re.compile(
    r'''\s*(?:(?P<open>\()|(?P<close>\))|(?P<slash>/)|'''
    r'''(?P<role>:[^\s()]+)|(?P<string>"(?:\\.|[^"\\])*")|'''
    r'''(?P<atom>[^\s()]+))'''
)


class _SourceDocument(Protocol):
    source_id: str
    source_revision: str
    text: str


@dataclass(frozen=True)
class UMRImportResult:
    frontend: LinguisticFrontendResult
    graph: SemanticGraphView

    def verify(self, document: _SourceDocument) -> None:
        self.frontend.verify(document)  # type: ignore[arg-type]
        self.graph.verify(self.frontend)


@dataclass
class _PenmanNode:
    node_id: str
    concept: str
    roles: list[tuple[str, "_PenmanValue"]]


_PenmanValue = _PenmanNode | str | int | float | bool


class _PenmanReader:
    def __init__(self, value: str) -> None:
        self.tokens = [match for match in _PENMAN_TOKEN_RE.finditer(value)]
        self.position = 0
        self.nodes: dict[str, _PenmanNode] = {}

    def parse(self) -> _PenmanNode:
        if not self.tokens:
            raise ValueError("UMR sentence graph must not be empty")
        root = self._node()
        if self.position != len(self.tokens):
            raise ValueError("unexpected content after UMR sentence graph")
        return root

    def _kind(self) -> str:
        if self.position >= len(self.tokens):
            return "eof"
        return str(self.tokens[self.position].lastgroup)

    def _take(self, kind: str) -> str:
        if self._kind() != kind:
            raise ValueError(f"expected UMR {kind}, found {self._kind()}")
        match = self.tokens[self.position]
        self.position += 1
        return match.group(kind)

    def _atom(self) -> _PenmanValue:
        kind = self._kind()
        if kind == "string":
            return json.loads(self._take("string"))
        raw = self._take("atom")
        if raw == "true":
            return True
        if raw == "false":
            return False
        try:
            return int(raw)
        except ValueError:
            try:
                return float(raw)
            except ValueError:
                return raw

    def _node(self) -> _PenmanNode:
        self._take("open")
        node_id = str(self._atom())
        self._take("slash")
        concept = str(self._atom())
        node = _PenmanNode(node_id=node_id, concept=concept, roles=[])
        if node_id in self.nodes:
            raise ValueError(f"duplicate UMR node definition: {node_id}")
        self.nodes[node_id] = node
        while self._kind() != "close":
            role = self._take("role")[1:]
            value: _PenmanValue
            if self._kind() == "open":
                value = self._node()
            else:
                value = self._atom()
            node.roles.append((role, value))
        self._take("close")
        return node


def _sections(block: str) -> tuple[str, str, str, str]:
    sentence_marker = "# sentence level graph:"
    alignment_marker = "# alignment:"
    document_marker = "# document level annotation:"
    if sentence_marker not in block or alignment_marker not in block or document_marker not in block:
        raise ValueError("UMR block must contain sentence, alignment, and document sections")
    header, remainder = block.split(sentence_marker, 1)
    sentence_graph, remainder = remainder.split(alignment_marker, 1)
    alignment, document_graph = remainder.split(document_marker, 1)
    return header, sentence_graph.strip(), alignment.strip(), document_graph.strip()


def _blocks(value: str) -> tuple[str, ...]:
    return tuple(block.strip() for block in _BLOCK_RE.split(value) if block.strip())


def _source_tokens(
    document: _SourceDocument,
    blocks: tuple[str, ...],
) -> tuple[tuple[LinguisticToken, ...], dict[str, tuple[str, ...]]]:
    cursor = 0
    tokens: list[LinguisticToken] = []
    tokens_by_sentence: dict[str, tuple[str, ...]] = {}
    for ordinal, block in enumerate(blocks, start=1):
        header, _, _, _ = _sections(block)
        sentence_match = _SENTENCE_ID_RE.search(header)
        sentence_id = f"s{sentence_match.group('index') if sentence_match else ordinal}"
        words_match = _WORDS_RE.search(header)
        if words_match is None:
            raise ValueError(f"UMR sentence {sentence_id} has no Words line")
        words = tuple(words_match.group("words").split())
        if not words:
            raise ValueError(f"UMR sentence {sentence_id} has no tokens")
        sentence_token_ids: list[str] = []
        for index, word in enumerate(words, start=1):
            start = document.text.find(word, cursor)
            if start < 0:
                raise ValueError(
                    f"UMR token {sentence_id}:{index} cannot be aligned to source revision"
                )
            end = start + len(word)
            token_id = f"{sentence_id}t{index}"
            tokens.append(
                LinguisticToken.from_text(
                    document.text,
                    token_id=token_id,
                    sentence_id=sentence_id,
                    index=index,
                    start=start,
                    end=end,
                )
            )
            sentence_token_ids.append(token_id)
            cursor = end
        tokens_by_sentence[sentence_id] = tuple(sentence_token_ids)
    return tuple(tokens), tokens_by_sentence


def _alignment_map(
    value: str,
    *,
    sentence_id: str,
    token_ids: tuple[str, ...],
    losses: list[RepresentationLoss],
) -> dict[str, tuple[str, ...] | None]:
    result: dict[str, tuple[str, ...] | None] = {}
    for line_number, line in enumerate(value.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ALIGNMENT_RE.match(stripped)
        if match is None:
            losses.append(
                RepresentationLoss(
                    path=f"sentence:{sentence_id}:alignment:{line_number}",
                    reason="unsupported-alignment-line",
                    detail=stripped,
                )
            )
            continue
        node_id = match.group("node")
        ranges = tuple(part.strip() for part in match.group("ranges").split(","))
        aligned: list[str] = []
        implicit = False
        valid = True
        for item in ranges:
            range_match = _RANGE_RE.match(item)
            if range_match is None:
                valid = False
                break
            start = int(range_match.group("start"))
            end = int(range_match.group("end"))
            if start == 0 and end == 0:
                implicit = True
                continue
            if start < 1 or end < start or end > len(token_ids):
                valid = False
                break
            aligned.extend(token_ids[start - 1 : end])
        if not valid or (implicit and aligned):
            losses.append(
                RepresentationLoss(
                    path=f"sentence:{sentence_id}:node:{node_id}:alignment",
                    reason="invalid-token-range",
                    detail=match.group("ranges"),
                )
            )
            result[node_id] = None
        elif implicit:
            result[node_id] = ()
        else:
            result[node_id] = tuple(dict.fromkeys(aligned))
    return result


def _walk_nodes(root: _PenmanNode) -> Iterable[_PenmanNode]:
    yield root
    for _, value in root.roles:
        if isinstance(value, _PenmanNode):
            yield from _walk_nodes(value)


def _sentence_projection(
    value: str,
    *,
    sentence_id: str,
    alignment: dict[str, tuple[str, ...] | None],
    losses: list[RepresentationLoss],
) -> tuple[list[SemanticNode], list[SemanticEdge], list[SemanticAttribute]]:
    reader = _PenmanReader(value)
    root = reader.parse()
    definitions = reader.nodes
    nodes: list[SemanticNode] = []
    edges: list[SemanticEdge] = []
    attributes: list[SemanticAttribute] = []
    for node in _walk_nodes(root):
        aligned = alignment.get(node.node_id)
        if aligned is None:
            status = "unknown"
            token_ids: tuple[str, ...] = ()
            losses.append(
                RepresentationLoss(
                    path=f"sentence:{sentence_id}:node:{node.node_id}:alignment",
                    reason="missing-or-invalid-alignment",
                )
            )
        elif not aligned:
            status = "implicit"
            token_ids = ()
        else:
            status = "aligned"
            token_ids = aligned
        nodes.append(
            SemanticNode(
                node_id=node.node_id,
                concept=node.concept,
                sentence_id=sentence_id,
                aligned_token_ids=token_ids,
                alignment_status=status,
            )
        )
        for role, target in node.roles:
            if isinstance(target, _PenmanNode):
                edges.append(SemanticEdge(node.node_id, role, target.node_id))
            elif isinstance(target, str) and target in definitions:
                edges.append(SemanticEdge(node.node_id, role, target))
            else:
                attributes.append(SemanticAttribute(node.node_id, role, target))
    unknown_alignment_nodes = sorted(set(alignment) - set(definitions))
    for node_id in unknown_alignment_nodes:
        losses.append(
            RepresentationLoss(
                path=f"sentence:{sentence_id}:node:{node_id}:alignment",
                reason="alignment-references-unknown-node",
            )
        )
    return nodes, edges, attributes


def _document_edges(
    value: str,
    *,
    known_nodes: dict[str, SemanticNode],
) -> tuple[list[SemanticNode], list[SemanticEdge]]:
    metanodes: dict[str, SemanticNode] = {}
    edges: list[SemanticEdge] = []
    for match in _DOCUMENT_TRIPLE_RE.finditer(value):
        source = match.group("source")
        relation = match.group("relation")
        target = match.group("target")
        for node_id in (source, target):
            if node_id not in known_nodes and node_id not in metanodes:
                metanodes[node_id] = SemanticNode(
                    node_id=node_id,
                    concept=node_id,
                    sentence_id=None,
                    alignment_status="implicit",
                    kind="metanode",
                )
        edges.append(
            SemanticEdge(
                source_id=source,
                relation=relation,
                target_id=target,
                scope="document",
            )
        )
    return list(metanodes.values()), edges


def import_umr_subset(
    value: str,
    *,
    document: _SourceDocument,
    language_tag: str,
) -> UMRImportResult:
    """Import a source-grounded subset of the official UMR text format.

    Unsupported or absent node alignments become ``RepresentationLoss`` entries.
    Failure to align the UMR token block to the exact source revision is fatal because
    a graph without trustworthy source identity would violate FVSC's foundation.
    """
    blocks = _blocks(value)
    if not blocks:
        raise ValueError("UMR document must contain at least one sentence block")
    tokens, tokens_by_sentence = _source_tokens(document, blocks)
    frontend = LinguisticFrontendResult(
        source_id=document.source_id,
        source_revision=document.source_revision,
        language_tag=language_tag,
        frontend="umr-token-block",
        frontend_version=UMR_SUBSET_VERSION,
        tokens=tokens,
    )
    frontend.verify(document)  # type: ignore[arg-type]

    nodes: list[SemanticNode] = []
    edges: list[SemanticEdge] = []
    attributes: list[SemanticAttribute] = []
    losses: list[RepresentationLoss] = []
    document_sections: list[str] = []
    for ordinal, block in enumerate(blocks, start=1):
        header, sentence_graph, alignment, document_graph = _sections(block)
        sentence_match = _SENTENCE_ID_RE.search(header)
        sentence_id = f"s{sentence_match.group('index') if sentence_match else ordinal}"
        alignment_by_node = _alignment_map(
            alignment,
            sentence_id=sentence_id,
            token_ids=tokens_by_sentence[sentence_id],
            losses=losses,
        )
        sentence_nodes, sentence_edges, sentence_attributes = _sentence_projection(
            sentence_graph,
            sentence_id=sentence_id,
            alignment=alignment_by_node,
            losses=losses,
        )
        nodes.extend(sentence_nodes)
        edges.extend(sentence_edges)
        attributes.extend(sentence_attributes)
        document_sections.append(document_graph)

    known_nodes = {item.node_id: item for item in nodes}
    for document_graph in document_sections:
        metanodes, document_edges = _document_edges(
            document_graph,
            known_nodes={**known_nodes, **{item.node_id: item for item in nodes}},
        )
        for node in metanodes:
            if node.node_id not in known_nodes:
                known_nodes[node.node_id] = node
                nodes.append(node)
        edges.extend(document_edges)

    graph = SemanticGraphView(
        source_id=document.source_id,
        source_revision=document.source_revision,
        language_tag=language_tag,
        frontend_digest=frontend.digest,
        extractor=UMR_SUBSET_EXTRACTOR,
        extractor_version=UMR_SUBSET_VERSION,
        nodes=tuple(sorted(nodes, key=lambda item: item.node_id)),
        edges=tuple(
            sorted(
                {item for item in edges},
                key=lambda item: (item.scope, item.source_id, item.relation, item.target_id),
            )
        ),
        attributes=tuple(
            sorted(attributes, key=lambda item: (item.node_id, item.name))
        ),
        losses=tuple(
            sorted(
                {item for item in losses},
                key=lambda item: (item.path, item.reason, item.detail),
            )
        ),
    )
    graph.verify(frontend)
    return UMRImportResult(frontend=frontend, graph=graph)


__all__ = [
    "UMRImportResult",
    "UMR_SUBSET_EXTRACTOR",
    "UMR_SUBSET_VERSION",
    "import_umr_subset",
]
