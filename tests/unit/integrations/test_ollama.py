from __future__ import annotations

from io import BytesIO
import hashlib
import json
import urllib.error

import pytest

from fvsc.ingest import ExpressionSpan, SourceDocument, source_attribution
from fvsc.integrations import (
    OllamaEmbeddingBackend,
    OllamaIntegrationError,
    OllamaInterpretationBackend,
)
from fvsc.interpretation import PromptSource


class _Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class _Opener:
    def __init__(self, responses: list[dict] | None = None, raw: bytes | None = None):
        self.responses = list(responses or [])
        self.raw = raw
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        if self.raw is not None:
            return _Response(self.raw)
        value = self.responses.pop(0)
        return _Response(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def _source() -> PromptSource:
    text = "Паразиты превращают внимание в чужой ресурс."
    span = ExpressionSpan.from_text(
        text,
        start=0,
        end=len("Паразиты"),
        kind="quotation",
        owner_relation="adopted",
        owner_endorsement="endorsed",
        derivation="test:v1",
    )
    attribution = source_attribution(
        transport_author_role="owner",
        owner_adopted_expression=True,
        forwarded=True,
        forward_origin_role="non_owner",
        expression_spans=(span,),
    )
    document = SourceDocument.create(
        source_id="private/diary/message-334",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=1.0,
        text=text,
        adapter="test",
        source_kind="owner_reflection",
        raw_chars=len(text),
        metadata={
            "display_time": "2026-01-01T03:00:00+03:00",
            "message_id": "334",
            "owner_adopted_expression": True,
            "owner_authored": True,
            "reply_to_source_id": "private/diary/message-333",
            "source_attribution": attribution.to_dict(),
            "temporal_context": {
                "previous_source_id": "private/diary/message-333",
            },
        },
    )
    return PromptSource.from_document(document, label="S1")


def test_ollama_generates_strict_claims_without_exposing_source_ids_to_model() -> None:
    model_content = {
        "answer": "Образ описывает захват внимания.",
        "claims": [
            {
                "text": "Внимание представлено захваченным ресурсом.",
                "citations": ["S1"],
                "support_level": "evidence_bound",
            }
        ],
    }
    opener = _Opener(
        responses=[{"message": {"content": json.dumps(model_content, ensure_ascii=False)}}]
    )
    backend = OllamaInterpretationBackend(opener=opener)

    result = backend.generate("Какова роль паразитов?", (_source(),))

    assert result.claims[0].source_labels == ("S1",)
    request = opener.requests[0][0]
    sent = json.loads(request.data.decode("utf-8"))
    user_payload = sent["messages"][1]["content"]
    assert "private/diary/message-334" not in user_payload
    assert "private/diary/message-333" not in user_payload
    assert "Паразиты" in user_payload
    decoded_payload = json.loads(user_payload)
    source = decoded_payload["sources"][0]
    assert source["message_id"] == "334"
    assert source["display_time"] == "2026-01-01T03:00:00+03:00"
    assert source["reply_to"] == "outside_prompt"
    assert source["temporal_previous"] == "outside_prompt"
    assert source["attribution"] == {
        "expression_spans": [
            {
                "end": len("Паразиты"),
                "kind": "quotation",
                "origin_status": "unresolved",
                "owner_endorsement": "endorsed",
                "owner_relation": "adopted",
                "start": 0,
            }
        ],
        "forward_origin_role": "non_owner",
        "forwarded": True,
        "owner_adopted_expression": True,
        "schema_version": 1,
        "text_origin_status": "unresolved",
        "transport_author_role": "owner",
    }
    assert sent["format"] == "json"
    assert sent["stream"] is False


def test_ollama_accepts_a_preregistered_prompt_variant() -> None:
    model_content = {
        "answer": "Кратко.",
        "claims": [
            {
                "text": "Подтверждено.",
                "citations": ["S1"],
                "support_level": "evidence_bound",
            }
        ],
    }
    opener = _Opener(
        responses=[{"message": {"content": json.dumps(model_content)}}]
    )
    backend = OllamaInterpretationBackend(
        model="test-model",
        system_prompt="Registered synthetic instruction.",
        prompt_version="synthetic-v1",
        opener=opener,
    )

    backend.generate("Question?", (_source(),))

    payload = json.loads(opener.requests[0][0].data)
    assert payload["messages"][0]["content"] == "Registered synthetic instruction."
    assert backend.prompt_version == "synthetic-v1"
    assert backend.last_generation_telemetry is not None
    assert backend.last_generation_telemetry.prompt_version == "synthetic-v1"


@pytest.mark.parametrize(
    "host",
    (
        "https://example.com:11434",
        "http://user:pass@127.0.0.1:11434",
        "http://127.0.0.1:11434/api",
    ),
)
def test_ollama_host_is_restricted_to_bare_loopback_origin(host) -> None:
    with pytest.raises(ValueError):
        OllamaInterpretationBackend(host=host, opener=_Opener())


def test_invalid_or_oversized_ollama_output_fails_without_echoing_private_text() -> None:
    malformed = _Opener(responses=[{"message": {"content": "not json"}}])
    backend = OllamaInterpretationBackend(opener=malformed)
    with pytest.raises(OllamaIntegrationError, match="not valid JSON") as caught:
        backend.generate("Question", (_source(),))
    assert "Паразиты" not in str(caught.value)

    oversized = _Opener(raw=b"x" * 1_025)
    backend = OllamaInterpretationBackend(
        opener=oversized,
        max_response_bytes=1_024,
    )
    with pytest.raises(OllamaIntegrationError, match="size limit"):
        backend.generate("Question", (_source(),))


def test_model_listing_is_deterministic_and_transport_failures_are_safe() -> None:
    opener = _Opener(
        responses=[
            {
                "models": [
                    {"name": "zeta:latest"},
                    {"name": "alpha:latest"},
                    {"name": "alpha:latest"},
                ]
            }
        ]
    )
    backend = OllamaInterpretationBackend(opener=opener)
    assert backend.list_local_models() == ("alpha:latest", "zeta:latest")

    class Broken:
        def open(self, request, timeout):
            raise urllib.error.URLError("private transport detail")

    broken = OllamaInterpretationBackend(opener=Broken())
    assert broken.ping() is False


def test_generation_timeout_is_reported_separately_from_connection_failure() -> None:
    class TimedOut:
        def open(self, request, timeout):
            raise TimeoutError

    backend = OllamaInterpretationBackend(opener=TimedOut(), timeout=12.5)
    with pytest.raises(OllamaIntegrationError, match="timed out after 12.5 seconds"):
        backend.generate("Question", (_source(),))


def test_stage4h_options_identity_and_generation_telemetry_are_explicit() -> None:
    digest = "d" * 64
    model_content = {
        "answer": "Образ описывает захват внимания.",
        "claims": [
            {
                "text": "Внимание представлено захваченным ресурсом.",
                "citations": ["S1"],
                "support_level": "evidence_bound",
            }
        ],
    }
    opener = _Opener(
        responses=[
            {
                "models": [
                    {
                        "name": "qwen:test",
                        "model": "qwen:test",
                        "digest": digest,
                        "size": 123,
                    }
                ]
            },
            {
                "model": "qwen:test",
                "message": {"content": json.dumps(model_content, ensure_ascii=False)},
                "done": True,
                "done_reason": "stop",
                "total_duration": 10,
                "load_duration": 1,
                "prompt_eval_count": 20,
                "prompt_eval_duration": 2,
                "eval_count": 8,
                "eval_duration": 7,
            },
        ]
    )
    backend = OllamaInterpretationBackend(
        model="qwen:test",
        model_digest=digest,
        temperature=0.0,
        seed=42,
        num_ctx=8_192,
        opener=opener,
    )

    identity = backend.model_identity()
    assert identity is not None
    assert identity.digest == digest
    backend.generate("Какова роль паразитов?", (_source(),))

    request = opener.requests[1][0]
    sent = json.loads(request.data.decode("utf-8"))
    assert sent["options"] == {
        "temperature": 0.0,
        "num_ctx": 8_192,
        "num_predict": 768,
        "seed": 42,
    }
    telemetry = backend.last_generation_telemetry
    assert telemetry is not None
    assert telemetry.model_digest == digest
    assert telemetry.num_predict == 768
    assert telemetry.prompt_eval_count == 20
    assert telemetry.eval_count == 8
    assert telemetry.source_count == 1
    assert telemetry.prompt_chars > len(_source().text)


def test_stage4h_seed_and_model_digest_validation_fail_closed() -> None:
    with pytest.raises(ValueError, match="seed"):
        OllamaInterpretationBackend(seed=-1, opener=_Opener())
    with pytest.raises(ValueError, match="model_digest"):
        OllamaInterpretationBackend(model_digest="not-a-digest", opener=_Opener())
    with pytest.raises(ValueError, match="num_predict"):
        OllamaInterpretationBackend(num_predict=0, opener=_Opener())


def test_embedding_backend_validates_batch_and_dimensions() -> None:
    opener = _Opener(
        responses=[
            {
                "model": "embed:test",
                "embeddings": [[0.1, 0.2], [0.3, 0.4]],
            }
        ]
    )
    backend = OllamaEmbeddingBackend(model="embed:test", opener=opener)

    assert backend.embed(("первый смысл", "второй смысл")) == (
        (0.1, 0.2),
        (0.3, 0.4),
    )
    request = opener.requests[0][0]
    assert request.full_url == "http://127.0.0.1:11434/api/embed"
    sent = json.loads(request.data.decode("utf-8"))
    assert sent == {
        "model": "embed:test",
        "input": ["первый смысл", "второй смысл"],
    }

    with pytest.raises(ValueError, match="non-empty tuple"):
        backend.embed(())


@pytest.mark.parametrize(
    "response, message",
    [
        ({"embeddings": [[0.1]]}, "batch"),
        ({"embeddings": [[0.1], []]}, "invalid embedding"),
        ({"embeddings": [[0.1], [0.2, 0.3]]}, "inconsistent"),
        ({"embeddings": [[0.1], [float("nan")]]}, "non-finite"),
    ],
)
def test_embedding_backend_rejects_malformed_vectors(response, message) -> None:
    backend = OllamaEmbeddingBackend(
        model="embed:test",
        opener=_Opener(responses=[response]),
    )
    with pytest.raises(OllamaIntegrationError, match=message):
        backend.embed(("one", "two"))
