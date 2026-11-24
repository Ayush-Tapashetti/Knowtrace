import { Check } from "lucide-react";

import type { EvalRun } from "../../api/types";
import { Card } from "../../components/ui/Card";
import { buildTable, formatMetric, reliabilityBins } from "./evalModel";
import { ReliabilityChart } from "./ReliabilityChart";

/** Our method against the baselines on simulated students whose true gaps are known. */
export function EvalPanel({ run }: { run: EvalRun }) {
  const rows = buildTable(run);
  const bins = reliabilityBins(run.metrics);
  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-lg">Accuracy against known answers</h2>
        <p className="mt-1 max-w-prose text-sm text-ink-soft">
          {String(run.n_students)} simulated students, each with a hidden gap we
          know. Higher is better except probes and Brier, where lower is better.
          The best value in each column has a tick.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Evaluation metrics by method</caption>
            <thead className="border-b border-line">
              <tr>
                <th scope="col" className="p-2">
                  Method
                </th>
                {rows[0]?.cells.map((c) => (
                  <th
                    key={c.metric.key}
                    scope="col"
                    className="p-2"
                    title={c.metric.hint}
                  >
                    {c.metric.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.method}
                  className="border-b border-line last:border-0"
                >
                  <th scope="row" className="p-2 font-medium">
                    {r.label}
                  </th>
                  {r.cells.map((c) => (
                    <td
                      key={c.metric.key}
                      className={c.best ? "p-2 font-semibold" : "p-2"}
                    >
                      {c.value === null ? (
                        "–"
                      ) : (
                        <span className="inline-flex items-center gap-1">
                          {formatMetric(c.metric, c.value)}
                          {c.best ? (
                            <Check
                              aria-label="best"
                              className="size-4 text-known"
                            />
                          ) : null}
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-ink-soft">
          Run {run.run_id} · seed {String(run.seed)} ·{" "}
          {new Date(run.created_at).toLocaleDateString()}
        </p>
      </Card>
      {bins.length > 0 ? (
        <Card>
          <h2 className="text-lg">Is the forecast calibrated?</h2>
          <ReliabilityChart bins={bins} />
        </Card>
      ) : null}
    </div>
  );
}
