from __future__ import annotations

from pathlib import Path

import pytest

_LIVE_TEST_FILES = {
    "test_interpretation.py",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Keep tests that require a running backend/Ollama out of unit CI."""
    for item in items:
        if Path(str(item.path)).name in _LIVE_TEST_FILES:
            item.add_marker(pytest.mark.integration)
