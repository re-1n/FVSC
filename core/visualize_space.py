"""
visualize_space.py — Render a SemanticSpace as an interactive HTML map.

Produces a single HTML file with vis-network:
  - Nodes sized by si weight (frequency proxy)
  - Nodes colored by polysemy (von Neumann entropy): cool→hot = unambiguous→polysemous
  - Edges directed by containment graded_hyponymy(B, A) > threshold
  - Side panel: click a node → polysemy, facets, contains, contained_in, query_similarity to selected
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from .density_core import SemanticSpace, graded_hyponymy


def _polysemy_color(poly: float, max_poly: float = 2.5) -> str:
    """Map polysemy → HSL hue. Low = blue, high = red."""
    t = min(poly / max_poly, 1.0)
    hue = int(220 * (1 - t) + 0 * t)  # 220 (blue) → 0 (red)
    sat = 60
    light = int(35 + 25 * t)
    return f"hsl({hue}, {sat}%, {light}%)"


def build_graph_data(
    space: SemanticSpace,
    si: Dict,
    top_n: int = 80,
    edge_threshold: float = 0.50,
    max_edges_per_node: int = 5,
) -> Dict:
    """Build vis.js-compatible nodes/edges from SemanticSpace + si."""
    skip = {"является", "содержит", "[self]"}
    ranked = sorted(
        [(c, v["weight"]) for c, v in si.items() if c not in skip],
        key=lambda x: -x[1],
    )[:top_n]
    top_terms = {t for t, _ in ranked}

    max_w = ranked[0][1] if ranked else 1.0

    nodes = []
    for term, w in ranked:
        poly = space.query_polysemy(term)
        n_facets = len(space.query_facets(term))
        size = 12 + 38 * (w / max_w)
        nodes.append({
            "id": term,
            "label": term,
            "value": w,
            "title": f"{term}\nw={w:.3f} | poly={poly:.2f} | facets={n_facets}",
            "size": size,
            "color": _polysemy_color(poly),
            "_poly": round(poly, 3),
            "_facets": n_facets,
            "_weight": round(w, 3),
        })

    edges = []
    edge_seen = set()
    for term, _ in ranked:
        contains = space.query_contains(term, top_k=20)
        kept = []
        for other, score in contains:
            if other in top_terms and other != term and score >= edge_threshold:
                kept.append((other, score))
                if len(kept) >= max_edges_per_node:
                    break
        for other, score in kept:
            key = (term, other)
            if key in edge_seen:
                continue
            edge_seen.add(key)
            edges.append({
                "from": term,
                "to": other,
                "value": score,
                "title": f"{term} ⊃ {other} = {score:.2f}",
                "arrows": "to",
            })

    return {"nodes": nodes, "edges": edges}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>FVSC — {title}</title>
<script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background: #0e0e10; color: #cfcfcf;
  font-family: 'Segoe UI', system-ui, sans-serif;
  display: flex; height: 100vh; overflow: hidden;
}}
#graph {{ flex: 1; position: relative; }}
#network {{ width: 100%; height: 100%; }}
#header {{
  position: absolute; top: 0; left: 0; right: 0;
  padding: 12px 18px; background: linear-gradient(180deg, #0e0e10ee, transparent);
  z-index: 10; pointer-events: none;
}}
#header h1 {{ font-size: 14px; font-weight: 500; color: #888; }}
#header h1 b {{ color: #ddd; }}
#header .meta {{ font-size: 11px; color: #555; margin-top: 4px; }}

#panel {{
  width: 380px; background: #131316;
  border-left: 1px solid #25252a; padding: 22px; overflow-y: auto;
}}
#panel h2 {{
  font-size: 22px; font-weight: 500; color: #eaeaea;
  margin-bottom: 16px; word-break: break-word;
}}
#panel h3 {{
  font-size: 10px; color: #666; text-transform: uppercase;
  letter-spacing: 1.8px; margin: 22px 0 8px;
}}
.placeholder {{ color: #555; font-size: 13px; padding: 30px 0; text-align: center; }}

.metric {{
  display: flex; justify-content: space-between; align-items: baseline;
  padding: 6px 0; border-bottom: 1px solid #1d1d22; font-size: 13px;
}}
.metric .k {{ color: #666; }}
.metric .v {{ color: #d0d0d0; font-family: 'Consolas', monospace; }}

.item {{
  padding: 5px 8px; margin: 2px 0; font-size: 12px;
  display: flex; justify-content: space-between;
  background: #18181c; border-radius: 3px; cursor: pointer;
  border-left: 2px solid transparent;
}}
.item:hover {{ background: #1f1f25; border-left-color: #555; }}
.item .term {{ color: #cfcfcf; }}
.item .score {{ color: #777; font-family: 'Consolas', monospace; }}
.item.contains {{ border-left-color: #2c6ba8; }}
.item.inside {{ border-left-color: #a87a2c; }}

.facet {{
  display: inline-block; background: #1c1c22; color: #aaa;
  border-radius: 10px; padding: 3px 11px; margin: 2px 3px 2px 0;
  font-size: 11px; font-family: 'Consolas', monospace;
}}

.legend {{ font-size: 11px; color: #666; margin-top: 30px; line-height: 1.7; }}
.legend .row {{ display: flex; align-items: center; gap: 8px; margin: 3px 0; }}
.legend .swatch {{
  width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0;
}}
</style>
</head>
<body>

<div id="graph">
  <div id="header">
    <h1><b>{title}</b></h1>
    <div class="meta">{subtitle}</div>
  </div>
  <div id="network"></div>
</div>

<div id="panel">
  <div id="content"><div class="placeholder">Кликни узел, чтобы развернуть концепт.</div></div>
  <div class="legend">
    <h3 style="margin-top:0">Легенда</h3>
    <div class="row"><div class="swatch" style="background:hsl(220,60%,40%)"></div>низкая полисемия (узкий смысл)</div>
    <div class="row"><div class="swatch" style="background:hsl(110,60%,48%)"></div>средняя</div>
    <div class="row"><div class="swatch" style="background:hsl(0,60%,55%)"></div>высокая (множественные грани → L6 Антураж)</div>
    <div style="margin-top:10px">Размер узла = частота. Стрелка = асимметричное содержание.</div>
  </div>
</div>

<script>
const DATA = {data_json};

const nodesById = {{}};
DATA.nodes.forEach(n => {{ nodesById[n.id] = n; }});

const adjacency = {{}};
DATA.edges.forEach(e => {{
  if (!adjacency[e.from]) adjacency[e.from] = {{ contains: [], inside: [] }};
  if (!adjacency[e.to])   adjacency[e.to]   = {{ contains: [], inside: [] }};
  adjacency[e.from].contains.push({{ other: e.to, score: e.value }});
  adjacency[e.to].inside.push({{ other: e.from, score: e.value }});
}});

const container = document.getElementById('network');
const options = {{
  nodes: {{
    shape: 'dot',
    font: {{ color: '#dddddd', size: 14, face: 'Segoe UI', strokeWidth: 0 }},
    borderWidth: 0,
  }},
  edges: {{
    color: {{ color: '#3a3a44', highlight: '#888', hover: '#666', opacity: 0.6 }},
    smooth: {{ enabled: true, type: 'continuous', roundness: 0.2 }},
    arrows: {{ to: {{ enabled: true, scaleFactor: 0.4 }} }},
    width: 1,
  }},
  physics: {{
    forceAtlas2Based: {{
      gravitationalConstant: -55,
      centralGravity: 0.012,
      springLength: 130,
      springConstant: 0.07,
      damping: 0.5,
      avoidOverlap: 0.3,
    }},
    solver: 'forceAtlas2Based',
    stabilization: {{ iterations: 200 }},
  }},
  interaction: {{ hover: true, tooltipDelay: 200 }},
}};

const network = new vis.Network(container, DATA, options);
const contentEl = document.getElementById('content');

function renderConcept(termId) {{
  const node = nodesById[termId];
  if (!node) return;
  const adj = adjacency[termId] || {{ contains: [], inside: [] }};
  const contains = adj.contains.sort((a,b) => b.score - a.score).slice(0, 12);
  const inside = adj.inside.sort((a,b) => b.score - a.score).slice(0, 12);

  let html = `<h2>${{node.label}}</h2>`;
  html += `<div class="metric"><span class="k">частота (w)</span><span class="v">${{node._weight}}</span></div>`;
  html += `<div class="metric"><span class="k">полисемия (H)</span><span class="v">${{node._poly}}</span></div>`;
  html += `<div class="metric"><span class="k">фасеты</span><span class="v">${{node._facets}}</span></div>`;

  if (contains.length) {{
    html += '<h3>содержит →</h3>';
    contains.forEach(it => {{
      html += `<div class="item contains" data-term="${{it.other}}"><span class="term">${{it.other}}</span><span class="score">${{it.score.toFixed(2)}}</span></div>`;
    }});
  }}
  if (inside.length) {{
    html += '<h3>← содержится в</h3>';
    inside.forEach(it => {{
      html += `<div class="item inside" data-term="${{it.other}}"><span class="term">${{it.other}}</span><span class="score">${{it.score.toFixed(2)}}</span></div>`;
    }});
  }}

  contentEl.innerHTML = html;
  contentEl.querySelectorAll('.item').forEach(el => {{
    el.addEventListener('click', () => {{
      const t = el.getAttribute('data-term');
      network.selectNodes([t]);
      network.focus(t, {{ scale: 1.2, animation: true }});
      renderConcept(t);
    }});
  }});
}}

network.on('click', params => {{
  if (params.nodes.length) renderConcept(params.nodes[0]);
}});
</script>
</body>
</html>
"""


