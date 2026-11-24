# RUNNING.md: how to run KnowTrace

Everything below is run from the **repo root** (the folder that contains `backend/`, `frontend/` and `docs/`).
You need **Python 3.11 or newer** (built and tested on 3.13) and **Node 20 or newer** with npm.

## 1. One-time setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.lock     # runtime + dev tools + the optional model SDK
cd ..
```

### Frontend

```bash
cd frontend
npm install
cd ..
```

### Settings (optional)

Defaults work as is. To change anything, copy the example file and edit it (it is gitignored):

```bash
cp .env.example .env
```

Leave `ANTHROPIC_API_KEY` empty and `DETERMINISTIC_ONLY=true`: the whole app, including diagnosis and lessons, runs with no model and no network.

## 2. Run the app (two terminals)

### Terminal 1: backend API on http://localhost:8000

```bash
source backend/.venv/bin/activate
PYTHONPATH=backend/src uvicorn knowtrace.main:create_app --factory --port 8000
```

On first start it creates `data/knowtrace.db` and loads the 47-concept curriculum from `backend/content/seed`.
Check it: open http://localhost:8000/api/v1/status (look for `"curriculum_loaded": true`) or the interactive docs at http://localhost:8000/docs.

### Terminal 2: frontend on http://localhost:5173

```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

Open **http://localhost:5173** (use `localhost`, not `127.0.0.1`: the API only allows the `localhost` origin).

### Optional: fill the Evaluation page

The Evaluation page shows "No evaluation has been run yet" until you run this (about 3 seconds):

```bash
source backend/.venv/bin/activate
PYTHONPATH=backend/src python -m knowtrace.cli.run_eval
```

It prints the comparison table and calibration, saves the run, and exits non-zero if the quality gates fail. Useful flags: `--students 300`, `--seed 7`, `--no-save`.

## 3. Try the demo flow

1. Practice page: pick a topic (for example *Adding fractions with different denominators*) and answer a question wrongly on purpose.
2. Answer the probe questions. The app finds the root gap and shows the evidence trail.
3. Work through the short lesson, then the recheck.
4. Open **Knowledge map** to see mastery colours and a forecast per concept, and **Evaluation** for accuracy against two baselines.

"Start over as a new student" on the Practice page resets your pseudonymous profile.

## 4. Tests and checks

### Backend (291 tests, network blocked)

```bash
source backend/.venv/bin/activate
cd backend
PYTHONPATH=src pytest                              # all tests
PYTHONPATH=src pytest --cov=knowtrace              # with coverage
ruff check . && ruff format --check .              # lint and format
PYTHONPATH=src mypy                                # strict types
PYTHONPATH=src lint-imports                        # layering rules
PYTHONPATH=src python -m tests.api.contract_check --frontend   # API contract vs docs/openapi.json + frontend types
cd ..
```

### Frontend (108 tests)

```bash
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
npm run check:types-fresh      # generated API types match docs/openapi.json
cd ..
```

## 5. When the API contract changes

```bash
source backend/.venv/bin/activate
PYTHONPATH=backend/src python -m knowtrace.cli.export_openapi    # rewrites docs/openapi.json
cd frontend && npm run gen:types                                 # regenerates src/api/schema.d.ts
```

## 6. Reload or reset the data

```bash
# reload the curriculum after editing backend/content/seed
PYTHONPATH=backend/src python -m knowtrace.cli.seed

# wipe everything (students, attempts, eval runs) and start fresh
rm -rf data
```

To regenerate the seed files themselves: `cd backend && python content/build_seed.py`.

## 7. Optional: AI rewording of lesson text

Off by default. Diagnosis and lesson choice are never done by the model. To try rewording, put this in `.env` and restart the backend:

```
DETERMINISTIC_ONLY=false
LLM_REPHRASE_ENABLED=true
ANTHROPIC_API_KEY=your-key
```

Reworded steps show a "Reworded by AI" badge. If the model fails or the guard rejects its text, the hand-written text is used and the badge says "Original text". Student names and ids are masked before anything is sent.

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| Page says "Can't reach the server" | Backend is not running, or you opened `127.0.0.1:5173`. Use `localhost` for both. |
| `ModuleNotFoundError: knowtrace` | Add `PYTHONPATH=backend/src` (or `PYTHONPATH=src` when inside `backend/`). |
| "No topics yet" or "curriculum is empty" | Start the API from the repo root so `./backend/content/seed` resolves, or set `CURRICULUM_DIR`. |
| Evaluation page is empty | Run `python -m knowtrace.cli.run_eval` (section 2). |
| 409 when answering | A diagnosis is open. Finish it or press "Stop this diagnosis". |
| 429 Too many requests | Rate limit (120/min). Wait a few seconds or raise `RATE_LIMIT_PER_MINUTE`. |
| Docker: `web` waits forever | `docker compose logs api`; the API must report healthy first. |
| Port already in use | Use `--port 8001` and set `VITE_API_BASE_URL=http://localhost:8001` in `frontend/.env`. |

## 9. Run with Docker (one command)

Needs Docker with Compose. From the repo root:

```bash
docker compose up --build
```

Then open **http://localhost:8080**. The `web` container (nginx) serves the app and forwards `/api/` to the `api` container, so there is no CORS setup and nothing else to install. The API is not published to your machine by default (uncomment the `ports` line for `api` in `docker-compose.yml` to reach it at http://localhost:8000/docs).

```bash
docker compose up --build -d          # run in the background
docker compose logs -f api            # follow API logs
docker compose ps                     # health status of both containers
docker compose down                   # stop (data is kept)
docker compose down -v                # stop and delete the database volume

# fill the Evaluation page (runs inside the api container)
docker compose exec api python -m knowtrace.cli.run_eval

```

Data lives in the `knowtrace-data` volume (SQLite at `/data/knowtrace.db`). To try AI rewording, export the three variables before starting:

```bash
export DETERMINISTIC_ONLY=false LLM_REPHRASE_ENABLED=true ANTHROPIC_API_KEY=your-key
docker compose up --build
```

If port 8080 is taken, change `"8080:80"` in `docker-compose.yml` and `CORS_ORIGINS` to match.
