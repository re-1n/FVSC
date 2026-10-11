"""Paired baseline/claim-first runner for public consistency fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence

from ..integrations.ollama import OllamaGenerationTelemetry
from ..interpretation.generation import GeneratedClaim, GeneratedInterpretation
from .claim_first_synthesis import (
    CLAIM_FIRST_INSTRUCTION,
    CLAIM_FIRST_PROMPT_VERSION,
    ClaimFirstOutput,
    render_claim_first_answer,
)
from .synthesis import SynthesisFixture
from .synthesis_runner import synthesis_system_prompt


class StructuredBackend(Protocol):
    last_generation_telemetry: OllamaGenerationTelemetry | None

    def generate_json_object(
        self,
        payload: dict[str, Any],
        *,
        source_count: int,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ClaimFirstGeneration:
    case_id: str
    arm: str
    status: str
    answer: str
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
            "status": self.status,
            "telemetry": self.telemetry,
        }


def _claims(raw_claims: object) -> tuple[GeneratedClaim, ...]:
    if not isinstance(raw_claims, list) or len(raw_claims) > 128:
        raise ValueError("structured claims must be a bounded list")
    result: list[GeneratedClaim] = []
    for raw in raw_claims:
        if not isinstance(raw, dict):
            raise ValueError("structured claim must be an object")
        text = raw.get("text")
        citations = raw.get("citations")
        support_level = raw.get("support_level")
        if (
            not isinstance(text, str)
            or not isinstance(citations, list)
            or not all(isinstance(item, str) for item in citations)
            or not isinstance(support_level, str)
        ):
            raise ValueError("structured claim schema is incomplete")
        result.append(
            GeneratedClaim(
                text=text,
                source_labels=tuple(citations),
                support_level=support_level,
            )
        )
    return tuple(result)


def _stored_claims(claims: tuple[GeneratedClaim, ...]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "citations": list(claim.source_labels),
            "support_level": claim.support_level,
            "text": claim.text,
        }
        for claim in claims
    )


def _raw_claims(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, dict))


def run_claim_first_pair(
    fixtures: Sequence[SynthesisFixture],
    *,
    backend_factory: Callable[[str, str, str], StructuredBackend],
) -> tuple[ClaimFirstGeneration, ...]:
    if not fixtures:
        raise ValueError("claim-first run requires fixtures")
    ids = tuple(item.case_id for item in fixtures)
    if len(ids) != len(set(ids)):
        raise ValueError("claim-first fixture ids must be unique")
    results: list[ClaimFirstGeneration] = []
    for index, fixture in enumerate(fixtures):
        arms = (
            ("baseline", "claim_first")
            if index % 2 == 0
            else ("claim_first", "baseline")
        )
        payload = {
            "question": fixture.question,
            "sources": [
                {"label": source.label, "text": source.text}
                for source in fixture.sources
            ],
        }
        for arm in arms:
            system_prompt = (
                synthesis_system_prompt("baseline")
                if arm == "baseline"
                else CLAIM_FIRST_INSTRUCTION
            )
            prompt_version = f"{CLAIM_FIRST_PROMPT_VERSION}-{arm}"
            backend = backend_factory(arm, system_prompt, prompt_version)
            raw = backend.generate_json_object(
                payload,
                source_count=len(fixture.sources),
            )
            error = None
            try:
                if arm == "baseline":
                    answer = raw.get("answer")
                    if not isinstance(answer, str):
                        raise ValueError("baseline structured answer is missing")
                    claims = _claims(raw.get("claims"))
                    generated = GeneratedInterpretation(answer=answer, claims=claims)
                    status = "answered"
                    answer = generated.answer
                else:
                    status = raw.get("status")
                    if not isinstance(status, str):
                        raise ValueError("claim-first status is missing")
                    claims = _claims(raw.get("claims"))
                    output = ClaimFirstOutput(status=status, claims=claims)
                    answer = render_claim_first_answer(output)
                stored_claims = _stored_claims(claims)
            except ValueError:
                status = "schema_error"
                answer = (
                    str(raw.get("answer")).strip()
                    if arm == "baseline" and str(raw.get("answer", "")).strip()
                    else "SCHEMA_ERROR"
                )
                stored_claims = _raw_claims(raw.get("claims"))
                error = "invalid_structured_output"
            telemetry = backend.last_generation_telemetry
            results.append(
                ClaimFirstGeneration(
                    case_id=fixture.case_id,
                    arm=arm,
                    status=status,
                    answer=answer,
                    claims=stored_claims,
                    telemetry=None if telemetry is None else telemetry.to_dict(),
                    error=error,
                )
            )
    return tuple(results)


__all__ = [
    "ClaimFirstGeneration",
    "StructuredBackend",
    "run_claim_first_pair",
]
