// @vitest-environment jsdom
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { ApiError } from "../../api/errors";
import { quietLearner, stubApi } from "../../api/__tests__/helpers";
import { AppRoutes } from "../../app/App";
import { readyStatus, renderApp } from "../../test/render";
import { buildTable, reliabilityBins } from "../eval/evalModel";
import { bandOf } from "../graph/heat";
import { layoutGraph } from "../graph/layout";

const node = (
  id: string,
  name: string,
  tier: number,
  prerequisites: string[] = [],
) => ({
  id,
  name,
  tier,
  prerequisites,
  strand: "number",
  description: `${name} desc`,
});
const point = (id: string, name: string, p: number, n = 3) => ({
  concept_id: id,
  name,
  p_mastery: p,
  mastered: p >= 0.85,
  n_obs: n,
  last_observed_at: null,
});

const base = stubApi({
  ...quietLearner,
  getStatus: () => Promise.resolve(readyStatus()),
  getGraph: () =>
    Promise.resolve({
      curriculum_hash: "h",
      nodes: [node("A", "Counting", 0), node("B", "Fractions", 1, ["A"])],
      edges: [{ prerequisite: "A", dependent: "B" }],
    }),
  getMastery: () =>
    Promise.resolve({
      student_id: "s1",
      theta_master: 0.85,
      concepts: [point("A", "Counting", 0.9), point("B", "Fractions", 0.2)],
    }),
  getConcept: (id) =>
    Promise.resolve({
      ...node(id, id === "A" ? "Counting" : "Fractions", 0),
      ancestors: {},
      dependents: id === "A" ? ["B"] : [],
      item_count: 3,
    }),
  getForecast: () =>
    Promise.resolve({
      student_id: "s1",
      concept_id: "B",
      concept_name: "Fractions",
      current_mastery: 0.2,
      p_next_correct: 0.4,
      theta_master: 0.85,
      steps_to_mastery: 7,
      points: [
        { step: 0, p_mastery: 0.2, p_lo: 0.1, p_hi: 0.3 },
        { step: 1, p_mastery: 0.3, p_lo: 0.2, p_hi: 0.4 },
      ],
    }),
});

beforeEach(() => {
  window.localStorage.clear();
});

describe("heat bands", () => {
  it("maps mastery to five named bands", () => {
    expect(bandOf(undefined).key).toBe("unseen");
    expect(bandOf(point("x", "x", 0.5, 0)).key).toBe("unseen");
    expect(bandOf(point("x", "x", 0.2)).key).toBe("weak");
    expect(bandOf(point("x", "x", 0.5)).key).toBe("building");
    expect(bandOf(point("x", "x", 0.75)).key).toBe("good");
    expect(bandOf(point("x", "x", 0.95)).key).toBe("mastered");
  });
});

describe("layout", () => {
  it("places prerequisites above their dependents", () => {
    const pos = layoutGraph(
      ["A", "B", "C"],
      [
        { prerequisite: "A", dependent: "B" },
        { prerequisite: "B", dependent: "C" },
      ],
    );
    expect(pos.get("A")?.y).toBeLessThan(pos.get("B")?.y ?? 0);
    expect(pos.get("B")?.y).toBeLessThan(pos.get("C")?.y ?? 0);
  });
});

describe("knowledge map page (P0-5 heatmap)", () => {
  it("shows the table view with mastery levels, and detail with forecast text for a chosen concept", async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes client={base} />, "/map");
    await user.click(await screen.findByRole("button", { name: "Table" }));
    const row = await screen.findByRole("row", { name: /Fractions/ });
    expect(within(row).getByText("20%")).toBeInTheDocument();
    expect(within(row).getByText("Weak (under 40%)")).toBeInTheDocument();
    await user.click(within(row).getByRole("button", { name: "Fractions" }));
    expect(
      (await screen.findAllByText(/about 7 more questions/)).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Fractions desc")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Filter concepts"), "zzz");
    expect(screen.getByText(/No concept matches/)).toBeInTheDocument();
  });

  it("shows an error with retry when the graph fails", async () => {
    const failing = stubApi({
      ...base,
      getGraph: () =>
        Promise.reject(
          new ApiError({
            status: 503,
            code: "curriculum_not_loaded",
            message: "No curriculum.",
          }),
        ),
    });
    renderApp(<AppRoutes client={failing} />, "/map");
    expect(
      await screen.findByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
  });

  it("shows an empty state for an empty curriculum", async () => {
    const empty = stubApi({
      ...base,
      getGraph: () =>
        Promise.resolve({ curriculum_hash: "h", nodes: [], edges: [] }),
    });
    renderApp(<AppRoutes client={empty} />, "/map");
    expect(
      await screen.findByText("The curriculum is empty"),
    ).toBeInTheDocument();
  });
});

