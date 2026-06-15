"""Interpretation tests — does Антураж читать образ через ρ пользователя?

Use case (interpretation_lens_vision.md):
    User даёт несколько абстракций/ситуаций своей жизни + один образ.
    Антураж разворачивает образ ЧЕРЕЗ карту пользователя, не через словарь.

Метрики каждого кейса:
    1. response_text     — стрим завершился, текст непустой
    2. personal_hits     — сколько [[concept:X]] из ОТВЕТА совпадает с карта.concepts
    3. canonical_hits    — сколько [[concept:X]] совпадает с anti_concepts кейса
                           (если высокий — модель скатилась к канонике)
    4. divergence_score  — personal_hits / max(1, personal_hits + canonical_hits)
                           1.0 = чистое личное прочтение, 0.0 = чистая каноника

Пороги (мягкие, можно подкручивать):
    - response_text непустой        — обязательно
    - personal_hits >= 2             — обязательно
    - divergence_score >= 0.6        — обязательно

Запуск:
    1) Backend: python -m uvicorn service.app:app --host 127.0.0.1 --port 8765
    2) Карта должна быть собрана (POST /viz/build_from_vault или существующий cache)
    3) Ollama должен отвечать
    4) python -m pytest service/tests/test_interpretation.py -v -s
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest


BASE = "http://127.0.0.1:8765"
CASES_PATH = Path(__file__).parent / "interpretation_cases.json"

_MARKER_RE = re.compile(r"\[\[(concept|edge|note|judgment|word):([^\]]+)\]\]")


def _load_cases() -> list[dict]:
    raw = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return [c for c in raw if not c["name"].startswith("_")]


def _build_user_message(case: dict) -> str:
    bullets = "\n".join(f"- {line}" for line in case["experience"])
    return (
        f"Мой опыт:\n{bullets}\n\n"
        f"Образ: «{case['image']}»\n\n"
        f"{case['instruction']}"
    )


def _stream_ask(messages: list[dict], timeout: float = 120.0) -> dict:
    """Hit /viz/ask, parse SSE, return dict with text, highlights, error?"""
    text_parts: list[str] = []
    highlights: list[dict] = []
    error: str | None = None
    done = False

    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", f"{BASE}/viz/ask",
                           json={"messages": messages, "stub": False}) as r:
            assert r.status_code == 200, f"viz/ask: {r.status_code} {r.text}"
            event_type: str | None = None
            for line in r.iter_lines():
                if not line:
                    event_type = None
                    continue
                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    payload_raw = line[5:].strip()
                    try:
                        payload = json.loads(payload_raw)
                    except json.JSONDecodeError:
                        continue
                    if event_type == "token":
                        text_parts.append(payload.get("text", ""))
                    elif event_type == "highlight":
                        highlights.append(payload)
                    elif event_type == "error":
                        error = payload.get("message", "<no message>")
                    elif event_type == "done":
                        done = True

    full_text = "".join(text_parts)
    inline_markers = _MARKER_RE.findall(full_text)
    return {
        "text": full_text,
        "highlights": highlights,
        "inline_markers": inline_markers,
        "error": error,
        "done": done,
    }


# ── fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def status():
    r = httpx.get(f"{BASE}/viz/status", timeout=5.0)
    if r.status_code != 200:
        pytest.skip(f"backend not running: {r.status_code}")
    return r.json()


@pytest.fixture(scope="module")
def known_concepts(status):
    if not status.get("space_loaded"):
        pytest.skip("карта не построена — открой плагин и нажми «Построить карту» или вызови POST /viz/build_from_vault")
    if not status.get("ollama_up"):
        pytest.skip(f"ollama down ({status.get('model')}) — запусти Ollama")
    # Pull full vocabulary via /silent + a probe. Easier: just collect from /viz HTML graph?
    # Simpler — use concept_count as sanity, but membership check uses /viz/concepts/.../sources.
    return status


def _is_known(term: str) -> bool:
    """A concept counts as 'personal' if /viz/concepts/{term}/sources resolves
    (200) — i.e. either strong concept or silent_pool entry.
    """
    r = httpx.get(f"{BASE}/viz/concepts/{term}/sources", timeout=10.0)
    return r.status_code == 200


# ── parameterised test ─────────────────────────────────────────────

@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["name"])
def test_interpretation_case(case, known_concepts):
    messages = [{"role": "user", "content": _build_user_message(case)}]
    result = _stream_ask(messages)

    # 1. Stream completed
    assert result["error"] is None, f"SSE error: {result['error']}"
    assert result["done"], "SSE didn't emit done"
    assert result["text"].strip(), "Empty response text"

    # 2. Collect concept terms (highlight events are pre-filtered against known_terms
    #    by viz_session.stream_response; inline markers in text aren't filtered).
    concept_terms_filtered = {
        h["term"] for h in result["highlights"] if h.get("kind") == "concept"
    }
    concept_terms_inline = {
        body.strip()
        for (kind, body) in result["inline_markers"]
        if kind == "concept"
    }
    concept_terms_inline -= concept_terms_filtered  # avoid double-counting

    # 3. Personal hits — filtered highlights are already vetted by the backend.
    personal_terms = set(concept_terms_filtered)
    for t in concept_terms_inline:
        if _is_known(t):
            personal_terms.add(t)

    # 4. Canonical hits — anti_concepts that LLM still pushed (unfiltered text)
    anti = {a.lower() for a in case.get("anti_concepts", [])}
    text_lower = result["text"].lower()
    canonical_hits = sum(1 for a in anti if a in text_lower)

    personal_hits = len(personal_terms)
    divergence = personal_hits / max(1, personal_hits + canonical_hits)

    # Report (always — pytest -s shows it)
    print("\n" + "=" * 60)
    print(f"CASE: {case['name']}")
    print(f"  image:           «{case['image']}»")
    print(f"  personal hits:   {personal_hits}  ({sorted(personal_terms)})")
    print(f"  canonical hits:  {canonical_hits} (from anti={sorted(anti)})")
    print(f"  divergence:      {divergence:.2f}")
    print(f"  response (head): {result['text'][:300]}...")
    print("=" * 60)

    # Asserts
    assert personal_hits >= case["min_personal_highlights"], (
        f"only {personal_hits} personal concept(s) highlighted, "
        f"need >= {case['min_personal_highlights']}"
    )
    assert divergence >= 0.6, (
        f"divergence={divergence:.2f} < 0.6 — model leaned canonical "
        f"(canonical_hits={canonical_hits}, anti={sorted(anti)})"
    )
