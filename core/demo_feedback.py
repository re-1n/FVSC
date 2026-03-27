# -*- coding: utf-8 -*-
"""
FVSC Demo: Map + Visualization + Antourage feedback — all in one.

Builds a semantic map from hand-crafted judgments, generates feedback questions,
and opens an interactive HTML with the Antourage panel.

Usage: python -X utf8 demo_feedback.py
"""

import os
import sys
import time
import json
import webbrowser
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from density_core import Judgment, SemanticSpace
from feedback import FeedbackEngine


def create_demo_space() -> tuple[SemanticSpace, list[Judgment]]:
    """Create a demo semantic space with interesting patterns for feedback."""

    np.random.seed(42)
    now = time.time()
    space = SemanticSpace(dim=30, min_components_for_query=1)

    judgments = [
        # Core beliefs about freedom
        Judgment("свобода", "требовать", "ответственность", modality=1.0, intensity=0.9,
                 timestamp=now - 30 * 86400, source_text="Свобода требует ответственности"),
        Judgment("свобода", "требовать", "ответственность", modality=1.0, intensity=0.9,
                 timestamp=now - 20 * 86400, source_text="Настоящая свобода требует ответственности"),
        Judgment("свобода", "требовать", "ответственность", modality=1.0, intensity=0.9,
                 timestamp=now - 10 * 86400, source_text="Без ответственности свобода невозможна"),
        Judgment("свобода", "включать", "выбор", modality=1.0, intensity=0.8,
                 timestamp=now - 25 * 86400, source_text="Свобода включает в себя выбор"),
        Judgment("свобода", "включать", "выбор", modality=1.0, intensity=0.8,
                 timestamp=now - 15 * 86400, source_text="Свобода — это прежде всего выбор"),
        Judgment("свобода", "быть", "независимость", modality=1.0, intensity=0.7,
                 timestamp=now - 5 * 86400, source_text="Свобода — это независимость"),

        # Anomaly: contradicts existing map
        Judgment("свобода", "приводить", "одиночество", modality=1.0, intensity=0.7,
                 timestamp=now, source_text="Свобода приводит к одиночеству"),

        # Contradiction about love
        Judgment("любовь", "давать", "свободу", quality="AFFIRMATIVE", modality=1.0, intensity=0.8,
                 timestamp=now - 20 * 86400, source_text="Любовь даёт свободу"),
        Judgment("любовь", "давать", "свободу", quality="NEGATIVE", modality=0.8, intensity=0.6,
                 timestamp=now - 2 * 86400, source_text="Любовь не даёт свободу, а ограничивает"),

        # More about love
        Judgment("любовь", "требовать", "терпение", modality=1.0, intensity=0.7,
                 timestamp=now - 15 * 86400, source_text="Любовь требует терпения"),
        Judgment("любовь", "включать", "доверие", modality=1.0, intensity=0.8,
                 timestamp=now - 10 * 86400, source_text="Любовь включает доверие"),
        Judgment("любовь", "порождать", "уязвимость", modality=1.0, intensity=0.6,
                 timestamp=now - 5 * 86400, source_text="Любовь порождает уязвимость"),

        # Responsibility
        Judgment("ответственность", "требовать", "мужество", modality=1.0, intensity=0.8,
                 timestamp=now - 25 * 86400, source_text="Ответственность требует мужества"),
        Judgment("ответственность", "включать", "долг", modality=1.0, intensity=0.7,
                 timestamp=now - 18 * 86400, source_text="Ответственность включает долг"),
        Judgment("ответственность", "давать", "свободу", modality=0.8, intensity=0.7,
                 timestamp=now - 12 * 86400, source_text="Ответственность даёт свободу"),

        # Defeasible L1 inference
        Judgment("дружба", "включать", "доверие", modality=0.5, intensity=0.6,
                 timestamp=now, source_text="[вывод] дружба включает доверие",
                 interpretation_layer=1, defeasible=True,
                 inference_chain=["любовь включает доверие", "дружба ~ любовь"]),
        Judgment("дружба", "требовать", "время", modality=0.5, intensity=0.5,
                 timestamp=now, source_text="[вывод] дружба требует времени",
                 interpretation_layer=1, defeasible=True,
                 inference_chain=["статистика: дружба + время в 80% текстов"]),

        # Choice and courage
        Judgment("выбор", "требовать", "ответственность", modality=1.0, intensity=0.8,
                 timestamp=now - 8 * 86400, source_text="Выбор требует ответственности"),
        Judgment("выбор", "включать", "отказ", modality=1.0, intensity=0.6,
                 timestamp=now - 6 * 86400, source_text="Выбор включает в себя отказ"),
        Judgment("мужество", "быть", "честность", modality=0.8, intensity=0.6,
                 timestamp=now - 4 * 86400, source_text="Мужество — это честность перед собой"),

        # Self
        Judgment("я", "стремиться", "свобода", modality=1.0, intensity=0.9,
                 timestamp=now - 10 * 86400, source_text="Я стремлюсь к свободе"),
        Judgment("я", "ценить", "честность", modality=1.0, intensity=0.8,
                 timestamp=now - 5 * 86400, source_text="Я ценю честность"),
    ]

    for j in judgments:
        space.materialize_judgment(j)

    space.recursive_deepen(iterations=3, alpha=0.7)
    return space, judgments


def main():
    print("=" * 60)
    print("FVSC Demo: Map + Antourage Feedback")
    print("=" * 60)

    # Build space
    print("\nBuilding semantic space...")
    space, judgments = create_demo_space()
    print(f"  {len(judgments)} judgments, {len(space.concepts)} concepts")

    # Generate feedback questions
    print("\nGenerating feedback questions...")
    engine = FeedbackEngine(space)
    questions = engine.generate_questions(max_count=10)
    print(f"  {len(questions)} questions generated")
    for q in questions:
        print(f"    [{q.question_type}] {q.prompt_text[:60]}...")

    # Build map data (imports interactive_map functions)
    print("\nBuilding interactive map...")
    from interactive_map import build_map_data, generate_html

    map_data = build_map_data(space, min_components=1, edge_threshold=0.2, top_n=30)
    print(f"  {len(map_data['nodes'])} nodes, {len(map_data['edges'])} edges")
    print(f"  {len(map_data.get('feedback', []))} feedback questions embedded")

    # Generate HTML
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "demo_feedback.html")
    generate_html(
        map_data,
        n_messages=len(judgments),
        n_judgments=len(judgments),
        threshold=0.3,
        output_path=output_path,
        title_suffix="[demo] ",
    )
    print(f"\n  Generated: {output_path}")

    # Open in browser
    print("  Opening in browser...")
    webbrowser.open(f"file:///{os.path.abspath(output_path).replace(os.sep, '/')}")

    print("\n" + "=" * 60)
    print("Ready! The map is open in your browser.")
    print("Click 'Antourage' button at the bottom to start the feedback session.")
    print("=" * 60)


if __name__ == "__main__":
    main()
