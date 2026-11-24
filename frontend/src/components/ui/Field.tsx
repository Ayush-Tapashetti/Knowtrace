import { useId, type ComponentProps, type ReactNode } from "react";

import { cn } from "../../lib/cn";

export interface FieldControlProps {
  id: string;
  "aria-describedby": string | undefined;
  "aria-invalid": true | undefined;
}

interface FieldProps {
  label: string;
  hint?: string;
  /** Error text; also marks the control invalid. */
  error?: string | null;
  required?: boolean;
  /** Receives the props that wire the control to its label, hint and error. */
  children: (control: FieldControlProps) => ReactNode;
}

/** A labelled control with optional hint and error text, wired with aria attributes. */
export function Field({ label, hint, error, required, children }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
        {required ? (
          <span className="font-normal text-ink-soft"> (required)</span>
        ) : null}
      </label>
      {hint ? (
        <p id={hintId} className="text-sm text-ink-soft">
          {hint}
        </p>
      ) : null}
      {children({
        id,
        "aria-describedby": describedBy === "" ? undefined : describedBy,
        "aria-invalid": error ? true : undefined,
      })}
      {error ? (
        <p id={errorId} className="text-sm font-medium text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function Input({ className, ...rest }: ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "min-h-11 w-full rounded-control border border-ink/40 bg-surface px-3 text-base",
        "placeholder:text-ink-soft/70 aria-[invalid=true]:border-danger aria-[invalid=true]:border-2",
        "disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...rest}
    />
  );
}

export function Select({ className, ...rest }: ComponentProps<"select">) {
  return (
    <select
      className={cn(
        "min-h-11 w-full rounded-control border border-ink/40 bg-surface px-3 text-base",
        "disabled:cursor-not-allowed disabled:opacity-60",
        className,
      )}
      {...rest}
    />
  );
}
