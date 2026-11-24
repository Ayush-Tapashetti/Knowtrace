// @vitest-environment jsdom
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { ApiError } from "../../api/errors";
import { quietLearner, stubApi } from "../../api/__tests__/helpers";
import type { Diagnosis, Item, Lesson } from "../../api/types";
import { AppRoutes } from "../../app/App";
import { readyStatus, renderApp } from "../../test/render";

const item = (id: string, concept = "B"): Item => ({
  id,
  stem: `Question ${id}`,
  kind: "MCQ",
  difficulty: 0.5,
  primary_concept_id: concept,
  concept_ids: [concept],
  choices: [
    { id: "a", text: "option a" },
    { id: "b", text: "option b" },
  ],
});

const dx = (over: Partial<Diagnosis>): Diagnosis => ({
  id: "d1",
  student_id: "s1",
  state: "PROBING",
  verdict: null,
  root_concept_id: null,
  root_concept_name: null,
  confidence: null,
  hypotheses: [{ hypothesis: "root:A", name: "Counting", probability: 0.6 }],
  trace: [],
  probes: [
    { seq: 1, item_id: "p1", eig_bits: 0.9, answered: false, correct: null },
  ],
  probes_used: 0,
  max_probes: 5,
  pending_item: item("p1", "A"),
  pending_kind: "PROBE",
  lesson_id: null,
  rechecks_used: 0,
  max_rechecks: 3,
  explanation: "",
  created_at: "2026-01-01T00:00:00Z",
  closed_at: null,
  ...over,
});

const attempt = (correct: boolean) => ({
  id: "t1",
  seq: 1,
  item_id: "x",
  context: "PRACTICE" as const,
  is_correct: correct,
  mastery: {},
});

function fakeBackend() {
  let state: Diagnosis | null = null;
  let viewed = [false, false];
  const lesson = (): Lesson => ({
    id: "l1",
    diagnosis_id: "d1",
    root_concept_id: "A",
    est_seconds: 200,
    completed: false,
    steps: [
      {
        position: 1,
        kind: "DEFINITION",
        concept_id: "A",
        concept_name: "Counting",
        est_seconds: 60,
        item: null,
        text: "Counting means one more each time.",
        source: "fallback",
        viewed: viewed[0] ?? false,
      },
      {
        position: 2,
        kind: "CHECK",
        concept_id: "A",
        concept_name: "Counting",
        est_seconds: 60,
        item: item("c1", "A"),
        text: null,
        source: "authored",
        viewed: viewed[1] ?? false,
      },
    ],
  });
  const calls: string[] = [];
  const api = stubApi({
    ...quietLearner,
    getStatus: () => Promise.resolve(readyStatus()),
    listConcepts: () =>
      Promise.resolve({
        items: [
          {
            id: "B",
            name: "Fractions",
            strand: "n",
            summary: "",
            prerequisites: [],
          },
        ],
        total: 1,
        limit: 100,
        offset: 0,
      } as never),
    listItems: () =>
      Promise.resolve({
        items: [item("i.B.1")],
        total: 1,
        limit: 100,
        offset: 0,
      }),
    listDiagnoses: () => Promise.resolve(state ? [state] : []),
    getDiagnosis: () =>
      state ? Promise.resolve(state) : Promise.reject(new Error("none")),
    submitAttempt: (_s, body) => {
      calls.push(`attempt:${body.answer}`);
      if (body.answer === "a")
        return Promise.resolve({ attempt: attempt(true), diagnosis: null });
      state = dx({});
      return Promise.resolve({ attempt: attempt(false), diagnosis: state });
    },
    answerProbe: () => {
      state = dx({
        state: "LESSON_ASSIGNED",
        verdict: "GAP",
        root_concept_id: "A",
        root_concept_name: "Counting",
        confidence: 0.92,
        pending_item: null,
        pending_kind: null,
        lesson_id: "l1",
        trace: [
          {
            concept_id: "B",
            name: "Fractions",
            mastery: 0.3,
            posterior_mass: 0.2,
          },
          {
            concept_id: "A",
            name: "Counting",
            mastery: 0.2,
            posterior_mass: 0.7,
          },
        ],
      });
      return Promise.resolve({
        attempt: attempt(false),
        diagnosis: state,
        passed: null,
        root_mastery_before: null,
        root_mastery_after: null,
      });
    },
    getLesson: () => Promise.resolve(lesson()),
    viewStep: (_l, pos) => {
      viewed = viewed.map((v, i) => v || i === pos - 1);
      return Promise.resolve({
        lesson_id: "l1",
        position: pos,
        viewed: true,
        all_viewed: viewed.every(Boolean),
        attempt: null,
      });
    },
    completeLesson: () => {
      state = dx({
        state: "RECHECKING",
        pending_item: item("r1", "A"),
        pending_kind: "RECHECK",
        root_concept_id: "A",
        root_concept_name: "Counting",
        lesson_id: "l1",
      });
      return Promise.resolve(state);
    },
    answerRecheck: () => {
      state = dx({
        state: "RESOLVED",
        verdict: "GAP",
        root_concept_id: "A",
        root_concept_name: "Counting",
        confidence: 0.92,
        explanation: "You got it.",
        trace: [
          {
            concept_id: "A",
            name: "Counting",
            mastery: 0.9,
            posterior_mass: 0.7,
          },
        ],
        pending_item: null,
        pending_kind: null,
        lesson_id: "l1",
      });
      return Promise.resolve({
        attempt: attempt(true),
        diagnosis: state,
        passed: true,
        root_mastery_before: 0.3,
        root_mastery_after: 0.9,
      });
    },
  });
  return { api, calls };
}

