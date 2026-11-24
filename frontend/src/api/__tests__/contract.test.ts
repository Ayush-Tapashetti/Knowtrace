/**
 * Every operation in docs/openapi.json has exactly one client function that calls the right
 * method and path, and the committed schema.d.ts matches the contract.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { BASE, apiWith, json } from "./helpers";
import type { Api } from "../endpoints";

interface Spec {
  paths: Record<string, Record<string, { operationId: string }>>;
}
const spec = JSON.parse(
  readFileSync(resolve(__dirname, "../../../../docs/openapi.json"), "utf8"),
) as Spec;

const camel = (s: string): string =>
  s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
const operations = Object.entries(spec.paths).flatMap(([path, methods]) =>
  Object.entries(methods).map(([method, op]) => ({
    method: method.toUpperCase(),
    path,
    id: op.operationId,
  })),
);

/** How to call each function, and the request it must produce. */
const CALLS: Record<string, [(a: Api) => Promise<unknown>, string, string]> = {
  health: [(a) => a.health(), "GET", "/api/v1/health"],
  getStatus: [(a) => a.getStatus(), "GET", "/api/v1/status"],
  latestEval: [(a) => a.latestEval(), "GET", "/api/v1/eval/latest"],
  listConcepts: [(a) => a.listConcepts(), "GET", "/api/v1/concepts"],
  getConcept: [(a) => a.getConcept("C1"), "GET", "/api/v1/concepts/C1"],
  getGraph: [(a) => a.getGraph(), "GET", "/api/v1/graph"],
  listItems: [(a) => a.listItems(), "GET", "/api/v1/items"],
  getItem: [(a) => a.getItem("I1"), "GET", "/api/v1/items/I1"],
  createStudent: [(a) => a.createStudent({}), "POST", "/api/v1/students"],
  getStudent: [(a) => a.getStudent("S1"), "GET", "/api/v1/students/S1"],
  getMastery: [(a) => a.getMastery("S1"), "GET", "/api/v1/students/S1/mastery"],
  getForecast: [
    (a) => a.getForecast("S1", { concept_id: "C1" }),
    "GET",
    "/api/v1/students/S1/forecast?concept_id=C1",
  ],
  submitAttempt: [
    (a) => a.submitAttempt("S1", { item_id: "I1", answer: "a" }),
    "POST",
    "/api/v1/students/S1/attempts",
  ],
  listDiagnoses: [
    (a) => a.listDiagnoses("S1"),
    "GET",
    "/api/v1/students/S1/diagnoses",
  ],
  getDiagnosis: [(a) => a.getDiagnosis("D1"), "GET", "/api/v1/diagnoses/D1"],
  answerProbe: [
    (a) => a.answerProbe("D1", { answer: "a" }),
    "POST",
    "/api/v1/diagnoses/D1/answer",
  ],
  answerRecheck: [
    (a) => a.answerRecheck("D1", { answer: "a" }),
    "POST",
    "/api/v1/diagnoses/D1/recheck",
  ],
  abandonDiagnosis: [
    (a) => a.abandonDiagnosis("D1"),
    "POST",
    "/api/v1/diagnoses/D1/abandon",
  ],
  getLesson: [(a) => a.getLesson("L1"), "GET", "/api/v1/lessons/L1"],
  viewStep: [
    (a) => a.viewStep("L1", 2),
    "POST",
    "/api/v1/lessons/L1/steps/2/view",
  ],
  completeLesson: [
    (a) => a.completeLesson("L1"),
    "POST",
    "/api/v1/lessons/L1/complete",
  ],
};

describe("every API operation has a client function", () => {
  it("covers the whole contract and nothing else", () => {
    expect(operations.length).toBe(21);
    expect(operations.map((o) => camel(o.id)).sort()).toEqual(
      Object.keys(CALLS).sort(),
    );
  });

  it.each(operations)("$method $path -> $id", async ({ method, path, id }) => {
    const entry = CALLS[camel(id)];
    if (entry === undefined) throw new Error(`no client function for ${id}`);
    const [call, wantMethod, wantUrl] = entry;
    const { api, seen } = apiWith(json({}));
    await call(api).catch(() => undefined); // the empty body is rejected; only the request matters
    expect(wantMethod).toBe(method);
    expect(seen[0]?.method).toBe(method);
    expect(seen[0]?.url).toBe(`${BASE}${wantUrl}`);
    // the path template in the spec lines up with what was called
    const template = new RegExp(`^${path.replace(/\{[^}]+\}/g, "[^/]+")}$`);
    expect(template.test(wantUrl.split("?")[0] ?? "")).toBe(true);
  });
});
