import type { EvalMetric, EvalRun } from "../../api/types";

export const METHOD_LABEL: Record<string, string> = {
  graph_bayes: "KnowTrace (graph + Bayes)",
  baseline_parent: "Blame the direct parent",
  baseline_flat_bkt: "Flat BKT, no graph",
};

export interface MetricSpec {
  key: string;
  label: string;
  hint: string;
  higherIsBetter: boolean;
  percent: boolean;
}

export const METRICS: MetricSpec[] = [
  {
    key: "top1",
    label: "Root cause, top 1",
    hint: "How often the first guess is the true gap",
    higherIsBetter: true,
    percent: true,
  },
  {
    key: "top3",
    label: "Root cause, top 3",
    hint: "True gap is among the first three guesses",
    higherIsBetter: true,
    percent: true,
  },
  {
    key: "probes_mean",
    label: "Probes needed",
    hint: "Average questions to reach a diagnosis",
    higherIsBetter: false,
    percent: false,
  },
  {
    key: "auc",
    label: "Next-answer AUC",
    hint: "How well it predicts the next answer",
    higherIsBetter: true,
    percent: false,
  },
  {
    key: "brier",
    label: "Brier score",
    hint: "Calibration error of those predictions",
    higherIsBetter: false,
    percent: false,
  },
];

export interface MethodRow {
  method: string;
  label: string;
  cells: { metric: MetricSpec; value: number | null; best: boolean }[];
}

/** One row per method, one cell per metric, with the best value in each column flagged. */
export function buildTable(run: Pick<EvalRun, "metrics">): MethodRow[] {
  const methods = [...new Set(run.metrics.map((m) => m.method))].sort((a, b) =>
    a === "graph_bayes" ? -1 : b === "graph_bayes" ? 1 : a.localeCompare(b),
  );
  const get = (method: string, metric: string): number | null => {
    const v =
      run.metrics.find((m) => m.method === method && m.metric === metric)
        ?.value ?? null;
    // Baselines do not probe: a stored 0 means "not applicable", never "zero probes".
    return metric === "probes_mean" && method !== "graph_bayes" && v === 0
      ? null
      : v;
  };
  const best = new Map<string, number>();
  for (const spec of METRICS) {
    const vals = methods
      .map((m) => get(m, spec.key))
      .filter((v): v is number => v !== null);
    if (vals.length > 0)
      best.set(
        spec.key,
        spec.higherIsBetter ? Math.max(...vals) : Math.min(...vals),
      );
  }
  return methods.map((method) => ({
    method,
    label: METHOD_LABEL[method] ?? method,
    cells: METRICS.map((metric) => {
      const value = get(method, metric.key);
      return {
        metric,
        value,
        // Ties are judged on what is displayed, so equal-looking numbers are all marked.
        best:
          value !== null &&
          best.get(metric.key) !== undefined &&
          formatMetric(metric, value) ===
            formatMetric(metric, best.get(metric.key) ?? NaN),
      };
    }),
  }));
}

export function formatMetric(spec: MetricSpec, v: number): string {
  return spec.percent ? `${String(Math.round(v * 100))}%` : v.toFixed(2);
}

export interface ReliabilityBin {
  predicted: number;
  observed: number;
  count: number;
}

/** Reads `detail.bins` of the reliability metric: [{p_pred_mean, p_obs_mean, count}]. Ignores malformed rows. */
export function reliabilityBins(metrics: EvalMetric[]): ReliabilityBin[] {
  const m = metrics.find(
    (x) => x.metric === "reliability" && x.method === "graph_bayes",
  );
  const bins = m?.detail?.["bins"];
  if (!Array.isArray(bins)) return [];
  const out: ReliabilityBin[] = [];
  for (const b of bins as unknown[]) {
    if (typeof b !== "object" || b === null) continue;
    const r = b as Record<string, unknown>;
    const { p_pred_mean: p, p_obs_mean: o, count: n } = r;
    if (typeof p === "number" && typeof o === "number" && typeof n === "number")
      out.push({ predicted: p, observed: o, count: n });
  }
  return out;
}
