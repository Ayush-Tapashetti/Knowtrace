import { useState } from "react";

import type { AttemptResult } from "../api/types";
import { useStudentDiagnoses } from "../api/hooks";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { ErrorState, LoadingState } from "../components/ui/states";
import { DiagnosisFlow } from "../features/diagnosis/DiagnosisFlow";
import { PracticePanel } from "../features/session/PracticePanel";
import { useSession } from "../features/session/useSession";

const OPEN = new Set(["PROBING", "LESSON_ASSIGNED", "RECHECKING"]);

export function PracticePage() {
  const session = useSession();
  return (
    <>
      <PageHeader
        title="Practice"
        description="Answer a question. If you miss it, we trace back to the idea you're missing."
        actions={
          session.studentId ? (
            <Button variant="ghost" onClick={session.restart}>
              Start over as a new student
            </Button>
          ) : null
        }
      />
      {session.status === "loading" ? (
        <LoadingState label="Setting up your session" />
      ) : null}
      {session.status === "error" ? (
        <ErrorState error={session.error} onRetry={session.restart} />
      ) : null}
      {session.studentId ? <Practice studentId={session.studentId} /> : null}
    </>
  );
}

function Practice({ studentId }: { studentId: string }) {
  const diagnoses = useStudentDiagnoses(studentId);
  // undefined: follow the server's open diagnosis; string/null: what this visit chose.
  const [active, setActive] = useState<string | null | undefined>(undefined);

  if (diagnoses.isPending)
    return <LoadingState label="Checking for an unfinished diagnosis" />;
  if (diagnoses.isError)
    return (
      <ErrorState
        error={diagnoses.error}
        onRetry={() => void diagnoses.refetch()}
        retrying={diagnoses.isFetching}
      />
    );

  const open = diagnoses.data.find((d) => OPEN.has(d.state));
  const activeId = active === undefined ? (open?.id ?? null) : active;

  if (activeId)
    return (
      <DiagnosisFlow
        key={activeId}
        diagnosisId={activeId}
        onDone={() => {
          setActive(null);
        }}
      />
    );
  return (
    <PracticePanel
      studentId={studentId}
      onResult={(r: AttemptResult) => {
        if (r.diagnosis) setActive(r.diagnosis.id);
      }}
    />
  );
}
