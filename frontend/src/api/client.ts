import createClient from "openapi-fetch";

import { NetworkError, isAbortError, toApiError } from "./errors";
import type { paths } from "./schema";

export const DEFAULT_TIMEOUT_MS = 15_000;
const API_SUFFIX = /\/api\/v1\/?$/;

/**
 * `VITE_API_BASE_URL` is `http://host:8000/api/v1`, but the generated paths already start with
 * `/api/v1`, so use only the origin part. An empty value means same-origin (dev proxy).
 */
export function resolveBaseUrl(raw: string | undefined): string {
  return (raw ?? "").replace(API_SUFFIX, "").replace(/\/+$/, "");
}

export interface ClientOptions {
  baseUrl?: string;
  timeoutMs?: number;
  /** Injected in tests. */
  fetch?: typeof fetch;
}

/**
 * Wrap fetch so that: our timeout fires as `NetworkError("timeout")`; a caller's abort stays an
 * AbortError (not an error to show); every other failure becomes `NetworkError("unreachable")`.
 */
export function guardedFetch(
  impl: typeof fetch,
  timeoutMs: number,
): (req: Request) => Promise<Response> {
  return async (request: Request) => {
    request.signal.throwIfAborted(); // already cancelled: never touch the network
    const timeout = new AbortController();
    const timer = setTimeout(() => {
      timeout.abort();
    }, timeoutMs);
    const signal = AbortSignal.any([request.signal, timeout.signal]);
    try {
      return await impl(new Request(request, { signal }));
    } catch (e) {
      if (request.signal.aborted) throw e; // the caller cancelled: let it propagate as an abort
      if (timeout.signal.aborted)
        throw new NetworkError("timeout", { cause: e });
      if (isAbortError(e)) throw e;
      throw new NetworkError("unreachable", { cause: e });
    } finally {
      clearTimeout(timer);
    }
  };
}

export function createRawClient(options: ClientOptions = {}) {
  const baseUrl =
    options.baseUrl ?? resolveBaseUrl(import.meta.env.VITE_API_BASE_URL);
  const impl = options.fetch ?? ((input, init) => fetch(input, init));
  return createClient<paths>({
    baseUrl,
    fetch: guardedFetch(impl, options.timeoutMs ?? DEFAULT_TIMEOUT_MS),
  });
}

export type RawClient = ReturnType<typeof createRawClient>;

interface Result<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Turn openapi-fetch's `{ data, error }` into "return the data, or throw an ApiError". */
export async function unwrap<T>(call: Promise<Result<T>>): Promise<T> {
  const { data, error, response } = await call;
  if (error !== undefined)
    throw toApiError(
      response.status,
      error,
      response.headers.get("retry-after"),
    );
  if (data === undefined) {
    throw toApiError(response.status, {
      error: { code: "empty_response", message: "The server sent no data." },
    });
  }
  return data;
}
