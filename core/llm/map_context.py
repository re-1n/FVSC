"""
Build a compact text context describing the semantic map for LLM prompting.

The LLM is NOT given access to math; it sees the map as structured text and
reasons narratively. Keep this dump tight — every token costs num_ctx budget.
"""
from __future__ import annotations

import json
from typing import Dict, Optional

from ..density_core import SemanticSpace


SYSTEM_PROMPT = """Ты — аналитик персональной семантической карты пользователя.

Карта построена системой FVSC (Field of Vector Semantic Computing). Концепты — это термины из текстов пользователя. Для каждого концепта есть:
- w — частота (вес в корпусе)
- H — полисемия (энтропия фон Неймана: 0 = однозначное, >1 = многогранное)
- contains → — какие концепты этот содержит (асимметричное вложение смысла)
- contained_in ← — в какие концепты входит сам

Твои задачи:
- Описывать кластеры и темы карты на основе показанных связей.
- Замечать необычное: высокая полисемия, концепт без связей, изолированные кластеры.
- Отвечать только на основе данных карты — не выдумывай связи которых нет.
- Если данных недостаточно — скажи это прямо.
- Отвечай на русском, кратко и по делу.
"""


def build_context_dump(
    space: SemanticSpace,
    si: Dict,
    top_n: int = 50,
    edges_per_concept: int = 3,
) -> str:
    """Compact textual representation of the top-N concepts and their edges.

    Format (one concept per block, JSON-ish but readable):

        # топ концептов карты (N=50)
        - кот | w=0.42 H=0.81 facets=2
          → животное (1.00), мяукать (0.99), пушистый (0.97)
          ← домашние (0.88), млекопитающее (0.85)
        ...
    """
    skip = {"является", "содержит", "[self]"}
    ranked = sorted(
        [(t, v["weight"]) for t, v in si.items() if t not in skip],
        key=lambda x: -x[1],
    )

    queryable = {t for t, _ in space._queryable_concepts()}
    ranked = [(t, w) for t, w in ranked if t in queryable][:top_n]

    lines = [f"# топ концептов карты (N={len(ranked)})", ""]
    for term, w in ranked:
        poly = space.query_polysemy(term)
        facets = len(space.query_facets(term))
        lines.append(f"- {term} | w={w:.2f} H={poly:.2f} facets={facets}")

        contains = space.query_contains(term, top_k=edges_per_concept)
        contains = [(o, s) for o, s in contains if s > 0.1]
        if contains:
            parts = [f"{o} ({s:.2f})" for o, s in contains]
            lines.append(f"  -> {', '.join(parts)}")

        contained_in = space.query_contained_in(term, top_k=edges_per_concept)
        contained_in = [(o, s) for o, s in contained_in if s > 0.1]
        if contained_in:
            parts = [f"{o} ({s:.2f})" for o, s in contained_in]
            lines.append(f"  <- {', '.join(parts)}")

    return "\n".join(lines)


def build_global_stats(space: SemanticSpace, si: Dict) -> str:
    """One-paragraph corpus-level summary prepended to context."""
    n_concepts = len(space.concepts)
    polys = []
    for term, c in space.concepts.items():
        if c.rho_deep_norm is not None:
            polys.append(space.query_polysemy(term))
    avg_poly = sum(polys) / len(polys) if polys else 0.0
    n_polysemous = sum(1 for p in polys if p > 1.0)
    return (
        f"# сводка карты\n"
        f"- концептов в пространстве: {n_concepts}\n"
        f"- средняя полисемия (H): {avg_poly:.2f}\n"
        f"- концептов с H>1.0 (заметно многогранных): {n_polysemous}\n"
    )


def build_full_prompt_context(
    space: SemanticSpace,
    si: Dict,
    top_n: int = 50,
    edges_per_concept: int = 3,
) -> str:
    stats = build_global_stats(space, si)
    dump = build_context_dump(space, si, top_n=top_n, edges_per_concept=edges_per_concept)
    return stats + "\n" + dump
