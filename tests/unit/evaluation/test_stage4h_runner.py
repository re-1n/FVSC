from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from fvsc.evaluation import (
    EvidenceRef,
    FrozenCandidate,
    FrozenCandidateBundle,
    FrozenCandidateSet,
    GoldCase,
    Stage4hModelConfig,
    Stage4hRunResultBundle,
    Stage4hRunSpec,
    corpus_digest,
    run_local_stage4h,
)
from fvsc.ingest import SourceDocument
from fvsc.interpretation import GeneratedClaim, GeneratedInterpretation


_MODEL_DIGEST = "d" * 64


def _document(source_id: str, text: str) -> SourceDocument:
    return SourceDocument.create(
        source_id=source_id,
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=1.0,
        text=text,
        adapter="test",
        source_kind="owner_reflection",
        raw_chars=len(text),
    )


class _Backend:
    backend_id = "local.test"
    model = "test:model"
    model_digest = _MODEL_DIGEST
    prompt_version = "stage4h-v1"
    interpretation_layer = 3
    temperature = 0.0
    seed = 42
    num_ctx = 8_192

    def __init__(self) -> None:
        self.calls = []
        self.last_generation_telemetry = None

    def generate(self, question, sources):
        self.calls.append((question, sources))
        self.last_generation_telemetry = SimpleNamespace(
            model=self.model,
            model_digest=self.model_digest,
            source_count=len(sources),
            prompt_chars=100 + sum(len(item.text) for item in sources),
            prompt_eval_count=20,
            eval_count=8,
            done_reason="stop",
        )
        return GeneratedInterpretation(
            answer="Проверяемая интерпретация.",
            claims=(
                GeneratedClaim(
                    text="Первый источник поддерживает утверждение.",
                    source_labels=("S1",),
                ),
            ),
        )


def _case() -> GoldCase:
    return GoldCase(
        case_id="gold-001",
        title="Metaphor",
        question="Какую роль играет образ?",
        decision="open",
        evidence=(EvidenceRef("Diary:1", "message-1", "primary"),),
        owner_interpretation="СЕКРЕТНАЯ GOLD ИНТЕРПРЕТАЦИЯ",
    )


def _spec(documents) -> Stage4hRunSpec:
    return Stage4hRunSpec(
        gold_sha256="a" * 64,
        challenge_sha256="b" * 64,
        corpus_sha256=corpus_digest(documents),
        case_ids=("gold-001",),
        arms=("A0", "A1", "A2", "A4"),
        model=Stage4hModelConfig(
            backend_id="local.test",
            model="test:model",
            model_digest=_MODEL_DIGEST,
            prompt_version="stage4h-v1",
            temperature=0.0,
            seed=42,
            num_ctx=8_192,
        ),
        created_at=1.0,
        top_k=1,
        prompt_source_cap=1,
        context_depth=0,
    )


def _candidate_set(spec, document, arm, *, empty=False):
    candidates = () if empty else (
        FrozenCandidate(
            rank=1,
            source_id=document.source_id,
            source_revision=document.source_revision,
            role="oracle" if arm == "A2" else "ranked",
        ),
    )
    return FrozenCandidateSet.create(
        run_id=spec.run_id,
        case_id="gold-001",
        arm=arm,
        retrieval_method=(
            "owner-gold-oracle-v1" if arm == "A2" else f"{arm.lower()}-method"
        ),
        candidates=candidates,
    )


def _bundle(spec, document, *, empty_a4=True):
    return FrozenCandidateBundle.create(
        spec=spec,
        candidate_sets=tuple(
            _candidate_set(spec, document, arm, empty=empty_a4 and arm == "A4")
            for arm in spec.arms
        ),
    )


def test_local_runner_executes_paired_arms_without_passing_gold_meaning() -> None:
    document = _document("message-1", "Паразиты захватывают внимание.")
    documents = (document,)
    spec = _spec(documents)
    backend = _Backend()
    times = iter((10.0, 11.0, 12.0, 13.0))
    timer_values = iter((1.0, 1.5, 2.0, 2.75))

    result = run_local_stage4h(
        spec=spec,
        candidate_bundle=_bundle(spec, document),
        cases=(_case(),),
        documents=documents,
        backend=backend,
        clock=lambda: next(times),
        timer=lambda: next(timer_values),
    )

    assert result.for_case_arm("gold-001", "A0").status == "extractive"
    assert result.for_case_arm("gold-001", "A1").status == "generated"
    assert result.for_case_arm("gold-001", "A2").status == "generated"
    assert result.for_case_arm("gold-001", "A4").status == "no_candidates"
    assert len(backend.calls) == 2
    assert all(call[0] == _case().question for call in backend.calls)
    assert all(
        "СЕКРЕТНАЯ" not in source.text
        for _, sources in backend.calls
        for source in sources
    )
    telemetry = result.for_case_arm("gold-001", "A1").telemetry
    assert telemetry is not None
    assert telemetry.model_digest == _MODEL_DIGEST
    assert telemetry.prompt_eval_count == 20
    assert telemetry.wall_seconds == pytest.approx(0.5)

    encoded = json.dumps(result.to_dict(), ensure_ascii=False)
    assert "СЕКРЕТНАЯ GOLD" not in encoded
    assert Stage4hRunResultBundle.from_dict(json.loads(encoded)) == result


def test_runner_refuses_backend_or_source_revision_drift() -> None:
    document = _document("message-1", "Исходная версия.")
    spec = _spec((document,))
    bundle = _bundle(spec, document)
    backend = _Backend()
    backend.seed = 7
    with pytest.raises(ValueError, match="seed"):
        run_local_stage4h(
            spec=spec,
            candidate_bundle=bundle,
            cases=(_case(),),
            documents=(document,),
            backend=backend,
        )

    changed = _document("message-1", "Изменённая версия.")
    backend.seed = 42
    with pytest.raises(ValueError, match="revision changed"):
        run_local_stage4h(
            spec=spec,
            candidate_bundle=bundle,
            cases=(_case(),),
            documents=(changed,),
            backend=backend,
        )


def test_runner_requires_model_digest_and_never_accepts_a3() -> None:
    document = _document("message-1", "Исходная версия.")
    base = _spec((document,))
    no_digest = Stage4hRunSpec(
        **{
            **{key: value for key, value in base.__dict__.items() if key != "model"},
            "model": Stage4hModelConfig(
                backend_id="local.test",
                model="test:model",
                prompt_version="stage4h-v1",
            ),
        }
    )
    with pytest.raises(ValueError, match="model digest"):
        run_local_stage4h(
            spec=no_digest,
            candidate_bundle=_bundle(no_digest, document),
            cases=(_case(),),
            documents=(document,),
            backend=_Backend(),
        )

    with_a3 = Stage4hRunSpec(
        **{
            **{key: value for key, value in base.__dict__.items() if key != "arms"},
            "arms": ("A0", "A1", "A2", "A3", "A4"),
            "external_reference_scope": "explicitly approved source fragments",
        }
    )
    with pytest.raises(ValueError, match="A3"):
        run_local_stage4h(
            spec=with_a3,
            candidate_bundle=_bundle(with_a3, document),
            cases=(_case(),),
            documents=(document,),
            backend=_Backend(),
        )
