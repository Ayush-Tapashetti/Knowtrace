import type { Hypothesis } from "../../api/types";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { pct } from "../../lib/format";

/** What we currently think is wrong, most likely first. Numbers are printed beside every bar. */
export function HypothesisBars({ hypotheses }: { hypotheses: Hypothesis[] }) {
  if (hypotheses.length === 0) return null;
  const sorted = [...hypotheses]
    .sort((a, b) => b.probability - a.probability)
    .slice(0, 4);
  return (
    <section
      aria-labelledby="hyp-h"
      className="rounded-panel border border-ink/20 bg-surface p-5"
    >
      <h2 id="hyp-h" className="text-lg">
        What we think is going on
      </h2>
      <ul className="mt-3 space-y-3">
        {sorted.map((h) => (
          <li key={h.hypothesis}>
            <div className="flex justify-between gap-3 text-sm">
              <span>{h.name}</span>
              <span className="font-medium">{pct(h.probability)}</span>
            </div>
            <ProgressBar
              value={h.probability}
              label={`${h.name} likelihood`}
              tone="gap"
              className="mt-1"
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
