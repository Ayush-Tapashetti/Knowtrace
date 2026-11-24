/** 0.3456 -> "35%". Mastery and confidence are shown as whole percentages. */
export function pct(p: number): string {
  return `${String(Math.round(p * 100))}%`;
}

/** 185 -> "3 min 5 s"; 40 -> "40 s". */
export function duration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m === 0) return `${String(s)} s`;
  return s === 0 ? `${String(m)} min` : `${String(m)} min ${String(s)} s`;
}

/** Plain-language rank for how sure the diagnosis is. */
export function confidenceWord(p: number): string {
  if (p >= 0.9) return "very sure";
  if (p >= 0.8) return "fairly sure";
  return "not very sure";
}
