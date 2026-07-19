"""Build arm-blinded, locally reviewable Stage 4h proposal packs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import re
import secrets
from typing import Any, Iterable, Mapping

from ...ingest import SourceAttribution, SourceDocument
from ...interpretation import InterpretationClaim
from .contracts import Stage4hArm, content_digest
from .runner import Stage4hArmResult, Stage4hRunResultBundle


_DIGEST_RE = re.compile(r"[0-9a-f]{64}")


def _digest(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if _DIGEST_RE.fullmatch(result) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return result


def _nonempty(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must not be empty")
    return result


@dataclass(frozen=True)
class BlindedSourceExcerpt:
    citation_id: str
    source_id: str
    source_revision: str
    start: int
    end: int
    text_sha256: str
    excerpt: str
    observed_at: float | None = None
    display_time: str | None = None
    message_id: str | None = None
    reply_to_source_id: str | None = None
    temporal_previous_source_id: str | None = None
    attribution: SourceAttribution | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "citation_id", _digest(self.citation_id, field="citation_id"))
        object.__setattr__(self, "source_id", _nonempty(self.source_id, field="source_id"))
        object.__setattr__(
            self,
            "source_revision",
            _digest(self.source_revision, field="source_revision"),
        )
        object.__setattr__(
            self,
            "text_sha256",
            _digest(self.text_sha256, field="text_sha256"),
        )
        if (
            isinstance(self.start, bool)
            or isinstance(self.end, bool)
            or not isinstance(self.start, int)
            or not isinstance(self.end, int)
            or self.start < 0
            or self.end <= self.start
        ):
            raise ValueError("blinded excerpt offsets must be a non-empty half-open span")
        if not isinstance(self.excerpt, str) or not self.excerpt:
            raise ValueError("blinded review excerpt must not be empty")
        if len(self.excerpt) != self.end - self.start:
            raise ValueError("blinded review excerpt length does not match its span")
        if hashlib.sha256(self.excerpt.encode("utf-8")).hexdigest() != self.text_sha256:
            raise ValueError("blinded review excerpt does not match its citation digest")
        if self.observed_at is not None:
            observed_at = float(self.observed_at)
            if not math.isfinite(observed_at):
                raise ValueError("blinded review observed_at must be finite or None")
            object.__setattr__(self, "observed_at", observed_at)
        for field in (
            "display_time",
            "message_id",
            "reply_to_source_id",
            "temporal_previous_source_id",
        ):
            value = getattr(self, field)
            if value is not None:
                normalized = str(value).strip()
                if not normalized:
                    raise ValueError(f"blinded review {field} must be non-empty or None")
                object.__setattr__(self, field, normalized)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "citation_id": self.citation_id,
            "end": self.end,
            "excerpt": self.excerpt,
            "source_id": self.source_id,
            "source_revision": self.source_revision,
            "start": self.start,
            "text_sha256": self.text_sha256,
        }
        if self.attribution is not None:
            payload["source_context"] = {
                "attribution": self.attribution.to_dict(),
                "display_time": self.display_time,
                "message_id": self.message_id,
                "observed_at": self.observed_at,
                "reply_to_source_id": self.reply_to_source_id,
                "temporal_previous_source_id": self.temporal_previous_source_id,
            }
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BlindedSourceExcerpt":
        raw_context = value.get("source_context")
        context = raw_context if isinstance(raw_context, dict) else {}
        raw_attribution = context.get("attribution")
        return cls(
            citation_id=value.get("citation_id", ""),
            source_id=value.get("source_id", ""),
            source_revision=value.get("source_revision", ""),
            start=value.get("start", -1),
            end=value.get("end", -1),
            text_sha256=value.get("text_sha256", ""),
            excerpt=value.get("excerpt", ""),
            observed_at=context.get("observed_at"),
            display_time=context.get("display_time"),
            message_id=context.get("message_id"),
            reply_to_source_id=context.get("reply_to_source_id"),
            temporal_previous_source_id=context.get("temporal_previous_source_id"),
            attribution=(
                SourceAttribution.from_dict(raw_attribution)
                if isinstance(raw_attribution, dict)
                else None
            ),
        )


@dataclass(frozen=True)
class BlindedReviewItem:
    blind_item_id: str
    case_id: str
    proposal_id: str
    question: str
    answer: str
    claims: tuple[InterpretationClaim, ...]
    citations: tuple[BlindedSourceExcerpt, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "blind_item_id",
            _digest(self.blind_item_id, field="blind_item_id"),
        )
        object.__setattr__(self, "case_id", _nonempty(self.case_id, field="case_id"))
        object.__setattr__(self, "proposal_id", _digest(self.proposal_id, field="proposal_id"))
        object.__setattr__(self, "question", _nonempty(self.question, field="question"))
        object.__setattr__(self, "answer", _nonempty(self.answer, field="answer"))
        if not self.claims:
            raise ValueError("blinded review item requires claims")
        claim_ids = tuple(item.claim_id for item in self.claims)
        citation_ids = tuple(item.citation_id for item in self.citations)
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("blinded review claim ids must be unique")
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("blinded review citation ids must be unique")
        known = set(citation_ids)
        if any(not set(claim.citation_ids) <= known for claim in self.claims):
            raise ValueError("blinded review claim cites outside its item")

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "blind_item_id": self.blind_item_id,
            "case_id": self.case_id,
            "citations": [item.to_dict() for item in self.citations],
            "claims": [item.to_dict() for item in self.claims],
            "proposal_id": self.proposal_id,
            "question": self.question,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "BlindedReviewItem":
        raw_claims = value.get("claims", [])
        raw_citations = value.get("citations", [])
        if not isinstance(raw_claims, list) or not isinstance(raw_citations, list):
            raise ValueError("blinded claims and citations must be arrays")
        return cls(
            blind_item_id=value.get("blind_item_id", ""),
            case_id=value.get("case_id", ""),
            proposal_id=value.get("proposal_id", ""),
            question=value.get("question", ""),
            answer=value.get("answer", ""),
            claims=tuple(InterpretationClaim.from_dict(item) for item in raw_claims),
            citations=tuple(BlindedSourceExcerpt.from_dict(item) for item in raw_citations),
        )


@dataclass(frozen=True)
class Stage4hReviewPack:
    pack_id: str
    run_id: str
    result_bundle_id: str
    items: tuple[BlindedReviewItem, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported Stage 4h review-pack version")
        object.__setattr__(self, "run_id", _digest(self.run_id, field="run_id"))
        object.__setattr__(
            self,
            "result_bundle_id",
            _digest(self.result_bundle_id, field="result_bundle_id"),
        )
        ids = tuple(item.blind_item_id for item in self.items)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("blinded review items must be unique and sorted")
        if self.pack_id != content_digest(self._payload()):
            raise ValueError("pack_id does not match the blinded review pack")

    def _payload(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "result_bundle_id": self.result_bundle_id,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
        }

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        result_bundle_id: str,
        items: Iterable[BlindedReviewItem],
    ) -> "Stage4hReviewPack":
        ordered = tuple(sorted(items, key=lambda item: item.blind_item_id))
        payload = {
            "items": [item.to_dict() for item in ordered],
            "result_bundle_id": result_bundle_id,
            "run_id": run_id,
            "schema_version": 1,
        }
        return cls(
            pack_id=content_digest(payload),
            run_id=run_id,
            result_bundle_id=result_bundle_id,
            items=ordered,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"pack_id": self.pack_id, **self._payload()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hReviewPack":
        raw_items = value.get("items", [])
        if not isinstance(raw_items, list):
            raise ValueError("review-pack items must be an array")
        return cls(
            pack_id=value.get("pack_id", ""),
            run_id=value.get("run_id", ""),
            result_bundle_id=value.get("result_bundle_id", ""),
            items=tuple(BlindedReviewItem.from_dict(item) for item in raw_items),
            schema_version=value.get("schema_version", 0),
        )


@dataclass(frozen=True)
class Stage4hBlindMapEntry:
    blind_item_id: str
    result_id: str
    case_id: str
    arm: Stage4hArm
    proposal_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "blind_item_id",
            _digest(self.blind_item_id, field="blind_item_id"),
        )
        object.__setattr__(self, "result_id", _digest(self.result_id, field="result_id"))
        object.__setattr__(self, "case_id", _nonempty(self.case_id, field="case_id"))
        object.__setattr__(self, "proposal_id", _digest(self.proposal_id, field="proposal_id"))
        if self.arm not in {"A1", "A2", "A4"}:
            raise ValueError("only local generative arms belong in a blind map")

    def to_dict(self) -> dict[str, str]:
        return {
            "arm": self.arm,
            "blind_item_id": self.blind_item_id,
            "case_id": self.case_id,
            "proposal_id": self.proposal_id,
            "result_id": self.result_id,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hBlindMapEntry":
        return cls(
            blind_item_id=value.get("blind_item_id", ""),
            result_id=value.get("result_id", ""),
            case_id=value.get("case_id", ""),
            arm=value.get("arm", ""),
            proposal_id=value.get("proposal_id", ""),
        )


@dataclass(frozen=True)
class Stage4hBlindMap:
    mapping_id: str
    run_id: str
    pack_id: str
    blinding_key_sha256: str
    entries: tuple[Stage4hBlindMapEntry, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported Stage 4h blind-map version")
        object.__setattr__(self, "run_id", _digest(self.run_id, field="run_id"))
        object.__setattr__(self, "pack_id", _digest(self.pack_id, field="pack_id"))
        object.__setattr__(
            self,
            "blinding_key_sha256",
            _digest(self.blinding_key_sha256, field="blinding_key_sha256"),
        )
        ids = tuple(item.blind_item_id for item in self.entries)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("blind-map entries must be unique and sorted")
        if self.mapping_id != content_digest(self._payload()):
            raise ValueError("mapping_id does not match the Stage 4h blind map")

    def _payload(self) -> dict[str, Any]:
        return {
            "blinding_key_sha256": self.blinding_key_sha256,
            "entries": [item.to_dict() for item in self.entries],
            "pack_id": self.pack_id,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
        }

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        pack_id: str,
        blinding_key_sha256: str,
        entries: Iterable[Stage4hBlindMapEntry],
    ) -> "Stage4hBlindMap":
        ordered = tuple(sorted(entries, key=lambda item: item.blind_item_id))
        payload = {
            "blinding_key_sha256": blinding_key_sha256,
            "entries": [item.to_dict() for item in ordered],
            "pack_id": pack_id,
            "run_id": run_id,
            "schema_version": 1,
        }
        return cls(
            mapping_id=content_digest(payload),
            run_id=run_id,
            pack_id=pack_id,
            blinding_key_sha256=blinding_key_sha256,
            entries=ordered,
        )

    def to_dict(self) -> dict[str, Any]:
        return {"mapping_id": self.mapping_id, **self._payload()}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Stage4hBlindMap":
        raw_entries = value.get("entries", [])
        if not isinstance(raw_entries, list):
            raise ValueError("blind-map entries must be an array")
        return cls(
            mapping_id=value.get("mapping_id", ""),
            run_id=value.get("run_id", ""),
            pack_id=value.get("pack_id", ""),
            blinding_key_sha256=value.get("blinding_key_sha256", ""),
            entries=tuple(Stage4hBlindMapEntry.from_dict(item) for item in raw_entries),
            schema_version=value.get("schema_version", 0),
        )

    def resolve(self, blind_item_id: str) -> Stage4hBlindMapEntry:
        for item in self.entries:
            if item.blind_item_id == blind_item_id:
                return item
        raise KeyError(blind_item_id)


def new_blinding_key() -> bytes:
    return secrets.token_bytes(32)


def _blind_id(key: bytes, result: Stage4hArmResult) -> str:
    if len(key) < 16:
        raise ValueError("Stage 4h blinding key must contain at least 16 bytes")
    payload = f"stage4h-v1:{result.run_id}:{result.result_id}".encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def build_blinded_review_pack(
    *,
    result_bundle: Stage4hRunResultBundle,
    documents: Iterable[SourceDocument],
    blinding_key: bytes,
) -> tuple[Stage4hReviewPack, Stage4hBlindMap]:
    """Strip arm/model/method telemetry and resolve exact local citation excerpts."""
    document_values = tuple(documents)
    by_id = {item.source_id: item for item in document_values}
    if len(by_id) != len(document_values):
        raise ValueError("review source documents must have unique ids")

    items: list[BlindedReviewItem] = []
    map_entries: list[Stage4hBlindMapEntry] = []
    for result in result_bundle.results:
        if result.status != "generated":
            continue
        proposal = result.proposal
        assert proposal is not None
        citations: list[BlindedSourceExcerpt] = []
        for citation in proposal.citations:
            document = by_id.get(citation.source_id)
            if document is None:
                raise ValueError("review citation source is absent")
            citation.verify(document)
            metadata = document.metadata
            attribution = SourceAttribution.from_metadata(metadata)
            attribution.verify(document.text)
            temporal = metadata.get("temporal_context")
            citations.append(
                BlindedSourceExcerpt(
                    citation_id=citation.citation_id,
                    source_id=citation.source_id,
                    source_revision=citation.source_revision,
                    start=citation.start,
                    end=citation.end,
                    text_sha256=citation.text_sha256,
                    excerpt=document.text[citation.start : citation.end],
                    observed_at=document.observed_at,
                    display_time=metadata.get("display_time"),
                    message_id=(
                        str(metadata["message_id"])
                        if metadata.get("message_id") is not None
                        else None
                    ),
                    reply_to_source_id=metadata.get("reply_to_source_id"),
                    temporal_previous_source_id=(
                        temporal.get("previous_source_id")
                        if isinstance(temporal, dict)
                        else None
                    ),
                    attribution=attribution,
                )
            )
        blind_item_id = _blind_id(blinding_key, result)
        items.append(
            BlindedReviewItem(
                blind_item_id=blind_item_id,
                case_id=result.case_id,
                proposal_id=proposal.proposal_id,
                question=proposal.question,
                answer=proposal.answer,
                claims=proposal.claims,
                citations=tuple(citations),
            )
        )
        map_entries.append(
            Stage4hBlindMapEntry(
                blind_item_id=blind_item_id,
                result_id=result.result_id,
                case_id=result.case_id,
                arm=result.arm,
                proposal_id=proposal.proposal_id,
            )
        )
    pack = Stage4hReviewPack.create(
        run_id=result_bundle.run_id,
        result_bundle_id=result_bundle.bundle_id,
        items=items,
    )
    mapping = Stage4hBlindMap.create(
        run_id=result_bundle.run_id,
        pack_id=pack.pack_id,
        blinding_key_sha256=hashlib.sha256(blinding_key).hexdigest(),
        entries=map_entries,
    )
    return pack, mapping


def review_pack_json(pack: Stage4hReviewPack) -> str:
    return json.dumps(
        pack.to_dict(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )


def review_pack_markdown(pack: Stage4hReviewPack) -> str:
    lines = [
        "# Stage 4h — blinded owner review",
        "",
        "Arm, retrieval method, model and telemetry are intentionally hidden.",
        "Score each claim before the blind map is opened.",
        "To find a Telegram source in result.json, search for its numeric message_id ",
        "as an exact JSON id. Excerpts below are normalized text; source_id and ",
        "source_revision identify the exact FVSC source revision.",
        "",
        "For each claim record: (1) accepted / partially_accepted / rejected / ",
        "needs_revision and a correction; (2) supports / partial / unsupported for ",
        "each citation. Then score the whole item: meaning fidelity 0–4 and usefulness ",
        "0–4, and mark any safety/context flags.",
        "",
    ]
    for index, item in enumerate(pack.items, start=1):
        citations = {value.citation_id: value for value in item.citations}
        lines.extend(
            [
                f"## Item {index}: `{item.blind_item_id}`",
                "",
                f"Case: `{item.case_id}`",
                "",
                f"Question: {item.question}",
                "",
                f"Answer: {item.answer}",
                "",
                "### Claims",
                "",
            ]
        )
        for claim_index, claim in enumerate(item.claims, start=1):
            lines.extend(
                [
                    f"#### Claim {claim_index}: `{claim.claim_id}`",
                    "",
                    claim.text,
                    "",
                    f"Support level: `{claim.support_level}`",
                    "",
                ]
            )
            if not claim.citation_ids:
                lines.extend(["Citations: none", ""])
            for citation_id in claim.citation_ids:
                citation = citations[citation_id]
                context_lines: list[str] = []
                if citation.message_id is not None:
                    context_lines.append(f"message_id=`{citation.message_id}`")
                if citation.display_time is not None:
                    context_lines.append(f"time=`{citation.display_time}`")
                if citation.attribution is not None:
                    attribution = citation.attribution
                    context_lines.extend(
                        [
                            f"transport_author=`{attribution.transport_author_role}`",
                            "owner_adopted="
                            f"`{str(attribution.owner_adopted_expression).lower()}`",
                            f"text_origin=`{attribution.text_origin_status}`",
                            f"forwarded=`{str(attribution.forwarded).lower()}`",
                        ]
                    )
                    if attribution.forward_origin_role is not None:
                        context_lines.append(
                            f"forward_origin=`{attribution.forward_origin_role}`"
                        )
                lines.extend(
                    [
                        f"- Citation `{citation.citation_id}` — "
                        f"`{citation.source_id}` [{citation.start}:{citation.end}]",
                        "",
                        f"> {citation.excerpt.replace(chr(10), chr(10) + '> ')}",
                        "",
                    ]
                )
                if context_lines:
                    lines.extend([f"Source context: {', '.join(context_lines)}", ""])
                if citation.reply_to_source_id is not None:
                    lines.extend(
                        [f"Reply target: `{citation.reply_to_source_id}`", ""]
                    )
                if citation.temporal_previous_source_id is not None:
                    lines.extend(
                        [
                            "Temporal previous: "
                            f"`{citation.temporal_previous_source_id}` (heuristic context)",
                            "",
                        ]
                    )
                if citation.attribution is not None:
                    for span in citation.attribution.expression_spans:
                        lines.extend(
                            [
                                f"Expression span [{span.start}:{span.end}]: "
                                f"`{span.kind}`, origin=`{span.origin_status}`, "
                                f"owner_relation=`{span.owner_relation}`",
                                "",
                            ]
                        )
        lines.extend(
            [
                "Review fields: claim verdict; citation support; meaning fidelity 0–4; "
                "usefulness 0–4; false owner attribution; unsupported referent; "
                "forbidden composite; missed context; abstention preferable.",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


__all__ = [
    "BlindedReviewItem",
    "BlindedSourceExcerpt",
    "Stage4hBlindMap",
    "Stage4hBlindMapEntry",
    "Stage4hReviewPack",
    "build_blinded_review_pack",
    "new_blinding_key",
    "review_pack_json",
    "review_pack_markdown",
]
