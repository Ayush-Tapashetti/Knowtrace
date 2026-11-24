import dagre from "@dagrejs/dagre";

import type { GraphEdge } from "../../api/types";

export const NODE_W = 140;
export const NODE_H = 56;

/** Top-to-bottom layered layout: prerequisites sit above the concepts that depend on them. */
export function layoutGraph(
  ids: string[],
  edges: GraphEdge[],
): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "TB", nodesep: 14, ranksep: 44 });
  g.setDefaultEdgeLabel(() => ({}));
  const known = new Set(ids);
  for (const id of ids) g.setNode(id, { width: NODE_W, height: NODE_H });
  for (const e of edges)
    if (known.has(e.prerequisite) && known.has(e.dependent))
      g.setEdge(e.prerequisite, e.dependent);
  dagre.layout(g);
  const out = new Map<string, { x: number; y: number }>();
  for (const id of ids) {
    const n = g.node(id) as { x: number; y: number };
    out.set(id, { x: n.x - NODE_W / 2, y: n.y - NODE_H / 2 });
  }
  return out;
}
