from __future__ import annotations

import pytest
from pydantic import ValidationError

from fvsc.service.models import (
    FeedbackRequest,
    InterpretRequest,
    SearchRequest,
)


def test_search_request_has_bounded_work_controls() -> None:
    request = SearchRequest(query="роль паразитов", top_k=10, context_depth=1)

    assert request.top_k == 10
    with pytest.raises(ValidationError):
        SearchRequest(query="x", top_k=101)
    with pytest.raises(ValidationError):
        SearchRequest(query="x", context_depth=5)


def test_feedback_schema_rejects_unknown_actions_and_event_shapes() -> None:
    FeedbackRequest(target_event_id="a" * 64, action="reject")

    with pytest.raises(ValidationError):
        FeedbackRequest(target_event_id="short", action="reject")
    with pytest.raises(ValidationError):
        FeedbackRequest(target_event_id="a" * 64, action="erase")


def test_interpretation_request_has_tighter_source_budget() -> None:
    request = InterpretRequest(question="роль паразитов", top_k=5)
    assert request.context_depth == 1
    with pytest.raises(ValidationError):
        InterpretRequest(question="x", top_k=21)
