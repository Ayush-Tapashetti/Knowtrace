import type { MasteryPoint } from "../../api/types";

export interface Band {
  key: "unseen" | "weak" | "building" | "good" | "mastered";
  label: string;
  /** Tailwind classes for a node or swatch: background, text and border together keep contrast. */
  className: string;
}

/** Five discrete bands (never a smooth gradient), each named in words so colour is not the only cue. */
export const BANDS: Band[] = [
  {
    key: "unseen",
    label: "Not tried yet",
    className: "border-dashed border-ink/50 bg-surface text-ink",
  },
  {
    key: "weak",
    label: "Weak (under 40%)",
    className: "border-gap-ink/60 bg-gap text-ink",
  },
  {
    key: "building",
    label: "Building (40–70%)",
    className: "border-gap-ink/40 bg-gap-tint text-ink",
  },
  {
    key: "good",
    label: "Good (70% and up)",
    className: "border-known/50 bg-known-tint text-ink",
  },
  {
    key: "mastered",
    label: "Mastered",
    className: "border-[#0a5f5e] bg-[#0a5f5e] text-white",
  },
];

const BY_KEY = Object.fromEntries(BANDS.map((b) => [b.key, b])) as Record<
  Band["key"],
  Band
>;

export function bandOf(
  p: Pick<MasteryPoint, "p_mastery" | "mastered" | "n_obs"> | undefined,
): Band {
  if (!p || p.n_obs === 0) return BY_KEY.unseen;
  if (p.mastered) return BY_KEY.mastered;
  if (p.p_mastery < 0.4) return BY_KEY.weak;
  if (p.p_mastery < 0.7) return BY_KEY.building;
  return BY_KEY.good;
}
