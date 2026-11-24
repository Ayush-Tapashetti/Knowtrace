/** One thin function per API operation: path and body only, no logic. Names match the OpenAPI operationIds. */
import {
  createRawClient,
  unwrap,
  type ClientOptions,
  type RawClient,
} from "./client";
import type {
  AnswerRequest,
  AttemptCreate,
  AttemptResult,
  Concept,
  ConceptDetail,
  ConceptPage,
  Diagnosis,
  DiagnosisState,
  DiagnosisStep,
  EvalRun,
  Forecast,
  Graph,
  Health,
  Item,
  ItemPage,
  Lesson,
  Mastery,
  Status,
  StepView,
  StepViewRequest,
  Student,
  StudentCreate,
} from "./types";

type Opts = { signal?: AbortSignal };
export interface Paging {
  limit?: number;
  offset?: number;
}

export function createApi(options?: ClientOptions | RawClient) {
  const c =
    options !== undefined && "GET" in options
      ? options
      : createRawClient(options);
  const P = "/api/v1";
  return {
    // system
    health: (o?: Opts): Promise<Health> =>
      unwrap(c.GET(`${P}/health`, { signal: o?.signal })),
    getStatus: (o?: Opts): Promise<Status> =>
      unwrap(c.GET(`${P}/status`, { signal: o?.signal })),
    latestEval: (o?: Opts): Promise<EvalRun> =>
      unwrap(c.GET(`${P}/eval/latest`, { signal: o?.signal })),

    // curriculum
    listConcepts: (
      q: Paging & { strand?: string; q?: string } = {},
      o?: Opts,
    ): Promise<ConceptPage> =>
      unwrap(
        c.GET(`${P}/concepts`, { params: { query: q }, signal: o?.signal }),
      ),
    getConcept: (conceptId: string, o?: Opts): Promise<ConceptDetail> =>
      unwrap(
        c.GET(`${P}/concepts/{concept_id}`, {
          params: { path: { concept_id: conceptId } },
          signal: o?.signal,
        }),
      ),
    getGraph: (o?: Opts): Promise<Graph> =>
      unwrap(c.GET(`${P}/graph`, { signal: o?.signal })),
    listItems: (
      q: Paging & { concept_id?: string } = {},
      o?: Opts,
    ): Promise<ItemPage> =>
      unwrap(c.GET(`${P}/items`, { params: { query: q }, signal: o?.signal })),
    getItem: (itemId: string, o?: Opts): Promise<Item> =>
      unwrap(
        c.GET(`${P}/items/{item_id}`, {
          params: { path: { item_id: itemId } },
          signal: o?.signal,
        }),
      ),

    // students
    createStudent: (body: StudentCreate, o?: Opts): Promise<Student> =>
      unwrap(c.POST(`${P}/students`, { body, signal: o?.signal })),
    getStudent: (studentId: string, o?: Opts): Promise<Student> =>
      unwrap(
        c.GET(`${P}/students/{student_id}`, {
          params: { path: { student_id: studentId } },
          signal: o?.signal,
        }),
      ),
    getMastery: (studentId: string, o?: Opts): Promise<Mastery> =>
      unwrap(
        c.GET(`${P}/students/{student_id}/mastery`, {
          params: { path: { student_id: studentId } },
          signal: o?.signal,
        }),
      ),
    getForecast: (
      studentId: string,
      q: { concept_id: string; horizon?: number },
      o?: Opts,
    ): Promise<Forecast> =>
      unwrap(
        c.GET(`${P}/students/{student_id}/forecast`, {
          params: { path: { student_id: studentId }, query: q },
          signal: o?.signal,
        }),
      ),
    submitAttempt: (
      studentId: string,
      body: AttemptCreate,
      o?: Opts,
    ): Promise<AttemptResult> =>
      unwrap(
        c.POST(`${P}/students/{student_id}/attempts`, {
          params: { path: { student_id: studentId } },
          body,
          signal: o?.signal,
        }),
      ),
    listDiagnoses: (
      studentId: string,
      q: Paging & { state?: DiagnosisState } = {},
      o?: Opts,
    ): Promise<Diagnosis[]> =>
      unwrap(
        c.GET(`${P}/students/{student_id}/diagnoses`, {
          params: { path: { student_id: studentId }, query: q },
          signal: o?.signal,
        }),
      ),

    // diagnoses
    getDiagnosis: (diagnosisId: string, o?: Opts): Promise<Diagnosis> =>
      unwrap(
        c.GET(`${P}/diagnoses/{diagnosis_id}`, {
          params: { path: { diagnosis_id: diagnosisId } },
          signal: o?.signal,
        }),
      ),
    answerProbe: (
      diagnosisId: string,
      body: AnswerRequest,
      o?: Opts,
    ): Promise<DiagnosisStep> =>
      unwrap(
        c.POST(`${P}/diagnoses/{diagnosis_id}/answer`, {
          params: { path: { diagnosis_id: diagnosisId } },
          body,
          signal: o?.signal,
        }),
      ),
    answerRecheck: (
      diagnosisId: string,
      body: AnswerRequest,
      o?: Opts,
    ): Promise<DiagnosisStep> =>
      unwrap(
        c.POST(`${P}/diagnoses/{diagnosis_id}/recheck`, {
          params: { path: { diagnosis_id: diagnosisId } },
          body,
          signal: o?.signal,
        }),
      ),
    abandonDiagnosis: (diagnosisId: string, o?: Opts): Promise<Diagnosis> =>
      unwrap(
        c.POST(`${P}/diagnoses/{diagnosis_id}/abandon`, {
          params: { path: { diagnosis_id: diagnosisId } },
          signal: o?.signal,
        }),
      ),

    // lessons
    getLesson: (lessonId: string, o?: Opts): Promise<Lesson> =>
      unwrap(
        c.GET(`${P}/lessons/{lesson_id}`, {
          params: { path: { lesson_id: lessonId } },
          signal: o?.signal,
        }),
      ),
    viewStep: (
      lessonId: string,
      position: number,
      body: StepViewRequest = {},
      o?: Opts,
    ): Promise<StepView> =>
      unwrap(
        c.POST(`${P}/lessons/{lesson_id}/steps/{position}/view`, {
          params: { path: { lesson_id: lessonId, position } },
          body,
          signal: o?.signal,
        }),
      ),
    completeLesson: (lessonId: string, o?: Opts): Promise<Diagnosis> =>
      unwrap(
        c.POST(`${P}/lessons/{lesson_id}/complete`, {
          params: { path: { lesson_id: lessonId } },
          signal: o?.signal,
        }),
      ),
  };
}

export type Api = ReturnType<typeof createApi>;
/** App-wide instance (base URL from `VITE_API_BASE_URL`). Tests build their own with `createApi`. */
export const api: Api = createApi();
export type { Concept };
