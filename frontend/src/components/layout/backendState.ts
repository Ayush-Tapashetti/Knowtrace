import { ApiError, NetworkError } from "../../api/errors";
import type { Status } from "../../api/types";
import type { BannerTone } from "../ui/Banner";

export type BackendKind =
  | "checking"
  | "ready"
  | "offline"
  | "unreachable"
  | "no-curriculum"
  | "no-database"
  | "error";

export interface BackendState {
  kind: BackendKind;
  /** Short text for the header pill. */
  pill: string;
  banner: {
    tone: BannerTone;
    title: string;
    body: string;
    retry: boolean;
  } | null;
}

/** Turn "what did /status say (or fail with)" into what the learner should see. Pure and testable. */
export function describeBackend(input: {
  online: boolean;
  isPending: boolean;
  data: Status | undefined;
  error: unknown;
}): BackendState {
  const { online, isPending, data, error } = input;
  if (!online) {
    return {
      kind: "offline",
      pill: "Offline",
      banner: {
        tone: "error",
        title: "You're offline",
        body: "Answers can't be saved until your connection comes back.",
        retry: false,
      },
    };
  }
  if (data === undefined && error === null && isPending)
    return { kind: "checking", pill: "Checking server", banner: null };
  if (error instanceof NetworkError) {
    return {
      kind: "unreachable",
      pill: "Server unreachable",
      banner: {
        tone: "error",
        title:
          error.reason === "timeout"
            ? "The server is too slow to respond"
            : "Can't reach the server",
        body: "Start the backend (see the README), then try again. Nothing you did was lost.",
        retry: true,
      },
    };
  }
  if (error instanceof ApiError && error.status === 503) {
    return {
      kind: "no-curriculum",
      pill: "No curriculum",
      banner: {
        tone: "error",
        title: "The server has no curriculum loaded",
        body: "Load the practice content with the seed command, then reload this page.",
        retry: true,
      },
    };
  }
  if (error !== null && error !== undefined) {
    return {
      kind: "error",
      pill: "Server error",
      banner: {
        tone: "error",
        title: "The server reported a problem",
        body:
          error instanceof ApiError ? error.message : "Try again in a moment.",
        retry: true,
      },
    };
  }
  if (data !== undefined && !data.database_ok) {
    return {
      kind: "no-database",
      pill: "Database down",
      banner: {
        tone: "error",
        title: "The server can't reach its database",
        body: "Check the backend logs, then try again.",
        retry: true,
      },
    };
  }
  if (data !== undefined && !data.curriculum_loaded) {
    return {
      kind: "no-curriculum",
      pill: "No curriculum",
      banner: {
        tone: "error",
        title: "The server has no curriculum loaded",
        body: "Load the practice content with the seed command, then reload this page.",
        retry: true,
      },
    };
  }
  return { kind: "ready", pill: "Server ready", banner: null };
}
