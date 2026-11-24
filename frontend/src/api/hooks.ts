/**
 * Server-state hooks (TanStack Query). Queries cancel in-flight requests on unmount and on key change
 * (the `signal` is passed through). Mutations update or invalidate exactly the data they affect.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useContext } from "react";

import { ApiContext } from "./context";
import type { Api, Paging } from "./endpoints";
import type {
  AnswerRequest,
  AttemptCreate,
  AttemptResult,
  Diagnosis,
  DiagnosisState,
  DiagnosisStep,
  Lesson,
  LessonSource,
  Status,
  StepView,
  StepViewRequest,
  Student,
  StudentCreate,
} from "./types";

const CURRICULUM_STALE_MS = 5 * 60_000;

export const queryKeys = {
  status: ["status"] as const,
  eval: ["eval", "latest"] as const,
  concepts: (q: object) => ["concepts", q] as const,
  concept: (id: string) => ["concept", id] as const,
  graph: ["graph"] as const,
  items: (q: object) => ["items", q] as const,
  item: (id: string) => ["item", id] as const,
  student: (id: string) => ["student", id] as const,
  mastery: (studentId: string) => ["mastery", studentId] as const,
  forecast: (studentId: string, conceptId: string, horizon: number) =>
    ["forecast", studentId, conceptId, horizon] as const,
  diagnoses: (studentId: string, state?: DiagnosisState) =>
    ["diagnoses", studentId, state ?? "all"] as const,
  diagnosis: (id: string) => ["diagnosis", id] as const,
  lesson: (id: string) => ["lesson", id] as const,
};

/** Hooks take an `Api` so tests (and 6C stories) can inject a fake; the app uses the shared instance. */
type Deps = { client?: Api };
function useClient(d?: Deps): Api {
  const fromContext = useContext(ApiContext); // tests and stories provide a fake; the app uses the shared client
  return d?.client ?? fromContext;
}

// ---- system ---------------------------------------------------------------------------------
export function useStatus(d?: Deps): UseQueryResult<Status> {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: ({ signal }) => c.getStatus({ signal }),
    refetchInterval: 30_000,
  });
}

export interface FallbackInfo {
  /** Backend answered `/status` and is ready. */
  ready: boolean;
  /** True when lesson text comes only from authored templates (the default). */
  deterministic: boolean;
  fallbackActive: boolean;
  llmModel: string | null;
}

/** Banner data for 6B: is the optional model in play, and is the backend ready at all? */
export function useFallbackInfo(
  d?: Deps,
): FallbackInfo & { status: UseQueryResult<Status>["status"] } {
  const q = useStatus(d);
  const s = q.data;
  return {
    status: q.status,
    ready: s?.status === "ok",
    deterministic: s?.llm_mode !== "model",
    fallbackActive: s?.fallback_active ?? true,
    llmModel: s?.llm_model ?? null,
  };
}

export function useLatestEval(d?: Deps) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.eval,
    queryFn: ({ signal }) => c.latestEval({ signal }),
  });
}

// ---- curriculum -------------------------------------------------------------------------------
export function useConcepts(
  q: Paging & { strand?: string; q?: string } = {},
  d?: Deps,
) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.concepts(q),
    queryFn: ({ signal }) => c.listConcepts(q, { signal }),
    staleTime: CURRICULUM_STALE_MS,
  });
}

export function useConcept(id: string | undefined, d?: Deps) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.concept(id ?? ""),
    queryFn: ({ signal }) => c.getConcept(id ?? "", { signal }),
    enabled: id !== undefined,
    staleTime: CURRICULUM_STALE_MS,
  });
}

export function useGraph(d?: Deps) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.graph,
    queryFn: ({ signal }) => c.getGraph({ signal }),
    staleTime: CURRICULUM_STALE_MS,
  });
}

export function useItems(q: Paging & { concept_id?: string } = {}, d?: Deps) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.items(q),
    queryFn: ({ signal }) => c.listItems(q, { signal }),
    staleTime: CURRICULUM_STALE_MS,
  });
}

export function useItem(id: string | undefined, d?: Deps) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.item(id ?? ""),
    queryFn: ({ signal }) => c.getItem(id ?? "", { signal }),
    enabled: id !== undefined,
    staleTime: CURRICULUM_STALE_MS,
  });
}

// ---- learner state ------------------------------------------------------------------------------
export function useStudent(id: string | undefined, d?: Deps) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.student(id ?? ""),
    queryFn: ({ signal }) => c.getStudent(id ?? "", { signal }),
    enabled: id !== undefined,
  });
}

export function useMastery(studentId: string | undefined, d?: Deps) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.mastery(studentId ?? ""),
    queryFn: ({ signal }) => c.getMastery(studentId ?? "", { signal }),
    enabled: studentId !== undefined,
  });
}

export function useForecast(
  studentId: string | undefined,
  conceptId: string | undefined,
  horizon = 20,
  d?: Deps,
) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.forecast(studentId ?? "", conceptId ?? "", horizon),
    queryFn: ({ signal }) =>
      c.getForecast(
        studentId ?? "",
        { concept_id: conceptId ?? "", horizon },
        { signal },
      ),
    enabled: studentId !== undefined && conceptId !== undefined,
  });
}

