# -*- coding: utf-8 -*-
"""
FVSC Interactive Semantic Map — generates a self-contained HTML file
with vis.js network graph + provenance panel.

Click on a concept → see its judgments, source texts, containment, facets.

Usage: python -X utf8 interactive_map.py <path_to_result.json> [max_messages] [min_components]
"""

import os
import sys
import json
import time
import numpy as np
import spacy

from density_core import SemanticSpace, graded_hyponymy, von_neumann_entropy, purity, facets
from tree_extractor import extract_judgments_recursive
from live_test import read_telegram_messages, build_seed_vectors
from thesaurus_loader import ThesaurusLoader


def build_map_data(space: SemanticSpace, min_components: int = 3,
                   edge_threshold: float = 0.3, top_n: int = 50) -> dict:
    """Build JSON-serializable data for the interactive map."""

    # Select top concepts
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

    # Build nodes with provenance
    nodes = []
    for term, concept in candidates:
        rho = concept.rho_deep
        rho_n = concept.rho_deep_norm
        mass = float(np.trace(rho))
        entropy = von_neumann_entropy(rho_n) if rho_n is not None else 0.0
        pur = purity(rho_n) if rho_n is not None else 1.0
        is_verb = concept.is_verb

        # Facets
        f = facets(rho_n, threshold=0.03) if rho_n is not None else []
        facet_list = [{"weight": round(w, 3), "index": i} for i, (w, _) in enumerate(f)]

        # Provenance: judgments that formed this concept
        seen = set()
        judgment_list = []
        for comp in concept.components:
            j = comp.judgment
            key = f"{j.subject}|{j.verb}|{j.object}|{j.quality}"
            if key in seen:
                continue
            seen.add(key)
            judgment_list.append({
                "subject": j.subject,
                "verb": j.verb,
                "object": j.object,
                "quality": j.quality,
                "modality": round(j.modality, 2),
                "intensity": round(j.intensity, 2),
                "source_text": j.source_text[:200],
                "condition_id": j.condition_id,
                "condition_role": j.condition_role,
                "anomaly": round(j.anomaly_score, 3) if j.anomaly_score else 0,
                # Feedback fields
                "layer": j.interpretation_layer,
                "defeasible": j.defeasible,
                "confirmation": j.confirmation_status,
                "confidence": round(j.extraction_confidence, 2),
            })

        nodes.append({
            "id": term,
            "label": term,
            "mass": round(mass, 3),
            "entropy": round(entropy, 3),
            "purity": round(pur, 3),
            "n_components": len(concept.components),
            "is_verb": is_verb,
            "facets": facet_list,
            "judgments": judgment_list,
        })

    # Build edges
    edges = []
    term_set = {n["id"] for n in nodes}
    concept_map = {t: c for t, c in candidates}

    for a in term_set:
        rho_a = concept_map[a].rho_deep
        for b in term_set:
            if a == b:
                continue
            rho_b = concept_map[b].rho_deep
            score = graded_hyponymy(rho_b, rho_a)
            if score > edge_threshold:
                edges.append({
                    "from": a,
                    "to": b,
                    "weight": round(score, 3),
                })

    # Self container
    self_data = None
    sc = space.self_concept
    if sc.components:
        sc._recompute_rho()
        seen = set()
        self_judgments = []
        for comp in sc.components:
            j = comp.judgment
            key = f"{j.verb}:{j.object}"
            if key in seen:
                continue
            seen.add(key)
            self_judgments.append({
                "verb": j.verb,
                "object": j.object,
                "quality": j.quality,
                "source_text": j.source_text[:200],
            })
        rho_n = sc.rho_norm
        self_data = {
            "n_components": len(sc.components),
            "mass": round(float(np.trace(sc.rho)), 3),
            "entropy": round(von_neumann_entropy(rho_n), 3) if rho_n is not None else 0,
            "judgments": self_judgments,
        }

    # Feedback questions (generated from FeedbackEngine if available)
    feedback_questions = []
    try:
        from feedback import FeedbackEngine
        engine = FeedbackEngine(space)
        for q in engine.generate_questions(max_count=10):
            feedback_questions.append({
                "type": q.question_type,
                "priority": round(q.priority, 2),
                "prompt": q.prompt_text,
                "options": q.options,
                "concepts": q.related_concepts,
            })
    except ImportError:
        pass

    return {"nodes": nodes, "edges": edges, "self": self_data,
            "feedback": feedback_questions}


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>FVSC — Персональная семантическая карта</title>
<script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #111; color: #ccc; font-family: 'Segoe UI', system-ui, sans-serif; display: flex; height: 100vh; overflow: hidden; }

#graph-container { flex: 1; position: relative; transition: background 0.6s ease; }
#graph-container.inside { background: radial-gradient(ellipse at center, #1a1a2e 0%, #0d0d1a 55%, #050508 100%); }
#network { width: 100%; height: 100%; }

/* Sphere vignette overlay */
#sphere-vignette { position: absolute; top: 0; left: 0; right: 0; bottom: 0; pointer-events: none; opacity: 0;
    transition: opacity 0.6s ease; border-radius: 0;
    box-shadow: inset 0 0 150px 60px rgba(0,0,0,0.8), inset 0 0 40px 20px rgba(10,10,30,0.5); z-index: 1; }
