import type { LessonSource } from "../../api/types";
import { Badge, type Tone } from "../../components/ui/Badge";

const MAP: Record<LessonSource, { tone: Tone; label: string; title: string }> =
  {
    authored: {
      tone: "neutral",
      label: "Written by hand",
      title: "Authored curriculum text",
    },
    model: {
      tone: "known",
      label: "Reworded by AI",
      title: "Rewritten by the language model, checked against the original",
    },
    cache: {
      tone: "known",
      label: "Reworded by AI (saved)",
      title: "A previously checked AI rewrite",
    },
    fallback: {
      tone: "gap",
      label: "Original text",
      title: "The AI rewrite was rejected, so the authored text is shown",
    },
  };

/** Says how a piece of lesson text was produced, always in words. */
export function SourceBadge({ source }: { source: LessonSource }) {
  const m = MAP[source];
  return (
    <Badge tone={m.tone} title={m.title}>
      {m.label}
    </Badge>
  );
}
