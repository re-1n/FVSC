"""Capability-scoped execution runtime for FVSC semantic operators."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Protocol

from .semantic_snapshot import SemanticSnapshot, StateDelta, apply_delta


STATE_READ = "state:read"
STATE_PROPOSE = "state:propose"
EVIDENCE_READ = "evidence:read"
SCENARIO_RANDOM = "scenario:random"
CROSS_PERSON_ALIGNMENT = "alignment:cross-person"


def _json(value: Mapping[str, Any] | None, *, field_name: str) -> str:
    try:
        return json.dumps(
            dict(value or {}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain JSON values") from exc


@dataclass(frozen=True)
class OperatorContext:
    request_id: str
    granted_capabilities: frozenset[str]
    input_text: str = ""
    context_tags: tuple[str, ...] = ()
    seed: int | None = None
    metadata_json: str = "{}"

    @classmethod
    def create(
        cls,
        *,
        request_id: str,
        granted_capabilities: set[str] | frozenset[str] | tuple[str, ...],
        input_text: str = "",
        context_tags: tuple[str, ...] | list[str] = (),
        seed: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "OperatorContext":
        request_clean = str(request_id).strip()
        if not request_clean:
            raise ValueError("request_id must not be empty")
        if seed is not None:
            if isinstance(seed, bool) or int(seed) != seed:
                raise ValueError("seed must be an integer or None")
            seed = int(seed)
        capabilities = frozenset(
            str(capability).strip()
            for capability in granted_capabilities
            if str(capability).strip()
        )
        tags = tuple(sorted(set(str(tag).strip() for tag in context_tags if str(tag).strip())))
        return cls(
            request_id=request_clean,
            granted_capabilities=capabilities,
            input_text=str(input_text),
            context_tags=tags,
            seed=seed,
            metadata_json=_json(metadata, field_name="operator metadata"),
        )

    @property
    def metadata(self) -> dict[str, Any]:
        return json.loads(self.metadata_json)

    @property
    def digest(self) -> str:
        payload = {
            "request_id": self.request_id,
            "granted_capabilities": sorted(self.granted_capabilities),
            "input_text": self.input_text,
            "context_tags": list(self.context_tags),
            "seed": self.seed,
            "metadata": self.metadata,
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OperatorProposal:
    delta: StateDelta
    artifacts_json: str = "{}"
    warnings: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        delta: StateDelta,
        artifacts: Mapping[str, Any] | None = None,
        warnings: tuple[str, ...] | list[str] = (),
    ) -> "OperatorProposal":
        return cls(
            delta=delta,
            artifacts_json=_json(artifacts, field_name="operator artifacts"),
            warnings=tuple(str(warning).strip() for warning in warnings if str(warning).strip()),
        )

    @property
    def artifacts(self) -> dict[str, Any]:
        return json.loads(self.artifacts_json)


class SemanticOperator(Protocol):
    operator_id: str
    operator_version: str
    required_capabilities: frozenset[str]

    def propose(
        self,
        snapshot: SemanticSnapshot,
        context: OperatorContext,
    ) -> OperatorProposal: ...


@dataclass(frozen=True)
class OperatorExecution:
    execution_id: str
    operator_id: str
    operator_version: str
    base_snapshot_id: str
    context_digest: str
    proposal: OperatorProposal


def execute_operator(
    operator: SemanticOperator,
    *,
    snapshot: SemanticSnapshot,
    context: OperatorContext,
) -> OperatorExecution:
    """Execute an operator as a pure proposal and validate its result contract."""
    operator_id = str(operator.operator_id).strip()
    operator_version = str(operator.operator_version).strip()
    if not operator_id or not operator_version:
        raise ValueError("operator id and version must not be empty")

    required = frozenset(operator.required_capabilities)
    missing = required - context.granted_capabilities
    if missing:
        raise PermissionError(
            "operator requires capabilities that were not granted: "
            + ", ".join(sorted(missing))
        )

    snapshot_id_before = snapshot.snapshot_id
    proposal = operator.propose(snapshot, context)
    if not isinstance(proposal, OperatorProposal):
        raise TypeError("operator must return OperatorProposal")
    if snapshot.snapshot_id != snapshot_id_before:
        raise RuntimeError("operator mutated the supplied snapshot")

    delta = proposal.delta
    if delta.base_snapshot_id != snapshot.snapshot_id:
        raise ValueError("operator returned a delta for a different base snapshot")
    if delta.operator_id != operator_id or delta.operator_version != operator_version:
        raise ValueError("operator returned a delta with mismatched identity")

    execution_id = hashlib.sha256(
        (
            snapshot.snapshot_id
            + context.digest
            + delta.delta_id
            + operator_id
            + operator_version
        ).encode("utf-8")
    ).hexdigest()
    return OperatorExecution(
        execution_id=execution_id,
        operator_id=operator_id,
        operator_version=operator_version,
        base_snapshot_id=snapshot.snapshot_id,
        context_digest=context.digest,
        proposal=proposal,
    )


def accept_execution(
    base: SemanticSnapshot,
    execution: OperatorExecution,
) -> SemanticSnapshot:
    """Explicitly accept an execution proposal and create a child snapshot."""
    if execution.base_snapshot_id != base.snapshot_id:
        raise ValueError("execution does not belong to the supplied base snapshot")
    return apply_delta(base, execution.proposal.delta)
