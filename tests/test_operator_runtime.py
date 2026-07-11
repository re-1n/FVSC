from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from core.operator_runtime import (
    OperatorContext,
    OperatorProposal,
    STATE_PROPOSE,
    STATE_READ,
    accept_execution,
    execute_operator,
)
from core.semantic_snapshot import (
    ConceptChange,
    SemanticSnapshot,
    SnapshotConcept,
    StateDelta,
)
from core.semantic_state import SemanticState


def _state(diagonal: list[float], *, mass: float = 1.0) -> SemanticState:
    shape = np.diag(diagonal).astype(float)
    shape /= np.trace(shape)
    return SemanticState(mass=mass, shape=shape, evidence_count=1)


def _snapshot() -> SemanticSnapshot:
    return SemanticSnapshot.create(
        concepts=[SnapshotConcept(term="свобода", state=_state([0.7, 0.3], mass=2.0))],
        origin="test",
    )


@dataclass(frozen=True)
class ReplaceOperator:
    operator_id: str = "replace-shape"
    operator_version: str = "1"
    required_capabilities: frozenset[str] = frozenset({STATE_READ, STATE_PROPOSE})

    def propose(self, snapshot: SemanticSnapshot, context: OperatorContext) -> OperatorProposal:
        current = snapshot.get("свобода")
        assert current is not None
        delta = StateDelta.create(
            base_snapshot_id=snapshot.snapshot_id,
            operator_id=self.operator_id,
            operator_version=self.operator_version,
            changes=[
                ConceptChange(
                    term="свобода",
                    proposed_state=_state([0.9, 0.1], mass=current.state.mass),
                    evidence_ids=current.evidence_ids,
                    reason="activate requested context",
                )
            ],
            confidence=0.8,
            speculative=True,
            metadata={"request_id": context.request_id},
        )
        return OperatorProposal.create(
            delta=delta,
            artifacts={"explanation": "contextual branch only"},
            warnings=["not canonical evidence"],
        )


def _context(*, capabilities: frozenset[str] | None = None) -> OperatorContext:
    return OperatorContext.create(
        request_id="request-1",
        granted_capabilities=capabilities or frozenset({STATE_READ, STATE_PROPOSE}),
        input_text="рассмотри свободу в рабочем контексте",
        context_tags=["work"],
        seed=7,
        metadata={"locale": "ru"},
    )


def test_execute_returns_proposal_without_mutating_snapshot() -> None:
    snapshot = _snapshot()
    before = snapshot.get("свобода")
    assert before is not None
    before_operator = before.state.to_operator()

    execution = execute_operator(
        ReplaceOperator(),
        snapshot=snapshot,
        context=_context(),
    )

    after = snapshot.get("свобода")
    assert after is not None
    assert np.array_equal(after.state.to_operator(), before_operator)
    assert execution.base_snapshot_id == snapshot.snapshot_id
    assert execution.proposal.delta.base_snapshot_id == snapshot.snapshot_id
    assert execution.proposal.artifacts["explanation"] == "contextual branch only"
    assert execution.proposal.warnings == ("not canonical evidence",)


def test_accept_execution_creates_child_snapshot_explicitly() -> None:
    base = _snapshot()
    execution = execute_operator(ReplaceOperator(), snapshot=base, context=_context())

    child = accept_execution(base, execution)

    assert child.parent_snapshot_id == base.snapshot_id
    assert child.snapshot_id != base.snapshot_id
    changed = child.get("свобода")
    original = base.get("свобода")
    assert changed is not None and original is not None
    assert changed.state.mass == pytest.approx(original.state.mass)
    assert not np.array_equal(changed.state.shape, original.state.shape)


def test_missing_capability_blocks_operator_before_execution() -> None:
    with pytest.raises(PermissionError, match="state:propose"):
        execute_operator(
            ReplaceOperator(),
            snapshot=_snapshot(),
            context=_context(capabilities=frozenset({STATE_READ})),
        )


def test_execution_id_is_deterministic_for_same_inputs() -> None:
    snapshot = _snapshot()
    operator = ReplaceOperator()
    context = _context()

    first = execute_operator(operator, snapshot=snapshot, context=context)
    second = execute_operator(operator, snapshot=snapshot, context=context)

    assert first.execution_id == second.execution_id
    assert first.proposal.delta.delta_id == second.proposal.delta.delta_id


def test_runtime_rejects_delta_with_mismatched_operator_identity() -> None:
    @dataclass(frozen=True)
    class BadOperator:
        operator_id: str = "declared"
        operator_version: str = "1"
        required_capabilities: frozenset[str] = frozenset({STATE_READ})

        def propose(self, snapshot: SemanticSnapshot, context: OperatorContext) -> OperatorProposal:
            delta = StateDelta.create(
                base_snapshot_id=snapshot.snapshot_id,
                operator_id="different",
                operator_version="1",
                changes=[],
                confidence=1.0,
                speculative=False,
            )
            return OperatorProposal.create(delta=delta)

    with pytest.raises(ValueError, match="mismatched identity"):
        execute_operator(
            BadOperator(),
            snapshot=_snapshot(),
            context=_context(capabilities=frozenset({STATE_READ})),
        )


def test_runtime_rejects_delta_for_different_base_snapshot() -> None:
    @dataclass(frozen=True)
    class WrongBaseOperator:
        operator_id: str = "wrong-base"
        operator_version: str = "1"
        required_capabilities: frozenset[str] = frozenset({STATE_READ})

        def propose(self, snapshot: SemanticSnapshot, context: OperatorContext) -> OperatorProposal:
            delta = StateDelta.create(
                base_snapshot_id="0" * 64,
                operator_id=self.operator_id,
                operator_version=self.operator_version,
                changes=[],
                confidence=1.0,
                speculative=False,
            )
            return OperatorProposal.create(delta=delta)

    with pytest.raises(ValueError, match="different base"):
        execute_operator(
            WrongBaseOperator(),
            snapshot=_snapshot(),
            context=_context(capabilities=frozenset({STATE_READ})),
        )


def test_artifact_access_returns_copy() -> None:
    execution = execute_operator(
        ReplaceOperator(),
        snapshot=_snapshot(),
        context=_context(),
    )

    artifacts = execution.proposal.artifacts
    artifacts["explanation"] = "mutated"

    assert execution.proposal.artifacts["explanation"] == "contextual branch only"
