import { useState } from "react";

import type { AttemptResult } from "../../api/types";
import { useConcepts, useItems, useSubmitAttempt } from "../../api/hooks";
import { Banner } from "../../components/ui/Banner";
import { Field, Select } from "../../components/ui/Field";
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "../../components/ui/states";
import { QuestionCard } from "./QuestionCard";

/** Pick a topic, answer one of its questions. A wrong answer starts a diagnosis (handled by the parent). */
export function PracticePanel({
  studentId,
  onResult,
}: {
  studentId: string;
  onResult: (r: AttemptResult) => void;
}) {
  const concepts = useConcepts({ limit: 100 });
  const [conceptId, setConceptId] = useState("");
  const [last, setLast] = useState<AttemptResult | null>(null);

  if (concepts.isPending) return <LoadingState label="Loading topics" />;
  if (concepts.isError)
    return (
      <ErrorState
        error={concepts.error}
        onRetry={() => void concepts.refetch()}
        retrying={concepts.isFetching}
      />
    );
  if (concepts.data.items.length === 0)
    return (
      <EmptyState
        title="No topics yet"
        description="The curriculum has not been loaded on the server. Run the seed command, then reload."
      />
    );

  return (
    <div className="space-y-5">
      <Field label="Topic" hint="Pick what you want to practise.">
        {(c) => (
          <Select
            {...c}
            value={conceptId}
            onChange={(e) => {
              setConceptId(e.target.value);
              setLast(null);
            }}
          >
            <option value="">Choose a topic…</option>
            {concepts.data.items.map((k) => (
              <option key={k.id} value={k.id}>
                {k.name}
              </option>
            ))}
          </Select>
        )}
      </Field>

      {last && !last.diagnosis ? (
        <Banner
          tone={last.attempt.is_correct ? "success" : "info"}
          title={last.attempt.is_correct ? "Correct" : "Not quite"}
        >
          {last.attempt.is_correct
            ? "Nice. Try another, or pick a different topic."
            : "No diagnosis was started for this one."}
        </Banner>
      ) : null}

      {conceptId === "" ? null : (
        <TopicQuestion
          key={conceptId}
          studentId={studentId}
          conceptId={conceptId}
          onResult={(r) => {
            setLast(r);
            onResult(r);
          }}
        />
      )}
    </div>
  );
}

/** Questions for one chosen topic, served in order and cycling. Only mounted once a topic is picked. */
function TopicQuestion({
  studentId,
  conceptId,
  onResult,
}: {
  studentId: string;
  conceptId: string;
  onResult: (r: AttemptResult) => void;
}) {
  const items = useItems({ concept_id: conceptId, limit: 100 });
  const submit = useSubmitAttempt(studentId);
  const [index, setIndex] = useState(0);

  if (items.isPending) return <LoadingState label="Loading questions" />;
  if (items.isError)
    return (
      <ErrorState
        error={items.error}
        onRetry={() => void items.refetch()}
        retrying={items.isFetching}
      />
    );
  const list = items.data.items;
  const item = list.length > 0 ? list[index % list.length] : undefined;
  if (item === undefined)
    return (
      <EmptyState
        title="No questions for this topic yet"
        description="Pick another topic."
      />
    );
  return (
    <QuestionCard
      key={`${item.id}-${String(index)}`}
      item={item}
      pending={submit.isPending}
      error={submit.error}
      onSubmit={(answer, latency_ms) => {
        submit.mutate(
          { item_id: item.id, answer, latency_ms },
          {
            onSuccess: (r) => {
              setIndex((i) => i + 1);
              onResult(r);
            },
          },
        );
      }}
    />
  );
}
