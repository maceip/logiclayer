# Current Validation Gates

Last updated: 2026-05-06

## Purpose

These gates are intentionally simple.

They exist to prove that we are checking real implementation seams instead of hand-waving over them.

They are built from existing code in the canonical backend and run against a real vendored repo plus a real saved artifact.

**Separate rail:** LogicLens **evidence retrieval** on the committed `test/logiclens` fixture is gated by `evidence-benchmark` (accuracy ≥ 0.80, hallucination_rate = 0 with `--fail-on-hallucinations`) and `test_evidence_benchmark_meets_phase17_thresholds`, not by `validate-gates`.

## Command

From the repo root:

```powershell
.\.venv-win\Scripts\python.exe -m heart_transplant.cli validate-gates --artifact-dir <artifact-directory>
```

## Reference Inputs

The older captured reference used `vendor/github-repos/elysia-supabase-tempate` and artifact `2026-04-24T12-57-30Z__boomNDS__elysia-supabase-tempate`. For release work, rerun against the shipping artifact instead of treating this older artifact as the current launch proof.

## Gate Definitions

1. `structural_ingest_produces_nodes`
- Uses the real Tree-sitter ingest path
- Passes only if a real repo emits code nodes and parser backends

2. `artifact_contains_expected_files`
- Checks that the artifact contains the files we claim to generate

3. `graph_smoke_structure_is_consistent`
- Checks that the stored graph is at least structurally sane

4. `scip_metadata_is_real`
- Checks that the artifact records a real SCIP indexer run and real output file

5. `scip_actually_resolves_nodes`
- Checks whether SCIP has actually resolved symbol identities into the graph
- This gate may fail on artifacts without `index.scip`; it should pass on TS/JS artifacts created with `ingest-local --with-scip`

## Captured Output From The Older Reference Artifact

Current overall result:

- total gates: `5`
- passed: `5`
- failed: `0`
- overall status: `pass`

### Pass: Structural ingest

Input:

- repo path: `C:\Users\mac\heart-transplant\vendor\github-repos\elysia-supabase-tempate`
- repo name: `boomNDS/elysia-supabase-tempate`

Output:

- `node_count = 40`
- `edge_count = 40`
- `parser_backends = ["tsx", "typescript"]`

### Pass: Artifact contains expected files

Output:

- `structural-artifact.json = true`
- `index.scip = true`
- `scip-index.json = true`
- `scip-consumed.json = true`

### Pass: Graph smoke structure is consistent

Output:

- `node_count = 40`
- `contains_edge_count = 40`
- `missing_containment = []`
- `scip_present = true`

### Pass: SCIP metadata is real

Output:

- `indexer = "scip-typescript"`
- `version = "0.4.0"`
- `output_exists = true`

### Pass: SCIP actually resolves nodes

Output:

- `resolved_code_nodes = 40`
- `total_code_nodes = 40`
- `unresolved_code_nodes = 0`
- `implementation_edge_count = 0`

Meaning:

- we do have a real SCIP file
- we do parse that real SCIP file
- and SCIP is now successfully driving symbol identity in the graph

Important remaining caveat:

- `implementation_edge_count` is still `0`
- the latest `scip-consumed.json` also reports a large `orphaned_symbol_count`

So SCIP resolution is real on this captured artifact, but structural coverage is still shallower than the symbol graph available from SCIP.

## Files Behind These Gates

- CLI:
  [cli.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/cli.py)
- Gate runner:
  [validation_gates.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/validation_gates.py)
- Tree-sitter ingest:
  [treesitter_ingest.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/ingest/treesitter_ingest.py)
- Graph smoke:
  [graph_smoke.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/graph_smoke.py)
- SCIP consume:
  [scip_consume.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/scip_consume.py)

## Why This Matters

These gates are not meant to be comprehensive.

They are meant to create a standing discipline:

- if a seam is real, it should pass a real gate
- if a seam is incomplete, the gate should fail in public

The next important seam is no longer path normalization.

It is structural coverage:

- reduce orphaned symbols
- enrich node kinds beyond functions
- extract more addressable code units so SCIP and Tree-sitter align more completely
- use the newer Rust/Java/C/C++ parser coverage and file-surface nodes when regenerating launch artifacts
