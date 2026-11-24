import { ApiError } from "../api/errors";

/**
 * Server-side validation message for one form field, taken from the error envelope, so it can be
 * shown next to that field. Returns null when the error is not about this field.
 */
export function fieldError(error: unknown, field: string): string | null {
  if (!(error instanceof ApiError)) return null;
  if (error.code === "invalid_answer" && field === "answer")
    return error.message;
  if (error.code !== "validation_error" || !Array.isArray(error.details))
    return null;
  const hit = error.details.find((d) => (d.loc ?? []).includes(field));
  return hit ? hit.message : null;
}

/** Mirror of the backend limits for fast feedback. The server stays the authority. */
export const ANSWER_MAX_LENGTH = 200;

export function validateAnswer(raw: string): string | null {
  const v = raw.trim();
  if (v === "") return "Enter an answer.";
  if (v.length > ANSWER_MAX_LENGTH)
    return `Keep it under ${String(ANSWER_MAX_LENGTH)} characters.`;
  return null;
}
