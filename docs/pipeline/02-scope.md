# 02 Scope

## P0 (max 5)
| ID | Feature | Persona | Acceptance check |
|---|---|---|---|
| P0-1 | **Curriculum knowledge graph**: prerequisite DAG with typed concepts, items mapped to concepts (Q-matrix), validation and traversal | Learner, Evaluator | Loading a graph with a cycle raises an error; `ancestors(c)` returns all transitive prerequisites; topological order puts every prerequisite before its dependent; seed has >= 40 concepts and >= 3 items per concept; every item maps to >= 1 concept |
| P0-2 | **Knowledge-state tracker**: per-concept mastery probability via Bayesian Knowledge Tracing (prior, learn, slip, guess, forget), noisy-AND for multi-concept items | Learner | A hand-computed BKT update on a fixture matches to 1e-9; correct answers raise and wrong answers lower mastery; all values stay in [0, 1]; a multi-concept item updates each required concept consistently |
| P0-3 | **Root-cause diagnosis**: on a failed item, compute a posterior over which prerequisite is missing, run adaptive probes chosen by expected information gain, return the root gap with confidence and traversal path | Learner, Evaluator | On fixtures where the true gap is an ancestor at depth >= 2, top-1 diagnosis equals the true gap; needs <= 4 probes on the seed graph; when evidence says all prerequisites are mastered it returns "likely slip" and assigns no lesson |
| P0-4 | **Micro-lesson assembler**: select and order lesson atoms (definition, worked example, practice, check) for the gap and any unmastered bridge concepts | Learner | Lesson only contains concepts with mastery below threshold, in topological order; estimated time <= 5 min; ends with >= 2 check items on the gap concept; identical inputs give an identical lesson |
| P0-5 | **Learner session UI**: answer items, see diagnosis trace, knowledge-state graph heatmap, lesson, and post-lesson recheck | Learner, Evaluator | Scripted end-to-end flow (API level plus one UI smoke test): fail item -> diagnosis shown with path -> lesson served -> recheck passed -> gap concept mastery increases |

## P1 (deferred)
- Teacher/class heatmap across many students
- Spaced-review scheduler driven by the forgetting term
- Curriculum import from JSON/CSV and a simple graph editor
- Optional LLM rephrasing of lesson text (guarded, see D3)
- Exportable session report (PDF)
- Mobile polish and dark mode
- Second subject domain

## Differentiators
| Name | Why it matters here | How it is demonstrated |
|---|---|---|
| **D1: Synthetic-student evaluation harness** | The brief demands algorithmic rigor. Simulated students with hidden, known gaps give ground truth, so accuracy is measured instead of claimed | `run_eval` CLI prints a table: root-cause top-1/top-3 accuracy, probes-to-diagnosis, and next-answer prediction AUC/Brier, for our method vs baselines (blame direct parent only, flat BKT with no graph). Same table appears in an Evaluation panel in the UI |
| **D2: Learning-trajectory forecast with calibration** | The brief says "predict and evaluate learning trajectories". A forecast is only credible if it is calibrated | UI sparkline per concept with an uncertainty band and predicted time-to-mastery; `run_eval` prints a reliability table (predicted vs observed mastery) and Brier score on held-out simulated students |
| **D3: Fully deterministic core, model optional** | Proves it is not a wrapper and keeps it working with no key or network | Env flag turns the optional LLM rephraser on/off; a test runs the whole fail -> diagnose -> lesson flow with network blocked; when the model is on, output is rejected and replaced by template text if it names a concept outside the selected list |

## Cut list
- Free-text answer grading by a model: breaks determinism and the rigor constraint; MCQ/numeric only.
- Deep Knowledge Tracing (neural sequence model): not explainable and hard to validate in the time available; BKT plus graph is defensible.
- Auto-generating the curriculum graph from textbooks with a model: unverifiable edges would poison diagnosis.
- Accounts, auth, multi-tenant storage: no PII goal and no value for the demo.
- Gamification, streaks, leaderboards: do not help solve the problem declaration.
- Multi-subject curriculum at launch: depth on one verified graph beats breadth.
- Voice/video lessons: out of scope for a bridge-the-gap micro-lesson.
