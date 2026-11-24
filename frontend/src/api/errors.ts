import type { ErrorBody, ErrorEnvelope } from "./types";

/** The server answered, and the answer was an error (the 5D envelope, or a bare HTTP failure). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ErrorBody["details"];
  /** Seconds to wait, from `Retry-After` on a 429. */
  readonly retryAfterSeconds: number | null;

  constructor(init: {
    status: number;
    code: string;
    message: string;
    details?: ErrorBody["details"];
    retryAfterSeconds?: number | null;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.details = init.details ?? null;
    this.retryAfterSeconds = init.retryAfterSeconds ?? null;
  }
}

/** The server never answered: unreachable, connection dropped, or our timeout fired. */
export class NetworkError extends Error {
  readonly reason: "unreachable" | "timeout";

  constructor(
    reason: "unreachable" | "timeout",
    options?: { cause?: unknown },
  ) {
    super(
      reason === "timeout"
        ? "The server took too long to respond."
        : "Could not reach the server.",
      options,
    );
    this.name = "NetworkError";
    this.reason = reason;
  }
}

export function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

/** Narrow an unknown JSON body to the shared `{ error: { code, message, details } }` envelope. */
export function isErrorEnvelope(v: unknown): v is ErrorEnvelope {
  if (!isRecord(v) || !isRecord(v["error"])) return false;
  const e = v["error"];
  return typeof e["code"] === "string" && typeof e["message"] === "string";
}

export function parseRetryAfter(header: string | null): number | null {
  if (header === null) return null;
  const n = Number(header);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

/** Build an ApiError from whatever the server sent back. */
export function toApiError(
  status: number,
  body: unknown,
  retryAfter: string | null = null,
): ApiError {
  const retryAfterSeconds = parseRetryAfter(retryAfter);
  if (isErrorEnvelope(body)) {
    const { code, message, details } = body.error;
    return new ApiError({ status, code, message, details, retryAfterSeconds });
  }
  const text =
    typeof body === "string" && body.length > 0
      ? body.slice(0, 200)
      : `HTTP ${String(status)}`;
  return new ApiError({
    status,
    code: "http_error",
    message: text,
    retryAfterSeconds,
  });
}

/** One-line text safe to show a learner. */
export function describeError(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof NetworkError) return e.message;
  return "Something unexpected happened.";
}
