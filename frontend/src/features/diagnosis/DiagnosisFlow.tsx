import { useState } from "react";

import type { DiagnosisStep } from "../../api/types";
import {
  useAbandonDiagnosis,
  useAnswerProbe,
  useAnswerRecheck,
  useDiagnosis,
} from "../../api/hooks";
import { Banner } from "../../components/ui/Banner";
import { Button } from "../../components/ui/Button";
import { ErrorState, LoadingState } from "../../components/ui/states";
import { LessonPlayer } from "../lesson/LessonPlayer";
import { QuestionCard } from "../session/QuestionCard";
import { HypothesisBars } from "./HypothesisBars";
import { ProbeList } from "./ProbeList";
import { ResultPanel } from "./ResultPanel";

const OPEN = new Set(["PROBING", "LESSON_ASSIGNED", "RECHECKING"]);

/** Renders whichever stage the diagnosis is in. The server owns the state; this only displays it. */
export function DiagnosisFlow({
  diagnosisId,
  onDone,
}: {
  diagnosisId: string;
  onDone: () => void;
}) {
  const dx = useDiagnosis(diagnosisId);
  const probe = useAnswerProbe();
  const recheck = useAnswerRecheck();
  const abandon = useAbandonDiagnosis();
  const [lastStep, setLastStep] = useState<DiagnosisStep | null>(null);

  if (dx.isPending)
    return <LoadingState label="Loading your diagnosis" lines={4} />;
  if (dx.isError)
    return (
      <ErrorState
        error={dx.error}
        onRetry={() => void dx.refetch()}
        retrying={dx.isFetching}
      />
    );

  const d = dx.data;
  if (!OPEN.has(d.state))
    return <ResultPanel diagnosis={d} lastStep={lastStep} onDone={onDone} />;

  const mutation = d.state === "RECHECKING" ? recheck : probe;
  const answer = (a: string, latency_ms: number) => {
    mutation.mutate(
      { diagnosisId: d.id, body: { answer: a, latency_ms } },
      { onSuccess: setLastStep },
    );
  };

  return (
    <div className="space-y-5">
      <Banner tone="warning" title="Let's find out why">
        {d.state === "PROBING"
          ? "A few targeted questions will show which earlier idea is behind that miss."
          : d.state === "LESSON_ASSIGNED"
            ? `Found it: ${d.root_concept_name ?? "an earlier idea"}. A short lesson comes next.`
            : "Quick recheck: answer to see whether the lesson stuck."}
      </Banner>

      {d.state === "LESSON_ASSIGNED" && d.lesson_id ? (
        <LessonPlayer lessonId={d.lesson_id} />
      ) : null}

      {d.state !== "LESSON_ASSIGNED" && d.pending_item ? (
        <>
          {d.state === "PROBING" ? (
            <ProbeList probes={d.probes} max={d.max_probes} />
          ) : null}
          {d.state === "RECHECKING" ? (
            <p className="text-sm text-ink-soft">
              Recheck {String(d.rechecks_used + 1)} of up to{" "}
              {String(d.max_rechecks)}
              {lastStep?.passed === false ? " · not yet, try this one" : ""}
            </p>
          ) : null}
          <QuestionCard
            key={d.pending_item.id}
            item={d.pending_item}
            pending={mutation.isPending}
            error={mutation.error}
            onSubmit={answer}
          />
        </>
      ) : null}

      {d.state === "PROBING" ? (
        <HypothesisBars hypotheses={d.hypotheses} />
      ) : null}

      <Button
        variant="ghost"
        pending={abandon.isPending}
        onClick={() => {
          abandon.mutate(d.id);
        }}
      >
        Stop this diagnosis
      </Button>
      {abandon.isError ? <ErrorState error={abandon.error} /> : null}
    </div>
  );
}
