from __future__ import annotations

from io import BytesIO
import hashlib
import json
import urllib.error

import pytest

from fvsc.ingest import SourceDocument
from fvsc.integrations import OllamaIntegrationError, OllamaInterpretationBackend
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
    document = SourceDocument.create(
        source_id="private/diary/message-334",
        source_revision=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        observed_at=1.0,
        text=text,
        adapter="test",
        source_kind="owner_reflection",
        raw_chars=len(text),
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
    assert "Паразиты" in user_payload
    assert sent["format"] == "json"
    assert sent["stream"] is False


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
    assert sent["options"] == {"temperature": 0.0, "num_ctx": 8_192, "seed": 42}
    telemetry = backend.last_generation_telemetry
    assert telemetry is not None
    assert telemetry.model_digest == digest
    assert telemetry.prompt_eval_count == 20
    assert telemetry.eval_count == 8
    assert telemetry.source_count == 1
    assert telemetry.prompt_chars > len(_source().text)


def test_stage4h_seed_and_model_digest_validation_fail_closed() -> None:
    with pytest.raises(ValueError, match="seed"):
        OllamaInterpretationBackend(seed=-1, opener=_Opener())
    with pytest.raises(ValueError, match="model_digest"):
        OllamaInterpretationBackend(model_digest="not-a-digest", opener=_Opener())