#graph-container.inside #sphere-vignette { opacity: 1; }

#panel { width: 400px; background: #161616; border-left: 1px solid #282828; overflow-y: auto; padding: 20px; }
#panel h2 { color: #eee; font-size: 18px; margin-bottom: 12px; font-weight: 500; }
#panel h3 { color: #777; font-size: 12px; margin: 18px 0 6px; text-transform: uppercase; letter-spacing: 1.5px; }

.stat { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #1e1e1e; font-size: 13px; }
.stat-label { color: #555; }
.stat-value { color: #bbb; }

.judgment { background: #1c1c1c; border-radius: 6px; padding: 10px 12px; margin: 5px 0; font-size: 12px; border-left: 2px solid #444; }
.judgment .triple { color: #ccc; font-weight: 500; margin-bottom: 4px; }
.judgment .source { color: #666; font-style: italic; line-height: 1.5; margin-top: 4px; }
.judgment.neg { border-left-color: #944; }
.judgment.cond { border-left-color: #885; }
.judgment.anomaly { border-left-color: #d90; background: #1f1c18; }
.anomaly-badge { display: inline-block; background: #d90; color: #111; font-size: 9px; padding: 1px 6px; border-radius: 8px; margin-left: 6px; font-weight: 600; }

.contains-item { padding: 4px 0; font-size: 12px; display: flex; justify-content: space-between; border-bottom: 1px solid #1c1c1c; cursor: pointer; }
.contains-item:hover { background: #1e1e1e; }
.contains-score { color: #888; font-family: monospace; }

.facet { display: inline-block; background: #222; border-radius: 10px; padding: 2px 10px; margin: 2px; font-size: 11px; color: #999; }

#self-btn { position: absolute; top: 16px; right: 420px; background: #1c1c1c; border: 1px solid #333; color: #999; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 12px; z-index: 10; }
#self-btn:hover { background: #252525; color: #ccc; }

#stats-bar { position: absolute; bottom: 16px; left: 16px; background: rgba(17,17,17,0.85); padding: 6px 14px; border-radius: 4px; font-size: 11px; color: #555; z-index: 10; }

#controls { position: absolute; top: 16px; left: 16px; background: rgba(22,22,22,0.9); border: 1px solid #282828; padding: 10px 16px; border-radius: 6px; z-index: 10; font-size: 12px; }
#controls label { color: #666; font-size: 11px; }
#controls input[type=range] { width: 120px; margin: 0 6px; vertical-align: middle; accent-color: #666; }
#controls span { color: #999; font-family: monospace; font-size: 11px; }

/* Breadcrumb navigation */
#breadcrumb { position: absolute; top: 16px; left: 50%; transform: translateX(-50%); background: rgba(22,22,22,0.95);
    border: 1px solid #333; padding: 6px 16px; border-radius: 20px; z-index: 10; font-size: 13px; display: none;
    color: #888; white-space: nowrap; }
#breadcrumb .crumb { color: #666; cursor: pointer; transition: color 0.2s; }
#breadcrumb .crumb:hover { color: #ccc; }
#breadcrumb .crumb-current { color: #ddd; cursor: default; }
#breadcrumb .sep { color: #444; margin: 0 6px; }

/* Hint for double-click */
#hint { position: absolute; bottom: 16px; right: 420px; background: rgba(22,22,22,0.8); padding: 4px 12px; border-radius: 4px; font-size: 10px; color: #444; z-index: 10; }

/* Antourage feedback panel */
#antourage { position: fixed; bottom: 0; left: 0; right: 400px; background: #141418; border-top: 1px solid #282828;
  z-index: 20; transition: transform 0.3s ease; }
#antourage.hidden { transform: translateY(100%); }
#antourage-toggle { position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%); z-index: 21;
  background: #1c1c24; border: 1px solid #333; color: #888; padding: 6px 18px; border-radius: 20px;
  cursor: pointer; font-size: 12px; transition: all 0.2s; }
#antourage-toggle:hover { background: #252530; color: #bbb; }
#antourage-toggle .badge { background: #d90; color: #111; font-size: 10px; padding: 1px 6px; border-radius: 8px; margin-left: 6px; }

#ant-inner { padding: 16px 24px; max-height: 220px; overflow-y: auto; }
#ant-prompt { color: #bbb; font-size: 14px; line-height: 1.6; margin-bottom: 12px; }
#ant-options { display: flex; flex-wrap: wrap; gap: 8px; }
#ant-options button { background: #1e1e28; border: 1px solid #333; color: #aaa; padding: 6px 16px;
  border-radius: 16px; cursor: pointer; font-size: 12px; transition: all 0.15s; }
#ant-options button:hover { background: #282838; color: #ddd; border-color: #555; }
#ant-options button.skip { color: #555; border-color: #222; }

#ant-progress { display: flex; align-items: center; gap: 12px; padding: 8px 24px; border-top: 1px solid #1c1c1c; }
#ant-progress-bar { flex: 1; height: 3px; background: #222; border-radius: 2px; overflow: hidden; }
#ant-progress-fill { height: 100%; background: #5a5a8a; transition: width 0.3s; }
#ant-progress-text { color: #444; font-size: 10px; white-space: nowrap; }
#ant-milestone { color: #8a8a5a; font-size: 12px; padding: 8px 24px; display: none; }

/* Layer indicators in judgments */
.layer-badge { display: inline-block; font-size: 9px; padding: 1px 5px; border-radius: 6px; margin-left: 4px; }
.layer-badge.l0 { background: #2a3a2a; color: #6a8a6a; }
.layer-badge.l1 { background: #3a3a2a; color: #8a8a5a; }
.layer-badge.l2 { background: #3a2a3a; color: #8a5a8a; }
.confirmed-badge { display: inline-block; font-size: 9px; padding: 1px 5px; border-radius: 6px; margin-left: 4px; background: #2a3a2a; color: #5a9a5a; }
.rejected-badge { display: inline-block; font-size: 9px; padding: 1px 5px; border-radius: 6px; margin-left: 4px; background: #3a2a2a; color: #9a5a5a; }
</style>
</head>
<body>

<div id="graph-container">
  <div id="sphere-vignette"></div>
  <div id="controls">
    <label>порог связей</label>
    <input type="range" id="threshold-slider" min="10" max="95" value="THRESHOLD_INIT">
    <span id="threshold-val">THRESHOLD_DISPLAY</span>
  </div>
  <div id="breadcrumb"></div>
  <button id="self-btn" onclick="showSelf()">[self]</button>
  <div id="network"></div>
  <div id="stats-bar">STATS_TEXT</div>
  <div id="hint">клик — параметры &nbsp;|&nbsp; двойной клик — войти внутрь</div>
</div>

<div id="panel">
  <div id="panel-content">
    <h2 style="color:#555">Кликните на понятие</h2>
    <p style="color:#444;font-size:13px;line-height:1.6;margin-top:8px;">Нажмите на узел — параметры и суждения.<br>Двойной клик — войти внутрь понятия.<br>Внутри: клик на пустоту — выйти обратно.<br><br>Перетаскивайте узлы. Граф пружинный.</p>
  </div>
</div>

<!-- Antourage feedback panel -->
<button id="antourage-toggle" onclick="toggleAntourage()">Антураж <span class="badge" id="ant-badge">0</span></button>
<div id="antourage" class="hidden">
  <div id="ant-inner">
    <div id="ant-prompt">Загрузка...</div>
    <div id="ant-options"></div>
  </div>
  <div id="ant-milestone"></div>
  <div id="ant-progress">
    <div id="ant-progress-bar"><div id="ant-progress-fill" style="width:0%"></div></div>
    <div id="ant-progress-text">0% проверено</div>
  </div>
</div>

<script>
const DATA = GRAPH_DATA_JSON;
const allEdges = DATA.edges;

// --- Navigation state ---
let navStack = [];       // [{nodeId, visibleNodes, visibleEdges}]  — path into spheres
let focusedNode = null;
let isInside = false;

const maxMass = Math.max(...DATA.nodes.map(x => x.mass));
const maxComp = Math.max(...DATA.nodes.map(x => x.n_components));
const nodeMap = {};
DATA.nodes.forEach(n => { nodeMap[n.id] = n; });

const nodeBaseStyles = {};
DATA.nodes.forEach(n => {
    const size = 12 + 30 * (n.mass / maxMass);
    const b = 50 + 50 * (n.n_components / maxComp);
    const g = Math.round(b * 2.55);
    nodeBaseStyles[n.id] = { size, g, isVerb: n.is_verb };
});

// --- Node styling ---
function makeNodeItem(id, role) {
    // role: 'center' | 'child' | 'parent' | 'normal' | 'dim' | 'focus'
    const s = nodeBaseStyles[id] || { size: 15, g: 80, isVerb: false };
    let sz = s.size, fg, border, fontColor, strokeColor, bw = 1;

    if (role === 'center') {
        sz = s.size * 1.8;
        fg = '#ddd'; border = 'rgba(255,255,255,0.5)'; fontColor = '#111'; strokeColor = 'rgba(255,255,255,0.8)'; bw = 2;
    } else if (role === 'child') {
        fg = `rgb(${s.g},${s.g},${Math.min(255, s.g + 40)})`;
        border = `rgb(${Math.min(255, s.g+20)},${Math.min(255, s.g+20)},${Math.min(255, s.g+60)})`;
        fontColor = '#111'; strokeColor = 'rgba(200,200,255,0.6)';
    } else if (role === 'parent') {
        fg = `rgb(${Math.min(255, s.g+20)},${s.g},${s.g})`;
        border = `rgb(${Math.min(255, s.g+40)},${s.g},${s.g})`;
        fontColor = '#111'; strokeColor = 'rgba(255,200,200,0.5)';
    } else if (role === 'focus') {
        sz = s.size * 1.2;
        fg = '#fff'; border = '#fff'; fontColor = '#111'; strokeColor = 'rgba(255,255,255,0.8)'; bw = 2;
    } else if (role === 'dim') {
        fg = '#333'; border = '#222'; fontColor = '#333'; strokeColor = '#1a1a1a';
    } else {
        const g = s.g;
        fg = `rgb(${g},${g},${g})`;
        border = `rgb(${Math.min(255,g+30)},${Math.min(255,g+30)},${Math.min(255,g+30)})`;
        fontColor = '#111'; strokeColor = 'rgba(255,255,255,0.7)';
    }
    return {
        id, label: id, size: sz,
        color: { background: fg, border, highlight: { background: '#ddd', border: '#fff' } },
        font: { color: '#eee', size: role === 'center' ? 14 : 11, face: 'Segoe UI', strokeWidth: 0 },
        borderWidth: bw, shape: s.isVerb ? 'diamond' : 'dot',
    };
}

function buildEdgeItem(e, lit) {
    return {
        id: e.from + '>' + e.to, from: e.from, to: e.to,
        color: { color: lit ? 'rgba(180,180,255,0.4)' : 'rgba(255,255,255,0.07)', highlight: 'rgba(255,255,255,0.5)' },
        arrows: { to: { enabled: true, scaleFactor: 0.35, type: 'arrow' } },
        smooth: { type: 'continuous' },
        width: lit ? 1 + 2 * e.weight : 0.4 + 1.5 * e.weight,
    };
}

let currentThreshold = THRESHOLD_INIT / 100;

// --- Build initial global view ---
const nodes = new vis.DataSet(DATA.nodes.map(n => makeNodeItem(n.id, 'normal')));
const globalEdges = allEdges.filter(e => e.weight >= currentThreshold);
const edges = new vis.DataSet(globalEdges.map(e => buildEdgeItem(e, false)));

const container = document.getElementById('network');
const network = new vis.Network(container, { nodes, edges }, {
    physics: {
        enabled: true, solver: 'forceAtlas2Based',
        forceAtlas2Based: { gravitationalConstant: -50, centralGravity: 0.005, springLength: 160, springConstant: 0.02, damping: 0.85, avoidOverlap: 0.3 },
        stabilization: { enabled: true, iterations: 300 }, maxVelocity: 30, minVelocity: 0.3,
    },
    interaction: { hover: true, dragNodes: true, dragView: true, zoomView: true, tooltipDelay: 300 },
    edges: { selectionWidth: 0 }, nodes: { chosen: false },
});
// Stop physics after initial layout settles — dragging still works
network.once('stabilized', () => { network.setOptions({ physics: false }); });

// =====================================================================
//  GLOBAL VIEW: single click = focus + panel, double click = enter
// =====================================================================

function showGlobalView() {
    isInside = false;
    focusedNode = null;
    document.getElementById('graph-container').classList.remove('inside');
    document.getElementById('breadcrumb').style.display = 'none';
    document.getElementById('hint').textContent = 'клик — параметры  |  двойной клик — войти внутрь';

    nodes.clear();
    nodes.add(DATA.nodes.map(n => makeNodeItem(n.id, 'normal')));
    edges.clear();
    edges.add(allEdges.filter(e => e.weight >= currentThreshold).map(e => buildEdgeItem(e, false)));

    network.setOptions({ physics: { enabled: true, stabilization: { iterations: 200 } } });
    network.once('stabilized', () => {
        network.setOptions({ physics: false });
        network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });
    });
    network.stabilize(200);
}

function applyGlobalFocus(nodeId) {
    focusedNode = nodeId;
    const connected = allEdges.filter(e => e.weight >= currentThreshold && (e.from === nodeId || e.to === nodeId));
    const neighborIds = new Set([nodeId]);
    connected.forEach(e => { neighborIds.add(e.from); neighborIds.add(e.to); });

    nodes.update(DATA.nodes.map(n =>
        makeNodeItem(n.id, n.id === nodeId ? 'focus' : (neighborIds.has(n.id) ? 'normal' : 'dim'))
    ));
    edges.clear();
    const filtered = allEdges.filter(e => e.weight >= currentThreshold);
    edges.add(filtered.map(e => buildEdgeItem(e, e.from === nodeId || e.to === nodeId)));
}

function clearGlobalFocus() {
    focusedNode = null;
    nodes.update(DATA.nodes.map(n => makeNodeItem(n.id, 'normal')));
    edges.clear();
    edges.add(allEdges.filter(e => e.weight >= currentThreshold).map(e => buildEdgeItem(e, false)));
}

// =====================================================================
//  ENTER SPHERE: double click → fly in → local neighborhood graph
// =====================================================================

function enterSphere(nodeId) {
    const nodeData = nodeMap[nodeId];
    if (!nodeData) return;

    // Save current state for returning
    navStack.push(nodeId);
    isInside = true;
    focusedNode = null;

    // Visual: sphere mode
    document.getElementById('graph-container').classList.add('inside');
    document.getElementById('hint').textContent = 'клик на пустоту — выйти  |  двойной клик — войти глубже';
    updateBreadcrumb();

    // Find neighborhood
    const childEdges = allEdges.filter(e => e.from === nodeId && e.weight >= 0.2);
    const parentEdges = allEdges.filter(e => e.to === nodeId && e.weight >= 0.2);

    const childIds = new Set(childEdges.map(e => e.to));
    const parentIds = new Set(parentEdges.map(e => e.from));
    const allNeighborIds = new Set([nodeId, ...childIds, ...parentIds]);

    // Cross-edges between neighbors
    const crossEdges = allEdges.filter(e =>
        e.weight >= 0.2 && allNeighborIds.has(e.from) && allNeighborIds.has(e.to)
    );

    // Rebuild graph with only neighborhood
    nodes.clear();
    // Center node
    if (nodeBaseStyles[nodeId]) {
        nodes.add(makeNodeItem(nodeId, 'center'));
    }
    // Children (what this concept contains)
    childIds.forEach(id => {
        if (nodeBaseStyles[id] && id !== nodeId) nodes.add(makeNodeItem(id, 'child'));
    });
    // Parents (what contains this concept)
    parentIds.forEach(id => {
        if (nodeBaseStyles[id] && id !== nodeId && !childIds.has(id)) nodes.add(makeNodeItem(id, 'parent'));
    });

    edges.clear();
    crossEdges.forEach(e => {
        const isDirectConnection = (e.from === nodeId || e.to === nodeId);
        edges.add(buildEdgeItem(e, isDirectConnection));
    });

    // Fixed circular layout — no physics, instant
    network.setOptions({ physics: false });
    const allIds = nodes.getIds();
    const others = allIds.filter(id => id !== nodeId);
    // Center node at origin
    nodes.update({ id: nodeId, x: 0, y: 0, fixed: { x: true, y: true } });
    // Arrange others in a circle
    const radius = 250 + others.length * 15;
    others.forEach((id, i) => {
        const angle = (2 * Math.PI * i) / others.length - Math.PI / 2;
        nodes.update({ id, x: radius * Math.cos(angle), y: radius * Math.sin(angle) });
    });
    network.fit({ animation: { duration: 400, easingFunction: 'easeInOutQuad' } });

    // Show panel for this concept
    showNodePanel(nodeData);
}

function exitSphere() {
    if (navStack.length === 0) return;

    navStack.pop();

    if (navStack.length === 0) {
        // Back to global view
        showGlobalView();
        document.getElementById('panel-content').innerHTML = '<h2 style="color:#555">Кликните на понятие</h2>';
    } else {
        // Go back one level — re-enter the parent sphere
        const parentId = navStack.pop(); // pop so enterSphere can push it again
        enterSphere(parentId);
    }
}

function updateBreadcrumb() {
    const bc = document.getElementById('breadcrumb');
    if (navStack.length === 0) {
        bc.style.display = 'none';
        return;
    }
    bc.style.display = 'block';
    let h = '<span class="crumb" onclick="showGlobalView(); navStack=[];">граф</span>';
    navStack.forEach((id, i) => {
        h += '<span class="sep">›</span>';
        if (i === navStack.length - 1) {
            h += `<span class="crumb-current">${esc(id)}</span>`;
        } else {
            h += `<span class="crumb" onclick="navigateTo(${i})">${esc(id)}</span>`;
        }
    });
    bc.innerHTML = h;
}

function navigateTo(index) {
    // Navigate to a breadcrumb level
    const targetId = navStack[index];
    navStack = navStack.slice(0, index); // pop everything after
    enterSphere(targetId);
}

// =====================================================================
//  EVENT HANDLERS
// =====================================================================

let clickTimer = null;

network.on('click', params => {
    // Delay single click to distinguish from double click
    if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; return; }
    clickTimer = setTimeout(() => {
        clickTimer = null;
        if (params.nodes.length > 0) {
            const nodeId = params.nodes[0];
            const nodeData = nodeMap[nodeId];
            if (nodeData) {
                if (!isInside) applyGlobalFocus(nodeId);
                showNodePanel(nodeData);
            }
        } else {
            // Click on empty space
            if (isInside) {
                exitSphere();
            } else {
                clearGlobalFocus();
            }
        }
    }, 250);
});

network.on('doubleClick', params => {
    if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; }
    if (params.nodes.length > 0) {
        enterSphere(params.nodes[0]);
    }
});

// Threshold slider
const slider = document.getElementById('threshold-slider');
const valSpan = document.getElementById('threshold-val');
slider.addEventListener('input', () => {
    currentThreshold = slider.value / 100;
    valSpan.textContent = currentThreshold.toFixed(2);
    if (!isInside) {
        edges.clear();
        edges.add(allEdges.filter(e => e.weight >= currentThreshold).map(e =>
            buildEdgeItem(e, focusedNode ? (e.from === focusedNode || e.to === focusedNode) : false)
        ));
    }
});

// =====================================================================
//  PANEL
// =====================================================================

function showNodePanel(n) {
    const containsEdges = allEdges.filter(e => e.from === n.id && e.weight >= 0.2).sort((a,b) => b.weight - a.weight).slice(0, 15);
    const containedInEdges = allEdges.filter(e => e.to === n.id && e.weight >= 0.2).sort((a,b) => b.weight - a.weight).slice(0, 15);

    let h = `<h2>${esc(n.label)}</h2>`;
    h += `<div class="stat"><span class="stat-label">компонентов</span><span class="stat-value">${n.n_components}</span></div>`;
    h += `<div class="stat"><span class="stat-label">масса</span><span class="stat-value">${n.mass}</span></div>`;
    h += `<div class="stat"><span class="stat-label">полисемия</span><span class="stat-value">${n.entropy}</span></div>`;
    h += `<div class="stat"><span class="stat-label">чистота</span><span class="stat-value">${n.purity}</span></div>`;
    h += `<div class="stat"><span class="stat-label">тип</span><span class="stat-value">${n.is_verb ? 'глагол' : 'понятие'}</span></div>`;

    if (n.facets.length > 0) {
        h += `<h3>грани (${n.facets.length})</h3>`;
        n.facets.forEach((f, i) => { h += `<span class="facet">грань ${i}: ${(f.weight * 100).toFixed(0)}%</span>`; });
    }

    if (containsEdges.length > 0) {
        h += `<h3>содержит</h3>`;
        containsEdges.forEach(e => {
            h += `<div class="contains-item" onclick="enterSphere('${escAttr(e.to)}')"><span>${esc(e.to)}</span><span class="contains-score">${e.weight.toFixed(3)}</span></div>`;
        });
    }

    if (containedInEdges.length > 0) {
        h += `<h3>содержится в</h3>`;
        containedInEdges.forEach(e => {
            h += `<div class="contains-item" onclick="enterSphere('${escAttr(e.from)}')"><span>${esc(e.from)}</span><span class="contains-score">${e.weight.toFixed(3)}</span></div>`;
        });
    }

    h += `<h3>суждения (${n.judgments.length})</h3>`;
    n.judgments.forEach(j => {
        const isAnomaly = j.anomaly >= 0.85;
        const cls = isAnomaly ? 'anomaly' : (j.quality === 'NEGATIVE' ? 'neg' : (j.condition_id ? 'cond' : ''));
        const neg = j.quality === 'NEGATIVE' ? ' [НЕТ]' : '';
        const mod = j.modality !== 1.0 ? ` mod=${j.modality}` : '';
        const cond = j.condition_role ? ` [${j.condition_role}]` : '';
        const anom = isAnomaly ? `<span class="anomaly-badge">аномалия ${(j.anomaly * 100).toFixed(0)}%</span>` : '';
        const layerBadge = j.layer > 0 ? `<span class="layer-badge l${j.layer}">L${j.layer}</span>` : '';
        const confBadge = j.confirmation === 'confirmed' ? '<span class="confirmed-badge">подтверждено</span>'
            : j.confirmation === 'rejected' ? '<span class="rejected-badge">отклонено</span>' : '';
        h += `<div class="judgment ${cls}">`;
        h += `<div class="triple">${esc(j.subject)} —[${esc(j.verb)}]→ ${esc(j.object)}${neg}${mod}${cond}${anom}${layerBadge}${confBadge}</div>`;
        h += `<div class="source">"${esc(j.source_text)}"</div>`;
        h += `</div>`;
    });

    document.getElementById('panel-content').innerHTML = h;
}

function showSelf() {
    if (isInside) { navStack = []; showGlobalView(); }
    clearGlobalFocus();
    const s = DATA.self;
    if (!s) { document.getElementById('panel-content').innerHTML = '<h2>[self]</h2><p style="color:#555">Пусто.</p>'; return; }
    let h = `<h2>[self]</h2>`;
    h += `<div class="stat"><span class="stat-label">характеристик</span><span class="stat-value">${s.n_components}</span></div>`;
    h += `<div class="stat"><span class="stat-label">масса</span><span class="stat-value">${s.mass}</span></div>`;
    h += `<div class="stat"><span class="stat-label">энтропия</span><span class="stat-value">${s.entropy}</span></div>`;
    h += `<h3>суждения о себе</h3>`;
    s.judgments.forEach(j => {
        h += `<div class="judgment"><div class="triple">я —[${esc(j.verb)}]→ ${esc(j.object)}</div><div class="source">"${esc(j.source_text)}"</div></div>`;
    });
    document.getElementById('panel-content').innerHTML = h;
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function escAttr(s) { return esc(s).replace(/'/g, '&#39;').replace(/"/g, '&quot;'); }

// ============================================================
// Antourage Feedback System
// ============================================================

const feedbackQuestions = DATA.feedback || [];
let fbIndex = 0;
let fbAnswered = 0;
let fbTotal = feedbackQuestions.length;
let fbLog = []; // collected feedback for export

function toggleAntourage() {
    const el = document.getElementById('antourage');
    el.classList.toggle('hidden');
    if (!el.classList.contains('hidden') && fbIndex < fbTotal) {
        showFeedbackQuestion(fbIndex);
    }
}

function showFeedbackQuestion(idx) {
    if (idx >= fbTotal) {
        document.getElementById('ant-prompt').innerHTML =
            '<span style="color:#5a8a5a">Все вопросы рассмотрены. Спасибо!</span>';
        document.getElementById('ant-options').innerHTML = '';
        showMilestone('Карта стала точнее. Ты помог мне лучше тебя понять.');
        return;
    }
    const q = feedbackQuestions[idx];
    document.getElementById('ant-prompt').textContent = q.prompt;

    let btns = '';
    q.options.forEach((opt, i) => {
        const cls = opt.toLowerCase().includes('пропустить') || opt.toLowerCase().includes('потом')
            ? 'skip' : '';
        btns += `<button class="${cls}" onclick="answerFeedback(${idx},${i})">${esc(opt)}</button>`;
    });
    document.getElementById('ant-options').innerHTML = btns;
    updateProgress();

    // Highlight related concepts on the graph
    if (q.concepts && q.concepts.length > 0) {
        const first = q.concepts[0];
        if (!isInside && nodeMap[first]) {
            applyGlobalFocus(first);
            const n = nodeMap[first];
            if (n) showNodePanel(n);
        }
    }
}

function answerFeedback(qIdx, optIdx) {
    const q = feedbackQuestions[qIdx];
    const answer = q.options[optIdx] || 'skip';

    // Log the answer
    fbLog.push({
        type: q.type,
        prompt: q.prompt,
        answer: answer,
        concepts: q.concepts,
        timestamp: Date.now() / 1000,
    });

    const isSkip = answer.toLowerCase().includes('пропустить') || answer.toLowerCase().includes('потом');
    if (!isSkip) {
        fbAnswered++;
        // Visual feedback on related judgments in panel
        if (answer.toLowerCase().includes('да') || answer.toLowerCase().includes('верно') ||
            answer.toLowerCase().includes('факт') || answer.toLowerCase().includes('важно') ||
            answer.toLowerCase().includes('по-прежнему')) {
            showMilestone('Записано. Твоя карта стала точнее.');
        } else if (answer.toLowerCase().includes('нет') || answer.toLowerCase().includes('убери') ||
                   answer.toLowerCase().includes('всерьёз')) {
            showMilestone('Понял, убрал. Спасибо за уточнение.');
        } else if (answer.toLowerCase().includes('контекст') || answer.toLowerCase().includes('зависит') ||
                   answer.toLowerCase().includes('частично')) {
            showMilestone('Интересно. Отметил как контекстуальное.');
        }
    }

    fbIndex++;
    updateProgress();

    // Small delay before next question for visual feedback
    setTimeout(() => showFeedbackQuestion(fbIndex), 600);
}

function updateProgress() {
    const totalJ = DATA.nodes.reduce((s, n) => s + n.judgments.length, 0);
    const reviewedJ = DATA.nodes.reduce((s, n) =>
        s + n.judgments.filter(j => j.confirmation !== 'unreviewed').length, 0);
    const pct = totalJ > 0 ? Math.round((reviewedJ + fbAnswered) / totalJ * 100) : 0;

    document.getElementById('ant-progress-fill').style.width = Math.min(pct, 100) + '%';
    document.getElementById('ant-progress-text').textContent = pct + '% проверено';
    document.getElementById('ant-badge').textContent = Math.max(0, fbTotal - fbIndex);
}

function showMilestone(text) {
    const el = document.getElementById('ant-milestone');
    el.textContent = text;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 3000);
}

function exportFeedback() {
    const blob = new Blob([JSON.stringify(fbLog, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'feedback_' + new Date().toISOString().slice(0,10) + '.json';
    a.click();
}

// Init badge count
document.getElementById('ant-badge').textContent = fbTotal;
if (fbTotal === 0) {
    document.getElementById('antourage-toggle').style.display = 'none';
}
</script>
</body>
</html>"""


def generate_html(map_data: dict, n_messages: int, n_judgments: int,
                  threshold: float = 0.3, output_path: str = "semantic_map.html",
                  title_suffix: str = ""):
    """Generate interactive HTML map."""
    stats_text = f"{title_suffix}{n_messages} сообщений → {n_judgments} суждений → {len(map_data['nodes'])} понятий"
    threshold_init = int(threshold * 100)
    threshold_display = f"{threshold:.2f}"

    html_content = HTML_TEMPLATE
    # Escape </ sequences to prevent </script> injection in JSON inside <script> block
    graph_json = json.dumps(map_data, ensure_ascii=False).replace("</", "<\\/")
    html_content = html_content.replace("GRAPH_DATA_JSON", graph_json)
    html_content = html_content.replace("STATS_TEXT", stats_text)
    html_content = html_content.replace("THRESHOLD_INIT", str(threshold_init))
    html_content = html_content.replace("THRESHOLD_DISPLAY", threshold_display)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"  → {output_path} ({len(map_data['nodes'])} nodes, {len(map_data['edges'])} edges)")


def _build_space_and_map(nlp, texts: list[str], seed_vectors: dict,
                         dim: int, min_comp: int, label: str,
                         thesaurus_loader: ThesaurusLoader = None) -> tuple:
    """Build SemanticSpace + map data for a set of texts. Returns (space, map_data, n_judgments)."""
    judgments = extract_judgments_recursive(nlp, texts)
    print(f"  {label}: {len(judgments)} judgments from {len(texts)} messages")

    if not judgments:
        return None, {"nodes": [], "edges": [], "self": None}, 0

    # Collect all personal terms
    personal_terms = set()
    for j in judgments:
        personal_terms.update([j.subject, j.verb, j.object])

    space = SemanticSpace(dim=dim, seed_vectors=seed_vectors, min_components_for_query=min_comp)

    # Thesaurus layer first (base, low modality)
    if thesaurus_loader:
        th_judgments = thesaurus_loader.load_for_terms(personal_terms)
        for j in th_judgments:
            space.materialize_judgment(j)
        if th_judgments:
            print(f"  {label}: +{len(th_judgments)} thesaurus judgments")

    # Personal judgments (higher modality, dominate)
    for j in judgments:
        space.materialize_judgment(j)

    space.recursive_deepen(iterations=3, alpha=0.7)
    map_data = build_map_data(space, min_components=min_comp, edge_threshold=0.3, top_n=50)
    return space, map_data, len(judgments)


def main():
    if len(sys.argv) < 2:
        print("Usage: python -X utf8 interactive_map.py <path_to_result.json> [min_comp]")
        sys.exit(1)

    path = sys.argv[1]
    min_comp = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    print("=" * 60)
    print("FVSC Interactive Semantic Map — Per-Speaker + Combined")
    print("=" * 60)

    # Load ALL messages with sender info
    print(f"\nLoading messages from {path}...")
    from live_test import read_telegram_messages_by_sender
    messages_with_sender = read_telegram_messages_by_sender(path, max_msgs=0)
    print(f"  Loaded {len(messages_with_sender)} text blocks (all messages, no limit)")

    # Split by sender
    senders = {}
    for sender, text in messages_with_sender:
        senders.setdefault(sender, []).append(text)

    all_texts = [text for _, text in messages_with_sender]

    print(f"  Senders:")
    for s, texts in sorted(senders.items(), key=lambda x: -len(x[1])):
        print(f"    {s}: {len(texts)} text blocks")

    # Load spaCy
    print("\nLoading spaCy...")
    t0 = time.time()
    nlp = spacy.load("ru_core_news_md")
    print(f"  Loaded in {time.time()-t0:.1f}s")

    # Collect all terms across all texts for shared seed vectors
    print("\nExtracting judgments for all speakers...")
    t0 = time.time()
    all_judgments = extract_judgments_recursive(nlp, all_texts)
    print(f"  Total: {len(all_judgments)} judgments in {time.time()-t0:.1f}s")

    all_terms = set()
    for j in all_judgments:
        all_terms.update([j.subject, j.verb, j.object])

    dim = 100
    print(f"\nBuilding shared seed vectors ({len(all_terms)} terms)...")
    seed_vectors = build_seed_vectors(nlp, all_terms, dim)
    print(f"  Terms with vectors: {len(seed_vectors)}/{len(all_terms)}")

    # Load thesaurus (if available)
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    thesaurus_path = os.path.join(data_dir, "conceptnet_ru.json")
    th_loader = None
    if os.path.exists(thesaurus_path):
        print(f"\nLoading thesaurus layer...")
        th_loader = ThesaurusLoader(conceptnet_cache=thesaurus_path, ruwordnet_dir=data_dir)
    else:
        print(f"\n  [thesaurus] No cache — skipping (run build_conceptnet_cache.py)")

    # Build per-sender maps
    print(f"\nBuilding per-speaker maps...")
    sender_names = sorted(senders.keys())

    for sender in sender_names:
        texts = senders[sender]
        print(f"\n  --- {sender} ---")
        t0 = time.time()
        _, map_data, n_j = _build_space_and_map(
            nlp, texts, seed_vectors, dim, min_comp, sender, th_loader)
        safe_name = sender.replace(" ", "_").lower()
        generate_html(map_data, len(texts), n_j,
                      threshold=0.5,
                      output_path=f"semantic_map_{safe_name}.html",
                      title_suffix=f"[{sender}] ")
        print(f"  Done in {time.time()-t0:.1f}s")

    # Build combined map
    print(f"\n  --- COMBINED ---")
    t0 = time.time()
    _, map_data_all, _ = _build_space_and_map(
        nlp, all_texts, seed_vectors, dim, min_comp, "combined", th_loader)
    generate_html(map_data_all, len(all_texts), len(all_judgments),
                  threshold=0.5,
                  output_path="semantic_map_combined.html",
                  title_suffix="[combined] ")
    print(f"  Done in {time.time()-t0:.1f}s")

    print("\n" + "=" * 60)
    print(f"Generated {len(sender_names) + 1} maps:")
    for sender in sender_names:
        safe_name = sender.replace(" ", "_").lower()
        print(f"  semantic_map_{safe_name}.html  — карта {sender}")
    print(f"  semantic_map_combined.html  — общая карта диалога")
    print("=" * 60)


if __name__ == "__main__":
    main()
