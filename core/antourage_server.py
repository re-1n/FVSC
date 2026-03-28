# -*- coding: utf-8 -*-
"""
FVSC Antourage Server — local HTTP server that bridges the interactive map
with the Ollama LLM and FeedbackEngine.

Serves the HTML map + provides API for Antourage dialogue.
Runs on localhost:8731.

Usage: python -X utf8 antourage_server.py [path_to_result.json]
       Without arguments: uses demo data.
"""

import os
import sys
import json
import time
import http.server
import urllib.request
import urllib.parse
import threading
import webbrowser
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from density_core import Judgment, SemanticSpace
from feedback import FeedbackEngine, FeedbackQuestion

# ---------------------------------------------------------------------------
# Session persistence
# ---------------------------------------------------------------------------

SESSION_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)
session_path: str = ""  # set in init_state()


def save_message(role: str, content: str, focused: str = None):
    """Append one message to the session JSONL file."""
    record = {"ts": time.time(), "role": role, "content": content}
    if focused:
        record["focused_concept"] = focused
    with open(session_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------------------
# Ollama client
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:7b"

EXTRACTION_PROMPT = """Из текста пользователя извлеки суждения — утверждения о связи между понятиями.
Формат: JSON-массив объектов. Каждый объект:
{"subject": "лемма", "verb": "лемма глагола", "object": "лемма", "quality": "AFFIRMATIVE или NEGATIVE"}

Правила:
- Только явные утверждения, не домыслы
- Леммы в начальной форме (именительный падеж, инфинитив)
- Если суждений нет — верни []
- Не более 3 суждений за раз
- quality: NEGATIVE только при явном отрицании ("не", "без")

Примеры:
"для меня свобода это возможность выбирать" → [{"subject":"свобода","verb":"быть","object":"возможность","quality":"AFFIRMATIVE"}]
"любовь не терпит лжи" → [{"subject":"любовь","verb":"терпеть","object":"ложь","quality":"NEGATIVE"}]
"ну да, наверное" → []

Текст: """

SYSTEM_PROMPT = """Ты — Антураж, мягкий и вдумчивый помощник в исследовании персональных смыслов.
Ты помогаешь человеку разобраться в своей семантической карте — карте того, что слова значат лично для него.

Правила:
- Говори кратко (2-4 предложения), тепло, без формальностей
- Никогда не обвиняй и не указывай на противоречия прямо — говори "интересный нюанс", "любопытно"
- Задавай открытые вопросы, которые помогают думать
- Если человек подтвердил — поддержи коротко ("записал", "понял")
- Если отклонил — прими спокойно ("хорошо, убрал")
- Используй данные карты для контекста, но не перегружай деталями
- Ты не психолог и не учитель — ты внимательный собеседник"""


def ollama_chat(messages: list[dict]) -> str:
    """Call Ollama chat API. Returns assistant response text."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 200},
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"(Ollama недоступна: {e})"


def extract_judgments_from_text(user_text: str) -> list[dict]:
    """Ask Ollama to extract S→V→O judgments from user's reply.
    Returns list of dicts with subject/verb/object/quality, or empty list.
    """
    if len(user_text.strip()) < 20:
        return []

    messages = [
        {"role": "system", "content": "Ты извлекаешь суждения из текста. Отвечай ТОЛЬКО валидным JSON-массивом."},
        {"role": "user", "content": EXTRACTION_PROMPT + f'"{user_text}"'},
    ]

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 300},
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
            content = raw.get("message", {}).get("content", "").strip()
            # Parse JSON from response (may have markdown fences)
            content = content.replace("```json", "").replace("```", "").strip()
            extracted = json.loads(content)
            if isinstance(extracted, list):
                return [e for e in extracted if "subject" in e and "verb" in e and "object" in e]
    except Exception as e:
        print(f"  [antourage] extraction error: {e}")
    return []


def materialize_extracted(extracted: list[dict], user_text: str) -> list[str]:
    """Add extracted judgments to the semantic space. Returns list of descriptions."""
    added = []
    now = time.time()
    for e in extracted:
        j = Judgment(
            subject=e["subject"],
            verb=e["verb"],
            object=e["object"],
            quality=e.get("quality", "AFFIRMATIVE"),
            modality=1.0,
            intensity=0.8,
            timestamp=now,
            source_text=f"[antourage_dialog] {user_text[:150]}",
            interpretation_layer=0,
            defeasible=False,
            confirmation_status="confirmed",
        )
        space.materialize_judgment(j)
        q = " [НЕТ]" if j.quality == "NEGATIVE" else ""
        added.append(f"{j.subject} —[{j.verb}]→ {j.object}{q}")
    return added


# ---------------------------------------------------------------------------
# Build semantic space (demo or from file)
# ---------------------------------------------------------------------------

def build_demo_space() -> tuple[SemanticSpace, list[Judgment]]:
    """Quick demo space for testing without Telegram data."""
    now = time.time()
    space = SemanticSpace(dim=30, min_components_for_query=1)
    judgments = [
        Judgment("свобода", "требовать", "ответственность", modality=1.0, intensity=0.9,
                 timestamp=now-30*86400, source_text="Свобода требует ответственности"),
        Judgment("свобода", "требовать", "ответственность", modality=1.0, intensity=0.9,
                 timestamp=now-20*86400, source_text="Настоящая свобода требует ответственности"),
        Judgment("свобода", "включать", "выбор", modality=1.0, intensity=0.8,
                 timestamp=now-25*86400, source_text="Свобода включает в себя выбор"),
        Judgment("свобода", "включать", "выбор", modality=1.0, intensity=0.8,
                 timestamp=now-15*86400, source_text="Свобода — это прежде всего выбор"),
        Judgment("свобода", "быть", "независимость", modality=1.0, intensity=0.7,
                 timestamp=now-5*86400, source_text="Свобода — это независимость"),
        Judgment("свобода", "приводить", "одиночество", modality=1.0, intensity=0.7,
                 timestamp=now, source_text="Свобода приводит к одиночеству"),
        Judgment("любовь", "давать", "свободу", quality="AFFIRMATIVE", modality=1.0, intensity=0.8,
                 timestamp=now-20*86400, source_text="Любовь даёт свободу"),
        Judgment("любовь", "давать", "свободу", quality="NEGATIVE", modality=0.8, intensity=0.6,
                 timestamp=now-2*86400, source_text="Любовь не даёт свободу, а ограничивает"),
        Judgment("любовь", "требовать", "терпение", modality=1.0, intensity=0.7,
                 timestamp=now-15*86400, source_text="Любовь требует терпения"),
        Judgment("любовь", "включать", "доверие", modality=1.0, intensity=0.8,
                 timestamp=now-10*86400, source_text="Любовь включает доверие"),
        Judgment("любовь", "порождать", "уязвимость", modality=1.0, intensity=0.6,
                 timestamp=now-5*86400, source_text="Любовь порождает уязвимость"),
        Judgment("ответственность", "требовать", "мужество", modality=1.0, intensity=0.8,
                 timestamp=now-25*86400, source_text="Ответственность требует мужества"),
        Judgment("ответственность", "включать", "долг", modality=1.0, intensity=0.7,
                 timestamp=now-18*86400, source_text="Ответственность включает долг"),
        Judgment("ответственность", "давать", "свободу", modality=0.8, intensity=0.7,
                 timestamp=now-12*86400, source_text="Ответственность даёт свободу"),
        Judgment("дружба", "включать", "доверие", modality=0.5, intensity=0.6,
                 timestamp=now, source_text="[вывод] дружба включает доверие",
                 interpretation_layer=1, defeasible=True),
        Judgment("дружба", "требовать", "время", modality=0.5, intensity=0.5,
                 timestamp=now, source_text="[вывод] дружба требует времени",
                 interpretation_layer=1, defeasible=True),
        Judgment("выбор", "требовать", "ответственность", modality=1.0, intensity=0.8,
                 timestamp=now-8*86400, source_text="Выбор требует ответственности"),
        Judgment("выбор", "включать", "отказ", modality=1.0, intensity=0.6,
                 timestamp=now-6*86400, source_text="Выбор включает в себе отказ"),
        Judgment("мужество", "быть", "честность", modality=0.8, intensity=0.6,
                 timestamp=now-4*86400, source_text="Мужество — это честность перед собой"),
        Judgment("я", "стремиться", "свобода", modality=1.0, intensity=0.9,
                 timestamp=now-10*86400, source_text="Я стремлюсь к свободе"),
        Judgment("я", "ценить", "честность", modality=1.0, intensity=0.8,
                 timestamp=now-5*86400, source_text="Я ценю честность"),
    ]
    for j in judgments:
        space.materialize_judgment(j)
    space.recursive_deepen(iterations=3, alpha=0.7)
    return space, judgments


# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------

space: SemanticSpace = None
engine: FeedbackEngine = None
chat_history: list[dict] = []       # Ollama message history
html_content: str = ""              # Cached HTML


def init_state(use_demo: bool = True, json_path: str = None):
    """Initialize semantic space, feedback engine, and HTML."""
    global space, engine, html_content, chat_history, session_path

    # Create session file
    ts = time.strftime("%Y%m%d_%H%M%S")
    session_path = os.path.join(SESSION_DIR, f"session_{ts}.jsonl")

    if use_demo or json_path is None:
        space, judgments = build_demo_space()
        n_msgs = len(judgments)
    else:
        # Load from Telegram JSON (reuse interactive_map pipeline)
        import spacy
        from live_test import read_telegram_messages, build_seed_vectors
        from tree_extractor import extract_judgments_recursive
        print("Loading spaCy...")
        nlp = spacy.load("ru_core_news_md")
        texts = read_telegram_messages(json_path, max_msgs=500)
        judgments = extract_judgments_recursive(nlp, texts)
        terms = set()
        for j in judgments:
            terms.update([j.subject, j.verb, j.object])
        seeds = build_seed_vectors(nlp, terms, 100)
        space = SemanticSpace(dim=100, seed_vectors=seeds, min_components_for_query=2)
        for j in judgments:
            space.materialize_judgment(j)
        space.recursive_deepen(iterations=3, alpha=0.7)
        n_msgs = len(texts)

    engine = FeedbackEngine(space)
    chat_history = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Build HTML
    from interactive_map import build_map_data, generate_html
    min_comp = 1 if use_demo else 2
    map_data = build_map_data(space, min_components=min_comp, edge_threshold=0.2, top_n=50)

    # Inject Antourage chat mode into HTML (replace button-based with chat)
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "_fvsc_map.html")
    generate_html(map_data, n_msgs, len(judgments) if isinstance(judgments, list) else 0,
                  threshold=0.3, output_path=tmp, title_suffix="[Антураж] ")
    with open(tmp, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Patch HTML: replace Antourage button panel with chat interface
    html_content = patch_html_for_chat(html_content)


def patch_html_for_chat(html: str) -> str:
    """Replace the button-based Antourage panel with a chat interface."""

    # Replace the antourage div content
    old_toggle = '<button id="antourage-toggle" onclick="toggleAntourage()">Антураж <span class="badge" id="ant-badge">0</span></button>'
    new_toggle = '<button id="antourage-toggle" onclick="toggleAntourage()">Антураж</button>'
    html = html.replace(old_toggle, new_toggle)

    old_panel = '''<div id="antourage" class="hidden">
  <div id="ant-inner">
    <div id="ant-prompt">Загрузка...</div>
    <div id="ant-options"></div>
  </div>
  <div id="ant-milestone"></div>
  <div id="ant-progress">
    <div id="ant-progress-bar"><div id="ant-progress-fill" style="width:0%"></div></div>
    <div id="ant-progress-text">0% проверено</div>
  </div>
</div>'''

    new_panel = '''<div id="antourage" class="hidden">
  <div id="ant-chat" style="max-height:200px;overflow-y:auto;padding:12px 24px;"></div>
  <div style="display:flex;padding:8px 24px 12px;gap:8px;">
    <input id="ant-input" type="text" placeholder="Напиши что-нибудь..."
           style="flex:1;background:#1a1a22;border:1px solid #333;color:#ccc;padding:8px 14px;border-radius:16px;font-size:13px;outline:none;"
           onkeydown="if(event.key==='Enter')sendToAntourage()">
    <button onclick="sendToAntourage()"
            style="background:#2a2a3a;border:1px solid #444;color:#aaa;padding:8px 16px;border-radius:16px;cursor:pointer;font-size:12px;">Отправить</button>
  </div>
</div>'''
    html = html.replace(old_panel, new_panel)

    # Replace the JS Antourage section with chat-based version
    old_js_start = '// ============================================================\n// Antourage Feedback System'
    old_js_end = '''if (fbTotal === 0) {
    document.getElementById('antourage-toggle').style.display = 'none';
}'''

    chat_js = '''// ============================================================
// Antourage Chat System (backed by local Ollama LLM)
// ============================================================

let antourageOpen = false;

function toggleAntourage() {
    const el = document.getElementById('antourage');
    antourageOpen = !antourageOpen;
    el.classList.toggle('hidden');
    if (antourageOpen) {
        const chat = document.getElementById('ant-chat');
        if (chat.children.length === 0) {
            // First open: Antourage greets
            startAntourage();
        }
        document.getElementById('ant-input').focus();
    }
}

async function startAntourage() {
    addMsg('antourage', 'Привет! Я Антураж. Давай посмотрим на твою карту вместе. Что тебя интересует?');
    // Auto-generate first question from feedback engine context
    try {
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: '__init__'}),
        });
        const data = await resp.json();
        if (data.reply) addMsg('antourage', data.reply);
    } catch(e) { /* server not available, that's ok */ }
}

async function sendToAntourage() {
    const input = document.getElementById('ant-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    addMsg('user', text);

    // Get focused node context
    const ctx = focusedNode ? nodeMap[focusedNode] : null;
    const payload = {message: text};
    if (ctx) payload.focused_concept = focusedNode;

    try {
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        const data = await resp.json();
        if (data.reply) addMsg('antourage', data.reply);
    } catch(e) {
        addMsg('antourage', '(не удалось связаться с сервером)');
    }
}

function addMsg(role, text) {
    const chat = document.getElementById('ant-chat');
    const div = document.createElement('div');
    div.style.cssText = role === 'user'
        ? 'text-align:right;margin:6px 0;'
        : 'text-align:left;margin:6px 0;';
    const bubble = document.createElement('span');
    bubble.style.cssText = role === 'user'
        ? 'display:inline-block;background:#2a2a3a;color:#ccc;padding:6px 14px;border-radius:14px;font-size:13px;max-width:80%;text-align:left;'
        : 'display:inline-block;background:#1e1e28;color:#aab;padding:6px 14px;border-radius:14px;font-size:13px;max-width:80%;text-align:left;';
    // Support extraction notes: split on double newline, render note in smaller font
    const parts = text.split('\\n\\n');
    parts.forEach((part, i) => {
        if (i > 0) {
            const note = document.createElement('div');
            note.style.cssText = 'color:#6a6a5a;font-size:11px;margin-top:4px;font-style:italic;';
            note.textContent = part.replace(/^_\\(/, '').replace(/\\)_$/, '');
            bubble.appendChild(note);
        } else {
            bubble.textContent = part;
        }
    });
    div.appendChild(bubble);
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
}'''

    # Find and replace the JS block
    idx_start = html.find(old_js_start)
    idx_end = html.find(old_js_end)
    if idx_start >= 0 and idx_end >= 0:
        idx_end += len(old_js_end)
        html = html[:idx_start] + chat_js + html[idx_end:]

    return html


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class AntourageHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            reply = handle_chat(body)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"reply": reply}, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Quiet logging
        pass


def handle_chat(body: dict) -> str:
    """Handle a chat message from the UI."""
    global chat_history

    user_msg = body.get("message", "")
    focused = body.get("focused_concept", None)

    # First message: generate initial question from feedback engine
    if user_msg == "__init__":
        questions = engine.generate_questions(max_count=3)
        if questions:
            q = questions[0]
            context_msg = (
                f"Контекст карты: у пользователя есть вопрос типа '{q.question_type}'. "
                f"Понятия: {', '.join(q.related_concepts)}. "
                f"Задай мягкий вопрос на основе этого: {q.prompt_text}"
            )
            chat_history.append({"role": "user", "content": context_msg})
        else:
            chat_history.append({"role": "user", "content":
                "Карта пользователя построена. Спроси, что его интересует или предложи начать обзор ключевых понятий."})

        reply = ollama_chat(chat_history)
        chat_history.append({"role": "assistant", "content": reply})
        save_message("assistant", reply)
        return reply

    # Save user message to session
    save_message("user", user_msg, focused)

    # Regular message — add context
    context = ""
    if focused and focused in space.concepts:
        concept = space.concepts[focused]
        top_content = []
        for c in concept.components[:5]:
            j = c.judgment
            top_content.append(f"{j.subject}→{j.verb}→{j.object} ({j.source_text[:50]})")
        context = f"\n[Контекст: пользователь смотрит на понятие '{focused}'. Содержимое: {'; '.join(top_content)}]"

    chat_history.append({"role": "user", "content": user_msg + context})

    # Keep history manageable
    if len(chat_history) > 20:
        chat_history = [chat_history[0]] + chat_history[-16:]

    reply = ollama_chat(chat_history)
    chat_history.append({"role": "assistant", "content": reply})
    save_message("assistant", reply)

    # --- Extract judgments from user's reply (L0) ---
    extracted = extract_judgments_from_text(user_msg)
    if extracted:
        added = materialize_extracted(extracted, user_msg)
        if added:
            note = "📌 " + " | ".join(added)
            save_message("system", f"extracted: {json.dumps(extracted, ensure_ascii=False)}")
            reply += f"\n\n_({note})_"

    return reply


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    port = 8731

    use_demo = len(sys.argv) < 2
    json_path = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 60)
    print("FVSC Antourage Server")
    print("=" * 60)

    if use_demo:
        print("\nMode: demo (hand-crafted judgments)")
    else:
        print(f"\nMode: Telegram data from {json_path}")

    print("Initializing...")
    init_state(use_demo=use_demo, json_path=json_path)
    print(f"  Space: {len(space.concepts)} concepts")
    print(f"  Ollama model: {OLLAMA_MODEL}")

    print(f"\nStarting server on http://localhost:{port}")
    server = http.server.HTTPServer(("localhost", port), AntourageHandler)

    # Open browser
    url = f"http://localhost:{port}"
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    print(f"  Opening {url} in browser...")
    print(f"\n  Press Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
