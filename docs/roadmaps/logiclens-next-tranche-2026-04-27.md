# LogicLens Next Tranche - 2026-04-27

Purpose: stop completing phase-shaped work that still leaves us short of a respectable LogicLens backend. This tranche defines the next phases by the evidence they must produce, not by whether a module or command exists.

## Respectable Place Definition

We are in a respectable place when a skeptical engineer can run one repo through the backend and receive:

1. a canonical architecture graph with addressable code, file, API, test, infra, semantic, temporal, and regret nodes,
2. block labels with measured holdout quality and explicit coverage gaps,
3. graph-backed answers that quote node IDs, file ranges, paths, and limits,
4. temporal drift evidence from replayed historical ingest, not path-only inference,
5. regret surfaces with typed evidence, simulation context, and domain-specific remediation plans,
6. a reproducible operator path on the beta environment with no private harness, hidden artifact, or machine-local assumption.

If any of those are missing, we should say "partial" even when the code imports and a CLI command exists.

## Current Baseline

Real and useful:

- Tree-sitter ingest with file-surface and symbol nodes.
- SCIP identity reconciliation and orphan-symbol reporting.
- SurrealDB load/verify path.
- 24-block deterministic classifier with multi-label fields.
- Block benchmark, graph integrity, validation, maximize, corpus, and program-surface gates.
- First-pass temporal, causal, regret, execution, and multimodal commands.

Still not respectable enough:

- The canonical graph is not yet the single home for all layers.
- Semantic quality is still below target on holdout and coverage is still a known weak spot.
- Query surfaces return useful graph data, but not a full LogicLens evidence bundle contract.
- Temporal replay exists as a Tree-sitter option, but not yet full SCIP + semantic snapshot replay.
- Regret detection is still pattern/evidence scaffolding, not yet validated product behavior.
- The beta gate story depends on generated artifacts and needs a clearly reproducible artifact manifest.

## Phase 15: Canonical Architecture Graph

Goal: make one graph schema carry every architectural surface we want to reason over.

Scope:

- Normalize IDs and node kinds for:
  - project
  - file surface
  - code symbol
  - route/API endpoint
  - test
  - OpenAPI operation
  - infra resource
  - semantic block assignment
  - temporal snapshot
  - regret surface
- Promote multimodal output from side-report into graph-compatible nodes and edges.
- Store graph provenance on every edge: `tree_sitter`, `scip`, `openapi`, `test_heuristic`, `infra_parser`, `semantic_classifier`, `temporal_replay`, or `regret_detector`.
- Add one canonical artifact manifest that records source repo, commit, commands, tool versions, artifact paths, and gold sets.

Exit evidence:

- `graph-integrity` checks all canonical node/edge layers, not only structural edges.
- No dangling edge targets across code/test/API/infra/semantic layers on the reference artifact.
- Artifact manifest exists and is emitted by ingest, classification, multimodal ingest, temporal replay, and regret scan.
- A small fixture repo demonstrates route -> handler -> service -> persistence -> test/API/infra links in one graph.

Hard gates:

- `canonical_graph_no_dangling_targets`
- `canonical_graph_all_edges_have_provenance`
- `canonical_graph_manifest_reproducible`
- `canonical_graph_cross_layer_fixture_passes`

Non-goals:

- Do not add a UI.
- Do not claim paper-grade retrieval yet.

## Phase 16: Semantic Quality Loop

Goal: turn block labels from useful heuristic output into measured semantic graph quality.

Scope:

- Make `block-benchmark` the canonical semantic quality command.
- Score primary and accepted secondary labels.
- Separate:
  - materialization coverage,
  - scorable accuracy,
  - end-to-end accuracy,
  - per-block confusion,
  - multi-label recall,
  - contradictory gold rows.
- Clean or annotate known contradictory `clean-elysia` rows.
- Add file-surface fallback as a first-class scoring path, not a special case.
- Produce a dated benchmark report every time classifier or ingest changes.

Exit evidence:

- Holdout report committed under `docs/evals/`.
- Current baseline and target are both visible.
- Missing-node rate is at or below `15%`.
- Scorable holdout accuracy is at or above `80%`.
- No known contradictory gold row is counted as a hard failure without annotation.

Hard gates:

- `semantic_holdout_scorable_accuracy_ge_80`
- `semantic_holdout_missing_node_rate_le_15`
- `semantic_multilabel_recall_reported`
- `semantic_gold_contradictions_zero_or_annotated`

Non-goals:

- Do not tune to a hidden holdout artifact by hand.
- Do not let a local reference artifact become the launch claim.

## Phase 17: LogicLens Evidence Retrieval Contract

**Status (2026-05, `main`):** The **fixture-bound** contract is met: committed artifact under `docs/evals/fixtures/logiclens-evidence-benchmark/`, ≥20 active `test/logiclens` rows in `docs/evals/evidence_questions.json` (28 active), committed `docs/evals/evidence_benchmark_report.json`, CLI gate (**accuracy ≥ 0.80**, **hallucination_rate = 0** with `--fail-on-hallucinations`), and `test_evidence_benchmark_meets_phase17_thresholds`. The `paper-checklist` feature `evidence_retrieval` is **implemented** on this corpus only; **real-repo** expansion is explicitly **Phase 18** (see checklist notes).

Goal: provide the backend behavior the LogicLens paper implies: answers and traversals with receipts.

Scope:

- Define an `EvidenceBundle` schema:
  - answer/claim,
  - source node IDs,
  - file paths and ranges,
  - graph paths,
  - edge provenance,
  - confidence,
  - missing evidence,
  - limitations.
- Add CLI/MCP commands:
  - `explain-node`
  - `explain-file`
  - `trace-architecture-path`
  - `find-block-evidence`
  - `answer-architecture-question`
