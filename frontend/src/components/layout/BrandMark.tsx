import { APP_NAME } from "../../lib/brand";

/** Three connected nodes; the last is highlighted: the gap at the end of the trace. */
export function BrandMark() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg viewBox="0 0 28 28" className="size-7" aria-hidden>
        <path
          d="M5 21 L13 9 L23 11"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="5" cy="21" r="3" fill="currentColor" />
        <circle cx="13" cy="9" r="3" fill="currentColor" />
        <circle
          cx="23"
          cy="11"
          r="4"
          className="fill-gap"
          stroke="currentColor"
          strokeWidth="2"
        />
      </svg>
      <span className="font-serif text-xl font-semibold tracking-tight">
        {APP_NAME}
      </span>
    </span>
  );
}
