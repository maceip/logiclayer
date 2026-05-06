# Gold Standards Rail

Gold rows define what "correct" means for block classification. Treat them as evaluation contracts, not as examples to optimize against casually.

## Row Schema

Every gold row uses this stable shape:

```json
{
  "id": "repo:path:block-or-multi_label",
  "repo_name": "clean-elysia",
  "file_path": "src/libs/cache/cache.ts",
  "node_id": "",
  "accepted_blocks": ["Data Persistence", "Persistence Strategy"],
  "primary_block": "Data Persistence",
  "confidence": "high",
  "source": "docs/evals/vendored-ground-truth.json",
  "notes": "Why this row exists or why it needs care.",
  "status": "active"
}
```

`node_id` is used when the gold target is a stable graph node. `file_path` is used for file-level targets, especially barrel/index files and files without symbol boundaries. `accepted_blocks` is the allowed answer set. `primary_block` is the preferred single-label readout and must be one of the accepted blocks. `status` is one of `active`, `needs_review`, or `deprecated`.

## Audit Command

Run this before changing classifier heuristics, refreshing benchmark reports, or using a holdout split:

```powershell
cd backend
.\.venv-win\Scripts\python.exe -m heart_transplant.cli gold-audit ..\docs\evals\gold_block_benchmark_holdout.json
```

The audit reports duplicate rows, contradictory labels for the same target, missing required fields, repo coverage, block coverage, confidence distribution, and rows that need multi-label treatment. It exits non-zero when blocking issues remain.

## Public And Holdout Policy

Public gold:

- `docs/evals/gold_block_benchmark.json`
- `docs/evals/gold_block_benchmark_broad.json`

These are visible development sets. They can guide debugging, coverage work, and error analysis, but they should not be the only evidence behind a launch claim.

Holdout gold:

- `docs/evals/gold_block_benchmark_holdout.json`

The holdout split is public in this repo for now, but it is treated as evaluation-only. Do not tune classifier rules, parser behavior, or graph materialization directly against individual holdout rows. Use failures to open issues or create new public training rows, then rerun the holdout after the general fix lands.

Hidden holdout:

- Future private-beta and paper-grade runs should include a non-committed holdout artifact generated from the same schema.
- Hidden holdouts should be stored outside the repo or in a private CI secret/artifact store.
- Hidden rows should only be exposed as aggregate health, coverage, and accuracy numbers.

## Generation Policy

Gold rows are generated from `docs/evals/vendored-ground-truth.json` through `build-gold`.

```powershell
cd backend
.\.venv-win\Scripts\python.exe -m heart_transplant.cli build-gold ..\docs\evals\vendored-ground-truth.json --out ..\docs\evals\gold_block_benchmark.json --max-items 55 --exclude-repo clean-elysia --include-medium
.\.venv-win\Scripts\python.exe -m heart_transplant.cli build-gold ..\docs\evals\vendored-ground-truth.json --out ..\docs\evals\gold_block_benchmark_holdout.json --max-items 20 --only-repo clean-elysia --include-medium
.\.venv-win\Scripts\python.exe -m heart_transplant.cli gold-audit ..\docs\evals\gold_block_benchmark.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli gold-audit ..\docs\evals\gold_block_benchmark_holdout.json
```

When multiple labels target the same file or node, the generator produces one row with multiple `accepted_blocks`. If a row is uncertain but still useful as a research prompt, mark it `needs_review` so benchmark scoring skips it while the audit still keeps it visible.

## Benchmark Report Contract

Every JSON report emitted by `block-benchmark` includes a `gold_health` object and summary fields for gold health status, review rows, multi-label rows, missing required fields, and active contradictory targets. A beta benchmark is not launch-ready unless the gold health summary passes for the scored split.

## Evidence retrieval rail (Phase 17)

Architecture Q&A over artifacts is scored separately from block classification:

- **Questions**: `docs/evals/evidence_questions.json` (active rows; the parity gate uses **28** rows scoped to `repo_name: test/logiclens`).
- **Fixture**: `docs/evals/fixtures/logiclens-evidence-benchmark/`.
- **Report**: `docs/evals/evidence_benchmark_report.json` (commit when the harness or fixture changes).
- **CLI** (from `backend/`): `python -m heart_transplant.cli evidence-benchmark <fixture-dir> --questions ../docs/evals/evidence_questions.json --fail-on-hallucinations` (see `README.md`).
- **CI**: `test_evidence_benchmark_meets_phase17_thresholds` enforces **accuracy ≥ 0.80** and **hallucination_rate = 0** on that corpus.

Do not conflate this rail with `gold_block_benchmark*.json`; they measure different contracts.
