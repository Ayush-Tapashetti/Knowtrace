import { describe, expect, it } from "vitest";

import { resolveBaseUrl } from "../client";
import {
  ApiError,
  NetworkError,
  isAbortError,
  isErrorEnvelope,
  toApiError,
} from "../errors";
import { BASE, apiWith, envelope, fakeFetch, json } from "./helpers";
import { createApi } from "../endpoints";

describe("success", () => {
  it("parses JSON and calls the right URL", async () => {
    const { api, seen } = apiWith(json({ status: "ok" }));
    await expect(api.health()).resolves.toEqual({ status: "ok" });
    expect(seen[0]).toMatchObject({
      method: "GET",
      url: `${BASE}/api/v1/health`,
    });
  });

  it("serialises query params and JSON bodies", async () => {
    const { api, seen } = apiWith(
      json({ items: [], total: 0, limit: 5, offset: 0 }),
      json({ id: "s1" }, 201),
    );
    await api.listConcepts({ limit: 5, strand: "fractions" });
    await api.submitAttempt("s1", {
      item_id: "i.A.1",
      answer: "a",
      latency_ms: 800,
    });
    expect(seen[0]?.url).toBe(
      `${BASE}/api/v1/concepts?limit=5&strand=fractions`,
    );
    expect(seen[1]).toMatchObject({
      method: "POST",
      url: `${BASE}/api/v1/students/s1/attempts`,
      body: { item_id: "i.A.1", answer: "a", latency_ms: 800 },
    });
  });

  it("encodes path parameters", async () => {
    const { api, seen } = apiWith(json({}));
    await api.getConcept("frac.add/unlike").catch(() => undefined);
    expect(seen[0]?.url).toBe(`${BASE}/api/v1/concepts/frac.add%2Funlike`);
  });
});

describe("ApiError", () => {
  it("is built from the 5D error envelope", async () => {
    const body = envelope("conflict", "finish the open diagnosis first", {
      diagnosis_id: "d1",
    });
    const { api } = apiWith(json(body, 409));
    const err = await api
      .submitAttempt("s1", { item_id: "i", answer: "a" })
      .catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 409,
      code: "conflict",
      message: "finish the open diagnosis first",
      details: { diagnosis_id: "d1" },
    });
  });

  it("carries validation details", async () => {
    const details = [
      {
        loc: ["body", "answer"],
        message: "String should have at least 1 character",
      },
    ];
    const { api } = apiWith(
      json(
        envelope("validation_error", "The request is not valid.", details),
        422,
      ),
    );
    const err = (await api
      .createStudent({})
      .catch((e: unknown) => e)) as ApiError;
    expect(err.code).toBe("validation_error");
    expect(err.details).toEqual(details);
  });

  it("reads Retry-After on a 429", async () => {
    const { api } = apiWith(
      json(envelope("rate_limited", "slow down"), 429, { "retry-after": "7" }),
    );
    const err = (await api.getGraph().catch((e: unknown) => e)) as ApiError;
    expect(err).toMatchObject({
      status: 429,
      code: "rate_limited",
      retryAfterSeconds: 7,
    });
  });

  it("survives a non-JSON error body (proxy HTML page)", async () => {
    const html = new Response("<html>Bad gateway</html>", {
      status: 502,
      headers: { "content-type": "text/html" },
    });
    const { api } = apiWith(html);
    const err = (await api.getStatus().catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 502, code: "http_error" });
  });

  it("treats a 2xx with an empty body as an error, not undefined data", async () => {
    const { api } = apiWith(new Response(null, { status: 200 }));
    await expect(api.getGraph()).rejects.toMatchObject({
      code: "empty_response",
    });
  });

  it("recognises only well-formed envelopes", () => {
    expect(isErrorEnvelope(envelope("x", "y"))).toBe(true);
    for (const bad of [
      null,
      "x",
      {},
      { error: "x" },
      { error: { code: 1, message: "m" } },
    ]) {
      expect(isErrorEnvelope(bad)).toBe(false);
    }
    expect(toApiError(500, undefined)).toMatchObject({
      code: "http_error",
      message: "HTTP 500",
    });
  });
});

describe("NetworkError", () => {
  it("wraps a rejected fetch as 'unreachable'", async () => {
    const { api } = apiWith(new TypeError("fetch failed"));
    const err = await api.getStatus().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(NetworkError);
    expect(err).toMatchObject({ reason: "unreachable" });
    expect(err).not.toBeInstanceOf(ApiError);
  });

  it("times out as 'timeout' when the server never answers", async () => {
    const hang = (): Promise<Response> => new Promise(() => undefined);
    const f = fakeFetch(hang);
    // honour the signal like real fetch does
    const impl: typeof fetch = (input) =>
      new Promise((_resolve, reject) => {
        const req = input as Request;
        req.signal.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
      });
    const api = createApi({ baseUrl: BASE, fetch: impl, timeoutMs: 20 });
    await expect(api.getGraph()).rejects.toMatchObject({
      name: "NetworkError",
      reason: "timeout",
    });
    expect(f.seen).toHaveLength(0);
  });
});

describe("abort", () => {
  it("a caller's abort stays an AbortError (not an ApiError or NetworkError)", async () => {
    const impl: typeof fetch = (input) =>
      new Promise((_resolve, reject) => {
        (input as Request).signal.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        });
      });
    const api = createApi({ baseUrl: BASE, fetch: impl, timeoutMs: 5_000 });
    const ctl = new AbortController();
    const pending = api
      .getGraph({ signal: ctl.signal })
      .catch((e: unknown) => e);
    ctl.abort();
    const err = await pending;
    expect(isAbortError(err)).toBe(true);
    expect(err).not.toBeInstanceOf(NetworkError);
    expect(err).not.toBeInstanceOf(ApiError);
  });

  it("an already-aborted signal never reaches the network", async () => {
    const { api, seen } = apiWith(json({}));
    const ctl = new AbortController();
    ctl.abort();
    const err = await api
      .getGraph({ signal: ctl.signal })
      .catch((e: unknown) => e);
    expect(isAbortError(err)).toBe(true);
    expect(seen).toHaveLength(0);
  });
});

describe("resolveBaseUrl", () => {
  it.each([
    ["http://localhost:8000/api/v1", "http://localhost:8000"],
    ["http://localhost:8000/api/v1/", "http://localhost:8000"],
    ["http://localhost:8000", "http://localhost:8000"],
    ["", ""],
    [undefined, ""],
  ])("%s -> %s", (raw, expected) => {
    expect(resolveBaseUrl(raw)).toBe(expected);
  });
});

describe("zero-network guard", () => {
  it("blocks a bare fetch in every test", () => {
    expect(() => fetch("http://localhost:8000/api/v1/health")).toThrow(
      "Unexpected network call",
    );
  });
});
