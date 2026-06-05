"""
viz_session.py — Streaming LLM session with on-the-fly [[marker]] parsing.

Yields a sequence of events (token / highlight / done) suitable for SSE.

Marker syntax (parsed):
    [[concept:term]]
    [[edge:a->b]]  (also accepts → or =>)
    [[note:path/to/file.md]]
    [[judgment:term#N]]
    [[word:literal]]

The parser is incremental: tokens stream through, markers are emitted as soon
as the closing `]]` is seen, no need to buffer the whole response.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Iterator, Optional

from core.llm import OllamaClient, ChatMessage
from core.llm.map_context import SYSTEM_PROMPT, build_full_prompt_context


VIZ_SYSTEM_ADDENDUM = """
Когда упоминаешь конкретный элемент карты — оборачивай его в маркер. Маркеры подсвечиваются в визуализации синхронно с твоим ответом. Используй ТОЛЬКО эти типы:

  [[concept:точное_имя_концепта]]   — узел
  [[edge:A->B]]                      — связь (стрелка обязательна)
  [[note:путь/имя.md]]               — заметка vault'а (только если знаешь имя)
  [[judgment:концепт#N]]             — N-е суждение концепта (1-based)
  [[word:слово]]                     — литеральное слово

Правила:
- Концепт должен ТОЧНО совпадать со списком в контексте карты. Не выдумывай.
- Маркер можно использовать прямо в прозе, как обычное упоминание.
- 2-6 маркеров на ответ — не больше. Подсвечивай только опорные узлы своего рассуждения.
"""


# ───── marker parser ─────

_MARKER_PATTERNS = {
    "concept": re.compile(r"^([^\]]+)$"),
    "edge":    re.compile(r"^(.+?)\s*(?:->|→|=>)\s*(.+)$"),
    "note":    re.compile(r"^(.+)$"),
    "judgment": re.compile(r"^(.+?)#(\d+)$"),
    "word":    re.compile(r"^(.+)$"),
}


def _parse_marker(body: str) -> Optional[dict]:
    """body is the text between [[ and ]]. Returns highlight dict or None."""
    if ":" not in body:
        return None
    kind, rest = body.split(":", 1)
    kind = kind.strip().lower()
    rest = rest.strip()
    if kind not in _MARKER_PATTERNS:
        return None
    m = _MARKER_PATTERNS[kind].match(rest)
    if not m:
        return None
    if kind == "concept":
        return {"kind": "concept", "term": m.group(1).strip()}
    if kind == "edge":
        return {"kind": "edge", "a": m.group(1).strip(), "b": m.group(2).strip()}
    if kind == "note":
        return {"kind": "note", "path": m.group(1).strip()}
    if kind == "judgment":
        return {"kind": "judgment", "term": m.group(1).strip(), "n": int(m.group(2))}
    if kind == "word":
        return {"kind": "word", "text": m.group(1).strip()}
    return None


class MarkerStream:
    """Incremental [[...]] extractor. feed(chunk) -> list of (text_to_emit, marker_or_None)."""

    def __init__(self):
        self._buf = ""

    def feed(self, chunk: str) -> list[tuple[str, Optional[dict]]]:
        """Append chunk, return list of (visible_text, highlight_dict_or_None).

        Visible text includes the [[marker]] literally (so user sees what was
        highlighted). Highlight dicts are emitted as separate events.
        Trailing partial `[` or `[[...` is retained in the buffer.
        """
        self._buf += chunk
        out: list[tuple[str, Optional[dict]]] = []
        i = 0

        while i < len(self._buf):
            open_pos = self._buf.find("[[", i)
            if open_pos == -1:
                # No marker start in the tail. The tail is safe to emit EXCEPT
                # we must retain a trailing single `[` (could become `[[`).
                tail = self._buf[i:]
                if tail.endswith("[") and not tail.endswith("[["):
                    safe = tail[:-1]
                    if safe:
                        out.append((safe, None))
                    self._buf = "["
                else:
                    if tail:
                        out.append((tail, None))
                    self._buf = ""
                return out

            # Emit prefix text before `[[`
            if open_pos > i:
                out.append((self._buf[i:open_pos], None))

            close_pos = self._buf.find("]]", open_pos + 2)
            if close_pos == -1:
                # Marker incomplete — keep from `[[` onward in buffer
                self._buf = self._buf[open_pos:]
                return out

            body = self._buf[open_pos + 2 : close_pos]
            marker_text = self._buf[open_pos : close_pos + 2]
            highlight = _parse_marker(body)
            out.append((marker_text, highlight))
            i = close_pos + 2

        self._buf = ""
        return out

    def flush(self) -> str:
        """Return whatever residual buffer is left (e.g. unclosed marker)."""
        residual = self._buf
        self._buf = ""
        return residual


# ───── SSE event helpers ─────

def sse(event_type: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


# ───── session orchestrator ─────

@dataclass
class VizConfig:
    model: str = "qwen2.5:14b-instruct-q4_K_M"
    host: str = "http://localhost:11434"
    temperature: float = 0.4
    num_ctx: int = 8192
    top_concepts_in_context: int = 50


def build_messages(
    space,
    si,
    history: list[dict],
    top_n: int,
) -> list[ChatMessage]:
    """history is a list of {role, content}; we inject system + map context."""
    context = build_full_prompt_context(space, si, top_n=top_n)
    msgs = [
        ChatMessage("system", SYSTEM_PROMPT + "\n\n" + VIZ_SYSTEM_ADDENDUM),
        ChatMessage("system", f"Контекст карты:\n\n{context}"),
    ]
    for m in history:
        msgs.append(ChatMessage(m["role"], m["content"]))
    return msgs


def stream_response(
    llm: OllamaClient,
    space,
    si,
    history: list[dict],
    config: VizConfig,
    known_terms: Optional[set[str]] = None,
) -> Iterator[str]:
    """Generator yielding SSE-formatted lines.

    If known_terms is provided, highlight markers referencing unknown concepts
    are filtered out (kept in visible text, dropped from highlight stream).
    """
    msgs = build_messages(space, si, history, config.top_concepts_in_context)
    parser = MarkerStream()

    try:
        for chunk in llm.chat_stream(msgs):
            for visible, marker in parser.feed(chunk):
                if visible:
                    yield sse("token", {"text": visible})
                if marker is not None:
                    if known_terms is not None and marker["kind"] == "concept":
                        if marker["term"] not in known_terms:
                            continue
                    if known_terms is not None and marker["kind"] == "edge":
                        if marker["a"] not in known_terms or marker["b"] not in known_terms:
                            continue
                    yield sse("highlight", marker)
        residual = parser.flush()
        if residual:
            yield sse("token", {"text": residual})
        yield sse("done", {})
    except RuntimeError as e:
        yield sse("error", {"message": str(e)})


# ───── stub mode (test pipeline without model) ─────

STUB_ANSWERS = [
    (
        "Я вижу в твоей карте три заметных опоры: [[concept:важно]] — это "
        "узел с высокой полисемией, через который проходят разные линии "
        "рассуждения. Он связан с [[concept:ограничения]] через "
        "[[edge:важно->ограничения]] — это похоже на твою привычку формулировать "
        "ценности через границы. Слово [[word:тяжело]] часто появляется рядом, "
        "что задаёт эмоциональный фон."
    ),
]


def stream_stub(history: list[dict]) -> Iterator[str]:
    """Generate fake response with markers — for testing the pipeline before model is ready."""
    import time
    answer = STUB_ANSWERS[len(history) % len(STUB_ANSWERS)]
    parser = MarkerStream()
    # Pretend to stream char-by-char
    for ch in answer:
        for visible, marker in parser.feed(ch):
            if visible:
                yield sse("token", {"text": visible})
            if marker is not None:
                yield sse("highlight", marker)
        time.sleep(0.005)
    residual = parser.flush()
    if residual:
        yield sse("token", {"text": residual})
    yield sse("done", {})
