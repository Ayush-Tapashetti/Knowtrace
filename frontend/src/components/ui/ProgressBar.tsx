import { cn } from "../../lib/cn";

/** A labelled bar. The numbers are always printed too, so colour and length never carry meaning alone. */
export function ProgressBar({
  value,
  label,
  tone = "known",
  className,
}: {
  /** 0 to 1 */
  value: number;
  label: string;
  tone?: "known" | "gap";
  className?: string;
}) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-valuetext={`${String(pct)}%`}
      className={cn(
        "h-2 w-full overflow-hidden rounded-full bg-line",
        className,
      )}
    >
      <div
        className={cn("h-full", tone === "known" ? "bg-known" : "bg-gap")}
        style={{ width: `${String(pct)}%` }}
      />
    </div>
  );
}
