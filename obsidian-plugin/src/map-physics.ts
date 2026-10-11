/** Bounded force layout. Coordinates express layout, never semantic distance. */
export interface Particle { term: string; x: number; y: number; vx: number; vy: number; pinned?: boolean }
export interface Spring { source: string; target: string }
export class MapPhysics {
  nodes: Particle[];
  private springs: [Particle, Particle][];
  energy = 1;
  constructor(terms: string[], links: Spring[]) {
    this.nodes = terms.map((term, i) => {
      const angle = i * 2.399963229728653, radius = 60 * Math.sqrt(i);
      return { term, x: 450 + radius * Math.cos(angle), y: 300 + radius * Math.sin(angle), vx: 0, vy: 0 };
    });
    const byTerm = new Map(this.nodes.map(n => [n.term, n])), seen = new Set<string>();
    this.springs = [];
    for (const link of links) {
      const a = byTerm.get(link.source), b = byTerm.get(link.target);
      const key = JSON.stringify([link.source, link.target].sort());
      if (a && b && a !== b && !seen.has(key)) { seen.add(key); this.springs.push([a, b]); }
    }
  }
  reheat(): void { this.energy = 1; }
  tick(): boolean {
    if (this.energy < 0.008) return false;
    const alpha = this.energy;
    for (let i = 0; i < this.nodes.length; i++) {
      const a = this.nodes[i];
      for (let j = i + 1; j < this.nodes.length; j++) {
        const b = this.nodes[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        if (Math.abs(dx) + Math.abs(dy) < 0.001) { dx = 0.1; dy = 0.1; }
        const distance = Math.max(1, Math.hypot(dx, dy));
        const force = Math.min(8, 1800 / (distance * distance) + Math.max(0, 95 - distance) * 0.06) * alpha;
        const fx = dx / distance * force, fy = dy / distance * force;
        a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
      }
      a.vx += (450 - a.x) * 0.002 * alpha; a.vy += (300 - a.y) * 0.002 * alpha;
    }
    for (const [a, b] of this.springs) {
      const dx = b.x - a.x, dy = b.y - a.y, length = Math.max(1, Math.hypot(dx, dy));
      const force = (length - 150) * 0.018 * alpha;
      const fx = dx / length * force, fy = dy / length * force;
      a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
    }
    for (const node of this.nodes) {
      if (node.pinned) { node.vx = 0; node.vy = 0; continue; }
      node.vx *= 0.72; node.vy *= 0.72;
      node.x += Math.max(-15, Math.min(15, node.vx)); node.y += Math.max(-15, Math.min(15, node.vy));
    }
    this.energy *= 0.982;
    return true;
  }
}
