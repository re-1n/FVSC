"""Protocol boundary for replaceable language-specific linguistic frontends."""

from __future__ import annotations

from typing import Protocol

from ..semantic.linguistic import LinguisticFrontendResult
from .vault_ingest import SourceDocument


class LanguageFrontend(Protocol):
    """Analyze a source without granting parser output canonical evidence status."""

    name: str
    version: str

    def analyze(
        self,
        document: SourceDocument,
        *,
        language_tag: str,
    ) -> LinguisticFrontendResult: ...


__all__ = ["LanguageFrontend"]
