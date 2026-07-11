from __future__ import annotations

import pytest
from pydantic import ValidationError

from service.models import CreateSpaceRequest, DeepenRequest, IngestRequest, RetrieveRequest


@pytest.mark.parametrize("dim", [0, 7, 1025, 100_000])
def test_space_dimension_is_bounded(dim: int) -> None:
    with pytest.raises(ValidationError):
        CreateSpaceRequest(name="test", dim=dim)


@pytest.mark.parametrize(
    ("iterations", "alpha"),
    [(0, 0.7), (21, 0.7), (3, -0.1), (3, 1.1)],
)
def test_deepen_parameters_are_bounded(iterations: int, alpha: float) -> None:
    with pytest.raises(ValidationError):
        DeepenRequest(iterations=iterations, alpha=alpha)


def test_empty_ingest_is_rejected() -> None:
    with pytest.raises(ValidationError):
        IngestRequest(text="", source_id="note.md")


def test_retrieve_top_k_is_bounded() -> None:
    with pytest.raises(ValidationError):
        RetrieveRequest(query="свобода", top_k=101)
