import { ApiError } from "../api/errors";
import { useLatestEval } from "../api/hooks";
import { PageHeader } from "../components/layout/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/states";
import { EvalPanel } from "../features/eval/EvalPanel";

export function EvaluationPage() {
  const q = useLatestEval();
  return (
    <>
      <PageHeader
        title="Evaluation"
        description="How often the diagnosis finds the true gap, compared with simpler methods."
      />
      {q.isPending ? (
        <LoadingState label="Loading evaluation" lines={4} />
      ) : null}
      {q.isError && q.error instanceof ApiError && q.error.status === 404 ? (
        <EmptyState
          title="No evaluation has been run yet"
          description="Run the evaluation command on the server (run_eval) and reload this page."
        />
      ) : q.isError ? (
        <ErrorState
          error={q.error}
          onRetry={() => void q.refetch()}
          retrying={q.isFetching}
        />
      ) : null}
      {q.data ? <EvalPanel run={q.data} /> : null}
    </>
  );
}
