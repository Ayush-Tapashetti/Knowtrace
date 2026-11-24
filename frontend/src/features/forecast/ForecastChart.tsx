import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

import type { Forecast } from "../../api/types";
import { pct } from "../../lib/format";

/** Plain-language reading of the forecast: the text alternative to the chart. */
export function forecastSummary(f: Forecast): string {
  const now = pct(f.current_mastery);
  const goal = pct(f.theta_master);
  if (f.current_mastery >= f.theta_master)
    return `${f.concept_name}: you are at ${now}, already above the ${goal} mastery line.`;
  if (f.steps_to_mastery === null)
    return `${f.concept_name}: you are at ${now}. Mastery (${goal}) is not reached within this forecast, so more practice is needed.`;
  return `${f.concept_name}: you are at ${now}. With steady practice we expect to reach ${goal} in about ${String(f.steps_to_mastery)} more questions.`;
}

/** Forecast of mastery with an uncertainty band and the mastery line, plus a text summary and data table. */
export function ForecastChart({ forecast }: { forecast: Forecast }) {
  const data = forecast.points.map((p) => ({
    step: p.step,
    band: [p.p_lo, p.p_hi],
    mastery: p.p_mastery,
  }));
  const summary = forecastSummary(forecast);
  return (
    <figure className="space-y-3">
      <figcaption className="font-medium">{summary}</figcaption>
      <div role="img" aria-label={summary} className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <ComposedChart
            data={data}
            margin={{ top: 8, right: 16, bottom: 24, left: 8 }}
          >
            <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" />
            <XAxis
              dataKey="step"
              label={{
                value: "Questions from now",
                position: "insideBottom",
                offset: -12,
              }}
            />
            <YAxis
              domain={[0, 1]}
              tickFormatter={pct}
              width={64}
              label={{ value: "Mastery", angle: -90, position: "insideLeft" }}
            />
            <ReferenceLine
              y={forecast.theta_master}
              stroke="var(--color-gap-ink)"
              strokeDasharray="6 4"
              label={{
                value: `Mastered (${pct(forecast.theta_master)})`,
                position: "insideTopRight",
                fill: "var(--color-gap-ink)",
              }}
            />
            <Area
              dataKey="band"
              stroke="none"
              fill="var(--color-known)"
              fillOpacity={0.2}
              isAnimationActive={false}
            />
            <Line
              dataKey="mastery"
              stroke="var(--color-known)"
              strokeWidth={3}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <details>
        <summary className="cursor-pointer text-sm underline">
          Show the numbers
        </summary>
        <table className="mt-2 w-full text-left text-sm">
          <caption className="sr-only">
            Forecast mastery by number of questions
          </caption>
          <thead>
            <tr>
              <th scope="col" className="p-1">
                Questions
              </th>
              <th scope="col" className="p-1">
                Expected
              </th>
              <th scope="col" className="p-1">
                Range
              </th>
            </tr>
          </thead>
          <tbody>
            {forecast.points.map((p) => (
              <tr key={p.step}>
                <td className="p-1">{p.step}</td>
                <td className="p-1">{pct(p.p_mastery)}</td>
                <td className="p-1">
                  {pct(p.p_lo)} to {pct(p.p_hi)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
