import type { Diagnosis, DiagnosisStep } from "../../api/types";
import { Banner, type BannerTone } from "../../components/ui/Banner";
import { Button } from "../../components/ui/Button";
import { confidenceWord, pct } from "../../lib/format";
import { HypothesisBars } from "./HypothesisBars";
import { TraceView } from "./TraceView";

const HEAD: Record<string, { tone: BannerTone; title: string }> = {
  RESOLVED: { tone: "success", title: "Gap closed" },
  UNRESOLVED: { tone: "warning", title: "Still shaky" },
  SLIP_DISMISSED: { tone: "info", title: "Just a slip" },
  INCONCLUSIVE: { tone: "info", title: "We couldn't pin it down" },
  ABANDONED: { tone: "info", title: "Diagnosis stopped" },
};

/** The end of a diagnosis: what happened, the evidence, and the way back to practice. */
export function ResultPanel({
  diagnosis,
  lastStep,
  onDone,
}: {
  diagnosis: Diagnosis;
  lastStep: DiagnosisStep | null;
  onDone: () => void;
}) {
  const head = HEAD[diagnosis.state] ?? {
    tone: "info" as const,
    title: "Diagnosis finished",
  };
  const before = lastStep?.root_mastery_before;
  const after = lastStep?.root_mastery_after;
  return (
    <div className="space-y-5">
      <Banner tone={head.tone} title={head.title}>
        <p>{diagnosis.explanation}</p>
        {diagnosis.root_concept_name && diagnosis.confidence !== null ? (
          <p className="mt-1">
            Root: <strong>{diagnosis.root_concept_name}</strong> (
            {confidenceWord(diagnosis.confidence)}, {pct(diagnosis.confidence)}
            ).
          </p>
        ) : null}
        {typeof before === "number" && typeof after === "number" ? (
          <p className="mt-1">
            Mastery of the root: {pct(before)} → {pct(after)}.
          </p>
        ) : null}
      </Banner>
      <TraceView trace={diagnosis.trace} rootId={diagnosis.root_concept_id} />
      <HypothesisBars hypotheses={diagnosis.hypotheses} />
      <Button size="lg" onClick={onDone}>
        Practise another question
      </Button>
    </div>
  );
}
