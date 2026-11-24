import type { ComponentProps } from "react";

import { cn } from "../../lib/cn";

export type Tone = "neutral" | "known" | "gap" | "danger";

const TONES: Record<Tone, string> = {
  neutral: "bg-info-tint text-ink",
  known: "bg-known-tint text-known",
  gap: "bg-gap-tint text-gap-ink",
  danger: "bg-danger-tint text-danger",
};

/** Always carries a text label: colour alone never carries meaning. */
export function Badge({
  tone = "neutral",
  className,
  ...rest
}: ComponentProps<"span"> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
      {...rest}
    />
  );
}