const run = {
  run_id: "r1",
  created_at: "2026-01-01T00:00:00Z",
  curriculum_hash: "h",
  n_students: 50,
  seed: 7,
  metrics: [
    { method: "graph_bayes", metric: "top1", value: 0.82, n: 50, detail: null },
    {
      method: "baseline_parent",
      metric: "top1",
      value: 0.41,
      n: 50,
      detail: null,
    },
    {
      method: "graph_bayes",
      metric: "brier",
      value: 0.12,
      n: 50,
      detail: null,
    },
    {
      method: "baseline_parent",
      metric: "brier",
      value: 0.2,
      n: 50,
      detail: null,
    },
    {
      method: "graph_bayes",
      metric: "reliability",
      value: 0.03,
      n: 50,
      detail: {
        bins: [{ p_pred_mean: 0.2, p_obs_mean: 0.25, count: 10 }, { bad: 1 }],
      },
    },
  ],
};

describe("evaluation page (D1, D2)", () => {
  it("flags the best value per metric and reads reliability bins defensively", () => {
    const rows = buildTable(run);
    expect(rows[0]?.method).toBe("graph_bayes");
    expect(rows[0]?.cells.find((c) => c.metric.key === "top1")?.best).toBe(
      true,
    );
    expect(rows[1]?.cells.find((c) => c.metric.key === "brier")?.best).toBe(
      false,
    );
    expect(reliabilityBins(run.metrics)).toEqual([
      { predicted: 0.2, observed: 0.25, count: 10 },
    ]);
  });

  it("never ticks a baseline for not probing, and ticks ties that display the same", () => {
    const rows = buildTable({
      metrics: [
        {
          method: "graph_bayes",
          metric: "probes_mean",
          value: 3.5,
          n: 5,
          detail: null,
        },
        {
          method: "baseline_parent",
          metric: "probes_mean",
          value: 0,
          n: 5,
          detail: null,
        },
        {
          method: "graph_bayes",
          metric: "auc",
          value: 0.7101,
          n: 5,
          detail: null,
        },
        {
          method: "baseline_flat_bkt",
          metric: "auc",
          value: 0.7099,
          n: 5,
          detail: null,
        },
      ],
    });
    const cell = (m: string, k: string) =>
      rows.find((r) => r.method === m)?.cells.find((c) => c.metric.key === k);
    expect(cell("baseline_parent", "probes_mean")?.value).toBeNull();
    expect(cell("graph_bayes", "probes_mean")?.best).toBe(true);
    expect(cell("graph_bayes", "auc")?.best).toBe(true);
    expect(cell("baseline_flat_bkt", "auc")?.best).toBe(true);
  });

  it("renders the comparison table and calibration summary", async () => {
    renderApp(
      <AppRoutes
        client={stubApi({ ...base, latestEval: () => Promise.resolve(run) })}
      />,
      "/evaluation",
    );
    expect(
      await screen.findByText("KnowTrace (graph + Bayes)"),
    ).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(
      screen.getByText(/Forecast calibration: across 1 groups/),
    ).toBeInTheDocument();
  });

  it("explains how to produce results when none exist (404)", async () => {
    const none = stubApi({
      ...base,
      latestEval: () =>
        Promise.reject(
          new ApiError({ status: 404, code: "not_found", message: "none" }),
        ),
    });
    renderApp(<AppRoutes client={none} />, "/evaluation");
    expect(
      await screen.findByText("No evaluation has been run yet"),
    ).toBeInTheDocument();
  });
});
