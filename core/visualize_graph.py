# -*- coding: utf-8 -*-
"""
FVSC Graph Visualizer — Build and render a directed semantic graph
from a SemanticSpace's density matrices.

Nodes = concepts (sized by mass, colored by type)
Edges = containment via graded_hyponymy (directed, weighted)

Usage: python -X utf8 visualize_graph.py <path_to_result.json> [max_messages] [min_components] [threshold]
"""

import os
import sys
import time
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import spacy

from density_core import SemanticSpace, graded_hyponymy, von_neumann_entropy
from tree_extractor import extract_judgments_recursive
from live_test import read_telegram_messages, build_seed_vectors
from thesaurus_loader import ThesaurusLoader


def build_graph(space: SemanticSpace, min_components: int = 3,
                edge_threshold: float = 0.15, top_n: int = 40) -> nx.DiGraph:
    """Build a directed graph from SemanticSpace."""
    G = nx.DiGraph()

    # Select top concepts by component count
    ranked = sorted(
        space.concepts.items(),
        key=lambda x: len(x[1].components),
        reverse=True,
    )

    candidates = []
    for term, concept in ranked:
        if len(concept.components) < min_components:
            continue
        if concept.rho_deep is None:
            continue
        candidates.append((term, concept))
        if len(candidates) >= top_n:
            break

    if not candidates:
        print("No concepts with enough components. Try lowering min_components.")
        return G

    # Add nodes
    for term, concept in candidates:
        rho = concept.rho_deep
        mass = float(np.trace(rho))
        rho_n = concept.rho_deep_norm
        entropy = von_neumann_entropy(rho_n) if rho_n is not None else 0.0
        n_components = len(concept.components)
        is_verb = concept.is_verb

        G.add_node(term, mass=mass, entropy=entropy,
                    n_components=n_components, is_verb=is_verb)

    # Add edges — directed containment via graded_hyponymy
    terms = [t for t, _ in candidates]
    concept_map = {t: c for t, c in candidates}

    for a in terms:
        rho_a = concept_map[a].rho_deep
        for b in terms:
            if a == b:
                continue
            rho_b = concept_map[b].rho_deep
            # hyp(B, A) = degree to which B is inside A = "A contains B"
            score = graded_hyponymy(rho_b, rho_a)
            if score > edge_threshold:
                G.add_edge(a, b, weight=score)

    return G


def render_graph(G: nx.DiGraph, title: str = "FVSC Semantic Graph",
                 output_path: str = "semantic_graph.png"):
    """Render graph to PNG."""
    if len(G.nodes) == 0:
        print("Empty graph, nothing to render.")
        return

    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#1a1a2e')

    # Layout
    pos = nx.spring_layout(G, k=2.5, iterations=80, seed=42, weight='weight')

    # Node sizes — proportional to mass
    masses = [G.nodes[n].get('mass', 1.0) for n in G.nodes]
    max_mass = max(masses) if masses else 1.0
    node_sizes = [300 + 1500 * (m / max_mass) for m in masses]

    # Node colors — verbs vs nouns
    node_colors = []
    for n in G.nodes:
        if G.nodes[n].get('is_verb', False):
            node_colors.append('#e94560')  # red for verbs
        else:
            entropy = G.nodes[n].get('entropy', 0.0)
            if entropy > 1.5:
                node_colors.append('#f5a623')  # orange for high polysemy
            elif entropy > 0.5:
                node_colors.append('#0f3460')  # dark blue for moderate
            else:
                node_colors.append('#16213e')  # very dark blue for focused

    # Edge widths — proportional to weight
    edge_weights = [G.edges[e].get('weight', 0.1) for e in G.edges]
    max_ew = max(edge_weights) if edge_weights else 1.0
    edge_widths = [0.5 + 3.0 * (w / max_ew) for w in edge_weights]

    # Draw edges
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        width=edge_widths,
        edge_color='#533483',
        alpha=0.6,
        arrows=True,
        arrowsize=15,
        arrowstyle='-|>',
        connectionstyle='arc3,rad=0.1',
        min_source_margin=15,
        min_target_margin=15,
    )

    # Draw nodes
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_size=node_sizes,
        node_color=node_colors,
        edgecolors='#e0e0e0',
        linewidths=1.0,
        alpha=0.9,
    )

    # Draw labels
    nx.draw_networkx_labels(
        G, pos, ax=ax,
        font_size=9,
        font_color='#e0e0e0',
        font_family='sans-serif',
        font_weight='bold',
    )

    # Legend
    legend_elements = [
        mpatches.Patch(facecolor='#16213e', edgecolor='#e0e0e0', label='Concept (focused)'),
        mpatches.Patch(facecolor='#0f3460', edgecolor='#e0e0e0', label='Concept (polysemous)'),
        mpatches.Patch(facecolor='#f5a623', edgecolor='#e0e0e0', label='Concept (high polysemy)'),
        mpatches.Patch(facecolor='#e94560', edgecolor='#e0e0e0', label='Verb-as-concept'),
    ]
    ax.legend(handles=legend_elements, loc='upper left',
              facecolor='#1a1a2e', edgecolor='#533483',
              labelcolor='#e0e0e0', fontsize=8)

    ax.set_title(title, color='#e0e0e0', fontsize=14, pad=20)
    ax.axis('off')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor=fig.get_facecolor(),
                bbox_inches='tight')
    plt.close()
    print(f"\n  Graph saved to: {output_path}")
    print(f"  Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")


