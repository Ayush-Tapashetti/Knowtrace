# KnowTrace

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-6BA539.svg)](docs/openapi.json)

**KnowTrace** is an adaptive learning, knowledge tracing, and diagnostic assessment platform. It combines **Bayesian Knowledge Tracing (BKT)**, dependency-graph prerequisite modeling, automated root-cause misconception diagnosis, mastery forecasting, and safety-guarded LLM content rephrasing into a full-stack containerized application.

---

## Table of Contents

- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Running with Docker Compose (Recommended)](#running-with-docker-compose-recommended)
  - [Local Development Setup](#local-development-setup)
- [CLI Utilities & Seeding](#cli-utilities--seeding)
- [Testing & Verification](#testing--verification)
- [Documentation](#documentation)

---

## Key Features

- **Bayesian Knowledge Tracing (BKT) & Mastery Forecasting:** Tracks real-time concept mastery probabilities across learner attempts and projects future retention curves (`bkt.py`, `forecast.py`).
- **Knowledge Graph & Curriculum Modeling:** Models concepts, prerequisite edges, learning atoms, and assessment items with topological dependency tracking (`graph.py`).
- **Root-Cause Diagnostic Engine:** Uses hypothesis-driven probing and state-machine flows to trace incorrect answers back to foundational prerequisite gaps (`diagnosis.py`, `state_machine.py`).
- **Adaptive Lesson Player:** Dynamically assembles targeted remediation lessons from curriculum atoms based on diagnosed knowledge gaps (`lesson.py`).
- **Safety-Guarded LLM Integration:** Integrates Anthropic/LLM rephrasing with strict output guards, PII/payload masking, deterministic caching, and offline fallbacks (`integrations/`).
- **Evaluation & Calibration Kit:** Built-in evaluation runner and reliability charting to measure model calibration and diagnostic accuracy (`evalkit.py`, `eval_runner.py`).
- **Contract-Enforced Full Stack:** Backend OpenAPI schema (`docs/openapi.json`) directly generates and validates TypeScript API types (`frontend/src/api/schema.d.ts`).

---

## System Architecture

```text
┌───────────────────────────┐       HTTP / JSON       ┌───────────────────────────┐
│     Frontend (React)      │ ◄─────────────────────► │     Backend (FastAPI)     │
│  • Vite + TypeScript      │    OpenAPI Contract     │  • Routers & Schemas      │
│  • Interactive Graph UI   │                         │  • Application Services   │
│  • Diagnosis & Lesson UI  │                         │  • Pure Domain Engine     │
│  • Nginx (Production)     │                         │  • Repositories & Models  │
└───────────────────────────┘                         └─────────────┬─────────────┘
                                                                    │
                                                      ┌─────────────▼─────────────┐
                                                      │   External / Persistence  │
                                                      │  • Database (SQL/SQLite)  │
                                                      │  • Guarded LLM Client     │
                                                      └───────────────────────────┘
```

### Architectural Boundaries
- **Pure Domain Core (`backend/src/knowtrace/domain/`):** Contains all mathematical models (BKT, forecasting, graph traversal, grading, diagnostics, state machines) with **zero I/O or framework dependencies**, enforced via `scripts/check_purity.sh` and `test_purity.py`.
- **Service & Repository Layer:** Orchestrates database persistence, learner state transitions, and evaluation runs.
- **Guardrailed AI Layer (`backend/src/knowtrace/integrations/`):** Wraps external LLM calls with payload masking, prompt templates, output validation guards, and response caching.

---

## Repository Structure

```text
knowtrace/
├── backend/
│   ├── content/
│   │   ├── build_seed.py               # Curriculum & assessment seed builder
│   │   └── seed/                       # Seed JSON datasets (concepts, edges, atoms, items)
│   ├── src/knowtrace/
│   │   ├── cli/                        # CLI tools (seed, run_eval, export_openapi)
│   │   ├── core/                       # Settings, DB session, dependencies, rate limiting
│   │   ├── domain/                     # Pure business logic (BKT, diagnosis, graph, forecast, grading)
│   │   ├── integrations/               # LLM client, rephraser, output_guard, payload_mask, cache
│   │   ├── models/                     # ORM database models (learner, curriculum, diagnosis, forecast)
│   │   ├── repositories/               # Data access layer
│   │   ├── routers/                    # REST API endpoints (curriculum, diagnoses, lessons, students)
│   │   ├── schemas/                    # Pydantic request/response contracts
│   │   ├── services/                   # Use-case orchestration & evaluation runners
│   │   └── main.py                     # FastAPI application entrypoint
│   ├── tests/
│   │   ├── api/                        # Endpoint, flow, security, and OpenAPI contract tests
│   │   ├── domain/                     # Unit tests for BKT, graph, purity, and state machines
│   │   └── integrations/               # Tests for LLM guards, masking, caching, and offline mode
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.lock
├── frontend/
│   ├── src/
│   │   ├── api/                        # Typed API client, React Query hooks, generated schema.d.ts
│   │   ├── app/                        # Root App component & routing
│   │   ├── components/                 # Reusable UI primitives & layout shell
│   │   ├── features/
│   │   │   ├── diagnosis/              # Probe lists, hypothesis bars, trace views
│   │   │   ├── eval/                   # Model reliability charts & evaluation metrics
│   │   │   ├── forecast/               # Mastery retention & forecast visualizations
│   │   │   ├── graph/                  # Interactive knowledge graph & mastery heatmap tables
│   │   │   ├── lesson/                 # Step-by-step adaptive lesson player
│   │   │   └── session/                # Practice session & question cards
│   │   ├── lib/                        # Formatting, student ID management, error utilities
│   │   └── pages/                      # Top-level views (Practice, Graph, Evaluation)
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── openapi.json                    # Exported OpenAPI specification
│   └── pipeline/                       # Architecture, domain schema, scope, and verification docs
├── scripts/
│   └── check_purity.sh                 # Verifies domain layer has no external/IO imports
├── .env.example                        # Environment variable template
├── COMMIT_PLAN.md                      # Engineering milestone & commit history plan
├── RUNNING.md                          # Detailed operational & runtime guide
└── docker-compose.yml                  # Multi-container orchestration
```

---

## Getting Started

### Prerequisites

- **Docker** & **Docker Compose** (for containerized setup)
- **Python 3.11+** and **Node.js 20+** (for local development without Docker)

### Running with Docker Compose (Recommended)

1. **Clone the repository and configure environment variables:**
   ```bash
   git clone https://github.com/your-org/knowtrace.git
   cd knowtrace
   cp .env.example .env
   ```
   *(Optional)* Add your LLM API key to `.env` if you want live LLM rephrasing enabled; otherwise, KnowTrace safely falls back to deterministic/cached content.

2. **Build and start the services:**
   ```bash
   docker compose up --build
   ```

3. **Access the application:**
   - **Frontend Web App:** `http://localhost:3000` (or port configured in `docker-compose.yml`)
   - **Backend API & Interactive Docs:** `http://localhost:8000/docs`

---

### Local Development Setup

#### 1. Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.lock
pip install -e .

# Seed the database with initial curriculum concepts, atoms, and items
python -m knowtrace.cli.seed

# Start the development server
uvicorn knowtrace.main:app --reload --port 8000
```

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## CLI Utilities & Seeding

The backend includes built-in CLI modules under `knowtrace.cli`:

| Command | Description |
| :--- | :--- |
| `python -m knowtrace.cli.seed` | Populates the database with concepts, prerequisite edges, atoms, and items from `backend/content/seed/`. |
| `python -m knowtrace.cli.run_eval` | Executes the offline evaluation suite to compute BKT calibration and diagnostic accuracy metrics. |
| `python -m knowtrace.cli.export_openapi` | Exports the latest FastAPI OpenAPI schema to `docs/openapi.json`. |

---

## Testing & Verification

KnowTrace enforces strict architectural purity, API contract synchronization, and zero-network isolation in integration tests.

### Backend Test Suite
```bash
cd backend
pytest
```
- **Domain Purity Check:**
  ```bash
  bash scripts/check_purity.sh
  ```
- **API Contract Verification:** Ensures `docs/openapi.json` matches live FastAPI routes (`tests/api/test_contract.py`).

### Frontend Test Suite
```bash
cd frontend
npm test
```
- Includes component tests, API client/hook tests, and frontend-backend OpenAPI schema contract tests (`src/api/__tests__/contract.test.ts`).

---

## Documentation

For deeper technical details, consult the included project documentation:
- **[RUNNING.md](RUNNING.md):** Detailed operational instructions, environment flags, and troubleshooting.
- **[docs/pipeline/01-problem.md](docs/pipeline/01-problem.md) & [02-scope.md](docs/pipeline/02-scope.md):** Problem formulation and system boundaries.
- **[docs/pipeline/03-domain-schema.md](docs/pipeline/03-domain-schema.md):** Mathematical specifications for BKT, diagnostics, and data models.
- **[docs/pipeline/04-architecture.md](docs/pipeline/04-architecture.md):** System design, layer boundaries, and LLM safety architecture.
- **[docs/pipeline/07-verification.md](docs/pipeline/07-verification.md):** Verification strategy, test coverage, and acceptance criteria.
