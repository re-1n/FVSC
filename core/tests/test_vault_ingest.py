from __future__ import annotations

from core.vault_ingest import collect_vault_per_file


_NOTE = "Свобода требует ответственности, внимания и постоянной честной работы над собой."


def test_generated_fvsc_notes_are_never_ingested(tmp_path) -> None:
    real = tmp_path / "notes" / "real.md"
    generated = tmp_path / "_fvsc_concepts" / "freedom.md"
    obsidian = tmp_path / ".obsidian" / "internal.md"

    for path in (real, generated, obsidian):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_NOTE, encoding="utf-8")

    files, stats = collect_vault_per_file(tmp_path)

    assert list(files) == ["notes/real.md"]
    assert stats["notes"]["files"] == 1


def test_custom_exclusions_extend_protected_defaults(tmp_path) -> None:
    keep = tmp_path / "keep" / "note.md"
    custom = tmp_path / "private" / "note.md"
    generated = tmp_path / "_fvsc_concepts" / "generated.md"

    for path in (keep, custom, generated):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_NOTE, encoding="utf-8")

    files, _ = collect_vault_per_file(tmp_path, exclude_dirs={"private"})

    assert list(files) == ["keep/note.md"]
