"""
exocortex_ingest.py — Ingest Telegram JSON exports into Obsidian MD + FVSC SemanticSpace.

Pipeline:
    TG JSON exports (result.json per channel)
      → extract text messages
      → write organized Obsidian MD files (vault/тг-каналы/<channel>/<YYYY-MM>.md)
      → aggregate per-channel corpus
      → text_to_semantic_input → SemanticSpace
      → save per-channel report + combined space

Usage:
    python3 -X utf8 -m core.exocortex_ingest
    python3 -X utf8 -m core.exocortex_ingest --tg-dir PATH --vault-dir PATH [--fvsc] [--quiet]

Channel L5 context_metadata is inferred from folder names — feeds directly into
RichJudgment.context_metadata when that pipeline is extended.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ─────────────────────────── TG preprocessing ────────────────────────────────

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"@\w+")
_TG_HASH_RE = re.compile(r"\b[A-Za-z0-9]{16,}\b")  # long alphanumeric tokens (bot IDs, hashes)
_DIGITS_ONLY_RE = re.compile(r"^\d+$")

# Russian + common function words to exclude from FVSC analysis
_RU_STOPWORDS = frozenset("""
    и в на не с по из что как за это так при это а но же то всё
    все уже уж был была были быть есть он она они оно его её их ему ей им
    для из за под над без от до про к со мне меня тебе тебя себе себя
    или ни да нет только вот тут там где когда если хотя чтобы
    потому поэтому который которые которых каждый каждая всегда никогда
    очень много мало такой такая такие один одна одно два три
    этот эта эти этого этой этих который которая которое
    какой какая какие чем чего кого кому ком
    будет будут буду будем сейчас потом раньше теперь
    мы вы ты нас вас ним ней ними нём
    бы ли ведь даже вдруг ещё еще
    можно нельзя нужно надо хочу хочет хотел хотела хотели
    просто совсем именно то есть
    было будто может кажется кто
    того тебя через других
    пока ещё еще
""".split())


def _clean_for_fvsc(text: str) -> str:
    """Strip URLs, mentions, hash-like tokens from TG text before FVSC parsing."""
    text = _URL_RE.sub(" ", text)
    text = _MENTION_RE.sub(" ", text)
    text = _TG_HASH_RE.sub(" ", text)
    return text.strip()


def _is_url_only(text: str) -> bool:
    """True if message is just a URL with no meaningful text."""
    stripped = _URL_RE.sub("", text).strip()
    return len(stripped) < 5

# ─────────────────────────── Channel → L5 metadata ───────────────────────────

CHANNEL_META: Dict[str, Dict] = {
    "личный дневник тг":                      {"register": "diary",        "source": "self", "social_group": "личное"},
    "сны тг":                                 {"register": "dream",        "source": "self", "medium": "thought"},
    "идеи тг":                                {"register": "ideas",        "source": "self", "medium": "thought"},
    "платформа тг":                           {"register": "project",      "source": "self", "social_group": "работа"},
    "llmнум тг":                              {"register": "dialogue",     "source": "self", "social_group": "AI"},
    "попытка самодиагностики тг":             {"register": "introspection","source": "self", "social_group": "психология"},
    "устал быть человеком тг":               {"register": "diary",        "source": "self", "social_group": "эмоции"},
    "когда я хотел умереть тг":              {"register": "crisis",       "source": "self"},
    "лечусь тг":                              {"register": "health",       "source": "self"},
    "словарик тг":                            {"register": "reference",    "source": "self"},
    "черновики стихов и тд тг":              {"register": "creative",     "source": "self"},
    "к L тг":                                 {"register": "letter",       "source": "self"},
    "Rein тг":                                {"register": "diary",        "source": "self"},
    "канал rags попытки заработать на крипте":{"register": "project",      "source": "self", "social_group": "крипта"},
}

# MD frontmatter labels for each register
REGISTER_LABEL = {
    "diary":        "Личный дневник",
    "dream":        "Сны",
    "ideas":        "Идеи",
    "project":      "Проект",
    "dialogue":     "Диалог с AI",
    "introspection":"Самодиагностика",
    "crisis":       "Кризис",
    "health":       "Лечение",
    "reference":    "Словарик",
    "creative":     "Творчество",
    "letter":       "Письмо",
}

# ─────────────────────────── TG JSON parsing ─────────────────────────────────

def _flatten_text(raw) -> str:
    """Handle TG text that is either str or list of str/entity dicts."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", ""))
        return "".join(parts)
    return ""


