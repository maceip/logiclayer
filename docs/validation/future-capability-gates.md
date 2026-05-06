# Future Capability Gates

Last updated: 2026-05-06

## Purpose

These are **not** restart-state gates.

They are future acceptance gates for the system we actually want to build.

Each gate is written in the form:

- `input`
- `action`
- `required output`
- `why it matters`

The intent is simple:

> given a real repo or real repo set, the system must produce a real result that proves a specific capability exists

This document defines the gates we should eventually pass before claiming:

- feature parity with the LogicLens paper
- no vendor-specific or repo-specific fakery
- readiness to power the original regret-SDK product

## Ground Rules

1. A gate only counts if it runs on real repositories.
2. A gate does not count if the result depends on vendor-specific or repo-specific hardcoding.
3. A gate should be runnable on at least one held-out repo before we call the capability general.
4. A gate should prefer structured output over narrative output.

**Note:** The **Phase 17** `evidence-benchmark` gate is intentionally run on a **small committed fixture** to freeze regression detection; expanding to “real repo sets” without hardcoding is covered by later phases and the gates below — do not treat the fixture alone as proof across arbitrary GitHub repos.

## Repo Sets

### Corpus A: Core vendored corpus

Use repos already present under:

- [vendor/github-repos](C:/Users/mac/heart-transplant/vendor/github-repos)

### Corpus B: Held-out corpus

Use at least one repo not present when the capability was developed.

This corpus is mandatory for anti-fakery validation.

### Corpus C: Source/target regret corpus

Use one or more repo pairs where we have:

- a source repo with a detectable subsystem or vendor footprint
- an expected replacement target or target architectural outcome

This corpus is mandatory for regret-SDK readiness.

## A. Structural Graph Parity Gates

These gates correspond to the paper’s preprocessing and structural graph layer.

### Gate A1: Repo ingest gate

Input:

- one real repo path from Corpus A

Action:

- run canonical structural ingest

Required output:

- one persisted artifact
- nonzero `System`, `Project`, `File`, and `Code` nodes
- nonzero `CONTAINS` edges
- artifact metadata including:
  - repo name
  - language coverage
  - file count
  - code-node count

Why it matters:

- proves the repo really loaded into the graph pipeline

### Gate A2: Multi-repo ingest gate

Input:

- two or more repos from Corpus A

Action:

- ingest both repos into the same graph backend

Required output:

- graph contains multiple `Project` nodes under one `System`
- project-level separation is preserved
- no node id collisions across repos

Why it matters:

- the paper is explicitly multi-repository

### Gate A3: SCIP identity gate

Input:

- one TypeScript or JavaScript repo from Corpus A with real SCIP output

Action:

- run SCIP generation
- consume SCIP into the canonical graph

Required output:

- nonzero `CodeNode` records resolved to real SCIP symbols
- nonzero definition/reference-backed edges
- resolution coverage metrics:
  - total code nodes
  - resolved nodes
  - unresolved nodes

Why it matters:

- “SCIP file exists” is not enough
- real symbol identity is the structural backbone

### Gate A4: Cross-file navigation gate

Input:

- one repo from Corpus A with route, service, and persistence layers

Action:

- start from one code node
- traverse graph edges through at least two files

Required output:

- a machine-readable path like:
  - `source node`
  - `edge type`
  - `target node`
  - repeated for each hop

Why it matters:

- proves the graph is navigable, not just indexed

### Gate A5: Cross-repo navigation gate

Input:

- two repos from Corpus A or B with meaningful structural interaction

Action:

- trace from a node in Repo A to related nodes in Repo B

Required output:

- a graph path that crosses project boundaries
- explicit evidence for the crossing:
  - shared symbol
  - external reference
  - dependency relation
  - or other real graph-supported relation

Why it matters:

- this is one of the core claims of the paper

## B. Semantic Enrichment Parity Gates

These gates correspond to semantic descriptions and higher-level abstractions.

### Gate B1: Code semantic description gate

Input:

- one repo from Corpus A

Action:

- enrich every `Code` node with a semantic description

Required output:

- each selected `Code` node has:
  - structural identity
  - semantic summary
  - provenance of how that summary was generated

Why it matters:

- this is the bridge from syntax to meaningful retrieval

### Gate B2: Project semantic description gate

Input:

- one repo from Corpus A

