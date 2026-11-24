import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { ApiProvider } from "../api/context";
import type { Api } from "../api/endpoints";
import type { Status } from "../api/types";

/** Render with a fresh query cache (no retries, so failures show immediately) and an in-memory router. */
export function renderApp(ui: ReactElement, route = "/", client?: Api) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    qc,
    ...render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[route]}>
          {client ? <ApiProvider client={client}>{ui}</ApiProvider> : ui}
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

export const readyStatus = (over: Partial<Status> = {}): Status => ({
  status: "ok",
  app_env: "test",
  database_ok: true,
  curriculum_loaded: true,
  curriculum_hash: "abc",
  counts: { concepts: 6 },
  llm_mode: "deterministic",
  fallback_active: true,
  llm_model: null,
  ...over,
});
