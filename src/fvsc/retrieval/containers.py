"""Owner-authored concept composition, separate from extracted evidence.

Shared children and cycles are permitted: navigation paths, not a tree, define
the current location. Labels are vault-local identities in this first UI version.
"""
from contextlib import closing
from pathlib import Path
import sqlite3
import time
import unicodedata


def concept_name(value: str) -> str:
    value = unicodedata.normalize("NFC", value).strip()
    if not value or len(value) > 512 or any(ord(c) < 32 for c in value):
        raise ValueError("concept name must contain 1–512 printable characters")
    return value


class ContainerStore:
    def __init__(self, path: Path):
        self.path = path

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("CREATE TABLE IF NOT EXISTS components (parent TEXT, child TEXT, created REAL, PRIMARY KEY(parent, child))")
        db.execute("CREATE TABLE IF NOT EXISTS changes (parent TEXT, child TEXT, action TEXT, recorded REAL)")
        return db

    def children(self, parent: str) -> list[str]:
        parent = concept_name(parent)
        with closing(self.connect()) as db:
            return [row[0] for row in db.execute("SELECT child FROM components WHERE parent=? ORDER BY created, child", (parent,))]

    def terms(self) -> list[str]:
        with closing(self.connect()) as db:
            return [row[0] for row in db.execute("SELECT parent AS term FROM changes UNION SELECT child FROM changes ORDER BY term")]

    def set_component(self, parent: str, child: str, present: bool):
        parent, child = concept_name(parent), concept_name(child)
        if parent == child:
            raise ValueError("a concept cannot be its own immediate component")
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            exists = db.execute("SELECT 1 FROM components WHERE parent=? AND child=?", (parent, child)).fetchone()
            if bool(exists) == present:
                return
            if present:
                count = db.execute("SELECT count(*) FROM components WHERE parent=?", (parent,)).fetchone()[0]
                if count >= 100:
                    raise ValueError("this prototype supports at most 100 direct components per concept")
                db.execute("INSERT INTO components VALUES (?, ?, ?)", (parent, child, time.time()))
            else:
                db.execute("DELETE FROM components WHERE parent=? AND child=?", (parent, child))
            db.execute("INSERT INTO changes VALUES (?, ?, ?, ?)", (parent, child, "add" if present else "remove", time.time()))