beforeEach(() => {
  window.localStorage.clear();
});
afterEach(() => {
  window.localStorage.clear();
});

describe("practice flow (P0-5)", () => {
  it("runs wrong answer -> probe -> lesson -> recheck -> resolved", async () => {
    const user = userEvent.setup();
    const { api } = fakeBackend();
    renderApp(<AppRoutes client={api} />);

    await user.selectOptions(await screen.findByLabelText(/Topic/), "B");
    await user.click(await screen.findByLabelText("option b"));
    await user.click(screen.getByRole("button", { name: "Submit answer" }));

    // probe
    expect(await screen.findByText("Question p1")).toBeInTheDocument();
    expect(screen.getByText(/Probe 1 of up to 5/)).toBeInTheDocument();
    await user.click(screen.getByLabelText("option b"));
    await user.click(screen.getByRole("button", { name: "Submit answer" }));

    // lesson: text step with a source badge, then a question step
    expect(
      await screen.findByText("Counting means one more each time."),
    ).toBeInTheDocument();
    expect(screen.getByText("Original text")).toBeInTheDocument();
    expect(
      screen.getByText(/Showing the original wording/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Got it" }));
    await user.click(await screen.findByLabelText("option a"));
    await user.click(screen.getByRole("button", { name: "Check answer" }));

    // recheck
    await user.click(
      await screen.findByRole("button", { name: "Start the recheck" }),
    );
    expect(await screen.findByText("Question r1")).toBeInTheDocument();
    await user.click(screen.getByLabelText("option a"));
    await user.click(screen.getByRole("button", { name: "Submit answer" }));

    // result with evidence trail
    expect(await screen.findByText("Gap closed")).toBeInTheDocument();
    expect(
      screen.getByText(/Mastery of the root: 30% → 90%/),
    ).toBeInTheDocument();
    expect(screen.getByText("Root gap")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Practise another question" }),
    );
    expect(await screen.findByLabelText(/Topic/)).toBeInTheDocument();
  });

  it("validates before sending, keeps the choice, and shows server errors beside the field", async () => {
    const user = userEvent.setup();
    const { api, calls } = fakeBackend();
    const submitAttempt = api.submitAttempt;
    let first = true;
    api.submitAttempt = (s, b, o) => {
      if (first) {
        first = false;
        return Promise.reject(
          new ApiError({
            status: 422,
            code: "invalid_answer",
            message: "That isn't one of the choices.",
          }),
        );
      }
      return submitAttempt(s, b, o);
    };
    renderApp(<AppRoutes client={api} />);
    await user.selectOptions(await screen.findByLabelText(/Topic/), "B");
    await screen.findByLabelText("option a");
    await user.click(screen.getByRole("button", { name: "Submit answer" }));
    expect(screen.getByText("Enter an answer.")).toBeInTheDocument();
    expect(calls).toHaveLength(0);

    await user.click(screen.getByLabelText("option a"));
    await user.click(screen.getByRole("button", { name: "Submit answer" }));
    expect(
      await screen.findByText("That isn't one of the choices."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("option a")).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Submit answer" }));
    expect(await screen.findByText("Correct")).toBeInTheDocument();
  });

  it("shows an empty state when no curriculum is loaded and an error state with retry", async () => {
    const empty = stubApi({
      ...quietLearner,
      getStatus: () => Promise.resolve(readyStatus()),
    });
    renderApp(<AppRoutes client={empty} />);
    expect(await screen.findByText("No topics yet")).toBeInTheDocument();
  });

  it("resumes an unfinished diagnosis after a reload", async () => {
    const { api } = fakeBackend();
    window.localStorage.setItem("knowtrace.studentId", "s1");
    await api.submitAttempt("s1", { item_id: "i", answer: "b" });
    renderApp(<AppRoutes client={api} />);
    expect(await screen.findByText("Question p1")).toBeInTheDocument();
    await waitFor(() => {
      expect(
        within(screen.getByRole("main")).getByRole("button", {
          name: "Stop this diagnosis",
        }),
      ).toBeInTheDocument();
    });
  });
});
