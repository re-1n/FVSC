"""On-demand, context-bound owner clarification outside canonical evidence.

This journal records explicit choices; it does not parse free-form answers or
convert endorsement into authorship. SQLite transactions preserve amendment history.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Literal

from ..ingest.judgment_events import SourceSpan
from ..ingest.source_provenance import SourceAttribution
from ..ingest.vault_ingest import SourceDocument


ClarificationAction = Literal["my_position", "agree", "saved_only", "unsure", "freeform", "skip"]
ACTIONS = frozenset({"my_position", "agree", "saved_only", "unsure", "freeform", "skip"})
MAX_FRAGMENT_CHARS = 8192


@dataclass(frozen=True)
class ClarificationTarget:
    source_id: str
    source_revision: str
    start: int
    end: int
    text_sha256: str
    question: str

    @classmethod
    def create(cls, document: SourceDocument, *, start: int, end: int, question: str):
        context = question.strip()
        if not context or len(context) > 8192:
            raise ValueError("question must contain 1 to 8192 characters")
        if end - start > MAX_FRAGMENT_CHARS:
            raise ValueError("select a fragment of at most 8192 characters")
        span = SourceSpan.from_document(document, start=start, end=end)
        return cls(document.source_id, document.source_revision, span.start, span.end,
                   span.text_sha256, context)

    @property
    def target_id(self) -> str:
        payload = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify(self, document: SourceDocument) -> None:
        if (document.source_id, document.source_revision) != (self.source_id, self.source_revision):
            raise ValueError("source changed; select its current fragment again")
        SourceSpan(self.start, self.end, self.text_sha256).verify(document)


class ClarificationStore:
    """Single-process local journal, shared by service routes; no source bodies stored."""

    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            path = Path(path)
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ValueError("clarification journal must be a regular file")
            path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("PRAGMA foreign_keys=ON")
        with self._db:
            self._db.execute("CREATE TABLE IF NOT EXISTS targets (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            self._db.execute("""CREATE TABLE IF NOT EXISTS answers (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id TEXT NOT NULL REFERENCES targets(id),
                action TEXT NOT NULL, note TEXT NOT NULL, recorded_at REAL NOT NULL
            )""")

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def target(self, target_id: str) -> ClarificationTarget:
        with self._lock:
            row = self._db.execute("SELECT payload FROM targets WHERE id=?", (target_id,)).fetchone()
            if row is None:
                raise KeyError("unknown clarification")
            target = ClarificationTarget(**json.loads(row[0]))
            if target.target_id != target_id:
                raise ValueError("clarification target digest mismatch")
            return target

    def history(self, target_id: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT sequence, action, note, recorded_at FROM answers WHERE target_id=? ORDER BY sequence",
                (target_id,),
            ).fetchall()
            return [dict(zip(("sequence", "action", "note", "recorded_at"), row)) for row in rows]

    def prepare(self, target: ClarificationTarget, document: SourceDocument) -> dict:
        target.verify(document)
        with self._lock, self._db:
            self._db.execute("INSERT OR IGNORE INTO targets(id,payload) VALUES (?,?)",
                             (target.target_id, json.dumps(asdict(target), ensure_ascii=False)))
            return self._view(target, document)

    def answer(self, target_id: str, document: SourceDocument, *, action: ClarificationAction,
               note: str = "", expected_sequence: int = 0) -> dict:
        if action not in ACTIONS:
            raise ValueError("unknown clarification action")
        note = note.strip()
        if len(note) > 8192 or (action == "freeform" and not note):
            raise ValueError("a free-form answer requires 1 to 8192 characters")
        if action != "freeform" and note:
            raise ValueError("use freeform for an answer in your own words")
        with self._lock, self._db:
            target = self.target(target_id)
            target.verify(document)
            history = self.history(target_id)
            latest = history[-1] if history else None
            # Retry of the identical submission is idempotent. A different stale
            # answer cannot overwrite a choice made in another card/tab.
            if latest and latest["action"] == action and latest["note"] == note:
                return self._view(target, document)
            if expected_sequence != (latest["sequence"] if latest else 0):
                raise ValueError("clarification changed; reopen it before editing")
            self._db.execute("INSERT INTO answers(target_id,action,note,recorded_at) VALUES (?,?,?,?)",
                             (target_id, action, note, time.time()))
            return self._view(target, document)

    def _view(self, target: ClarificationTarget, document: SourceDocument) -> dict:
        history = self.history(target.target_id)
        answer = history[-1] if history else None
        status = "pending"
        basis = "unresolved"
        if answer:
            status = {"my_position": "ready", "agree": "ready", "saved_only": "excluded",
                      "unsure": "unresolved", "freeform": "unresolved", "skip": "deferred"}[answer["action"]]
            basis = answer["action"]
        else:
            attribution = SourceAttribution.from_metadata(document.metadata)
            attribution.verify(document.text)
            # Literal authorship/adoption alone says nothing about agreement.
            for span in attribution.expression_spans:
                if span.start <= target.start and target.end <= span.end:
                    if span.owner_endorsement in {"endorsed", "rejected"}:
                        status = "ready" if span.owner_endorsement == "endorsed" else "excluded"
                        basis = "explicit_endorsement_annotation"
        return {
            "clarification_id": target.target_id, **asdict(target),
            "fragment": document.text[target.start:target.end],
            "status": status, "basis": basis, "answer": answer,
            "usable_as_owner_position": status == "ready",
            "prompt": "Как этот фрагмент относится к твоей позиции в этом вопросе?",
        }