export function useStudentDiagnoses(
  studentId: string | undefined,
  state?: DiagnosisState,
  d?: Deps,
) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.diagnoses(studentId ?? "", state),
    queryFn: ({ signal }) =>
      c.listDiagnoses(studentId ?? "", state ? { state } : {}, { signal }),
    enabled: studentId !== undefined,
  });
}

export function useDiagnosis(id: string | undefined, d?: Deps) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.diagnosis(id ?? ""),
    queryFn: ({ signal }) => c.getDiagnosis(id ?? "", { signal }),
    enabled: id !== undefined,
  });
}

export function useLesson(id: string | undefined, d?: Deps) {
  const c = useClient(d);
  return useQuery({
    queryKey: queryKeys.lesson(id ?? ""),
    queryFn: ({ signal }) => c.getLesson(id ?? "", { signal }),
    enabled: id !== undefined,
  });
}

// ---- mutations ----------------------------------------------------------------------------------
/** What an answer changes: mastery, the forecast curves, and the student's diagnosis list. */
function invalidateLearnerState(
  qc: QueryClient,
  studentId: string,
): Promise<unknown> {
  return Promise.all([
    qc.invalidateQueries({ queryKey: queryKeys.mastery(studentId) }),
    qc.invalidateQueries({ queryKey: ["forecast", studentId] }),
    qc.invalidateQueries({ queryKey: ["diagnoses", studentId] }),
  ]);
}

export function useCreateStudent(
  d?: Deps,
): UseMutationResult<Student, Error, StudentCreate> {
  const c = useClient(d);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: StudentCreate) => c.createStudent(body),
    onSuccess: (s) => {
      qc.setQueryData(queryKeys.student(s.id), s);
    },
  });
}

export function useSubmitAttempt(
  studentId: string,
  d?: Deps,
): UseMutationResult<AttemptResult, Error, AttemptCreate> {
  const c = useClient(d);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AttemptCreate) => c.submitAttempt(studentId, body),
    onSuccess: async (res) => {
      if (res.diagnosis)
        qc.setQueryData(queryKeys.diagnosis(res.diagnosis.id), res.diagnosis);
      await invalidateLearnerState(qc, studentId);
    },
  });
}

function useDiagnosisStep(
  kind: "answerProbe" | "answerRecheck",
  d?: Deps,
): UseMutationResult<
  DiagnosisStep,
  Error,
  { diagnosisId: string; body: AnswerRequest }
> {
  const c = useClient(d);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ diagnosisId, body }) => c[kind](diagnosisId, body),
    onSuccess: async (res) => {
      qc.setQueryData(queryKeys.diagnosis(res.diagnosis.id), res.diagnosis);
      await invalidateLearnerState(qc, res.diagnosis.student_id);
    },
  });
}

export const useAnswerProbe = (d?: Deps) => useDiagnosisStep("answerProbe", d);
export const useAnswerRecheck = (d?: Deps) =>
  useDiagnosisStep("answerRecheck", d);

export function useAbandonDiagnosis(
  d?: Deps,
): UseMutationResult<Diagnosis, Error, string> {
  const c = useClient(d);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (diagnosisId: string) => c.abandonDiagnosis(diagnosisId),
    onSuccess: async (res) => {
      qc.setQueryData(queryKeys.diagnosis(res.id), res);
      await invalidateLearnerState(qc, res.student_id);
    },
  });
}

export function useViewLessonStep(
  lessonId: string,
  d?: Deps,
): UseMutationResult<
  StepView,
  Error,
  { position: number; body?: StepViewRequest }
> {
  const c = useClient(d);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ position, body }) =>
      c.viewStep(lessonId, position, body ?? {}),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: queryKeys.lesson(lessonId) });
    },
  });
}

export function useCompleteLesson(
  lessonId: string,
  d?: Deps,
): UseMutationResult<Diagnosis, Error, void> {
  const c = useClient(d);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => c.completeLesson(lessonId),
    onSuccess: async (res) => {
      qc.setQueryData(queryKeys.diagnosis(res.id), res);
      await qc.invalidateQueries({ queryKey: queryKeys.lesson(lessonId) });
    },
  });
}

// ---- fallback / source info for banners (6B/6C) -----------------------------------------------------
export interface SourceSummary {
  /** At least one step was rewritten by the model (fresh or from cache). */
  usesModel: boolean;
  /** The model was tried but its text was rejected, so authored text is shown. */
  anyFallback: boolean;
  counts: Record<LessonSource, number>;
}

export function summarizeSources(lesson: Pick<Lesson, "steps">): SourceSummary {
  const counts: Record<LessonSource, number> = {
    authored: 0,
    model: 0,
    fallback: 0,
    cache: 0,
  };
  for (const s of lesson.steps) if (s.text !== null) counts[s.source] += 1;
  return {
    usesModel: counts.model + counts.cache > 0,
    anyFallback: counts.fallback > 0,
    counts,
  };
}
