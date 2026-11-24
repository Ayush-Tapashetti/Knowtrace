import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  XAxis,
  YAxis,
} from "recharts";

import { pct } from "../../lib/format";
import type { ReliabilityBin } from "./evalModel";

/** Predicted vs observed mastery. Points on the dashed diagonal mean the forecast is well calibrated. */
export function ReliabilityChart({ bins }: { bins: ReliabilityBin[] }) {
  const worst = bins.reduce(
    (w, b) => Math.max(w, Math.abs(b.predicted - b.observed)),
    0,
  );
  const summary = `Forecast calibration: across ${String(bins.length)} groups, predictions are off by at most ${pct(worst)} from what was observed.`;
  const data = bins.map((b) => ({
    predicted: b.predicted,
    observed: b.observed,
  }));
  return (
    <figure className="space-y-3">
      <figcaption className="font-medium">{summary}</figcaption>
      <div role="img" aria-label={summary} className="h-64 w-full max-w-md">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <ComposedChart
            data={data}
            margin={{ top: 8, right: 16, bottom: 28, left: 8 }}
          >
            <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" />
            <XAxis
              type="number"
              dataKey="predicted"
              domain={[0, 1]}
              tickFormatter={pct}
              label={{
                value: "Predicted",
                position: "insideBottom",
                offset: -14,
              }}
            />
            <YAxis
              type="number"
              domain={[0, 1]}
              tickFormatter={pct}
              width={64}
              label={{ value: "Observed", angle: -90, position: "insideLeft" }}
            />
            <ReferenceLine
              segment={[
                { x: 0, y: 0 },
                { x: 1, y: 1 },
              ]}
              stroke="var(--color-ink-soft)"
              strokeDasharray="6 4"
            />
            <Line
              dataKey="observed"
              stroke="var(--color-known)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Scatter
              dataKey="observed"
              fill="var(--color-known)"
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <details>
        <summary className="cursor-pointer text-sm underline">
          Show the numbers
        </summary>
        <table className="mt-2 w-full max-w-md text-left text-sm">
          <caption className="sr-only">
            Predicted versus observed mastery by group
          </caption>
          <thead>
            <tr>
              <th scope="col" className="p-1">
                Predicted
              </th>
              <th scope="col" className="p-1">
                Observed
              </th>
              <th scope="col" className="p-1">
                Students
              </th>
            </tr>
          </thead>
          <tbody>
            {bins.map((b) => (
              <tr key={b.predicted}>
                <td className="p-1">{pct(b.predicted)}</td>
                <td className="p-1">{pct(b.observed)}</td>
                <td className="p-1">{b.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
