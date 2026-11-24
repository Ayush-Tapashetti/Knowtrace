import { useConcept, useForecast } from "../../api/hooks";
import type { Concept, MasteryPoint } from "../../api/types";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { ErrorState, LoadingState } from "../../components/ui/states";
import { pct } from "../../lib/format";
import { ForecastChart } from "../forecast/ForecastChart";
import { bandOf } from "./heat";

/** One concept: what it is, what it needs, how you are doing, and where practice will take you. */
export function ConceptDetail({
  conceptId,
  studentId,
  names,
  point,
  onSelect,
}: {
  conceptId: string;
  studentId: string;
  names: Map<string, Concept>;
  point: MasteryPoint | undefined;
  onSelect: (id: string) => void;
}) {
  const detail = useConcept(conceptId);
  const forecast = useForecast(studentId, conceptId);
  const band = bandOf(point);
  const link = (id: string) => (
    <li key={id}>
      <button
        type="button"
        className="underline decoration-gap decoration-2 underline-offset-2"
        onClick={() => {
          onSelect(id);
        }}
      >
        {names.get(id)?.name ?? id}
      </button>
    </li>
  );
  return (
    <Card aria-label="Concept detail">
      {detail.isPending ? <LoadingState label="Loading concept" /> : null}
      {detail.isError ? (
        <ErrorState
          error={detail.error}
          onRetry={() => void detail.refetch()}
          retrying={detail.isFetching}
        />
      ) : null}
      {detail.data ? (
        <div className="space-y-4">
          <div>
            <h2 className="text-xl">{detail.data.name}</h2>
            <p className="mt-1 flex flex-wrap gap-2 text-sm">
              <Badge>{detail.data.strand}</Badge>
              <Badge
                tone={
                  band.key === "mastered"
                    ? "known"
                    : band.key === "weak"
                      ? "gap"
                      : "neutral"
                }
              >
                {band.label}
                {point && point.n_obs > 0 ? `, ${pct(point.p_mastery)}` : ""}
              </Badge>
              <Badge>{String(detail.data.item_count)} questions</Badge>
            </p>
            <p className="mt-2 max-w-prose">{detail.data.description}</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <h3 className="text-base">Needs first</h3>
              {detail.data.prerequisites.length === 0 ? (
                <p className="text-ink-soft">
                  Nothing. This is a starting point.
                </p>
              ) : (
                <ul className="list-disc pl-5">
                  {detail.data.prerequisites.map(link)}
                </ul>
              )}
            </div>
            <div>
              <h3 className="text-base">Unlocks</h3>
              {detail.data.dependents.length === 0 ? (
                <p className="text-ink-soft">
                  Nothing else depends on this yet.
                </p>
              ) : (
                <ul className="list-disc pl-5">
                  {detail.data.dependents.map(link)}
                </ul>
              )}
            </div>
          </div>
        </div>
      ) : null}
      <div className="mt-5 border-t border-line pt-4">
        <h3 className="text-base">Forecast</h3>
        {forecast.isPending ? (
          <LoadingState label="Loading forecast" lines={2} />
        ) : null}
        {forecast.isError ? (
          <ErrorState
            error={forecast.error}
            onRetry={() => void forecast.refetch()}
            retrying={forecast.isFetching}
          />
        ) : null}
        {forecast.data ? <ForecastChart forecast={forecast.data} /> : null}
      </div>
    </Card>
  );
}
