import { useMemo, useState } from "react";

import { useGraph, useMastery } from "../api/hooks";
import type { MasteryPoint } from "../api/types";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { ConceptDetail } from "../features/graph/ConceptDetail";
import { BANDS } from "../features/graph/heat";
import { KnowledgeGraph } from "../features/graph/KnowledgeGraph";
import { MasteryTable } from "../features/graph/MasteryTable";
import { useSession } from "../features/session/useSession";

export function GraphPage() {
  const session = useSession();
  return (
    <>
      <PageHeader
        title="Knowledge map"
        description="Every concept, how they depend on each other, and what you know so far."
      />
      {session.status === "loading" ? (
        <LoadingState label="Setting up your session" />
      ) : null}
      {session.status === "error" ? (
        <ErrorState error={session.error} onRetry={session.restart} />
      ) : null}
      {session.studentId ? <MapView studentId={session.studentId} /> : null}
    </>
  );
}

function MapView({ studentId }: { studentId: string }) {
  const graph = useGraph();
  const mastery = useMastery(studentId);
  const [view, setView] = useState<"graph" | "table">("graph");
  const [selected, setSelected] = useState<string | null>(null);

  const points = useMemo(
    () =>
      new Map<string, MasteryPoint>(
        (mastery.data?.concepts ?? []).map((p) => [p.concept_id, p]),
      ),
    [mastery.data],
  );
  const names = useMemo(
    () => new Map((graph.data?.nodes ?? []).map((n) => [n.id, n])),
    [graph.data],
  );
  const related = useMemo(() => {
    const out = new Set<string>();
    if (!graph.data || !selected) return out;
    const parents = new Map<string, string[]>();
    for (const e of graph.data.edges)
      parents.set(e.dependent, [
        ...(parents.get(e.dependent) ?? []),
        e.prerequisite,
      ]);
    const stack = [...(parents.get(selected) ?? [])];
    while (stack.length > 0) {
      const id = stack.pop();
      if (id === undefined || out.has(id)) continue;
      out.add(id);
      stack.push(...(parents.get(id) ?? []));
    }
    return out;
  }, [graph.data, selected]);

  if (graph.isPending || mastery.isPending)
    return <LoadingState label="Loading the knowledge map" lines={5} />;
  if (graph.isError)
    return (
      <ErrorState
        error={graph.error}
        onRetry={() => void graph.refetch()}
        retrying={graph.isFetching}
      />
    );
  if (mastery.isError)
    return (
      <ErrorState
        error={mastery.error}
        onRetry={() => void mastery.refetch()}
        retrying={mastery.isFetching}
      />
    );
  if (graph.data.nodes.length === 0)
    return (
      <EmptyState
        title="The curriculum is empty"
        description="Seed the server with concepts, then reload."
      />
    );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="View" className="flex gap-2">
          {(["graph", "table"] as const).map((v) => (
            <Button
              key={v}
              variant={view === v ? "primary" : "secondary"}
              aria-pressed={view === v}
              onClick={() => {
                setView(v);
              }}
            >
              {v === "graph" ? "Graph" : "Table"}
            </Button>
          ))}
        </div>
        <ul aria-label="Legend" className="flex flex-wrap gap-2 text-xs">
          {BANDS.map((b) => (
            <li
              key={b.key}
              className={`rounded-full border-2 px-2 py-0.5 ${b.className}`}
            >
              {b.label}
            </li>
          ))}
        </ul>
      </div>
      {view === "graph" ? (
        <KnowledgeGraph
          graph={graph.data}
          mastery={points}
          selectedId={selected}
          related={related}
          onSelect={setSelected}
        />
      ) : (
        <MasteryTable
          concepts={graph.data.nodes}
          mastery={points}
          selectedId={selected}
          onSelect={setSelected}
        />
      )}
      {selected ? (
        <ConceptDetail
          conceptId={selected}
          studentId={studentId}
          names={names}
          point={points.get(selected)}
          onSelect={setSelected}
        />
      ) : (
        <p className="text-ink-soft">
          Pick a concept to see what it needs and where you are headed. In the
          graph, scroll or use + and − to zoom; the table lists everything at
          once.
        </p>
      )}
    </div>
  );
}
