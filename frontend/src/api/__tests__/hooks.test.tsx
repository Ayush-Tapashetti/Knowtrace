// @vitest-environment jsdom
import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { ApiError, NetworkError } from "../errors";
import {
  queryKeys,
  summarizeSources,
  useAnswerProbe,
  useFallbackInfo,
  useGraph,
  useMastery,
  useSubmitAttempt,
} from "../hooks";
import { createQueryClient, shouldRetry } from "../queryClient";
import type {
  AttemptResult,
  Diagnosis,
  DiagnosisStep,
  Graph,
  Status,
} from "../types";
import { stubApi } from "./helpers";

function setup(): {
  qc: QueryClient;
  wrapper: (p: { children: ReactNode }) => ReactNode;
} {
  const qc = createQueryClient();
  return {
    qc,
    wrapper: ({ children }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    ),
  };
}

const status = (over: Partial<Status> = {}): Status => ({
  status: "ok",
  app_env: "test",
  database_ok: true,
  curriculum_loaded: true,
  curriculum_hash: "h",
  counts: {},
  llm_mode: "deterministic",
  fallback_active: true,
  llm_model: null,
  ...over,
});

const diagnosis = (over: Partial<Diagnosis> = {}): Diagnosis => ({
  id: "d1",
  student_id: "s1",
  state: "PROBING",
  verdict: null,
  root_concept_id: null,
  root_concept_name: null,
  confidence: null,
  hypotheses: [],
  trace: [],
  probes: [],
  probes_used: 0,
  max_probes: 4,
  pending_item: null,
  pending_kind: null,
  lesson_id: null,
  rechecks_used: 0,
  max_rechecks: 3,
  explanation: "",
  created_at: "2026-11-01T00:00:00Z",
  closed_at: null,
  ...over,
});

describe("useFallbackInfo", () => {
  it("reports deterministic mode and readiness from /status", async () => {
    const { wrapper } = setup();
    const client = stubApi({ getStatus: () => Promise.resolve(status()) });
    const { result } = renderHook(() => useFallbackInfo({ client }), {
      wrapper,
    });
    await waitFor(() => {
      expect(result.current.status).toBe("success");
    });
    expect(result.current).toMatchObject({
      ready: true,
      deterministic: true,
      fallbackActive: true,
      llmModel: null,
    });
  });

  it("reports model mode, and not-ready when the backend is degraded", async () => {
    const { wrapper } = setup();
    const client = stubApi({
      getStatus: () =>
        Promise.resolve(
          status({
            status: "degraded",
            llm_mode: "model",
            fallback_active: false,
            llm_model: "m",
          }),
        ),
    });
    const { result } = renderHook(() => useFallbackInfo({ client }), {
      wrapper,
    });
    await waitFor(() => {
      expect(result.current.status).toBe("success");
    });
    expect(result.current).toMatchObject({
      ready: false,
      deterministic: false,
      fallbackActive: false,
      llmModel: "m",
    });
  });

  it("is not ready while loading or when the server is unreachable", async () => {
    const { wrapper } = setup();
    const client = stubApi({
      getStatus: () =>
        Promise.reject(
          new ApiError({ status: 503, code: "not_ready", message: "x" }),
        ),
    });
    const { result } = renderHook(() => useFallbackInfo({ client }), {
      wrapper,
    });
    expect(result.current.ready).toBe(false);
    await waitFor(() => {
      expect(result.current.status).toBe("error");
    });
    expect(result.current.ready).toBe(false);
  });
});

describe("queries", () => {
  it("cancel the in-flight request on unmount", async () => {
    const { wrapper } = setup();
    let signal: AbortSignal | undefined;
    const client = stubApi({
      getGraph: (o) => {
        signal = o?.signal;
        return new Promise<Graph>(() => undefined);
      },
    });
    const { unmount } = renderHook(() => useGraph({ client }), { wrapper });
    await waitFor(() => {
      expect(signal).toBeDefined();
    });
    expect(signal?.aborted).toBe(false);
    unmount();
    await waitFor(() => {
      expect(signal?.aborted).toBe(true);
    });
  });

  it("expose an ApiError without retrying a 4xx", async () => {
    const { wrapper } = setup();
    const getMastery = vi.fn(() =>
      Promise.reject(
        new ApiError({ status: 404, code: "not_found", message: "no student" }),
      ),
    );
    const { result } = renderHook(
      () => useMastery("s1", { client: stubApi({ getMastery }) }),
      { wrapper },
    );
    await waitFor(() => {
      expect(result.current.status).toBe("error");
    });
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect(getMastery).toHaveBeenCalledTimes(1);
  });

  it("stay idle until an id exists", () => {
    const { wrapper } = setup();
    const getMastery = vi.fn();
    const { result } = renderHook(
      () => useMastery(undefined, { client: stubApi({ getMastery }) }),
      { wrapper },
    );
    expect(result.current.fetchStatus).toBe("idle");
    expect(getMastery).not.toHaveBeenCalled();
  });
});

