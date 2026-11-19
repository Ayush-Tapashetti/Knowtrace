# 01 Problem & Guardrails

## Problem
A student stuck on advanced material needs to know *which foundational concept* they are actually missing (not just that the answer was wrong), because platforms only mark answers right/wrong, so the app tracks a probabilistic knowledge state over a curriculum prerequisite graph, traces a failure back to the root-cause concept, and assembles a targeted micro-lesson that bridges that exact gap.

## Personas & deployment
- **Learner (primary)**: school/early-college student, mixed skill, attempts practice problems in short sessions (10 to 20 min). Moment of use: right after getting a hard problem wrong.
- **Evaluator / judge (secondary)**: hackathon reviewer who must see the algorithm working and trust that it is not a text wrapper. Moment of use: a 5-minute demo plus a reproducible eval run.
- Deployment: **desktop web demo, responsive enough for a phone browser**. Runs locally or on a free-tier host, no accounts.

## Deterministic vs model
| Capability | Owner | Fallback if model fails |
|---|---|---|
| Curriculum graph (DAG) load, cycle check, ancestors/descendants, topological order | code | n/a (no model) |
| Answer grading (MCQ / numeric / exact match) | code | n/a |
| Knowledge-state update per concept (Bayesian Knowledge Tracing with slip/guess/learn/forget) | code | n/a |
| Multi-concept item handling (noisy-AND over required concepts via Q-matrix) | code | n/a |
| Root-cause posterior over candidate missing prerequisites + ranking | code | n/a |
| Next diagnostic probe selection (expected information gain / entropy reduction) | code | n/a |
| Learning-trajectory forecast (mastery at t+n, time-to-mastery, uncertainty band) | code | n/a |
| Micro-lesson assembly (pick and order lesson atoms along the gap path, time-capped) | code | n/a |
| Lesson text polish / rephrasing (optional) | language model | ship authored template text as-is |
| Seed content authoring (graph, items, lesson atoms) | offline, human-reviewed (may be model-assisted at dev time, never at runtime) | n/a |

Rule: **everything that decides what the student is missing or what they study next is code.** A model may only reword already-selected content, and its output is checked against the allowed concept list.

## Hard limits
- [hard] Not a generative-text wrapper: diagnosis and lesson selection must be reproducible math/graph code with no model call.
- [hard] Entire core pipeline runs offline with no network and no API key.
- [hard] Deterministic and reproducible: same inputs + same seed gives the same diagnosis and lesson.
- [hard] No real student PII: pseudonymous student IDs only, no names, emails or roll numbers stored or sent to any third party.
- [hard] Every diagnosis is explainable: stores the evidence (observations, posterior, path traversed).
- [hard] Zero paid services; free-tier hosting or local only.
- [soft] Diagnosis latency under 500 ms on the seed graph (about 40 to 60 concepts).
- [soft] Seed domain small enough to hand-verify (see assumptions).
- [soft] Strict typing throughout (stack is chosen in Step 4, not here).

## Assumptions
- Seed curriculum is **school math** (fractions, ratios, linear equations, quadratics), about 40 to 60 concepts, 3+ items each. Chosen because prerequisites are unambiguous and easy to verify.
- Answers are structured (MCQ/numeric), so no free-text grading.
- Single learner per session, local persistence, no auth.
- Delivery target is a hackathon demo plus an eval script; no production scale.
- Model parameters (slip, guess, learn, forget) start from fixed priors and can optionally be fit from simulated data.
