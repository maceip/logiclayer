# heart-transplant

Canonical restart of the project around a verified stack:

- Tree-sitter
- SCIP
- SurrealDB
- Pydantic-AI
- MCP Python SDK
- Continue CLI

**Docs:** For paper-alignment counts and Phase 17 evidence gates, run `heart-transplant paper-checklist` and see `PROJECT.md`. This README summarizes operator paths and the LogicLens feature table.

## What We Kept

- `vendor/`
  - local vendored GitHub repos for evaluation
- `docs/`
  - evaluation notes and architecture comparisons
- the 24 universal semantic blocks

## What We Archived

This clean-room restart intentionally does not include the previous exploratory
prototype in the checkout. The canonical backend path is `backend/src/heart_transplant/`;
legacy code was excluded during the transplant rather than preserved under an
`archive/` directory in this repository.

## Main Operator Path

The foundational milestone, **structural ingestion**, is implemented. The active work is turning that foundation into a LogicLens-style architecture backend with measured evidence retrieval.

1. parse local repos with Tree-sitter
2. emit `CodeNode` records using the verified schema direction
3. persist durable structural artifacts

Current command:

```powershell
python -m heart_transplant.cli ingest-local C:\path\to\repo
```

or, once installed from `backend/`:

```powershell
heart-transplant ingest-local C:\path\to\repo
```

To also generate a real SCIP index for TypeScript or JavaScript repos:

```powershell
heart-transplant ingest-local C:\path\to\repo --with-scip
```

If dependencies are not installed yet:

```powershell
heart-transplant ingest-local C:\path\to\repo --with-scip --install-deps
```

## Current State

Real now:

- clean canonical Python backend package
- 24-block ontology in Python
- Tree-sitter-backed local structural ingest, including file-surface nodes and parser coverage for TypeScript/TSX/JavaScript/Python/Go/Prisma/Rust/Java/C/C++
- durable JSON structural artifacts
- real `scip-typescript` indexing into the artifact directory for TS/JS repos
- SCIP→artifact consumption, optional corpus symbol index, and SurrealDB load/verify
- block classification and optional persistence of semantics to Surreal
- **MCP stdio server** (`heart-transplant mcp-serve` or `python -m heart_transplant.mcp_server`) exposing graph tools when Surreal is running and loaded
- dated trending-repo input manifests for beta corpus refreshes (`docs/evals/trending-repos-2026-04-27.json`)
- preserved 50-repo EC2 synthesis with landed fixes for the three first-run ingest crashes and six zero-node successes
- LogicLens paper checklist and evidence-contract CLIs (`paper-checklist`, `canonical-graph`, `explain-node`, `explain-file`, `trace-dependency`, `query-entities`, `query-projects`, **`query-codes`**, `trace-entity-workflow`, `find-architectural-block`, `answer-with-evidence`, **`evidence-benchmark`**)
- **Phase 17 (LogicLens evidence retrieval on a fixed corpus)** — committed structural + semantic fixture under `docs/evals/fixtures/logiclens-evidence-benchmark/`, question set `docs/evals/evidence_questions.json` (28 active rows scoped to `test/logiclens`), last report `docs/evals/evidence_benchmark_report.json`, and CI test `test_evidence_benchmark_meets_phase17_thresholds`. The CLI fails if accuracy drops below **0.80** or, with `--fail-on-hallucinations`, if **hallucination_rate** is greater than zero. Real-repo variance for this harness is **Phase 18** (see `paper-checklist` notes on `evidence_retrieval`).

## Phase 17: run the evidence benchmark

From `backend/` (adjust paths if your shell differs):

```powershell
python -m heart_transplant.cli evidence-benchmark `
  ..\docs\evals\fixtures\logiclens-evidence-benchmark `
  --questions ..\docs\evals\evidence_questions.json `
  --out ..\docs\evals\evidence_benchmark_report.json `
  --fail-on-hallucinations
```

```bash
cd backend
python3 -m heart_transplant.cli evidence-benchmark \
  ../docs/evals/fixtures/logiclens-evidence-benchmark \
  --questions ../docs/evals/evidence_questions.json \
  --out ../docs/evals/evidence_benchmark_report.json \
  --fail-on-hallucinations
```

Regenerate the committed report after intentional retrieval or fixture changes, then commit the updated JSON.

## Canonical Graph Contract

The canonical graph is the central backend contract. Producers may still write
their native artifacts for auditability, but every product surface should either
write into `canonical-graph.json` or be a derived view from it.

Current projections into the canonical graph include:

- structural ingest: project, file, code, and SCIP-backed structural edges
- semantic classification: block assignments, secondary block assignments, entities, and actions
- SCIP consume reports: document nodes and implementation/reference provenance
- multimodal reports: test, OpenAPI, infra, and correlated codefile nodes
- temporal reports: replayed graph snapshot nodes
- regret SDK reports: regret surface nodes linked back to evidence nodes

`graph-integrity` checks the central contract: no dangling canonical targets,
every canonical edge has provenance, stable node IDs, derived nodes linking back
to source evidence, source manifest records, and a typed `CanonicalGraph`
roundtrip.

## LogicLens Paper Feature Map

