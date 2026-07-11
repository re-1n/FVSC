"""Feedback revision helpers for the FVSC pilot."""

from __future__ import annotations

from typing import Any, Iterable


def latest_feedback_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the latest record per query ID in deterministic order.

    Feedback persistence remains append-only. A later record with the same
    ``query_id`` supersedes the earlier rating for summaries and readiness gates.
    Ties are resolved by append order.
    """
    latest: dict[str, tuple[float, int, dict[str, Any]]] = {}
    anonymous: list[tuple[float, int, dict[str, Any]]] = []
    for index, record in enumerate(records):
        copy = dict(record)
        try:
            recorded_at = float(copy.get("recorded_at", 0.0))
        except (TypeError, ValueError):
            recorded_at = 0.0
        query_id = str(copy.get("query_id", "")).strip()
        entry = (recorded_at, index, copy)
        if not query_id:
            anonymous.append(entry)
            continue
        previous = latest.get(query_id)
        if previous is None or entry[:2] >= previous[:2]:
            latest[query_id] = entry
    resolved = [entry for entry in latest.values()] + anonymous
    resolved.sort(key=lambda entry: (entry[0], entry[1]))
    return [entry[2] for entry in resolved]


def feedback_summary(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize only current feedback revisions."""
    current = latest_feedback_records(records)
    if not current:
        return {
            "count": 0,
            "history_count": 0,
            "mean_rating": None,
            "useful_rate": None,
            "by_query_type": {},
        }
    history = list(records) if not isinstance(records, list) else records
    by_type: dict[str, list[dict[str, Any]]] = {}
    for record in current:
        by_type.setdefault(str(record.get("query_type", "unknown")), []).append(record)
    return {
        "count": len(current),
        "history_count": len(history),
        "mean_rating": sum(int(record.get("rating", 0)) for record in current) / len(current),
        "useful_rate": sum(bool(record.get("useful", False)) for record in current) / len(current),
        "by_query_type": {
            query_type: {
                "count": len(group),
                "mean_rating": sum(int(record.get("rating", 0)) for record in group) / len(group),
                "useful_rate": sum(bool(record.get("useful", False)) for record in group) / len(group),
            }
            for query_type, group in sorted(by_type.items())
        },
    }
