# Build status
Project: KnowTrace (placeholder name)
| Step | State | Frozen on | Notes |
|---|---|---|---|
| 1 | frozen | 2026-10-31 | problem + guardrails |
| 2 | frozen | 2026-10-31 | 5 P0, 3 differentiators (D1 eval harness, D2 forecast, D3 deterministic core) |
| 3 | frozen | 2026-10-31 | 15 entities, Diagnosis state machine, pure function contracts (user confirmed) |
| 4 | frozen | 2026-10-31 | Python/FastAPI + SQLModel + SQLite, React 19 + Vite 8 + TS 5.9.3 strict; pins verified (confirmed by moving on to 5A) |
| 5A | frozen | 2026-11-01 | settings, DB core, 15 SQLModel tables; constraints enforced by tests (confirmed) |
| 5B | frozen | 2026-11-01 | pure domain layer (graph, grading, BKT, diagnosis, lesson, state machine, forecast, evalkit); 111 tests, 98% domain coverage, mypy --strict, ruff, purity script clean (confirmed) |
| 5C | frozen | 2026-11-01 | optional LLM rephraser (D3): masking allowlist, client interface + Anthropic + fake, output guard, TTL cache, retry/fallback routing; 211 tests (confirmed by moving on to 5D) |
| 5D | frozen | 2026-11-01 | repositories, services, schemas, 21 endpoints under /api/v1, error envelope, rate limit, CORS, seed + OpenAPI CLIs; contract at docs/openapi.json; 258 tests, 97% coverage, mypy --strict, ruff, 6 import-linter contracts kept; confirmed by moving on to 6A |
| 6A | frozen | 2026-11-02 | typed seam: generated types, openapi-fetch client (ApiError/NetworkError/timeout/abort), 21 endpoint functions, TanStack Query hooks; 67 Vitest tests, tsc strict + eslint clean; confirmed by moving on to 6B |
| 6B | frozen | 2026-11-03 | shell (header, top nav + phone tab bar, 404), persistent disclaimer, status pill and banners (offline, unreachable, no curriculum, model on), Button/Card/Badge/Banner/Field/Input, Loading/Empty/Error states, ErrorBoundary; tokens in index.css; 94 Vitest tests, tsc strict + eslint clean, checked in a real browser at 1280 and 390 px with the API up and down; confirmed by moving on to 6C |
| 6C | frozen | 2026-11-03 | Practice flow (topic, question, probes, evidence trail, lesson with source badges, recheck, result, resume after reload, stop), Knowledge map (React Flow + dagre heat bands, table alternative, concept detail, forecast chart with text summary), Evaluation (method table, best-per-metric, reliability chart, 404 empty state); 106 Vitest tests, tsc strict, eslint, build clean; P0-5 flow walked in a real browser against the real backend: 18/18 checks pass on the 6-concept fixture |
| 7 | frozen | 2026-11-04 | 291 backend tests (97% coverage), 108 frontend tests, contract script OK on all 21 operations, run_eval gate passes (top-1 64.7% vs 35.0% and 26.0% baselines), real-browser walkthrough on the 47-concept seed; report in 07-verification.md; known gap: inconclusive diagnoses on some cold-start gaps |

Open notes: TypeScript pinned to 5.9.3 (7.x breaks typescript-eslint and openapi-typescript peers). 12 moderate npm-audit findings are dev-tooling only.

Resolved in Step 7: seed curriculum (47 concepts, 188 items, 282 atoms) and `run_eval` now exist; `GET /eval/latest` serves the saved run.