Action:

- produce project-level semantic summaries from graph structure plus code summaries

Required output:

- each `Project` has a summary that is derivable from the actual graph

Why it matters:

- the paper reasons at more than just function level

### Gate B3: Entity extraction gate

Input:

- one repo from Corpus A with a recognizable business or functional domain

Action:

- extract semantic entities and connect them to code

Required output:

- nonzero `Entity` nodes
- nonzero edges such as:
  - `REPRESENTS`
  - `CREATE`
  - `PRODUCE`
  - `CONFIGURE`
  - `RELATES_TO`
- explicit mapping from code node to entity

Why it matters:

- entity/workflow reasoning is central to the paper’s emergent behavior

### Gate B4: 24-block classification gate

Input:

- one repo from Corpus A

Action:

- classify structural nodes into the 24-block ontology

Required output:

- for each classified node:
  - primary block
  - confidence
  - reasoning
- block assignments stored in the graph

Why it matters:

- this is our intended extension beyond the paper’s original formulation

### Gate B5: Held-out semantic generalization gate

Input:

- one repo from Corpus B

Action:

- run the same semantic enrichment and block classification pipeline without code changes

Required output:

- valid structural graph
- valid semantic descriptions
- valid block classifications

Why it matters:

- proves we did not overfit to the vendored corpus

## C. Reactive Exploration Parity Gates

These gates correspond to the paper’s reactive conversational exploration layer.

### Gate C1: Project tool gate

Input:

- one multi-project graph
- a query asking for systems or projects relevant to a topic

Action:

- invoke the project-oriented graph tool

Required output:

- ranked or filtered project results with graph-backed evidence

Why it matters:

- mirrors the paper’s `Projects Tool`

### Gate C2: Entity tool gate

Input:

- a graph containing extracted entities
- a query about a business concept or workflow

Action:

- invoke the entity-oriented graph tool

Required output:

- returned entities
- attached related code or projects
- evidence path from question to result

Why it matters:

- mirrors the paper’s `Entities Tool`

### Gate C3: Code tool gate

Input:

- a query about concrete implementation logic

Action:

- invoke the code-oriented graph tool

Required output:

- relevant code nodes
- paths to source locations
- graph neighborhood for each returned node

Why it matters:

- mirrors the paper’s `Codes Tool`

### Gate C4: Graph query tool gate

Input:

- a cross-cutting architecture question

Action:

- invoke a general graph query tool over the stored graph

Required output:

- explicit subgraph or traversal result
- not just retrieved source snippets

Why it matters:

- proves we have graph-native reasoning, not disguised RAG

### Gate C5: Source tool gate

Input:

- a graph-backed answer that references concrete implementation

Action:

- retrieve the linked source text for the relevant code nodes

Required output:

- source excerpts or source locations tied to graph results

Why it matters:

- mirrors the paper’s source-grounding behavior

### Gate C6: Continue integration gate

Input:

- one graph-backed query

Action:

- answer it through Continue using MCP tools against the real backend

Required output:

- a response that cites graph-backed results from real tools
- tool-use trace or logged evidence of tool invocation

Why it matters:

- this is the first real operator surface

## D. Paper-Behavior Gates

These gates correspond to the types of outcomes the paper claims as emergent capabilities.

### Gate D1: Impact analysis gate

Input:

- a change question like:
  - “What components must be updated to safely modify this schema?”

Action:

- trace graph neighborhoods and affected components

Required output:

- impacted nodes/files/projects
- graph path or justification for each impacted item

Why it matters:

- this is one of the paper’s headline capabilities

### Gate D2: Symptom-based debugging gate

Input:

- a user symptom stated in functional terms, not code terms

Action:

- use entities, semantic descriptions, and graph traversal to reconstruct likely workflow

Required output:

- candidate failure path
- relevant projects and code nodes
- structured explanation of likely breakpoints

Why it matters:

- this is another of the paper’s headline capabilities

### Gate D3: High-level architecture view gate

Input:

- a query like:
  - “show the flow for authentication”
  - “show the flow for order creation”

Action:

- generate a graph-backed workflow or sequence-style view

Required output:

- ordered path of components, code nodes, entities, or blocks
- optional sequence-diagram-ready structure

Why it matters:

- the paper explicitly calls out architectural view generation

## E. Anti-Fakery Gates

