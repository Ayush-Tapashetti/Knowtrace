import type { ComponentProps } from "react";

import { cn } from "../../lib/cn";

/** A worksheet panel: hairline border, near-square corners, no shadow. */
export function Card({ className, ...rest }: ComponentProps<"section">) {
  return (
    <section
      className={cn(
        "rounded-panel border border-line bg-surface p-5",
        className,
      )}
      {...rest}
    />
  );
}
