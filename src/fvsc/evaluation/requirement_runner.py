"""Paired baseline/requirement-coverage runner for held-out public fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence

from ..integrations.ollama import OllamaGenerationTelemetry
from ..interpretation import GeneratedInterpretation
from .claim_first_runner import _claims, _raw_claims, _stored_claims
from .requirement_synthesis import (
    REQUIREMENT_COVERAGE_INSTRUCTION,
    REQUIREMENT_PROMPT_VERSION,
    RequirementCoverage,
    RequirementCoverageOutput,
    render_requirement_answer,
)
from .synthesis import SynthesisFixture
from .synthesis_runner import synthesis_system_prompt


class RequirementBackend(Protocol):
    last_generation_telemetry: OllamaGenerationTelemetry | None

    def generate_json_object(
        self, payload: dict[str, Any], *, source_count: int
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class RequirementGeneration:
    case_id: str
    arm: str
    status: str
    answer: str
    requirements: tuple[dict[str, Any], ...]
    claims: tuple[dict[str, Any], ...]
    telemetry: dict[str, Any] | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "arm": self.arm,
            "case_id": self.case_id,
            "claims": list(self.claims),
            "error": self.error,
            "requirements": list(self.requirements),
            "status": self.status,
            "telemetry": self.telemetry,
        }


def _requirements(value: object) -> tuple[RequirementCoverage, ...]:
    if not isinstance(value, list):
        raise ValueError("requirements must be a list")
    result: list[RequirementCoverage] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("requirement must be an object")
        indices = item.get("claim_indices")
        if not isinstance(indices, list):
            raise ValueError("requirement claim_indices must be a list")
        result.append(
            RequirementCoverage(
                requirement_id=item.get("requirement_id", ""),
                description=item.get("description", ""),
                status=item.get("status", ""),
                claim_indices=tuple(indices),
            )
        )
    return tuple(result)


def _stored_requirements(
    requirements: tuple[RequirementCoverage, ...],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "claim_indices": list(item.claim_indices),
            "description": item.description,
            "requirement_id": item.requirement_id,
            "status": item.status,
        }
        for item in requirements
    )


def _raw_requirements(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, dict))


def run_requirement_pair(
    fixtures: Sequence[SynthesisFixture],
    *,
    backend_factory: Callable[[str, str, str], RequirementBackend],
) -> tuple[RequirementGeneration, ...]:
    if not fixtures:
        raise ValueError("requirement run requires fixtures")
    ids = tuple(item.case_id for item in fixtures)
    if len(ids) != len(set(ids)):
        raise ValueError("requirement fixture ids must be unique")
    results: list[RequirementGeneration] = []
    for index, fixture in enumerate(fixtures):
        arms = (
            ("baseline", "requirement_coverage")
            if index % 2 == 0
            else ("requirement_coverage", "baseline")
        )
        payload = {
            "question": fixture.question,
            "sources": [
                {"label": source.label, "text": source.text}
                for source in fixture.sources
            ],
        }
        for arm in arms:
            prompt = (
                synthesis_system_prompt("baseline")
                if arm == "baseline"
                else REQUIREMENT_COVERAGE_INSTRUCTION
            )
            backend = backend_factory(
                arm,
                prompt,
                f"{REQUIREMENT_PROMPT_VERSION}-{arm}",
            )
            raw = backend.generate_json_object(
                payload, source_count=len(fixture.sources)
            )
            error = None
            try:
                claims = _claims(raw.get("claims"))
                if arm == "baseline":
                    answer = raw.get("answer")
                    if not isinstance(answer, str):
                        raise ValueError("baseline answer is missing")
                    generated = GeneratedInterpretation(answer, claims)
                    status = "answered"
                    answer = generated.answer
                    requirements: tuple[RequirementCoverage, ...] = ()
                else:
                    status = raw.get("status")
                    if not isinstance(status, str):
                        raise ValueError("requirement status is missing")
                    requirements = _requirements(raw.get("requirements"))
                    output = RequirementCoverageOutput(status, requirements, claims)
                    answer = render_requirement_answer(output)
                stored_claims = _stored_claims(claims)
                stored_requirements = _stored_requirements(requirements)
            except ValueError:
                status = "schema_error"
                answer = (
                    str(raw.get("answer")).strip()
                    if arm == "baseline" and str(raw.get("answer", "")).strip()
                    else "SCHEMA_ERROR"
                )
                stored_claims = _raw_claims(raw.get("claims"))
                stored_requirements = _raw_requirements(raw.get("requirements"))
                error = "invalid_structured_output"
            telemetry = backend.last_generation_telemetry
            results.append(
                RequirementGeneration(
                    fixture.case_id,
                    arm,
                    status,
                    answer,
                    stored_requirements,
                    stored_claims,
                    None if telemetry is None else telemetry.to_dict(),
                    error,
                )
            )
    return tuple(results)


__all__ = ["RequirementGeneration", "RequirementBackend", "run_requirement_pair"]
