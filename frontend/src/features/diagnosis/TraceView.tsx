import type { TraceNode } from "../../api/types";
import { Badge } from "../../components/ui/Badge";
import { pct } from "../../lib/format";

/**
 * The evidence trail: from the concept the question was about down the prerequisite chain to the root
 * gap. The marigold thread links the nodes; the root is marked in text as well as colour.
 */
export function TraceView({
  trace,
  rootId,
}: {
  trace: TraceNode[];
  rootId: string | null;
}) {
  if (trace.length === 0) return null;
  const last = trace.length - 1;
  return (
    <section
      aria-labelledby="trace-h"
      className="rounded-panel border border-ink/20 bg-surface p-5"
    >
      <h2 id="trace-h" className="text-lg">
        How we traced it
      </h2>
      <p className="mt-1 text-sm text-ink-soft">
        Each step is a prerequisite of the one above it. The root is the
        earliest idea that looks shaky.
      </p>
      <ol className="mt-4">
        {trace.map((n, i) => {
          const isRoot = n.concept_id === rootId;
          return (
            <li key={n.concept_id} className="relative pl-8">
              {i < last ? (
                <span
                  aria-hidden
                  className="absolute left-[0.6875rem] top-5 h-full w-[3px] bg-gap"
                />
              ) : null}
              <span
                aria-hidden
                className={`absolute left-0 top-1.5 size-6 rounded-full border-2 ${
                  isRoot ? "border-gap-ink bg-gap" : "border-gap bg-surface"
                }`}
              />
              <div className="pb-5">
                <p className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{n.name}</span>
                  {isRoot ? <Badge tone="gap">Root gap</Badge> : null}
                </p>
                <p className="text-sm text-ink-soft">
                  Mastery {pct(n.mastery)} · chance this is the root{" "}
                  {pct(n.posterior_mass)}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