- Ensure every answer can be checked against artifact JSON without model memory.
- Add fixture questions with expected evidence nodes.

Exit evidence:

- At least 20 fixture questions over reference and holdout artifacts.
- Each answer returns evidence bundles, not plain prose only.
- Retrieval quality report includes exact match, partial match, and unsupported answer rate.
- Unsupported questions return "insufficient evidence" rather than hallucinated structure.

Hard gates:

- `retrieval_evidence_bundle_schema_valid`
- `retrieval_fixture_exact_or_partial_ge_80`
- `retrieval_unsupported_hallucination_rate_zero`
- `retrieval_all_claims_have_node_or_path_evidence`

Non-goals:

- Do not optimize for chat polish.
- Do not depend on an LLM to invent graph edges.

## Phase 18: Historical Graph Replay

Goal: temporal truth comes from historical graph snapshots, not just changed path inference.

Scope:

- Extend `temporal-scan --replay-snapshots` to optionally run:
  - Tree-sitter ingest,
  - SCIP indexing when feasible,
  - semantic classification,
  - graph integrity,
  - block benchmark deltas when gold rows apply.
- Persist snapshot lineage:
  - commit,
  - parent,
  - artifact manifest,
  - node/edge counts,
  - block counts,
  - changed architecture surfaces.
- Diff replayed graph snapshots, not only file paths.

Exit evidence:

- One fixture repo with at least three commits shows graph replay and architecture diff.
- One real vendored repo replay runs within an agreed budget.
- Temporal report clearly marks which snapshots are path-only and which are graph-replayed.
- Drift candidates cite changed graph nodes and block transitions.

Hard gates:

- `temporal_replay_fixture_three_commits_passes`
- `temporal_snapshot_lineage_persisted`
- `temporal_replayed_diff_uses_graph_nodes`
- `temporal_path_only_claims_marked_limited`

Non-goals:

- Do not require SCIP replay on every commit for the first pass.
- Do not claim causal proof from temporal correlation.

## Phase 19: Regret SDK Evidence And Plan Quality

Goal: make the Regret SDK a product contract, not a keyword report.

Scope:

- Stabilize schemas:
  - `RegretSurface`,
  - `RegretEvidence`,
  - `SurgeryPlan`,
  - `SimulationResult`,
  - `ExecutionLedger`,
  - `ValidationCommand`.
- For each initial regret type, define:
  - required evidence,
  - supporting evidence,
  - disqualifying evidence,
  - graph pattern,
  - temporal pattern when available,
  - domain-specific remediation plan.
- Start with:
  - logging inconsistency,
  - database sprawl,
  - auth scattering,
  - config leakage,
  - queue/job sprawl,
  - missing observability.
- Add fixtures with hidden labels and human-review notes.

Exit evidence:

- `regret-sdk-scan` returns ranked typed surfaces with evidence bundles.
- Every emitted regret has at least one graph-backed evidence item.
- Logging inconsistency and database sprawl plans are domain-specific and pass fixture assertions.
- Human review rubric exists for plan usefulness.

Hard gates:

- `regret_surfaces_schema_valid`
- `regret_fixture_precision_ge_target`
- `regret_each_surface_has_graph_evidence`
- `regret_plan_specificity_gate_passes`

Non-goals:

- Do not promise autonomous code edits.
- Do not emit generic "refactor this" plans as passing output.

## Phase 20: Beta Artifact And Operator Contract

Goal: make the operator path boring, reproducible, and honest.

Scope:

- Create a beta artifact manifest format:
  - reference artifact,
  - holdout artifact input source,
  - gold set,
  - holdout gold set,
  - corpus report,
  - commands,
  - tool versions,
  - expected gate status.
- Update `run-hard-gates` so a single manifest can drive the run.
- Publish a "known current status" report that says exactly what is green, warning, and red.
- Add Windows smoke instructions and Linux equivalent instructions.
- Keep hidden holdout anti-gaming posture, but document what is intentionally external.

Exit evidence:

- A beta user can run one manifest command and reproduce the claimed result.
- If a hidden/evaluation holdout is required, the command fails with an explicit "holdout required" message rather than an ambiguous quality number.
- Docs never claim a green launch unless the manifest gate is green.

Hard gates:

- `beta_manifest_schema_valid`
- `beta_manifest_run_reproduces_expected_status`
- `beta_no_private_paths`
- `beta_docs_match_gate_status`

Non-goals:

- Do not make "all gates pass" mean "paper complete."
- Do not commit hidden holdout source if anti-gaming requires it to stay controlled.

## Execution Order

1. Phase 15: Canonical Architecture Graph.
2. Phase 16: Semantic Quality Loop.
3. Phase 17: LogicLens Evidence Retrieval Contract.
4. Phase 18: Historical Graph Replay.
5. Phase 19: Regret SDK Evidence And Plan Quality.
6. Phase 20: Beta Artifact And Operator Contract.

This order matters. Regret quality and beta trust depend on graph completeness and semantic quality. Retrieval depends on canonical evidence. Temporal replay depends on canonical artifacts. Beta readiness depends on all of the above agreeing.

## What To Stop Doing

- Stop treating an importable module as a completed phase.
- Stop adding phase commands without a fixture, metric, and failure mode.
- Stop using reference-artifact success as a launch claim.
- Stop reporting "accuracy" without separating coverage from classification quality.
- Stop letting side reports become parallel products outside the canonical graph.

## Decision Rule

A phase is complete only when all are true:

1. implementation exists,
2. CLI/API surface exists,
3. artifact schema is documented,
4. fixture tests pass,
5. holdout or external-corpus report exists where applicable,
6. failure mode is explicit,
7. docs state the current measured status.

Anything less is "implemented but not respectable yet."