def render_html(
    space: SemanticSpace,
    si: Dict,
    output_path: Path,
    title: str = "Семантическая карта",
    subtitle: str = "",
    top_n: int = 80,
    edge_threshold: float = 0.50,
    max_edges_per_node: int = 5,
):
    data = build_graph_data(
        space, si,
        top_n=top_n,
        edge_threshold=edge_threshold,
        max_edges_per_node=max_edges_per_node,
    )
    html = HTML_TEMPLATE.format(
        title=title,
        subtitle=subtitle,
        data_json=json.dumps(data, ensure_ascii=False),
    )
    output_path.write_text(html, encoding="utf-8")
    return data


# ─────────────────────────── CLI ─────────────────────────────────────────────

def main():
    """Build diary visualization."""
    from .exocortex_ingest import (
        load_channel, _clean_for_fvsc, _RU_STOPWORDS,
    )
    from .text_parser_agnostic import text_to_semantic_input, ParseConfig

    diary_path = Path(
        "/mnt/c/Users/daur1/Desktop/экзокортекс для fvsc map/личный дневник тг/result.json"
    )
    print(f"Loading {diary_path.parent.name} …")
    _, messages = load_channel(diary_path)
    cleaned = [_clean_for_fvsc(m["text"]) for m in messages]
    corpus = "\n\n".join(t for t in cleaned if len(t) >= 5)

    _synthetic = {"является", "содержит"}
    cfg = ParseConfig(
        window=4, min_freq=3, max_concepts=800, min_token_len=3,
        stopwords=_RU_STOPWORDS | _synthetic,
    )
    si = text_to_semantic_input(corpus, config=cfg)
    space = SemanticSpace(dim=64)
    space.load_from_semantic_input(si, source_text="[diary]")
    space.recursive_deepen(iterations=3, alpha=0.7)
    print(f"Space built: {len(space.concepts)} concepts")

    out = Path("/mnt/c/Users/daur1/Desktop/FVSC/core/diary_map.html")
    n_msgs = len(messages)
    dates = [m["date"] for m in messages if m["date"]]
    period = ""
    if dates:
        period = f"{min(dates).strftime('%Y-%m')} → {max(dates).strftime('%Y-%m')}"

    data = render_html(
        space, si, out,
        title="Личный дневник — карта смыслов",
        subtitle=f"{n_msgs} сообщений · {period} · top-80 концептов · асимметрия содержания",
        top_n=80,
        edge_threshold=0.50,
        max_edges_per_node=5,
    )
    print(f"  nodes={len(data['nodes'])}  edges={len(data['edges'])}")
    print(f"[saved] {out}")
    print(f"Open in browser:  file://{out}")


if __name__ == "__main__":
    main()
