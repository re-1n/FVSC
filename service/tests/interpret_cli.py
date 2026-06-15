"""interpret_cli — quick interactive harness for the interpretation lens.

Usage:
    1) Backend на 127.0.0.1:8765 уже запущен
    2) Карта построена, Ollama up
    3) python -m service.tests.interpret_cli

Что делает:
    Спрашивает несколько строк опыта (Ctrl-D / пустая строка → конец блока),
    потом образ. Шлёт в /viz/ask, печатает ответ потоком и отчёт:
      [PERSONAL] подсвеченные концепты твоей карты
      [INLINE]   маркеры, упомянутые в тексте, но не пропущенные фильтром
                 (LLM что-то выдумал — повод заглянуть в карту)

Покидать: Ctrl-C или пустой образ.
"""
from __future__ import annotations

import json
import re
import sys

import httpx


BASE = "http://127.0.0.1:8765"
_MARKER_RE = re.compile(r"\[\[(concept|edge|note|judgment|word):([^\]]+)\]\]")


def _check_backend() -> dict:
    try:
        r = httpx.get(f"{BASE}/viz/status", timeout=5.0)
    except httpx.ConnectError:
        print(f"❌ Backend на {BASE} не отвечает. Запусти uvicorn.")
        sys.exit(1)
    if r.status_code != 200:
        print(f"❌ /viz/status вернул {r.status_code}")
        sys.exit(1)
    st = r.json()
    if not st.get("space_loaded"):
        print("❌ Карта не построена. Открой Obsidian → плагин Антураж → «Построить карту».")
        sys.exit(1)
    if not st.get("ollama_up"):
        print(f"❌ Ollama не отвечает ({st.get('model')}). Запусти `ollama serve`.")
        sys.exit(1)
    return st


def _read_block(prompt: str) -> list[str]:
    print(prompt)
    lines: list[str] = []
    while True:
        try:
            line = input("  ").strip()
        except EOFError:
            break
        if not line:
            break
        lines.append(line)
    return lines


def _build_user_message(experience: list[str], image: str) -> str:
    bullets = "\n".join(f"- {x}" for x in experience)
    return (
        f"Мой опыт:\n{bullets}\n\n"
        f"Образ: «{image}»\n\n"
        "Разверни образ через мой опыт — не через общий словарь. "
        "Какие концепты из моей карты он активирует, и почему это значение "
        "отличается от того, что лежит в обычном словаре."
    )


def _stream(messages: list[dict]) -> dict:
    text_parts: list[str] = []
    highlights: list[dict] = []
    error: str | None = None
    print("\n— ответ —")
    with httpx.Client(timeout=180.0) as client:
        with client.stream("POST", f"{BASE}/viz/ask",
                           json={"messages": messages, "stub": False}) as r:
            if r.status_code != 200:
                print(f"\n❌ /viz/ask: {r.status_code}")
                return {"text": "", "highlights": [], "error": "http", "done": False}
            event_type = None
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
                        chunk = payload.get("text", "")
                        text_parts.append(chunk)
                        # live stream to stdout (no extra newlines)
                        print(chunk, end="", flush=True)
                    elif event_type == "highlight":
                        highlights.append(payload)
                    elif event_type == "error":
                        error = payload.get("message", "<no message>")
                    elif event_type == "done":
                        pass
    print()  # final newline
    return {
        "text": "".join(text_parts),
        "highlights": highlights,
        "error": error,
    }


def _report(result: dict) -> None:
    if result["error"]:
        print(f"\n⚠ Ошибка SSE: {result['error']}")
        return
    personal_concepts = [h for h in result["highlights"] if h.get("kind") == "concept"]
    personal_edges = [h for h in result["highlights"] if h.get("kind") == "edge"]
    inline = _MARKER_RE.findall(result["text"])
    filtered_terms = {h["term"] for h in personal_concepts}
    inline_only = [
        (k, b.strip()) for (k, b) in inline
        if k == "concept" and b.strip() not in filtered_terms
    ]

    print("\n— отчёт —")
    if personal_concepts:
        print("  [PERSONAL concepts]")
        for h in personal_concepts:
            print(f"    • {h['term']}")
    if personal_edges:
        print("  [PERSONAL edges]")
        for h in personal_edges:
            print(f"    • {h['a']} → {h['b']}")
    if inline_only:
        print("  [INLINE / unknown — фильтр не пропустил]")
        for kind, body in inline_only:
            print(f"    • {body}  (фильтр сказал: не в карте)")
    if not (personal_concepts or personal_edges or inline_only):
        print("  (никаких маркеров — LLM не подсветил карту)")


def main() -> None:
    st = _check_backend()
    print(f"✔ Карта: {st.get('concept_count')} концептов, model={st.get('model')}\n")

    while True:
        print("=" * 60)
        experience = _read_block("Опыт (по одной строке, пустая строка = конец):")
        if not experience:
            print("Пустой опыт — выход.")
            break
        image = input("Образ: ").strip()
        if not image:
            print("Пустой образ — выход.")
            break
        messages = [{"role": "user", "content": _build_user_message(experience, image)}]
        result = _stream(messages)
        _report(result)
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n— прерван —")