This table maps the paper-shaped capabilities we are rebuilding to the current
implementation surface. Status follows `heart-transplant paper-checklist` (**10** features as of 2026-05). **Partial** means the path exists but the paper-grade gate or benchmark is not fully green for that feature; **implemented** means the checklist marks it satisfied (evidence retrieval only on the committed Phase 17 fixture — see above).

| Paper feature | Current status | Implemented in | CLI / artifact / benchmark |
| --- | --- | --- | --- |
| Repository program graph construction | Implemented | `backend/src/heart_transplant/ingest/treesitter_ingest.py`, `backend/src/heart_transplant/models.py` | `heart-transplant ingest-local`, `structural-artifact.json`, `validate-gates` |
| Stable symbol identity and reference graph | Partial | `backend/src/heart_transplant/scip_typescript.py`, `backend/src/heart_transplant/scip_consume.py`, `backend/src/heart_transplant/scip/` | `ingest-local --with-scip`, `index.scip`, `scip-consumed.json`, `scip_actually_resolves_nodes` |
| Canonical multi-layer architecture graph | Partial | `backend/src/heart_transplant/canonical_graph.py`, `backend/src/heart_transplant/multimodal/` | `heart-transplant canonical-graph`, `canonical-graph.json`, `graph-integrity` |
| Semantic component/block labeling | Partial | `backend/src/heart_transplant/ontology.py`, `backend/src/heart_transplant/classify/`, `backend/src/heart_transplant/semantic/` | `classify`, `semantic-artifact.json`, `block-benchmark`, `docs/evals/gold_block_benchmark*.json` |
| Domain entities and semantic action edges | Partial | `backend/src/heart_transplant/semantic/enrichment.py`, `backend/src/heart_transplant/canonical_graph.py`, `backend/src/heart_transplant/evidence.py` | `semantic-artifact.json`, `canonical-graph.json`, `query-entities`, `trace-entity-workflow` |
| Evidence-grounded architecture Q&A | **Implemented** (Phase 17 fixture gate) | `backend/src/heart_transplant/evidence.py`, `backend/src/heart_transplant/db/graph_queries.py`, `backend/src/heart_transplant/mcp_server.py` | `explain-node`, `explain-file`, `trace-dependency`, `find-architectural-block`, `answer-with-evidence`, `evidence-benchmark`; committed fixture + `docs/evals/evidence_benchmark_report.json`; `pytest` Phase 17 threshold test |
| Reactive graph retrieval tools | Partial | `backend/src/heart_transplant/evidence.py`, `backend/src/heart_transplant/db/graph_queries.py`, `backend/src/heart_transplant/mcp_server.py` | `query-projects`, `query-entities`, **`query-codes`**, `trace-entity-workflow`, `mcp-serve`, SurrealDB graph tools (Graph Query remains DB-backed; see checklist) |
| Queryable graph backend | Partial | `backend/src/heart_transplant/db/`, `backend/src/heart_transplant/mcp_server.py` | `load-surreal`, `verify-surreal`, `mcp-serve`, SurrealDB `ht_code` / `ht_edge` rows |
| Architecture evolution over time | Partial | `backend/src/heart_transplant/temporal/` | `temporal-scan`, `temporal-scan --replay-snapshots`, `temporal-diff`, `temporal-gates` |
| Cross-layer code/test/API/infra reasoning | Partial | `backend/src/heart_transplant/multimodal/`, `backend/src/heart_transplant/canonical_graph.py` | `multimodal-ingest`, `canonical-graph`, future correlation accuracy benchmark |
| Blast radius / impact reasoning | Partial | `backend/src/heart_transplant/blast_radius.py`, `backend/src/heart_transplant/causal/` | `simulate-change`, `get_impact_radius` MCP tool, causal simulation reports |
| Regret detection and remediation planning | Partial, beyond original paper scope | `backend/src/heart_transplant/regret/`, `backend/src/heart_transplant/execution/` | `regret-scan`, `regret-sdk-scan`, `execute-transplant`, `RegretSurface` / `SurgeryPlan` JSON |
| Paper reproduction checklist | Implemented as tracking surface | `backend/src/heart_transplant/paper_checklist.py` | `heart-transplant paper-checklist` maps feature → status → gate/test → artifact → benchmark |

Deferred / active follow-up (see [docs/roadmaps/logiclens-paper-grade-roadmap.md](docs/roadmaps/logiclens-paper-grade-roadmap.md)):

- end-to-end **Continue** operator session proof on your machine
- **evidence-benchmark on diverse real repos** (beyond the committed `test/logiclens` fixture) — Phase 18 measurement
- block classification: full paper-style semantic scoring (starter gold: [docs/evals/gold_block_benchmark.json](docs/evals/gold_block_benchmark.json))
- rerun of the full 50-repo corpus after parser/traversal fixes, replacing the preserved first-synthesis baseline only when the strict corpus gate passes

Machine-readable status: `heart-transplant paper-checklist` (currently **10** tracked features; **2** implemented — structural graph + evidence retrieval; **8** partial).

## Beta Corpus

Trending repos are vendored locally, not committed:

```powershell
.\scripts\vendor-trending-inputs.ps1
cd backend
.\.venv-win\Scripts\python.exe -m heart_transplant.cli ingest-vendor-corpus ..\vendor\github-repos
```
