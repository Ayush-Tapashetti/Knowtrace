import { QueryClient } from "@tanstack/react-query";

import { ApiError, NetworkError } from "./errors";

const MAX_NETWORK_RETRIES = 2;

/** Server said no (4xx): retrying cannot help. Unreachable/slow server or a 5xx: retry a couple of times. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= MAX_NETWORK_RETRIES) return false;
  if (error instanceof NetworkError) return true;
  return (
    error instanceof ApiError && error.status >= 500 && error.status !== 503
  );
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        staleTime: 0,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}

export const queryClient = createQueryClient();
