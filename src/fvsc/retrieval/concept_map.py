"""Bounded navigation over materialized concepts and their evidence links.

Edges expose existing extractor assertions, not inferred truth or density distance.
"""
from collections import defaultdict
import re


class ConceptMap:
    def __init__(self, snapshot, ledger):
        self.snapshot_id = snapshot.snapshot_id
        self.nodes = {c.term: {"term": c.term, "evidence_count": len(c.evidence_ids)} for c in snapshot.concepts}
        self.aliases = {}
        for term in sorted(self.nodes):
            self.aliases.setdefault(term.casefold(), term)
        self.sources = defaultdict(set)
        self.neighbors = defaultdict(set)
        self.edges = {}
        for event in ledger.active_events:
            for value in (event.subject, event.object, event.relation):
                if value in self.nodes:
                    self.sources[value].add(event.source_id)
            a, b = event.subject, event.object
            if a not in self.nodes or b not in self.nodes or a == b:
                continue
            key = (a, b, event.relation, event.polarity, event.modality)
            edge = self.edges.setdefault(key, {"source": a, "target": b, "relation": event.relation,
                                               "polarity": event.polarity, "modality": event.modality,
                                               "count": 0, "source_ids": set()})
            edge["count"] += 1
            edge["source_ids"].add(event.source_id)
            self.neighbors[a].add(key)
            self.neighbors[b].add(key)
        # Longest exact phrase first. No fuzzy links to nonexistent concepts.
        terms = sorted(self.aliases, key=lambda value: (-len(value), value))
        self.pattern = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(t) for t in terms) + r")(?!\w)", re.I) if terms else None

    def mentions(self, text):
        segments = []
        offset = 0
        for match in self.pattern.finditer(text) if self.pattern else ():
            term = self.aliases.get(match.group().casefold())
            if term is None:
                continue
            if offset < match.start():
                segments.append({"text": text[offset:match.start()], "term": None})
            segments.append({"text": match.group(), "term": term})
            offset = match.end()
        if offset < len(text):
            segments.append({"text": text[offset:], "term": None})
        return segments

    def view(self, focus=None, limit=17):
        if not self.nodes:
            return {"snapshot_id": self.snapshot_id, "focus": None, "nodes": [], "edges": [], "total_neighbors": 0}
        if focus is None:
            # Predicate-only concepts can have many citations but no subject/object
            # neighbors. Start at a connected node when one exists.
            focus = min(self.nodes, key=lambda term: (-len(self.neighbors[term]), -self.nodes[term]["evidence_count"], term))
        if focus not in self.nodes:
            raise KeyError("concept is absent from current map")
        adjacent = sorted(self.neighbors[focus], key=lambda key: (-self.edges[key]["count"], key))
        all_neighbors = {v for key in adjacent for v in key[:2]} - {focus}
        selected = [focus]
        for key in adjacent:
            other = key[1] if key[0] == focus else key[0]
            if other not in selected and len(selected) < limit:
                selected.append(other)
        allowed = set(selected)
        return {
            "snapshot_id": self.snapshot_id, "focus": focus, "total_neighbors": len(all_neighbors),
            "nodes": [{**self.nodes[t], "source_count": len(self.sources[t]),
                       "source_ids": sorted(self.sources[t])[:30]} for t in selected],
            "edges": [{**self.edges[k], "source_ids": sorted(self.edges[k]["source_ids"])[:30]}
                      for k in adjacent if set(k[:2]) <= allowed][:100],
        }

    def composition(self, focus, children):
        allowed = set(children)
        keys = {key for term in children for key in self.neighbors.get(term, ())}
        edges = [self.edges[k] for k in sorted(keys) if set(k[:2]) <= allowed]
        return {
            "nodes": [{**self.nodes.get(t, {"term": t, "evidence_count": 0}),
                       "source_count": len(self.sources.get(t, ())),
                       "source_ids": sorted(self.sources.get(t, ()))[:30]} for t in [focus, *children]],
            "edges": [{**e, "source_ids": sorted(e["source_ids"])[:30]} for e in edges[:500]],
            "total_edges": len(edges),
        }