def print_graph_stats(G: nx.DiGraph):
    """Print key graph statistics."""
    if len(G.nodes) == 0:
        return

    print("\n  === Graph Statistics ===")
    print(f"  Nodes: {len(G.nodes)}")
    print(f"  Edges: {len(G.edges)}")

    # Most connected nodes (by in-degree = "most contained in others")
    in_deg = sorted(G.in_degree(weight='weight'), key=lambda x: -x[1])
    print(f"\n  Most contained in others (high in-degree):")
    for term, deg in in_deg[:8]:
        print(f"    {term}: {deg:.2f}")

    # Hubs (by out-degree = "contains most")
    out_deg = sorted(G.out_degree(weight='weight'), key=lambda x: -x[1])
    print(f"\n  Richest containers (high out-degree):")
    for term, deg in out_deg[:8]:
        print(f"    {term}: {deg:.2f}")

    # Strongest edges
    edges = sorted(G.edges(data=True), key=lambda x: -x[2].get('weight', 0))
    print(f"\n  Strongest containment edges:")
    for a, b, data in edges[:10]:
        print(f"    {a} ──({data['weight']:.3f})──> {b}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -X utf8 visualize_graph.py <path_to_result.json> [max_msgs] [min_comp] [threshold]")
        sys.exit(1)

    path = sys.argv[1]
    max_msgs = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    min_comp = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    threshold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.15

    print("=" * 60)
    print("FVSC Semantic Graph Builder")
    print("=" * 60)

    # Load messages
    print(f"\nLoading messages from {path}...")
    texts, timestamps = read_telegram_messages(path, max_msgs)
    print(f"  Loaded {len(texts)} messages")

    # Load spaCy
    print("\nLoading spaCy...")
    t0 = time.time()
    nlp = spacy.load("ru_core_news_md")
    print(f"  Loaded in {time.time()-t0:.1f}s")

    # Extract judgments
    print("\nExtracting judgments (recursive tree walk)...")
    t0 = time.time()
    judgments = extract_judgments_recursive(nlp, texts, timestamps=timestamps)
    print(f"  Extracted {len(judgments)} judgments in {time.time()-t0:.1f}s")

    if not judgments:
        print("  No judgments found.")
        return

    # Collect terms and build space
    all_terms = set()
    for j in judgments:
        all_terms.update([j.subject, j.verb, j.object])

    dim = 100
    seed_vectors = build_seed_vectors(nlp, all_terms, dim)
    space = SemanticSpace(dim=dim, seed_vectors=seed_vectors, min_components_for_query=min_comp)

    # Thesaurus layer (if available)
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    thesaurus_path = os.path.join(data_dir, "conceptnet_ru.json")
    if os.path.exists(thesaurus_path):
        loader = ThesaurusLoader(conceptnet_cache=thesaurus_path, ruwordnet_dir=data_dir)
        th_judgments = loader.load_for_terms(all_terms)
        for j in th_judgments:
            space.materialize_judgment(j)
        print(f"  Thesaurus: +{len(th_judgments)} judgments")

    for j in judgments:
        space.materialize_judgment(j)

    print(f"  Concepts: {len(space.concepts)}")

    # Recursive deepening
    print("\nRecursive deepening...")
    t0 = time.time()
    space.recursive_deepen(iterations=3, alpha=0.7)
    print(f"  Done in {time.time()-t0:.1f}s")

    # Build graph
    print(f"\nBuilding graph (min_components={min_comp}, threshold={threshold})...")
    G = build_graph(space, min_components=min_comp, edge_threshold=threshold, top_n=40)

    print_graph_stats(G)

    # Render
    output_path = "semantic_graph.png"
    render_graph(G, title=f"FVSC — {len(texts)} messages, {len(judgments)} judgments",
                 output_path=output_path)

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