These gates are mandatory because “paper parity” is meaningless if we achieved it by cheating.

### Gate E1: No vendor-special-casing gate

Input:

- source code audit of canonical backend

Action:

- inspect implementation for vendor names used outside tests, fixtures, or examples

Required output:

- a report listing every vendor string found in the implementation
- each occurrence labeled as:
  - test-only
  - fixture-only
  - docs/example-only
  - justified generic runtime logic

Pass condition:

- no vendor-specific runtime logic is required for core capability gates

### Gate E2: No repo-special-casing gate

Input:

- source code audit of canonical backend

Action:

- inspect implementation for explicit references to vendored repo names

Required output:

- same style of report as E1

Pass condition:

- no vendored repo names are required in core runtime logic

### Gate E3: Holdout-corpus portability gate

Input:

- one or more repos from Corpus B

Action:

- run ingest, semantic enrichment, and reactive exploration without modifying the implementation

Required output:

- at least a partial but valid result across the same core stages

Pass condition:

- the system works on a held-out repo with no new repo-specific code

## F. Regret-SDK Readiness Gates

These gates ensure the graph is not just an exploration tool, but a real substrate for the original product.

### Gate F1: Regret surface detection gate

Input:

- one repo from Corpus C
- one target subsystem, module family, or vendor footprint

Action:

- detect the structural and semantic footprint of that regret surface

Required output:

- identified entrypoints
- related files/code nodes
- related semantic blocks
- confidence

Why it matters:

- this is the first step of the original regret workflow

### Gate F2: Blast-radius gate

Input:

- one regret surface from F1

Action:

- traverse affected graph neighborhoods

Required output:

- impacted files
- impacted blocks
- impacted entities
- unresolved or low-confidence zones

Why it matters:

- this is the core transplant-planning step

### Gate F3: Noise-pruning gate

Input:

- one blast-radius result

Action:

- classify direct targets versus adjacent or passive surfaces

Required output:

- `core targets`
- `adjacent references`
- `manual review`
- `excluded noise`

Why it matters:

- without pruning, the regret system becomes noisy and unusable

### Gate F4: Surgery-plan gate

Input:

- one regret surface and one desired target outcome

Action:

- convert graph findings into an execution-ready plan

Required output:

- target nodes/files
- related blocks
- confidence
- unresolved risks
- structured output suitable for downstream editing/orchestration

Why it matters:

- this is the bridge from understanding to action

### Gate F5: Execution-handoff gate

Input:

- one surgery plan

Action:

- hand it to an execution layer such as Continue

Required output:

- a structured payload that a downstream tool can consume without bespoke glue for one repo

Why it matters:

- proves the graph is useful for the actual product, not just research-style exploration

## G. Evaluation Gates

These gates define when we can claim paper-level quality, not just paper-shaped architecture.

### Gate G1: Question benchmark gate

Input:

- a benchmark of system questions over Corpus A and B

Action:

- run the reactive graph system over the benchmark

Required output:

- stored answers
- stored evidence paths
- stored scores

### Gate G2: Baseline comparison gate

Input:

- same benchmark as G1

Action:

- compare graph-backed system to a simpler retrieval baseline

Required output:

- side-by-side result set
- measured differences

### Gate G3: Quality-score gate

Input:

- benchmark answers from G1 and G2

Action:

- score for:
  - accuracy
  - completeness
  - coherence

Required output:

- a report that lets us compare against the paper’s evaluation shape

## Minimal Future Milestone Sequence

If we want a realistic but challenging order, it should be:

1. Pass `A1`, `A2`, `A3`, `A4`
2. Pass `A5`
3. Pass `B1`, `B2`, `B3`
4. Pass `B4`, `B5`
5. Pass `C1` through `C6`
6. Pass `D1`, `D2`, `D3`
7. Pass `E1`, `E2`, `E3`
8. Pass `F1` through `F5`
9. Pass `G1`, `G2`, `G3`

## Final Definition Of “Done”

We should only say we reached the target when all three are true:

1. enough of `A` through `D` are passing that paper feature parity is real in behavior, not just architecture
2. `E` passes, so we know we did not fake that parity with vendor- or repo-specific scaffolding
3. `F` passes, so the system is actually useful for the original regret-SDK product

Until then, we should describe the system by the highest set of future gates it actually passes, and nothing more.
