import { useState, type SyntheticEvent } from "react";

import type { Item } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Field, Input } from "../../components/ui/Field";
import { describeError } from "../../api/errors";
import { fieldError, validateAnswer } from "../../lib/formErrors";

export interface QuestionCardProps {
  item: Item;
  /** Called with the trimmed answer and how long the student took. */
  onSubmit: (answer: string, latencyMs: number) => void;
  pending: boolean;
  /** Last submit error; field-level messages render next to the answer, the rest above the form. */
  error?: unknown;
  submitLabel?: string;
  /** Small label above the question, e.g. "Probe 2 of 5". */
  eyebrow?: string;
}

/**
 * One question with an MCQ radio group or a numeric box. The chosen answer is kept on failure so the
 * student never has to retype. Remount with `key={item.id}` for each new question.
 */
export function QuestionCard({
  item,
  onSubmit,
  pending,
  error,
  submitLabel = "Submit answer",
  eyebrow,
}: QuestionCardProps) {
  const [answer, setAnswer] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [startedAt] = useState(() => performance.now());

  const serverFieldError = fieldError(error, "answer");
  const otherError = error && !serverFieldError ? describeError(error) : null;
  const shownError = localError ?? serverFieldError;

  function submit(e: SyntheticEvent) {
    e.preventDefault();
    if (pending) return;
    const problem = validateAnswer(answer);
    setLocalError(problem);
    if (problem) return;
    onSubmit(answer.trim(), Math.round(performance.now() - startedAt));
  }

  return (
    <Card>
      <form onSubmit={submit} noValidate aria-label="Question">
        {eyebrow ? <p className="text-sm text-ink-soft">{eyebrow}</p> : null}
        {item.kind === "MCQ" ? (
          <fieldset
            className="mt-1 space-y-2"
            aria-describedby={shownError ? "answer-error" : undefined}
          >
            <legend className="font-serif text-xl">{item.stem}</legend>
            {item.choices.map((c) => (
              <label
                key={c.id}
                className="flex min-h-11 cursor-pointer items-center gap-3 rounded-control border border-ink/30 bg-surface px-3 has-checked:border-ink has-checked:bg-gap-tint"
              >
                <input
                  type="radio"
                  name={`answer-${item.id}`}
                  value={c.id}
                  checked={answer === c.id}
                  onChange={() => {
                    setAnswer(c.id);
                    setLocalError(null);
                  }}
                  className="size-4 accent-ink"
                />
                <span>{c.text}</span>
              </label>
            ))}
            {shownError ? (
              <p id="answer-error" className="text-sm font-medium text-danger">
                {shownError}
              </p>
            ) : null}
          </fieldset>
        ) : (
          <>
            <p className="mt-1 font-serif text-xl">{item.stem}</p>
            <div className="mt-3">
              <Field label="Your answer" error={shownError} required>
                {(c) => (
                  <Input
                    {...c}
                    inputMode="decimal"
                    autoComplete="off"
                    value={answer}
                    onChange={(e) => {
                      setAnswer(e.target.value);
                      setLocalError(null);
                    }}
                  />
                )}
              </Field>
            </div>
          </>
        )}
        {otherError ? (
          <p role="alert" className="mt-3 text-sm font-medium text-danger">
            {otherError}
          </p>
        ) : null}
        <Button type="submit" className="mt-4" pending={pending}>
          {submitLabel}
        </Button>
      </form>
    </Card>
  );
}
