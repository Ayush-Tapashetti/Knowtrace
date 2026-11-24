import { createApi, type Api } from "../endpoints";

export interface Seen {
  method: string;
  url: string;
  body: unknown;
}

/** A fetch stand-in that records each request and answers with the next canned response. */
export function fakeFetch(
  ...responses: Array<Response | Error | (() => Promise<Response>)>
) {
  const seen: Seen[] = [];
  let i = 0;
  const impl: typeof fetch = async (input) => {
    const req = input as Request;
    const text = await req.clone().text();
    seen.push({
      method: req.method,
      url: req.url,
      body: text === "" ? undefined : (JSON.parse(text) as unknown),
    });
    const next = responses[Math.min(i, responses.length - 1)];
    i += 1;
    if (next === undefined) throw new Error("no canned response");
    if (next instanceof Error) throw next;
    return typeof next === "function" ? next() : next.clone();
  };
  return { impl, seen };
}

export function json(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
}

export const envelope = (
  code: string,
  message: string,
  details: unknown = null,
) => ({
  error: { code, message, details },
});

export const BASE = "http://api.test";

export function apiWith(...responses: Parameters<typeof fakeFetch>) {
  const f = fakeFetch(...responses);
  return {
    api: createApi({ baseUrl: BASE, fetch: f.impl, timeoutMs: 200 }),
    seen: f.seen,
  };
}

/** A full `Api` whose every method fails loudly unless a test overrides it. */
export function stubApi(overrides: Partial<Api>): Api {
  const never = createApi({
    baseUrl: BASE,
    fetch: () => Promise.reject(new Error("unexpected network call")),
  });
  return { ...never, ...overrides };
}

/** A student with nothing in progress and an empty curriculum, for tests that only care about the shell. */
export const quietLearner: Partial<Api> = {
  createStudent: () =>
    Promise.resolve({
      id: "s1",
      pseudonym: "Test student",
      created_at: "2026-01-01T00:00:00Z",
    }),
  getStudent: () =>
    Promise.resolve({
      id: "s1",
      pseudonym: "Test student",
      created_at: "2026-01-01T00:00:00Z",
    }),
  listDiagnoses: () => Promise.resolve([]),
  listConcepts: () =>
    Promise.resolve({ items: [], total: 0, limit: 100, offset: 0 }),
};
