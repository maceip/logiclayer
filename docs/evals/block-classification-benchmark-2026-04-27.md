# Block Classification Benchmark - 2026-04-27

Purpose: give the beta story a measured block-accuracy claim, while separating semantic classifier quality from graph/materialization coverage.

## What Was Run

From `C:\Users\mac\heart-transplant\backend`:

```powershell
$env:PYTHONPATH='src'
.\.venv-win\Scripts\python.exe -m heart_transplant.cli phase-metrics --artifact-dir ..\.heart-transplant\artifacts\2026-04-25T20-06-30Z__vendor__elysia-supabase-tempate --gold-set ..\docs\evals\gold_block_benchmark.json --classify-if-missing
.\.venv-win\Scripts\python.exe -m heart_transplant.cli phase-metrics --artifact-dir ..\.heart-transplant\artifacts\2026-04-26T17-22-18Z__vendor__clean-elysia --gold-set ..\docs\evals\gold_block_benchmark_holdout.json --classify-if-missing
.\.venv-win\Scripts\python.exe -m heart_transplant.cli gold-audit ..\docs\evals\gold_block_benchmark.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli gold-audit ..\docs\evals\gold_block_benchmark_holdout.json
.\.venv-win\Scripts\python.exe -m pytest tests/test_gold_benchmark.py tests/test_phase_metrics.py
```

Current focused test result for the gold rail: `21 passed, 1 warning`.

## Results

| Split | Artifact | Gold rows scored | End-to-end correct | End-to-end accuracy | Missing-node rate | Scorable-node accuracy |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Reference | `2026-04-25T20-06-30Z__vendor__elysia-supabase-tempate` | 10 | 10 | 100.0% | 0.0% | 100.0% |
| Holdout | `2026-04-26T17-22-18Z__vendor__clean-elysia` | 20 | 8 | 40.0% | 45.0% | 72.7% |

The reference score is a useful smoke proof, not the launch claim. The holdout split is the beta baseline from this run: on nodes the ingest actually materialized at the time, the heuristic block classifier got 8 of 11 rows right. End-to-end accuracy dropped to 8 of 20 because 9 gold rows pointed at files that did not become addressable `CodeNode` records.

Update after the 50-repo hardening pass: file-surface nodes, secondary block scoring, and broader parser coverage have landed. This report remains the preserved baseline for the April 27 artifact pair; rerun the benchmark before treating these numbers as the current product score.

Update after the Rail 1 gold-standard pass: the committed gold files now use the stable `accepted_blocks` / `primary_block` schema, duplicate same-target rows have been consolidated into multi-label rows, and `gold-audit` passes on the committed reference, broad, and holdout splits. New `block-benchmark` JSON reports include a `gold_health` object and summary fields for review rows, multi-label rows, missing required fields, and contradictory active targets.

## What This Proves

- The repo has a repeatable gold benchmark path; it is no longer judged by screenshots or vibes.
- The current classifier is already useful on materialized nodes: `72.7%` scorable holdout accuracy.
- The main blocker is not only semantic classification. It is the join between file-level gold expectations and graph materialization.
- The benchmark can be rerun after every classifier or ingest change through `phase-metrics`.

## What It Does Not Prove Yet

- It does not prove broad language/framework generalization. The current scored gold sets are Elysia/TypeScript-family repos.
- It does not yet provide a fresh multi-label launch score. Secondary block scoring exists now, but this preserved report predates that change.
- It does not prove a paper-grade semantic model. The Phase 8.5 holdout gate still needs a first-class semantic score, not only structural gate reruns.

## Error Analysis

Historical holdout missing rows from the preserved April 27 artifact:

- `src/bull/index.ts` appears twice in gold.
- `src/bull/queue/index.ts` appears twice in gold.
- `src/bull/worker/index.ts` appears twice in gold.
- `src/libs/cache/index.ts` appears twice in gold.
- `src/libs/config/index.ts` appears once in gold.

These are mostly barrel/index files. They are real architectural surfaces. File-surface materialization now exists, so these rows should be rerun before the missing-node rate is used in a launch claim.

Historical holdout scorable misses from the preserved April 27 artifact:

- `src/libs/cache/cache.ts`: gold contains conflicting expectations across rows; after the cache-path correction it classifies as `Persistence Strategy`, while one gold row expects `Data Persistence`.
- `src/libs/config/database.config.ts`: expected `Experimentation`, classified `Data Persistence`; the code is a database config wrapper, so the gold label may need review.
- `src/libs/config/env.config.ts`: expected `Global Interface`, classified `Data Persistence`; the file aggregates app, database, Redis, mail, JWT, CORS, and ClickHouse env, so this likely needs multi-label scoring.

## Next Benchmark Step

Before making this a beta headline, keep using the dedicated `block-benchmark` command to report:

1. end-to-end primary-block accuracy,
2. scorable-node primary-block accuracy,
3. missing-node coverage,
4. multi-label recall for files with multiple accepted blocks,
5. per-block confusion, and
6. a corpus table including the daily-trending vendored repos.

Target beta gate: `>=80%` scorable holdout accuracy, `<=15%` missing-node rate, and no known contradictory gold rows in the scored set.

---

**Related (2026-05):** Block accuracy is independent of the **evidence-benchmark** rail (`docs/evals/evidence_questions.json`, committed fixture under `docs/evals/fixtures/logiclens-evidence-benchmark/`). See `gold-standards.md` and `README.md`.
