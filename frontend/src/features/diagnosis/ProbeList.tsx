import { Check, Circle, X } from "lucide-react";

import type { Probe } from "../../api/types";

/** Probe progress as a text list, so the count never depends on colour. */
export function ProbeList({ probes, max }: { probes: Probe[]; max: number }) {
  return (
    <div className="text-sm text-ink-soft">
      <span className="font-medium text-ink">
        Probe {String(Math.min(probes.length, max))} of up to {String(max)}
      </span>
      <ol className="mt-1 flex flex-wrap gap-2" aria-label="Probes so far">
        {probes.map((p) => (
          <li
            key={p.seq}
            className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5"
          >
            {p.correct === null ? (
              <Circle aria-hidden className="size-3.5" />
            ) : p.correct ? (
              <Check aria-hidden className="size-3.5 text-known" />
            ) : (
              <X aria-hidden className="size-3.5 text-danger" />
            )}
            <span>
              {String(p.seq)}:{" "}
              {p.correct === null ? "waiting" : p.correct ? "right" : "wrong"}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
