import { useState } from "react";

import {
  summarizeSources,
  useCompleteLesson,
  useLesson,
  useViewLessonStep,
} from "../../api/hooks";
import { Banner } from "../../components/ui/Banner";
import { Button } from "../../components/ui/Button";
import { ProgressBar } from "../../components/ui/ProgressBar";
import { ErrorState, LoadingState } from "../../components/ui/states";
import { duration } from "../../lib/format";
import { LessonStepCard } from "./LessonStepCard";

/** Walks the micro-lesson one step at a time, then asks the server to move on to the recheck. */
export function LessonPlayer({ lessonId }: { lessonId: string }) {
  const lesson = useLesson(lessonId);
  const view = useViewLessonStep(lessonId);
  const complete = useCompleteLesson(lessonId);
  const [checks, setChecks] = useState<Record<number, boolean>>({});

  if (lesson.isPending)
    return <LoadingState label="Loading your lesson" lines={4} />;
  if (lesson.isError)
    return (
      <ErrorState
        error={lesson.error}
        onRetry={() => void lesson.refetch()}
        retrying={lesson.isFetching}
      />
    );

  const steps = [...lesson.data.steps].sort((a, b) => a.position - b.position);
  const doneCount = steps.filter((s) => s.viewed).length;
  const currentIndex = steps.findIndex((s) => !s.viewed);
  const current = currentIndex === -1 ? undefined : steps[currentIndex];
  const sources = summarizeSources(lesson.data);

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl">Your short lesson</h2>
        <p className="text-sm text-ink-soft">
          About {duration(lesson.data.est_seconds)} · {String(doneCount)} of{" "}
          {String(steps.length)} steps done
        </p>
        <ProgressBar
          value={steps.length === 0 ? 0 : doneCount / steps.length}
          label="Lesson progress"
          className="mt-2"
        />
      </div>

      {sources.anyFallback ? (
        <Banner tone="warning" title="Showing the original wording">
          The AI rewrite of {String(sources.counts.fallback)} step(s) didn't
          pass our checks, so the hand-written text is used. The lesson is
          unchanged in meaning.
        </Banner>
      ) : sources.usesModel ? (
        <Banner tone="info">
          Some steps were reworded by AI and checked against the original before
          you see them.
        </Banner>
      ) : null}

      {current ? (
        <>
          {currentIndex > 0 &&
          checks[steps[currentIndex - 1]?.position ?? -1] !== undefined ? (
            <Banner
              tone={
                checks[steps[currentIndex - 1]?.position ?? -1]
                  ? "success"
                  : "info"
              }
            >
              {checks[steps[currentIndex - 1]?.position ?? -1]
                ? "Correct."
                : "Not quite. Keep going, you will see it again in the recheck."}
            </Banner>
          ) : null}
          <LessonStepCard
            key={current.position}
            step={current}
            index={currentIndex}
            total={steps.length}
            pending={view.isPending}
            error={view.error}
            onView={(answer, latency_ms) => {
              view.mutate(
                {
                  position: current.position,
                  body: answer === null ? {} : { answer, latency_ms },
                },
                {
                  onSuccess: (r) => {
                    if (r.attempt)
                      setChecks((c) => ({
                        ...c,
                        [current.position]: r.attempt?.is_correct ?? false,
                      }));
                  },
                },
              );
            }}
          />
        </>
      ) : (
        <div className="space-y-3">
          <Banner tone="success" title="Lesson finished">
            Ready for a quick recheck to see whether it stuck.
          </Banner>
          {complete.isError ? (
            <ErrorState
              error={complete.error}
              onRetry={() => {
                complete.mutate();
              }}
              retrying={complete.isPending}
            />
          ) : (
            <Button
              size="lg"
              pending={complete.isPending}
              onClick={() => {
                complete.mutate();
              }}
            >
              Start the recheck
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
