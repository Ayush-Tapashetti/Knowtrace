import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/errors";
import { useCreateStudent, useStudent } from "../../api/hooks";
import {
  clearStudentId,
  readStudentId,
  writeStudentId,
} from "../../lib/studentId";

export interface Session {
  studentId: string | null;
  status: "loading" | "ready" | "error";
  error: unknown;
  /** Forget this pseudonym and start a fresh student. */
  restart: () => void;
}

/** One pseudonymous student per browser: created on first visit, re-created if the server forgot it. */
export function useSession(): Session {
  const qc = useQueryClient();
  const [id, setId] = useState<string | null>(() => readStudentId());
  const create = useCreateStudent();
  const student = useStudent(id ?? undefined);
  const creating = useRef(false); // StrictMode runs effects twice; never create two students

  const { mutate, reset } = create;
  useEffect(() => {
    if (id !== null || creating.current) return;
    creating.current = true;
    mutate(
      {},
      {
        onSuccess: (s) => {
          writeStudentId(s.id);
          setId(s.id);
        },
        onSettled: () => {
          creating.current = false;
        },
      },
    );
  }, [id, mutate]);

  const staleId =
    student.error instanceof ApiError && student.error.status === 404;
  if (staleId && id !== null) setId(null); // derived during render: the server forgot this student
  useEffect(() => {
    if (!staleId) return;
    clearStudentId();
    reset();
  }, [staleId, reset]);

  const restart = useCallback(() => {
    clearStudentId();
    qc.clear();
    setId(null);
    reset();
  }, [qc, reset]);

  const error = create.error ?? (staleId ? null : student.error);
  const ready = id !== null && student.isSuccess;
  return {
    studentId: ready ? id : null,
    status: error ? "error" : ready ? "ready" : "loading",
    error,
    restart,
  };
}
