import { useState } from "react";

import type { Concept, MasteryPoint } from "../../api/types";
import { Field, Input } from "../../components/ui/Field";
import { cn } from "../../lib/cn";
import { pct } from "../../lib/format";
import { bandOf } from "./heat";

/** The same data as the graph, as a filterable table: the accessible alternative and the dense view. */
export function MasteryTable({
  concepts,
  mastery,
  selectedId,
  onSelect,
}: {
  concepts: Concept[];
  mastery: Map<string, MasteryPoint>;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [q, setQ] = useState("");
  const rows = concepts
    .filter((c) => c.name.toLowerCase().includes(q.trim().toLowerCase()))
    .sort((a, b) => a.tier - b.tier || a.name.localeCompare(b.name));
  return (
    <div className="space-y-3">
      <Field label="Filter concepts">
        {(c) => (
          <Input
            {...c}
            type="search"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
            }}
          />
        )}
      </Field>
      <div className="overflow-x-auto rounded-panel border border-ink/20 bg-surface">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">
            Concepts with your mastery of each
          </caption>
          <thead className="border-b border-line">
            <tr>
              <th scope="col" className="p-3">
                Concept
              </th>
              <th scope="col" className="p-3">
                Strand
              </th>
              <th scope="col" className="p-3">
                Tier
              </th>
              <th scope="col" className="p-3">
                Mastery
              </th>
              <th scope="col" className="p-3">
                Level
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => {
              const p = mastery.get(c.id);
              const band = bandOf(p);
              return (
                <tr
                  key={c.id}
                  className={cn(
                    "border-b border-line last:border-0",
                    c.id === selectedId && "bg-gap-tint",
                  )}
                >
                  <th scope="row" className="p-3 font-medium">
                    <button
                      type="button"
                      className="text-left underline decoration-gap decoration-2 underline-offset-2"
                      aria-pressed={c.id === selectedId}
                      onClick={() => {
                        onSelect(c.id);
                      }}
                    >
                      {c.name}
                    </button>
                  </th>
                  <td className="p-3">{c.strand}</td>
                  <td className="p-3">{c.tier}</td>
                  <td className="p-3">
                    {p && p.n_obs > 0 ? pct(p.p_mastery) : "–"}
                  </td>
                  <td className="p-3">{band.label}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length === 0 ? (
          <p className="p-4 text-ink-soft">No concept matches “{q}”.</p>
        ) : null}
      </div>
    </div>
  );
}
