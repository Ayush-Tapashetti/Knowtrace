import "@xyflow/react/dist/style.css";

import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { Check } from "lucide-react";
import { useMemo } from "react";

import type { Graph, MasteryPoint } from "../../api/types";
import { cn } from "../../lib/cn";
import { pct } from "../../lib/format";
import { bandOf } from "./heat";
import { NODE_H, NODE_W, layoutGraph } from "./layout";

interface ConceptData extends Record<string, unknown> {
  name: string;
  point: MasteryPoint | undefined;
  selected: boolean;
  related: boolean;
}

function ConceptNode({ data }: NodeProps<Node<ConceptData>>) {
  const band = bandOf(data.point);
  return (
    <div
      style={{ width: NODE_W, height: NODE_H }}
      className={cn(
        "flex flex-col justify-center rounded-panel border-2 px-2 text-center text-sm leading-tight",
        band.className,
        data.selected && "outline-3 outline-offset-2 outline-ink",
        data.related && !data.selected && "ring-3 ring-gap",
      )}
    >
      <Handle type="target" position={Position.Top} className="opacity-0!" />
      <span className="line-clamp-2 font-medium">{data.name}</span>
      <span className="flex items-center justify-center gap-1 text-xs">
        {band.key === "mastered" ? (
          <Check aria-hidden className="size-3" />
        ) : null}
        {data.point && data.point.n_obs > 0 ? pct(data.point.p_mastery) : "–"}
      </span>
      <Handle type="source" position={Position.Bottom} className="opacity-0!" />
    </div>
  );
}

const NODE_TYPES = { concept: ConceptNode };

/** Prerequisite graph coloured by mastery. Selecting a concept lights up its prerequisite chain in marigold. */
export function KnowledgeGraph({
  graph,
  mastery,
  selectedId,
  related,
  onSelect,
}: {
  graph: Graph;
  mastery: Map<string, MasteryPoint>;
  selectedId: string | null;
  related: ReadonlySet<string>;
  onSelect: (id: string) => void;
}) {
  const positions = useMemo(
    () =>
      layoutGraph(
        graph.nodes.map((n) => n.id),
        graph.edges,
      ),
    [graph],
  );
  const nodes: Node<ConceptData>[] = graph.nodes.map((n) => ({
    id: n.id,
    type: "concept",
    position: positions.get(n.id) ?? { x: 0, y: 0 },
    data: {
      name: n.name,
      point: mastery.get(n.id),
      selected: n.id === selectedId,
      related: related.has(n.id),
    },
    draggable: false,
    connectable: false,
  }));
  const edges: Edge[] = graph.edges.map((e) => {
    const hot =
      related.has(e.prerequisite) &&
      (related.has(e.dependent) || e.dependent === selectedId);
    return {
      id: `${e.prerequisite}->${e.dependent}`,
      source: e.prerequisite,
      target: e.dependent,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: {
        stroke: hot ? "var(--color-gap)" : "var(--color-ink-soft)",
        strokeWidth: hot ? 3 : 1.25,
      },
    };
  });
  return (
    <div
      className="h-[36rem] rounded-panel border border-ink/20 bg-surface"
      role="group"
      aria-label="Prerequisite graph. A table view with the same information is available."
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        fitView
        minZoom={0.2}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        onNodeClick={(_, n) => {
          onSelect(n.id);
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
