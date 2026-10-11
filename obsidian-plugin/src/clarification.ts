/** Translate textarea UTF-16 offsets (including normalized newlines) to source code points. */
export function sourceRangeForSelection(raw: string, start: number, end: number): [number, number] {
  const points = Array.from(raw);
  const boundaries = new Map<number, number>([[0, 0]]);
  let displayOffset = 0;
  for (let i = 0; i < points.length; i++) {
    const char = points[i];
    if (char === "\r" && points[i + 1] === "\n") i++;
    displayOffset += char === "\r" ? 1 : char.length;
    boundaries.set(displayOffset, i + 1);
  }
  const from = boundaries.get(start);
  const to = boundaries.get(end);
  if (from === undefined || to === undefined || from >= to) throw new Error("Выдели непустой фрагмент записи.");
  return [from, to];
}

export interface Clarification {
  clarification_id: string;
  source_id: string;
  source_revision: string;
  question: string;
  fragment: string;
  status: "pending" | "ready" | "excluded" | "unresolved" | "deferred";
  basis: string;
  usable_as_owner_position: boolean;
  prompt: string;
  answer: { sequence: number; action: string; note: string } | null;
}
