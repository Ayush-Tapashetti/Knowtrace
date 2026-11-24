/**
 * Friendly aliases over the generated OpenAPI types (`schema.d.ts`).
 * Never hand-write a response shape: add an alias here instead. Regenerate with `npm run gen:types`.
 */
import type { components } from "./schema";

type S = components["schemas"];

// Curriculum
export type Concept = S["ConceptOut"];
export type ConceptDetail = S["ConceptDetailOut"];
export type ConceptPage = S["ConceptPage"];
export type Graph = S["GraphOut"];
export type GraphEdge = S["EdgeOut"];
export type Item = S["ItemOut"];
export type ItemPage = S["ItemPage"];
export type Choice = S["ChoiceOut"];
export type ItemKind = Item["kind"];

// Students, attempts, mastery, forecast
export type Student = S["StudentOut"];
export type StudentCreate = S["StudentCreate"];
export type AttemptCreate = S["AttemptCreate"];
export type AttemptRef = S["AttemptRef"];
export type AttemptResult = S["AttemptResultOut"];
export type AttemptContext = AttemptRef["context"];
export type Mastery = S["MasteryOut"];
export type MasteryPoint = S["MasteryPointOut"];
export type Forecast = S["ForecastOut"];
export type ForecastPoint = S["ForecastPointOut"];

// Diagnosis and lessons
export type Diagnosis = S["DiagnosisOut"];
export type DiagnosisState = Diagnosis["state"];
export type DiagnosisVerdict = NonNullable<Diagnosis["verdict"]>;
export type DiagnosisStep = S["DiagnosisStepOut"];
export type Hypothesis = S["HypothesisOut"];
export type TraceNode = S["TraceNodeOut"];
export type Probe = S["ProbeOut"];
export type AnswerRequest = S["AnswerRequest"];
export type Lesson = S["LessonOut"];
export type LessonStep = S["LessonStepOut"];
export type AtomKind = LessonStep["kind"];
/** Where lesson text came from: authored template, or the optional model (with cache / fallback). */
export type LessonSource = LessonStep["source"];
export type StepViewRequest = S["StepViewRequest"];
export type StepView = S["StepViewOut"];

// System
export type Health = S["HealthOut"];
export type Status = S["StatusOut"];
export type EvalRun = S["EvalOut"];
export type EvalMetric = S["EvalMetricOut"];

// Errors
export type ErrorEnvelope = S["ErrorEnvelope"];
export type ErrorBody = S["ErrorBody"];

/** Diagnosis states in which no further action is possible. */
export const TERMINAL_STATES: readonly DiagnosisState[] = [
  "RESOLVED",
  "UNRESOLVED",
  "SLIP_DISMISSED",
  "INCONCLUSIVE",
  "ABANDONED",
];

export function isTerminal(state: DiagnosisState): boolean {
  return TERMINAL_STATES.includes(state);
}