def load_channel(json_path: Path) -> Tuple[str, List[Dict]]:
    """Load a TG result.json. Returns (channel_name, messages)."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    name = data.get("name", json_path.parent.name)
    messages = []
    for m in data.get("messages", []):
        if m.get("type") != "message":
            continue
        text = _flatten_text(m.get("text", "")).strip()
        if not text or len(text) < 5:
            continue
        if _is_url_only(text):
            continue
        date_str = m.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            dt = None
        messages.append({"text": text, "date": dt, "id": m.get("id")})
    return name, messages


def find_channels(tg_dir: Path) -> List[Tuple[str, Path]]:
    """Find all result.json files in subdirectories."""
    results = []
    for child in sorted(tg_dir.iterdir()):
        rj = child / "result.json"
        if child.is_dir() and rj.exists():
            results.append((child.name, rj))
    return results

# ─────────────────────────── Obsidian MD writer ──────────────────────────────

RU_MONTHS = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


def write_obsidian_vault(
    channel_dir_name: str,
    channel_name: str,
    messages: List[Dict],
    vault_dir: Path,
) -> int:
    """Write monthly MD files for one channel. Returns number of files written."""
    meta = CHANNEL_META.get(channel_dir_name, CHANNEL_META.get(channel_name, {}))
    register = meta.get("register", "diary")
    label = REGISTER_LABEL.get(register, channel_name)

    out_dir = vault_dir / "тг-каналы" / channel_dir_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Group by YYYY-MM
    by_month: Dict[str, List[Dict]] = defaultdict(list)
    undated: List[Dict] = []
    for m in messages:
        if m["date"]:
            key = m["date"].strftime("%Y-%m")
            by_month[key].append(m)
        else:
            undated.append(m)

    files_written = 0
    for ym in sorted(by_month):
        year, month = ym.split("-")
        month_label = RU_MONTHS[int(month)]
        fname = out_dir / f"{ym}.md"

        lines = [
            "---",
            f"channel: {channel_name}",
            f"register: {register}",
            f"period: {ym}",
        ]
        for k, v in meta.items():
            if k != "register":
                lines.append(f"{k}: {v}")
        lines += ["---", "", f"# {month_label} {year}", ""]

        for msg in by_month[ym]:
            dt_str = msg["date"].strftime("%Y-%m-%d %H:%M") if msg["date"] else "?"
            lines.append(f"## {dt_str}")
            lines.append("")
            lines.append(msg["text"])
            lines.append("")
            lines.append("---")
            lines.append("")

        fname.write_text("\n".join(lines), encoding="utf-8")
        files_written += 1

    if undated:
        fname = out_dir / "_без_даты.md"
        lines = ["---", f"channel: {channel_name}", "register: unknown", "---", ""]
        for msg in undated:
            lines.append(msg["text"])
            lines.append("")
            lines.append("---")
            lines.append("")
        fname.write_text("\n".join(lines), encoding="utf-8")
        files_written += 1

    return files_written


def write_channel_index(vault_dir: Path, summary: List[Dict]):
    """Write тг-каналы/_index.md with channel overview."""
    out = vault_dir / "тг-каналы" / "_index.md"
    lines = [
        "---",
        "type: index",
        "---",
        "",
        "# Телеграм-каналы",
        "",
        "| Канал | Сообщений | Регистр | Период |",
        "|-------|-----------|---------|--------|",
    ]
    for s in sorted(summary, key=lambda x: -x["count"]):
        lines.append(
            f"| [[{s['dir_name']}/_index|{s['dir_name']}]] "
            f"| {s['count']} "
            f"| {s['register']} "
            f"| {s['period']} |"
        )
    lines += ["", ""]
    out.write_text("\n".join(lines), encoding="utf-8")

# ─────────────────────────── FVSC ingestion ──────────────────────────────────

def ingest_channel_fvsc(
    channel_dir_name: str,
    messages: List[Dict],
    dim: int = 64,
    quiet: bool = False,
) -> Optional[object]:
    """Run FVSC pipeline on aggregated channel text. Returns SemanticSpace or None."""
    try:
        from .text_parser_agnostic import text_to_semantic_input, ParseConfig
        from .density_core import SemanticSpace
    except ImportError:
        from text_parser_agnostic import text_to_semantic_input, ParseConfig
        from density_core import SemanticSpace

    # Aggregate all messages into one corpus text (clean for FVSC — strip URLs/mentions/hashes)
    cleaned_texts = [_clean_for_fvsc(m["text"]) for m in messages]
    corpus = "\n\n".join(t for t in cleaned_texts if len(t) >= 5)
    if not corpus.strip():
        return None

    meta = CHANNEL_META.get(channel_dir_name, {})

    # Tune ParseConfig for personal short-message corpus:
    # - min_freq=2: fine for large channels, keeps signal
    # - window=4: short sentences in TG messages
    # - max_concepts=500: personal vocabulary can be large
    # - stopwords: Russian function words + synthetic FVSC verbs
    _synthetic = {"является", "содержит"}
    cfg = ParseConfig(
        window=4,
        min_freq=2,
        max_concepts=500,
        min_token_len=3,
        stopwords=_RU_STOPWORDS | _synthetic,
    )

    si = text_to_semantic_input(corpus, config=cfg)
    if not si:
        if not quiet:
            print(f"  [skip] {channel_dir_name}: no semantic_input extracted")
        return None

    space = SemanticSpace(dim=dim)
    space.load_from_semantic_input(si, source_text=f"[tg:{channel_dir_name}]")

    if not quiet:
        # Rank by weight in si dict (original frequency signal), skip synthetic verbs
        _skip = {"является", "содержит", "[self]"}
        top = sorted(
            [(c, v["weight"]) for c, v in si.items() if c not in _skip],
            key=lambda x: -x[1],
        )[:5]
        top_names = [t[0] for t in top]
        print(f"  concepts={len(space.concepts)}  top5={top_names}")

    return space

# ─────────────────────────── Main ────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(description="Ingest TG exports → Obsidian MD + FVSC")
    parser.add_argument(
        "--tg-dir",
        default=r"/mnt/c/Users/daur1/Desktop/экзокортекс для fvsc map",
        help="Folder containing TG channel subdirs with result.json",
    )
    parser.add_argument(
        "--vault-dir",
        default=r"/mnt/c/Users/daur1/Desktop/экзокортекс для fvsc map/Rein",
        help="Target Obsidian vault directory",
    )
    parser.add_argument("--fvsc", action="store_true", help="Also run FVSC ingestion")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    tg_dir = Path(args.tg_dir)
    vault_dir = Path(args.vault_dir)

    channels = find_channels(tg_dir)
    if not channels:
        print(f"No result.json files found in {tg_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(channels)} channels in {tg_dir}")
    print(f"Vault output → {vault_dir}")
    print()

    summary = []
    fvsc_spaces = {}

    for dir_name, json_path in channels:
        channel_name, messages = load_channel(json_path)
        if not messages:
            continue

        dates = [m["date"] for m in messages if m["date"]]
        period = ""
        if dates:
            period = f"{min(dates).strftime('%Y-%m')} → {max(dates).strftime('%Y-%m')}"

        meta = CHANNEL_META.get(dir_name, CHANNEL_META.get(channel_name, {}))
        register = meta.get("register", "?")

        print(f"[{dir_name}]  {len(messages)} msgs  {period}")

        # 1. Obsidian MD
        n_files = write_obsidian_vault(dir_name, channel_name, messages, vault_dir)
        if not args.quiet:
            print(f"  → {n_files} MD files written")

        # 2. FVSC (optional)
        if args.fvsc:
            space = ingest_channel_fvsc(dir_name, messages, quiet=args.quiet)
            if space:
                fvsc_spaces[dir_name] = space

        summary.append({
            "dir_name": dir_name,
            "channel_name": channel_name,
            "count": len(messages),
            "period": period,
            "register": register,
        })
        print()

    write_channel_index(vault_dir, summary)
    print(f"Index written → {vault_dir}/тг-каналы/_index.md")

    total_msgs = sum(s["count"] for s in summary)
    total_channels = len(summary)
    print(f"\nDone: {total_channels} channels, {total_msgs} messages")

    if args.fvsc and fvsc_spaces:
        print(f"FVSC spaces built: {list(fvsc_spaces.keys())}")

    return fvsc_spaces  # useful when imported


if __name__ == "__main__":
    main()