describe("retry policy", () => {
  it("retries unreachable servers and 5xx a couple of times, never 4xx", () => {
    expect(shouldRetry(0, new NetworkError("unreachable"))).toBe(true);
    expect(shouldRetry(1, new NetworkError("timeout"))).toBe(true);
    expect(shouldRetry(2, new NetworkError("unreachable"))).toBe(false);
    expect(
      shouldRetry(
        0,
        new ApiError({ status: 500, code: "internal_error", message: "" }),
      ),
    ).toBe(true);
    for (const status of [400, 404, 409, 422, 429, 503]) {
      expect(
        shouldRetry(0, new ApiError({ status, code: "x", message: "" })),
      ).toBe(false);
    }
    expect(shouldRetry(0, new Error("bug"))).toBe(false);
  });
});

describe("mutations", () => {
  it("a wrong attempt seeds the diagnosis cache and refreshes mastery, forecasts and diagnoses", async () => {
    const { qc, wrapper } = setup();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const result_: AttemptResult = {
      attempt: {
        id: "a1",
        seq: 1,
        item_id: "i",
        context: "PRACTICE",
        is_correct: false,
        mastery: { A: 0.2 },
      },
      diagnosis: diagnosis(),
    };
    const client = stubApi({ submitAttempt: () => Promise.resolve(result_) });
    const { result } = renderHook(() => useSubmitAttempt("s1", { client }), {
      wrapper,
    });
    await act(() => result.current.mutateAsync({ item_id: "i", answer: "b" }));
    expect(qc.getQueryData(queryKeys.diagnosis("d1"))).toEqual(
      result_.diagnosis,
    );
    const keys = spy.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toEqual(
      expect.arrayContaining([
        JSON.stringify(queryKeys.mastery("s1")),
        JSON.stringify(["forecast", "s1"]),
        JSON.stringify(["diagnoses", "s1"]),
      ]),
    );
  });

  it("a correct attempt (no diagnosis) still refreshes learner state", async () => {
    const { qc, wrapper } = setup();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const client = stubApi({
      submitAttempt: () =>
        Promise.resolve({
          attempt: {
            id: "a",
            seq: 1,
            item_id: "i",
            context: "PRACTICE",
            is_correct: true,
            mastery: {},
          },
          diagnosis: null,
        }),
    });
    const { result } = renderHook(() => useSubmitAttempt("s1", { client }), {
      wrapper,
    });
    await act(() => result.current.mutateAsync({ item_id: "i", answer: "a" }));
    expect(qc.getQueryData(queryKeys.diagnosis("d1"))).toBeUndefined();
    expect(spy).toHaveBeenCalled();
  });

  it("surfaces a mutation error and does not retry", async () => {
    const { wrapper } = setup();
    const submitAttempt = vi.fn(() =>
      Promise.reject(
        new ApiError({ status: 409, code: "conflict", message: "open" }),
      ),
    );
    const { result } = renderHook(
      () => useSubmitAttempt("s1", { client: stubApi({ submitAttempt }) }),
      { wrapper },
    );
    await act(async () => {
      await result.current
        .mutateAsync({ item_id: "i", answer: "a" })
        .catch(() => undefined);
    });
    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(ApiError);
    });
    expect(result.current.isPending).toBe(false);
    expect(submitAttempt).toHaveBeenCalledTimes(1);
  });

  it("a probe answer replaces the cached diagnosis", async () => {
    const { qc, wrapper } = setup();
    const next = diagnosis({ state: "LESSON_ASSIGNED", lesson_id: "l1" });
    const step: DiagnosisStep = {
      attempt: {
        id: "a",
        seq: 2,
        item_id: "i",
        context: "PROBE",
        is_correct: false,
        mastery: {},
      },
      diagnosis: next,
      passed: null,
      root_mastery_before: null,
      root_mastery_after: null,
    };
    const client = stubApi({ answerProbe: () => Promise.resolve(step) });
    const { result } = renderHook(() => useAnswerProbe({ client }), {
      wrapper,
    });
    await act(() =>
      result.current.mutateAsync({ diagnosisId: "d1", body: { answer: "b" } }),
    );
    expect(qc.getQueryData(queryKeys.diagnosis("d1"))).toEqual(next);
  });
});

describe("summarizeSources", () => {
  const step = (
    source: "authored" | "model" | "fallback" | "cache",
    text: string | null,
  ) => ({
    position: 1,
    concept_id: "A",
    concept_name: "A",
    kind: "DEFINITION" as const,
    est_seconds: 30,
    text,
    source,
    item: null,
    viewed: false,
  });

  it("flags model use and fallbacks, ignoring steps without text", () => {
    expect(
      summarizeSources({
        steps: [step("authored", "x"), step("authored", "y")],
      }),
    ).toMatchObject({
      usesModel: false,
      anyFallback: false,
      counts: { authored: 2 },
    });
    expect(
      summarizeSources({
        steps: [step("model", "x"), step("cache", "y"), step("authored", null)],
      }),
    ).toMatchObject({
      usesModel: true,
      anyFallback: false,
      counts: { model: 1, cache: 1, authored: 0 },
    });
    expect(summarizeSources({ steps: [step("fallback", "x")] })).toMatchObject({
      usesModel: false,
      anyFallback: true,
    });
  });
});
