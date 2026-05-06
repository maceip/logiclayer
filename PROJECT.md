# heart-transplant — Master Project Document

**Last Updated**: 2026-05-06  
**Source of truth for paper alignment**: `heart-transplant paper-checklist` (10 LogicLens-style features tracked in code).

## Current State

### Paper checklist snapshot

Run from `backend/`:

```bash
python3 -m heart_transplant.cli paper-checklist
```

As of the last doc refresh, the checklist reports **10** features: **2 implemented**, **8 partial**, **0 missing**.

- **Implemented**: repository program graph construction (`structural_graph`); **evidence-grounded architecture Q&A** (`evidence_retrieval`) — declared **only** on the committed Phase 17 fixture corpus (see below).
- **Partial**: symbol identity, semantic blocks, semantic entities, reactive graph tools (incl. Codes tool; Graph Query still Surreal-first), graph persistence, temporal reasoning, multimodal, regret SDK.

### Phase 17 — fixed-corpus evidence retrieval (closed on fixture)

Parity for **measured** evidence retrieval on **one** corpus is defined as:

- **Fixture**: `docs/evals/fixtures/logiclens-evidence-benchmark/` (`structural-artifact.json` + `semantic-artifact.json`).
- **Questions**: `docs/evals/evidence_questions.json` — **28** active rows with `repo_name: test/logiclens`.
- **Report**: `docs/evals/evidence_benchmark_report.json` (summary + per-row scores; commit when the harness or fixture changes).
- **Gate**: `evidence-benchmark` exits non-zero if `accuracy < 0.80`, or if `--fail-on-hallucinations` and `hallucination_rate > 0`.
- **CI**: `backend/tests/test_evidence_benchmark.py::test_evidence_benchmark_meets_phase17_thresholds` re-runs the benchmark and checks the committed report summary.

**Not in scope for Phase 17**: running the same question set against arbitrary real repos without a separate Phase 18 process; that variance is explicitly deferred in checklist notes.

### What has been built (stable spine)

- Canonical Python backend (`backend/src/heart_transplant/`)
- Tree-sitter structural ingest + optional SCIP for TS/JS; broad parser coverage
- 24-block ontology and deterministic classification; `semantic-artifact.json`
- SurrealDB load/verify, MCP graph tools
- Canonical graph export, graph integrity, validation gates, gold block benchmarks
- Temporal, multimodal, causal, regret, and execution first passes (roadmap: still partial)
- **Evidence bundle** helpers, **`query-codes`** (Codes tool shape), hybrid project+codes routing where applicable, MCP `query_codes_artifact`
- Optional **`logiclens_cleanroom/`** package: paper-shaped standalone pipeline (separate from the main backend checklist)

### After Phase 17 — what’s next

- **Phase 18+**: real-repo evidence-benchmark expansion, temporal/graph replay depth, regret and multimodal gates per roadmaps — without redefining the Phase 17 fixture contract unless intentionally versioned.

## Key Documents

- **PROJECT.md** — This file
- `README.md` — Operator entrypoints and paper feature table
- `docs/roadmaps/logiclens-paper-grade-roadmap.md` — Historical assessment and long-form roadmap
- `docs/roadmaps/logiclens-next-tranche-2026-04-27.md` — Phase 15–20 intent (Phase 17 exit criteria aligned with committed fixture)
- `docs/roadmaps/alignment-and-trajectory-2026-04-27.md` — Product alignment
- `docs/evals/evidence_questions.json` — Evidence QA rows (incl. `test/logiclens` active set)
- `docs/evals/evidence_benchmark_report.json` — Last committed benchmark summary
- `docs/evals/codes_tool_calibration.md` — Codes-tool abstention constant (`DEFAULT_CODES_MIN_SCORE`)
- `docs/evals/gold-standards.md` — Block gold rail (separate from evidence-benchmark)
- `backend/src/heart_transplant/paper_checklist.py` — Checklist generator

## Useful Commands

```bash
cd backend

python3 -m pytest

python3 -m heart_transplant.cli paper-checklist

python3 -m heart_transplant.cli evidence-benchmark \
  ../docs/evals/fixtures/logiclens-evidence-benchmark \
  --questions ../docs/evals/evidence_questions.json \
  --out ../docs/evals/evidence_benchmark_report.json \
  --fail-on-hallucinations

python3 -m heart_transplant.cli validate-gates --artifact-dir <artifact-directory>
python3 -m heart_transplant.cli graph-integrity <artifact-directory>
python3 -m heart_transplant.cli program-surface
```

Windows equivalents: use `.\.venv-win\Scripts\python.exe` and backslash paths as in historical docs.

---

**Status**: Structural graph + Phase 17 evidence retrieval (on the committed `test/logiclens` fixture) are the only checklist items marked **implemented**. Remaining paper-shaped capabilities are **partial** until their phases ship measured gates.  
**Decision**: Treat `paper-checklist`, the committed `evidence_benchmark_report.json`, and Phase 17 pytest as the launch bar for evidence retrieval; broaden real-repo scoring under Phase 18 without conflating it with the frozen fixture contract.
