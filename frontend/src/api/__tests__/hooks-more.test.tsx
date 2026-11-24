// @vitest-environment jsdom
import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  queryKeys,
  useAbandonDiagnosis,
  useAnswerRecheck,
  useCompleteLesson,
  useConcept,
  useConcepts,
  useCreateStudent,
  useDiagnosis,
  useForecast,
  useItem,
  useItems,
  useLatestEval,
  useLesson,
  useStudent,
  useStudentDiagnoses,
  useViewLessonStep,
} from "../hooks";
import { createQueryClient } from "../queryClient";
import { isTerminal, type Diagnosis } from "../types";
import { stubApi } from "./helpers";

const wrap = () => {
  const qc = createQueryClient();
  return {
    qc,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    ),
  };
};
const dx = { id: "d1", student_id: "s1", state: "ABANDONED" } as Diagnosis;

describe("read hooks call the matching endpoint with their arguments", () => {
  type C = ReturnType<typeof stubApi>;
  const cases: Array<
    [string, (c: C) => { status: string }, keyof C, unknown[]]
  > = [
    [
      "useConcepts",
      (c) => useConcepts({ limit: 5 }, { client: c }),
      "listConcepts",
      [{ limit: 5 }],
    ],
    [
      "useConcept",
      (c) => useConcept("C1", { client: c }),
      "getConcept",
      ["C1"],
    ],
    [
      "useItems",
      (c) => useItems({ concept_id: "C1" }, { client: c }),
      "listItems",
      [{ concept_id: "C1" }],
    ],
    ["useItem", (c) => useItem("I1", { client: c }), "getItem", ["I1"]],
    [
      "useStudent",
      (c) => useStudent("s1", { client: c }),
      "getStudent",
      ["s1"],
    ],
    [
      "useForecast",
      (c) => useForecast("s1", "C1", 7, { client: c }),
      "getForecast",
      ["s1", { concept_id: "C1", horizon: 7 }],
    ],
    [
      "useStudentDiagnoses",
      (c) => useStudentDiagnoses("s1", "PROBING", { client: c }),
      "listDiagnoses",
      ["s1", { state: "PROBING" }],
    ],
    [
      "useDiagnosis",
      (c) => useDiagnosis("d1", { client: c }),
      "getDiagnosis",
      ["d1"],
    ],
    ["useLesson", (c) => useLesson("l1", { client: c }), "getLesson", ["l1"]],
    ["useLatestEval", (c) => useLatestEval({ client: c }), "latestEval", []],
  ];

  it.each(cases)("%s", async (_name, hook, fn, args) => {
    const spy = vi.fn(() => Promise.resolve({}));
    const client = stubApi({ [fn]: spy });
    const { wrapper } = wrap();
    const { result } = renderHook(() => hook(client), { wrapper });
    await waitFor(() => {
      expect(result.current.status).toBe("success");
    });
    expect(spy.mock.calls[0]?.slice(0, args.length)).toEqual(args);
  });
});

describe("write hooks", () => {
  it("abandon stores the closed diagnosis", async () => {
    const { qc, wrapper } = wrap();
    const { result } = renderHook(
      () =>
        useAbandonDiagnosis({
          client: stubApi({ abandonDiagnosis: () => Promise.resolve(dx) }),
        }),
      { wrapper },
    );
    await act(() => result.current.mutateAsync("d1"));
    expect(qc.getQueryData(queryKeys.diagnosis("d1"))).toEqual(dx);
  });

  it("recheck answers replace the cached diagnosis", async () => {
    const { qc, wrapper } = wrap();
    const step = {
      attempt: {},
      diagnosis: dx,
      passed: false,
      root_mastery_before: 0.2,
      root_mastery_after: 0.4,
    };
    const client = stubApi({
      answerRecheck: () => Promise.resolve(step as never),
    });
    const { result } = renderHook(() => useAnswerRecheck({ client }), {
      wrapper,
    });
    await act(() =>
      result.current.mutateAsync({ diagnosisId: "d1", body: { answer: "a" } }),
    );
    expect(qc.getQueryData(queryKeys.diagnosis("d1"))).toEqual(dx);
  });

  it("viewing a step and completing a lesson refresh the lesson", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const client = stubApi({
      viewStep: () =>
        Promise.resolve({
          lesson_id: "l1",
          position: 1,
          viewed: true,
          attempt: null,
          all_viewed: true,
        }),
      completeLesson: () => Promise.resolve(dx),
    });
    const view = renderHook(() => useViewLessonStep("l1", { client }), {
      wrapper,
    });
    await act(() => view.result.current.mutateAsync({ position: 1 }));
    const done = renderHook(() => useCompleteLesson("l1", { client }), {
      wrapper,
    });
    await act(() => done.result.current.mutateAsync());
    expect(spy).toHaveBeenCalledWith({ queryKey: queryKeys.lesson("l1") });
    expect(qc.getQueryData(queryKeys.diagnosis("d1"))).toEqual(dx);
  });

  it("creating a student caches it", async () => {
    const { qc, wrapper } = wrap();
    const s = { id: "s1", pseudonym: "student-1", created_at: "t" };
    const { result } = renderHook(
      () =>
        useCreateStudent({
          client: stubApi({ createStudent: () => Promise.resolve(s) }),
        }),
      { wrapper },
    );
    await act(() => result.current.mutateAsync({}));
    expect(qc.getQueryData(queryKeys.student("s1"))).toEqual(s);
  });
});

describe("isTerminal", () => {
  it("is true only for closed states", () => {
    expect(
      [
        "RESOLVED",
        "UNRESOLVED",
        "SLIP_DISMISSED",
        "INCONCLUSIVE",
        "ABANDONED",
      ].every((s) => isTerminal(s as never)),
    ).toBe(true);
    expect(
      ["PROBING", "LESSON_ASSIGNED", "RECHECKING"].some((s) =>
        isTerminal(s as never),
      ),
    ).toBe(false);
  });
});
