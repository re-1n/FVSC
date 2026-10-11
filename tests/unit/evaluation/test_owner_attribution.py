from dataclasses import replace
from types import SimpleNamespace

import pytest

from fvsc.ingest.owner_attribution import direct_owner_eligibility, reported_expressions
from fvsc.ingest.source_provenance import ExpressionSpan, SourceAttribution
from fvsc.evaluation.planned_slot_synthesis import FrozenQuestionPlan, PlannedRequirement
from fvsc.evaluation.relation_support_guard import PUBLIC_RELATION_SUPPORT_GUARD
from fvsc.evaluation.planned_slot_runner import run_planned_slots


def annotation(text, fragment, *, kind="owner_commentary", origin="owner", relation="authored", stance="unresolved"):
    start = text.index(fragment)
    return ExpressionSpan.from_text(
        text, start=start, end=start + len(fragment), kind=kind,
        origin_status=origin, owner_relation=relation, owner_endorsement=stance,
    )


def source(text, *, role="owner", origin="owner", spans=(), label="S1"):
    return SimpleNamespace(label=label, text=text, attribution=SourceAttribution(
        role, False, origin, expression_spans=spans,
    ))


def plan(relation="confirmed", scope="direct_owner"):
    return FrozenQuestionPlan("owner-test", (PlannedRequirement("R1", relation, scope),))


def test_scope_is_explicit_and_validated():
    item = source("The dome is confirmed.", role="non_owner")
    assert PUBLIC_RELATION_SUPPORT_GUARD.compile(plan(scope="source"), (item,))[0].eligible_source_labels == ("S1",)
    result = PUBLIC_RELATION_SUPPORT_GUARD.compile(plan(), (item,))[0]
    assert result.eligible_source_labels == ()
    assert result.source_decisions[0].reason == "author_not_owner_or_unknown"
    with pytest.raises(ValueError, match="scope"):
        plan(scope="infer_from_words")


def test_missing_metadata_abstains_even_with_direct_owner_wording():
    item = SimpleNamespace(label="S1", text="The dome is confirmed.")
    result = PUBLIC_RELATION_SUPPORT_GUARD.compile(plan(), (item,))[0]
    assert result.source_decisions[0].reason == "missing_attribution"


@pytest.mark.parametrize("text", [
    "The dome is not confirmed.", "The dome might be confirmed.",
])
def test_owner_scope_preserves_polarity_and_modality(text):
    result = PUBLIC_RELATION_SUPPORT_GUARD.compile(plan(), (source(text),))[0]
    assert result.eligible_source_labels == ()
    assert result.source_decisions[0].reason == "no_affirmed_relation_in_owner_regions"


def test_relation_cue_must_be_inside_owner_region():
    text = 'Lea: "The dome is confirmed." I bought a ticket.'
    spans = (
        annotation(text, "The dome is confirmed.", kind="quotation", origin="external", relation="selected"),
        annotation(text, "I bought a ticket."),
    )
    result = PUBLIC_RELATION_SUPPORT_GUARD.compile(plan(), (source(text, origin="mixed", spans=spans),))[0]
    assert result.eligible_source_labels == ()


def test_separated_owner_spans_are_not_joined_into_relation_cue():
    text = "It opens only [external material] if approved."
    spans = (annotation(text, "It opens only"), annotation(text, "if approved."))
    result = PUBLIC_RELATION_SUPPORT_GUARD.compile(plan("conditional"), (source(text, origin="mixed", spans=spans),))[0]
    assert result.eligible_source_labels == ()


def test_polarity_before_annotation_is_not_discarded():
    text = "The dome is not confirmed."
    span = annotation(text, "confirmed")
    result = PUBLIC_RELATION_SUPPORT_GUARD.compile(plan(), (source(text, origin="mixed", spans=(span,)),))[0]
    assert result.eligible_source_labels == ()


def test_source_decisions_do_not_borrow_metadata():
    items = (source("The dome is confirmed."), source("The dome is confirmed.", role="unknown", label="S2"))
    result = PUBLIC_RELATION_SUPPORT_GUARD.compile(plan(), items)[0]
    assert result.eligible_source_labels == ("S1",)
    assert [d.eligible for d in result.source_decisions] == [True, False]


def test_stale_annotation_rejected_even_for_nonowner():
    text = "The dome is confirmed."
    span = annotation(text, text)
    item = source(text.replace("dome", "hall"), role="non_owner", spans=(span,))
    with pytest.raises(ValueError, match="does not match"):
        direct_owner_eligibility(item.text, item.attribution)


def test_ambiguous_labels_cannot_bypass_owner_scope():
    items = (source("The dome is confirmed."), source("The dome is confirmed.", role="unknown"))
    with pytest.raises(ValueError, match="unique source labels"):
        PUBLIC_RELATION_SUPPORT_GUARD.compile(plan(), items)


def test_conflicting_commentary_cannot_become_owner_evidence():
    text = "The dome is confirmed."
    span = annotation(text, text, origin="external")
    item = source(text, spans=(span,))
    assert not direct_owner_eligibility(text, item.attribution).eligible


def test_agreement_remains_distinct_from_authorship_and_adoption():
    text = 'I agree: "The dome is confirmed."'
    quote = annotation(text, "The dome is confirmed.", kind="quotation", origin="external", relation="adopted", stance="endorsed")
    item = source(text, origin="mixed", spans=(quote,))
    report, = reported_expressions(item.label, text, item.attribution)
    assert report.owner_endorsement == "endorsed"
    assert report.speaker is None
    assert not direct_owner_eligibility(text, item.attribution).eligible
    selection = replace(item.attribution, owner_adopted_expression=True,
                        expression_spans=(replace(quote, owner_endorsement="unresolved"),))
    assert reported_expressions(item.label, text, selection)[0].owner_endorsement == "unresolved"
    report.verify(source_label=item.label, text=text)
    with pytest.raises(ValueError, match="label"):
        report.verify(source_label="S2", text=text)
    with pytest.raises(ValueError, match="revision"):
        report.verify(source_label=item.label, text=text + " extra")


@pytest.mark.parametrize("allowlist", [None, {"owner-test": {"R1": ("S1",)}}])
def test_runner_enforces_owner_scope_without_optional_external_guard(allowlist):
    class Backend:
        last_generation_telemetry = None

        def generate_json_object(self, payload, *, source_count):
            assert payload["requirements"][0]["attribution_scope"] == "direct_owner"
            return {"slots": [{"requirement_id": "R1", "status": "supported", "claim": {
                "text": "The dome is confirmed.", "citations": ["S1"], "support_level": "evidence_bound",
            }}]}

    fixture = SimpleNamespace(case_id="owner-test", question="What did the owner confirm?",
                              sources=(source("The dome is confirmed.", role="unknown"),))
    result, = run_planned_slots((fixture,), backend_factory=lambda *_: Backend(),
                               plans_by_case={"owner-test": plan()}, eligible_labels_by_case=allowlist)
    assert result.status == "insufficient"
    assert result.slots[0]["claim"] is None
