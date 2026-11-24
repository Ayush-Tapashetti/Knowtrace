const KEY = "knowtrace.studentId";

/** The pseudonymous student id lives in this browser only. Storage can be blocked, so never throw. */
export function readStudentId(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function writeStudentId(id: string): void {
  try {
    window.localStorage.setItem(KEY, id);
  } catch {
    /* private mode: the session simply won't survive a reload */
  }
}

export function clearStudentId(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* nothing to clear */
  }
}
