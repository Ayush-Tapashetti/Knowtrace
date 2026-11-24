import { Component, type ErrorInfo, type ReactNode } from "react";
import { RotateCw } from "lucide-react";

import { ApiError, NetworkError, describeError } from "../../api/errors";
import { Button } from "./Button";
import { cn } from "../../lib/cn";

/** Shown while data loads. Announced once to assistive tech; skeleton lines are decorative. */
export function LoadingState({
  label = "Loading",
  lines = 3,
}: {
  label?: string;
  lines?: number;
}) {
  return (
    <div role="status" aria-busy="true" className="space-y-3 py-2">
      <span className="sr-only">{label}</span>
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          aria-hidden
          className={cn(
            "h-4 animate-pulse rounded-panel bg-line motion-reduce:animate-none",
            i === lines - 1 ? "w-2/3" : "w-full",
          )}
        />
      ))}
    </div>
  );
}

/** Nothing to show yet: say what goes here and offer the next action. */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-panel border border-dashed border-ink/30 px-5 py-8 text-center">
      <h2 className="text-lg">{title}</h2>
      {description ? (
        <p className="mx-auto mt-1 max-w-prose text-ink-soft">{description}</p>
      ) : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function errorTitle(error: unknown): string {
  if (error instanceof NetworkError)
    return error.reason === "timeout"
      ? "The server is too slow"
      : "Can't reach the server";
  if (error instanceof ApiError) {
    if (error.status === 404) return "Not found";
    if (error.status === 409) return "That isn't possible right now";
    if (error.status === 429) return "Too many requests";
    if (error.status === 503) return "The server isn't ready";
    if (error.status < 500) return "That request didn't work";
  }
  return "Something went wrong";
}

/** What failed and what to do next. Never a stack trace. */
export function ErrorState({
  error,
  onRetry,
  retrying = false,
  title,
}: {
  error: unknown;
  onRetry?: () => void;
  retrying?: boolean;
  title?: string;
}) {
  const wait = error instanceof ApiError ? error.retryAfterSeconds : null;
  return (
    <div
      role="alert"
      className="rounded-panel border border-danger/50 bg-danger-tint px-5 py-4"
    >
      <h2 className="text-lg">{title ?? errorTitle(error)}</h2>
      <p className="mt-1 max-w-prose">{describeError(error)}</p>
      {wait !== null ? (
        <p className="mt-1 text-sm">Try again in {String(wait)} seconds.</p>
      ) : null}
      {onRetry ? (
        <Button
          variant="secondary"
          className="mt-3"
          onClick={onRetry}
          pending={retrying}
        >
          {retrying ? null : <RotateCw aria-hidden className="size-4" />}
          Try again
        </Button>
      ) : null}
    </div>
  );
}

interface BoundaryState {
  failed: boolean;
}

/** Last line of defence: a render error shows a recovery screen instead of a blank page. */
export class ErrorBoundary extends Component<
  { children: ReactNode },
  BoundaryState
> {
  override state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("render error", error, info.componentStack);
  }

  override render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="mx-auto max-w-xl p-6">
        <div
          role="alert"
          className="rounded-panel border border-danger/50 bg-danger-tint px-5 py-4"
        >
          <h1 className="text-xl">This page hit a problem</h1>
          <p className="mt-1">
            Your progress is saved on the server. Reload to pick up where you
            left off.
          </p>
          <Button
            className="mt-3"
            onClick={() => {
              window.location.reload();
            }}
          >
            Reload page
          </Button>
        </div>
      </div>
    );
  }
}
