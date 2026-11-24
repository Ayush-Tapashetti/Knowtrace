import type { LessonStep } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { QuestionCard } from "../session/QuestionCard";
import { SourceBadge } from "./SourceBadge";

const KIND_LABEL: Record<LessonStep["kind"], string> = {
  DEFINITION: "The idea",
  WORKED_EXAMPLE: "Worked example",
  BRIDGE: "Bridge back",
  PRACTICE: "Try it",
  CHECK: "Quick check",
};

/** The step the student is on. Text steps ask for "Got it"; question steps take an answer. */
export function LessonStepCard({
  step,
  index,
  total,
  pending,
  error,
  onView,
}: {
  step: LessonStep;
  /** Zero-based place in the lesson (the server's `position` numbering is not shown). */
  index: number;
  total: number;
  pending: boolean;
  error: unknown;
  onView: (answer: string | null, latencyMs: number | null) => void;
}) {
  const eyebrow = `Step ${String(index + 1)} of ${String(total)} · ${KIND_LABEL[step.kind]} · ${step.concept_name}`;
  if (step.item) {
    return (
      <div className="space-y-2">
        <QuestionCard
          key={step.position}
          item={step.item}
          eyebrow={eyebrow}
          pending={pending}
          error={error}
          submitLabel="Check answer"
          onSubmit={(a, ms) => {
            onView(a, ms);
          }}
        />
      </div>
    );
  }
  return (
    <Card>
      <p className="text-sm text-ink-soft">{eyebrow}</p>
      <p className="mt-2 whitespace-pre-line font-serif text-lg">{step.text}</p>
      <div className="mt-3">
        <SourceBadge source={step.source} />
      </div>
      <Button
        className="mt-4"
        pending={pending}
        onClick={() => {
          onView(null, null);
        }}
      >
        Got it
      </Button>
    </Card>
  );
}
