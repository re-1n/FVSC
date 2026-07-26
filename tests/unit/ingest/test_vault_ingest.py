from __future__ import annotations

import hashlib

import pytest

from fvsc.ingest import OBSIDIAN_VAULT_ADAPTER, SourceDocument, normalize_markdown, scan_vault


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def test_scan_is_sorted_and_protected_exclusions_cannot_be_removed(tmp_path) -> None:
    note = """---
fvsc_source_kind: owner_reflection
---
# Values
I value [[Freedom|freedom]] and [care](https://example.test).
"""
    _write(tmp_path / "z" / "second.md", "External source text")
    _write(tmp_path / "a" / "first.md", note)
    _write(tmp_path / ".obsidian" / "workspace.md", note)
    _write(tmp_path / ".fvsc" / "generated.md", note)
    _write(tmp_path / "_fvsc_concepts" / "feedback.md", note)
    _write(tmp_path / "private" / "hidden.md", note)

    scan = scan_vault(tmp_path, exclude_dirs={"private"})

    assert [document.source_id for document in scan.documents] == [
        "a/first.md",
        "z/second.md",
    ]
    first = scan.documents[0]
    assert first.adapter == OBSIDIAN_VAULT_ADAPTER
    assert first.source_kind == "owner_reflection"
    assert first.text == "Values\nI value freedom and care."
    assert scan.folder_stats["a"]["files"] == 1
    assert scan.source_revisions[first.source_id] == first.source_revision


def test_revision_hashes_raw_file_and_scan_keeps_relative_ids_only(tmp_path) -> None:
    raw = "# Note\nAlpha beta gamma."
    path = tmp_path / "notes" / "value.md"
    _write(path, raw)

    document = scan_vault(tmp_path).documents[0]

    assert document.source_id == "notes/value.md"
    assert document.source_revision == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert str(tmp_path) not in document.source_id
    assert document.metadata == {"encoding": "utf-8", "format": "obsidian-markdown"}


@pytest.mark.parametrize("line_ending", ["\r\n", "\r"])
def test_markdown_normalizer_canonicalizes_platform_line_endings(line_ending: str) -> None:
    raw = line_ending.join(
        [
            "---",
            "fvsc_source_kind: owner_reflection",
            "---",
            "# Values",
            "I value [[Freedom|freedom]].",
        ]
    )

    text, source_kind = normalize_markdown(raw)

    assert text == "Values\nI value freedom."
    assert source_kind == "owner_reflection"


@pytest.mark.parametrize("kind", ["owner_reflection", "dream_report", "external_fact"])
def test_explicit_source_kinds_remain_distinct(kind) -> None:
    text, parsed_kind = normalize_markdown(f"---\nsource_kind: {kind}\n---\nA real sentence.")

    assert text == "A real sentence."
    assert parsed_kind == kind


def test_missing_source_kind_is_unknown_and_invalid_kind_is_rejected() -> None:
    assert normalize_markdown("Unclassified note.")[1] == "unknown"

    with pytest.raises(ValueError, match="unknown source kind"):
        normalize_markdown("---\nsource_kind: owner_fact\n---\nNo silent promotion.")


def test_markdown_normalizer_removes_code_embeds_and_destinations_not_languages() -> None:
    text, _ = normalize_markdown(
        """# Заголовок
Русский and English.
`secret()` ![[asset.png]] ![image](image.png)
```python
print("not evidence")
```
"""
    )

    assert "Русский and English." in text
    assert "secret" not in text
    assert "asset.png" not in text
    assert "not evidence" not in text


def test_symlinked_note_is_not_ingested(tmp_path) -> None:
    target = tmp_path / "outside.md"
    _write(target, "A source outside the scanned notes folder.")
    link = tmp_path / "notes" / "linked.md"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")

    scan = scan_vault(tmp_path, exclude_dirs={"outside"})

    assert all(document.source_id != "notes/linked.md" for document in scan.documents)


def test_source_document_rejects_unsafe_or_untyped_identity() -> None:
    digest = "0" * 64
    with pytest.raises(ValueError, match="POSIX-relative"):
        SourceDocument.create(
            source_id="..\\outside.md",
            source_revision=digest,
            observed_at=1.0,
            text="text",
            adapter="test",
        )
    with pytest.raises(ValueError, match="unknown source kind"):
        SourceDocument.create(
            source_id="note.md",
            source_revision=digest,
            observed_at=1.0,
            text="text",
            adapter="test",
            source_kind="owner_fact",  # type: ignore[arg-type]
        )


def test_scan_rejects_symlink_root(tmp_path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable on this platform")

    with pytest.raises(ValueError, match="symlink vault root"):
        scan_vault(link)
