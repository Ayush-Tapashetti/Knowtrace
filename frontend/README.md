# KnowTrace frontend

React 19 + Vite + strict TypeScript. Server state via TanStack Query; types generated from the backend contract.

## Commands
| Command | What it does |
|---|---|
| `npm run gen:types` | Regenerate `src/api/schema.d.ts` from `../docs/openapi.json` (re-export the contract first: `python -m knowtrace.cli.export_openapi` in `backend/`) |
| `npm run check:types-fresh` | Fails if `schema.d.ts` is out of date with the contract |
| `npm run typecheck` / `npm run lint` / `npm test` | tsc strict, eslint, vitest |
| `npm run dev` | Dev server (reads `VITE_API_BASE_URL` from the repo-root `.env`) |

## The API seam (`src/api/`)
- `schema.d.ts`: generated, never edited. `types.ts`: friendly aliases.
- `client.ts` / `endpoints.ts`: one function per operation, named after its OpenAPI `operationId`. Pages never call `fetch`.
- `errors.ts`: `ApiError` (server answered with an error), `NetworkError` (unreachable or timed out), aborts stay `AbortError`.
- `hooks.ts`: query and mutation hooks, plus `useFallbackInfo` and `summarizeSources` for banners.
