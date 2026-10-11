from dataclasses import replace
import hashlib

import pytest

from fvsc.ingest.source_provenance import ExpressionSpan, SourceAttribution
from fvsc.ingest.vault_ingest import SourceDocument
from fvsc.interpretation.clarifications import ClarificationStore, ClarificationTarget


def document(text="Лея: «Можно передумать». 🪶 Мой комментарий.", metadata=None):
    return SourceDocument.create(source_id="note.md", source_revision=hashlib.sha256(text.encode()).hexdigest(),
                                 observed_at=1.0, text=text, adapter="test", metadata=metadata)


def target(doc, question="Как я отношусь к изменениям?"):
    return ClarificationTarget.create(doc, start=0, end=len(doc.text), question=question)


@pytest.fixture
def store():
    value = ClarificationStore(":memory:")
    yield value
    value.close()


@pytest.mark.parametrize("action,status", [
    ("my_position", "ready"), ("agree", "ready"), ("saved_only", "excluded"),
    ("unsure", "unresolved"), ("skip", "deferred"), ("freeform", "unresolved"),
])
def test_choice_is_reused_without_repeating_question(store, action, status):
    doc = document()
    item = target(doc)
    assert store.prepare(item, doc)["status"] == "pending"
    note = "Согласен лишь отчасти, зависит от ситуации" if action == "freeform" else ""
    result = store.answer(item.target_id, doc, action=action, note=note)
    assert result["status"] == status
    assert result["usable_as_owner_position"] == (status == "ready")
    assert store.prepare(item, doc) == result
    store.answer(item.target_id, doc, action=action, note=note)  # transport retry
    assert len(store.history(item.target_id)) == 1
    assert result["fragment"] == doc.text
    assert doc.metadata == {}


def test_context_revision_and_span_are_not_generalized(store):
    doc = document()
    item = target(doc)
    store.prepare(item, doc)
    store.answer(item.target_id, doc, action="agree")
    assert store.prepare(target(doc, "Как Лея относится к изменениям?"), doc)["status"] == "pending"
    shorter = ClarificationTarget.create(doc, start=0, end=4, question=item.question)
    assert store.prepare(shorter, doc)["status"] == "pending"
    changed = document(doc.text + " Дополнение.")
    with pytest.raises(ValueError, match="source changed"):
        store.answer(item.target_id, changed, action="saved_only")
    assert store.prepare(target(changed), changed)["status"] == "pending"


def test_changed_text_with_same_revision_is_rejected(store):
    doc = document()
    item = target(doc)
    store.prepare(item, doc)
    tampered = replace(doc, text=doc.text.replace("Лея", "Зоя"))
    with pytest.raises(ValueError, match="does not match"):
        store.answer(item.target_id, tampered, action="agree")
    assert store.history(item.target_id) == []


def test_amendments_preserve_history_and_reject_stale_edits(store):
    doc = document()
    item = target(doc)
    store.prepare(item, doc)
    first = store.answer(item.target_id, doc, action="agree")
    with pytest.raises(ValueError, match="changed"):
        store.answer(item.target_id, doc, action="saved_only", expected_sequence=0)
    second = store.answer(item.target_id, doc, action="saved_only", expected_sequence=first["answer"]["sequence"])
    assert second["status"] == "excluded"
    assert [a["action"] for a in store.history(item.target_id)] == ["agree", "saved_only"]


def test_adoption_and_authorship_are_not_endorsement(store):
    doc = document(metadata={"source_attribution": SourceAttribution("owner", True, "owner").to_dict()})
    assert store.prepare(target(doc), doc)["status"] == "pending"


def test_explicit_stance_needs_no_question_but_can_be_corrected(store):
    doc = document()
    span = ExpressionSpan.from_text(doc.text, start=0, end=len(doc.text), kind="quotation",
                                    origin_status="external", owner_endorsement="endorsed")
    doc = document(metadata={"source_attribution": SourceAttribution("owner", True, "mixed", expression_spans=(span,)).to_dict()})
    item = target(doc)
    assert store.prepare(item, doc)["status"] == "ready"
    assert store.answer(item.target_id, doc, action="unsure")["status"] == "unresolved"


@pytest.mark.parametrize("action,note", [("freeform", "   "), ("agree", "Actually not"), ("invented", "")])
def test_invalid_answer_never_appends(store, action, note):
    doc = document()
    item = target(doc)
    store.prepare(item, doc)
    with pytest.raises(ValueError):
        store.answer(item.target_id, doc, action=action, note=note)
    assert store.history(item.target_id) == []


def test_persistence_does_not_copy_source_body(tmp_path):
    path = tmp_path / "clarifications.sqlite3"
    doc = document()
    item = target(doc)
    store = ClarificationStore(path)
    store.prepare(item, doc)
    store.answer(item.target_id, doc, action="skip")
    store.close()
    restored = ClarificationStore(path)
    assert restored.prepare(item, doc)["status"] == "deferred"
    restored.close()
    assert doc.text.encode("utf-8") not in path.read_bytes()
