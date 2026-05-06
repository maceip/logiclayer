# LogicLens-Paper-Grade Roadmap

Last updated: 2026-05-06

**Checklist snapshot**: run `heart-transplant paper-checklist` — the repo tracks **10** paper-shaped features (**2** implemented, **8** partial, **0** missing). The second **implemented** item is **evidence retrieval**, gated on the **committed Phase 17 fixture** (`docs/evals/fixtures/logiclens-evidence-benchmark/`, `docs/evals/evidence_questions.json`, `docs/evals/evidence_benchmark_report.json`, CI test). For the long-form April 2026 assessment below, treat prose that still says “1 implemented” as **superseded** by the checklist output.

---

Last updated: 2026-04-28

**Major update (April 2026 archive below)**: The roadmap body reflects the April 27-28 work: 50-repo corpus synthesis, iterative ingest traversal, Rust/Java/C/C++ parser coverage, file-surface nodes, SCIP-only orphan promotion, canonical graph/evidence surfaces, `paper-checklist`, and the GitHub Pages repo-surgery console. Phases 9–14 remain the organizing structure. **Do not** use the sentence below about “1 paper feature implemented” as current — use `paper-checklist` (see box at top of this file).

## Purpose

This document is a hard reset on project claims.

Its job is to describe:

- what `heart-transplant` actually does today
- what is only partial or broken
- what exact steps are needed to reach a system that is as good as, and eventually better than, the LogicLens paper architecture

This document is intentionally based only on real code, real files, and real command output from the current repo.

## Evidence Used For This Assessment

This roadmap started from the older commands below and has been updated with the current April 28 code surface. Use `paper-checklist`, `program-surface`, and the repo-root gates for the latest machine-readable status.

- `.\.venv-win\Scripts\python.exe -m pytest`
  - current recently verified result: `61 passed, 1 warning`
- `.\.venv-win\Scripts\python.exe -m heart_transplant.cli paper-checklist`
  - use the emitted JSON for current counts; as of 2026-05-06: **10** features, **2** implemented, **8** partial, **0** missing
- `docs/evals/trending-top50-ec2-first-synthesis-2026-04-27.md`
  - preserved first 50-repo EC2 synthesis with 3 ingest crashes and 6 zero-node successes documented
- `docs/evals/block-classification-benchmark-2026-04-27.md`
  - preserved block benchmark baseline; predates file-surface and secondary-block scoring

Older reference artifact retained for comparison:

- [2026-04-24T12-57-30Z__boomNDS__elysia-supabase-tempate](C:/Users/mac/heart-transplant/.heart-transplant/artifacts/2026-04-24T12-57-30Z__boomNDS__elysia-supabase-tempate)

## Status Legend

- `real`: implemented and exercised with real tools or real data
- `partial`: implemented, but a critical seam is incomplete or broken
- `missing`: not implemented in the canonical backend
- `archived`: exists only in the legacy prototype and should not be treated as the foundation

## Current State Snapshot

### What is real today

1. `Tree-sitter-based local ingest`

- Implemented in [treesitter_ingest.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/ingest/treesitter_ingest.py)
- Supports TypeScript/TSX/JavaScript/Python/Go/Prisma/Rust/Java/C/C++
- Produces `FileNode`, file-surface `CodeNode`, symbol `CodeNode`, and `CONTAINS` edges
- Uses iterative traversal for deep parse trees

2. `Canonical Python backend`

- Package config: [pyproject.toml](C:/Users/mac/heart-transplant/backend/pyproject.toml)
- CLI: [cli.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/cli.py)
- Models: [models.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/models.py)
- 24-block ontology preserved in [ontology.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/ontology.py)

3. `Durable structural artifacts on disk`

- Stored under [C:\Users\mac\heart-transplant\.heart-transplant\artifacts](C:/Users/mac/heart-transplant/.heart-transplant/artifacts)
- Written by [artifact_store.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/artifact_store.py)

4. `Real SCIP generation for TS/JS repos`

- Implemented in [scip_typescript.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/scip_typescript.py)
- Uses real `@sourcegraph/scip-typescript`
- Latest captured metadata:
  - tool name: `scip-typescript`
  - version: `0.4.0`
  - package manager detected: `bun`

5. `Basic graph smoke testing`

- Implemented in [graph_smoke.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/graph_smoke.py)
- Current reference artifact reports:
  - `40` code nodes
  - `40` structural edges
  - `40` contains edges
  - `0` missing containment edges

6. `LogicLens evidence-contract surfaces`

- Implemented through `canonical-graph`, `explain-node`, `explain-file`, `trace-dependency`, `find-architectural-block`, `answer-with-evidence`, `query-codes`, `evidence-benchmark`, and `paper-checklist`
- **Phase 17**: `evidence_retrieval` is **implemented** on the committed `test/logiclens` fixture (see `docs/evals/evidence_benchmark_report.json` and `test_evidence_benchmark_meets_phase17_thresholds`). Broader real-repo scoring remains future work (Phase 18+).

7. `50-repo corpus pressure`

- The first 50-repo EC2 synthesis is preserved under `docs/evals/`
- The three first-run ingest crashes were recursive traversal failures; iterative traversal has landed
- The six zero-node successes were parser coverage failures; Rust/Java/C/C++ coverage has landed
- The full 50-repo corpus still needs a post-fix rerun before replacing the preserved baseline

### What is partial today

1. `SCIP consumption`

- Implemented in [scip_consume.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/scip_consume.py)
- It parses the real binary `index.scip` via official protobuf bindings from [scip_pb2.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/generated/scip_pb2.py)
- It reads definitions, references, and symbol relationships

Current status:

- latest reference artifact now shows `resolved_code_nodes = 40`
- latest reference artifact still shows `implementation_edges = []`
- latest reference artifact shows `orphaned_symbol_count = 616`

That means SCIP is now successfully driving symbol identity inside our graph, but our structural extraction is still too shallow relative to the symbol information available in the index.

The current canonical backend has a real SCIP integration seam now. The remaining problem is not path normalization anymore; it is parser coverage and symbol-to-structure granularity.

2. `Structural coverage`

- The latest graph smoke report shows `node_kind_counts = { "function": 40 }`
- That means the current extractor is function-heavy and not yet giving us a rich structural spine across classes, methods, interfaces, routes, configs, schemas, imports, and symbol references

This is useful, but still too shallow to be called paper-grade.

### What is missing today

1. `Cross-repo SCIP linking`

- We do not yet stitch multiple repos together through shared symbol identities or external references

2. `Continue CLI graph exploration`

- Continue is not yet acting against the new canonical graph backend

3. `Paper-style evaluation harness`

- We do not yet have the equivalent of a reproducible question set with answer scoring against a baseline
- We do have starter gold block benchmarks and a paper feature checklist

### What is archived and should not guide new architecture

- The old JS/Semantica/frontend path is not present in this checkout. Legacy code was excluded from the clean-room restart rather than preserved under an `archive/` path.

That code may still contain useful ideas or reference implementations, but it is not the canonical path.

## Comparison To The LogicLens Paper

If the standard is:

> “are we implementing the same kind of system the paper describes?”

then the current answer is:

- `structural ingest`: yes, but shallow
- `semantic enrichment`: partial
- `entity/action semantic layer`: partial and not yet scored
- `graph retrieval tooling`: partial
- `paper-style evaluation`: no

If the standard is:

> “are we building something fake?”

then the answer is: no. The current backend is implemented and testable, but most paper-shaped capabilities are still partial.

The biggest present danger is stopping at “we have surfaces” instead of measuring whether they answer architecture questions better than a baseline.

## Architectural Target

We are implementing a concrete stack inspired by the LogicLens architecture pattern:

1. `Structural extraction`
- Tree-sitter
- SCIP
- durable code-unit artifacts
- later: SurrealDB as canonical graph storage

2. `Semantic enrichment`
- Pydantic-AI
- classification into 24 universal functional blocks
- confidence + reasoning attached to structural nodes

3. `Reactive reasoning`
- MCP Python SDK
- graph query tools exposed to an agent
- Continue CLI as the first operator surface

This means the path forward is not “add more heuristics.”

It is:

- make the structural spine trustworthy
- then add semantic meaning
- then add agentic navigation

## Principles For The Next Phase

1. Do not add demo-only layers before the structural seam is correct.
2. Do not claim cross-repo intelligence before SCIP-backed linking exists.
3. Do not call semantic classification product-ready until holdout scoring improves.
4. Do not add Continue orchestration claims until the real query surface is exercised end to end.
5. Prefer fewer real capabilities over more impressive-looking partial ones.
6. Canonicalize identity early. File and node identity must not depend on operating-system path separators.
7. Make parser ownership explicit. Tree-sitter owns spatial boundaries; SCIP owns logical identity and reference topology.
8. Control graph density deliberately. Only structurally addressable units should become first-class graph nodes by default.
9. Prune trajectories before they reach an agent. Large raw neighborhoods are a backend problem, not an LLM problem.

## Concrete Implementation Glue

This section turns the roadmap into a buildable blueprint.

It does **not** mean all of this exists today.

It means:

- these are the concrete structures we should converge toward
- new code should prefer these shapes instead of inventing ad hoc ones
- future work should fill these modules in rather than creating side paths

### Canonical Backend Layout

Target backend package shape:

- `backend/src/heart_transplant/models/`
  - Pydantic models and enums
- `backend/src/heart_transplant/ingest/`
  - Tree-sitter extraction
  - repo traversal
  - import extraction
  - route/config extraction
- `backend/src/heart_transplant/scip/`
  - SCIP generation
  - SCIP consumption
  - symbol linking
- `backend/src/heart_transplant/graph/`
  - graph builders
  - neighborhood expansion
  - path tracing
- `backend/src/heart_transplant/db/`
  - SurrealDB schema
  - loaders
  - read/query repository
- `backend/src/heart_transplant/classify/`
  - Pydantic-AI prompts
  - semantic mapping services
  - block classifiers
- `backend/src/heart_transplant/entities/`
  - entity extraction
  - workflow/action edge generation
- `backend/src/heart_transplant/mcp/`
  - MCP server
  - tool definitions
- `backend/src/heart_transplant/evals/`
  - benchmark loaders
  - baseline runners
  - scoring
- `backend/src/heart_transplant/cli.py`
  - thin entrypoint only, delegating to services

### Domain Model Targets

These are the main structures we should standardize around.

#### Structural layer

```python
from enum import Enum
from pydantic import BaseModel, Field


class NodeKind(str, Enum):
    SYSTEM = "system"
    PROJECT = "project"
    FILE = "file"
    CODE = "code"
    ENTITY = "entity"
    BLOCK = "block"
    PACKAGE = "package"


class CodeKind(str, Enum):
    FUNCTION = "function"
    CLASS = "class"
    INTERFACE = "interface"
    METHOD = "method"
    VARIABLE = "variable"
    ROUTE_HANDLER = "route_handler"
    CONFIG_OBJECT = "config_object"


class SourceRange(BaseModel):
    start_line: int
    start_col: int
    end_line: int
    end_col: int


class CodeNode(BaseModel):
    node_id: str
    scip_id: str | None = None
    provisional_id: str | None = None
    repo_name: str
    project_id: str
    file_path: str
    language: str
    name: str
    kind: CodeKind
    range: SourceRange
    content: str
    symbol_source: str = "provisional"
```

Identity contract:

- `node_id` should become the canonical graph identity
- `scip_id` is the raw upstream SCIP symbol when available
- `provisional_id` is the Tree-sitter fallback
- file references should normalize to a canonical URI like:
  - `repo://<repo_name>/<normalized_path>`
- provisional structural identities should normalize to:
  - `repo://<repo_name>/<normalized_path>#<symbol_name>:<kind>:<start_line>`

#### Structural relations

```python
class EdgeKind(str, Enum):
    CONTAINS = "CONTAINS"
    DEPENDS_ON = "DEPENDS_ON"
    CALLS = "CALLS"
    IMPLEMENTS = "IMPLEMENTS"
    DEFINES = "DEFINES"
    REFERENCES = "REFERENCES"
    IMPORTS_MODULE = "IMPORTS_MODULE"
    BELONGS_TO_BLOCK = "BELONGS_TO_BLOCK"
    REPRESENTS = "REPRESENTS"
    RELATES_TO = "RELATES_TO"
    CREATE = "CREATE"
    PRODUCE = "PRODUCE"
    CONFIGURE = "CONFIGURE"


class GraphEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeKind
    repo_name: str | None = None
    confidence: float | None = None
    provenance: str | None = None
```

#### Semantic layer

```python
class SemanticSummary(BaseModel):
    node_id: str
    summary_type: str  # code, file, project, system
    text: str
    provenance: str  # pydantic-ai:model-name:prompt-version


class SemanticEntity(BaseModel):
    entity_id: str
    name: str
    category: str
    description: str | None = None


class SemanticAction(BaseModel):
    source_code_node_id: str
    entity_id: str
    action: str  # CREATE / PRODUCE / CONFIGURE / REPRESENTS / RELATES_TO
    confidence: float
    reasoning: str
```

#### 24-block layer

```python
class BlockAssignment(BaseModel):
    node_id: str
    primary_block: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    supporting_neighbors: list[str] = []
```

#### Artifact layer

```python
class StructuralArtifact(BaseModel):
    artifact_id: str
    repo_name: str
    repo_path: str
    parser_backends: list[str]
    node_count: int
    edge_count: int
    code_nodes: list[CodeNode]
    edges: list[GraphEdge]


class SemanticArtifact(BaseModel):
    artifact_id: str
    semantic_summaries: list[SemanticSummary]
    entities: list[SemanticEntity]
    actions: list[SemanticAction]
    block_assignments: list[BlockAssignment]
```

### Service Structure

The backend should be organized around a few explicit services instead of one large script.

#### 1. Ingest service

Purpose:

- walk repositories
- parse source files
- produce structural nodes and edges

Target interface:

```python
from pathlib import Path
from typing import Protocol


class IngestService(Protocol):
    def ingest_repo(self, repo_path: Path, repo_name: str) -> StructuralArtifact: ...
```

Likely implementation modules:

- `ingest/repo_walker.py`
- `ingest/treesitter_ingest.py`
- `ingest/import_extractor.py`
- `ingest/file_classifier.py`

#### 2. SCIP service

Purpose:

- generate SCIP indices
- consume them
- reconcile structural nodes with real symbol identities

Target interface:

```python
class ScipService(Protocol):
    def generate_index(self, repo_path: Path, artifact_dir: Path) -> dict: ...
    def consume_index(self, artifact_dir: Path) -> StructuralArtifact: ...
    def resolution_metrics(self, artifact_dir: Path) -> dict: ...
```

Likely implementation modules:

- `scip/generate.py`
- `scip/consume.py`
- `scip/linker.py`
- `scip/path_normalization.py`

Resolution contract:

- Tree-sitter owns:
  - `SourceRange`
  - `content`
  - file-local spatial extraction
- SCIP owns:
  - canonical logical identity
  - `DEFINES`
  - `REFERENCES`
  - `IMPLEMENTS`
- if SCIP finds a symbol but Tree-sitter has no matching structural node, log it as a parser deficiency rather than guessing boundaries

#### 3. Graph store service

Purpose:

- load artifacts into SurrealDB
- provide graph-native read/query methods

Target interface:

```python
class GraphStore(Protocol):
    def load_structural_artifact(self, artifact: StructuralArtifact) -> None: ...
    def load_semantic_artifact(self, artifact: SemanticArtifact) -> None: ...
    def get_node(self, node_id: str) -> dict | None: ...
    def get_neighbors(self, node_id: str, edge_types: list[str] | None = None) -> list[dict]: ...
    def trace_path(self, start_id: str, end_id: str | None = None, max_depth: int = 6) -> list[dict]: ...
```

Likely implementation modules:

- `db/surreal_schema.py`
- `db/surreal_loader.py`
- `db/surreal_queries.py`

#### 4. Semantic enrichment service

Purpose:

- produce code/project/system summaries
- extract entities and action edges
- classify into the 24 blocks

Target interface:

```python
class SemanticEnrichmentService(Protocol):
    def summarize_code_nodes(self, nodes: list[CodeNode]) -> list[SemanticSummary]: ...
    def summarize_projects(self, project_ids: list[str]) -> list[SemanticSummary]: ...
    def extract_entities(self, repo_name: str) -> list[SemanticEntity]: ...
    def classify_blocks(self, node_ids: list[str]) -> list[BlockAssignment]: ...
```

Likely implementation modules:

- `classify/code_summarizer.py`
- `classify/project_summarizer.py`
- `entities/extractor.py`
- `classify/block_mapper.py`

#### 5. Reactive query service

Purpose:

- expose paper-style retrieval tools over the graph

Target interface:

```python
class QueryService(Protocol):
    def find_projects(self, query: str) -> list[dict]: ...
    def find_entities(self, query: str) -> list[dict]: ...
    def find_codes(self, query: str) -> list[dict]: ...
    def graph_query(self, query: str) -> dict: ...
    def source_lookup(self, node_ids: list[str]) -> list[dict]: ...
```

Likely implementation modules:

- `graph/projects_tool.py`
- `graph/entities_tool.py`
- `graph/codes_tool.py`
- `graph/query_tool.py`
- `graph/source_tool.py`

#### 6. Regret planning service

Purpose:

- convert graph understanding into a structured surgery plan

Target interface:

```python
class RegretPlanner(Protocol):
    def detect_regret_surface(self, repo_name: str, regret_hint: str) -> dict: ...
    def compute_blast_radius(self, root_ids: list[str]) -> dict: ...
    def prune_targets(self, blast_radius: dict) -> dict: ...
    def build_surgery_plan(self, pruned_targets: dict, target_outcome: str) -> dict: ...
```

Likely implementation modules:

- `graph/regret_detector.py`
- `graph/blast_radius.py`
- `graph/pruning.py`
- `graph/surgery_plan.py`

Trajectory-pruning contract:

- `compute_blast_radius` may explore a larger subgraph than an agent should ever see
- `prune_targets` must compress the result into a bounded architectural view
- pruning should:
  - remove high-degree utility nodes when they do not represent architectural seams
  - collapse uninformative linear call chains
  - preserve cross-project, entity, and block boundary nodes
  - respect configurable node or token budgets

### SurrealDB Shape

We should settle on a small, explicit record design early.

Target record families:

- `system:<id>`
- `project:<id>`
- `file:<id>`
- `code:<id>`
- `entity:<id>`
- `block:<id>`
- `package:<id>`

Target edge tables or relations:

- `contains`
- `depends_on`
- `calls`
- `implements`
- `defines`
- `references`
- `imports_module`
- `belongs_to_block`
- `represents`
- `relates_to`
- `creates`
- `produces`
- `configures`

Target minimum stored fields:

```python
{
  "id": "code:...",
  "repo_name": "...",
  "project_id": "project:...",
  "file_path": "...",
  "name": "...",
  "kind": "...",
  "language": "...",
  "scip_id": "...",
  "provisional_id": "...",
  "summary": "...",  # when available
}
```

Indexing strategy target:

- index node ids
- index `scip_id`
- index `edge_type`
- index `repo_name`

### Artifact File Shape

The artifact directory should gradually standardize around these files:

- `structural-artifact.json`
- `scip-index.json`
- `index.scip`
- `scip-consumed.json`
- `semantic-artifact.json`
- `block-assignments.json`
- `entity-artifact.json`
- `surreal-load-report.json`
- `eval-report.json`

This keeps replay and debugging easy.

### MCP Tool Contracts

We should keep the first MCP tool set close to the paper’s affordances.

#### `get_projects`

Input:

```json
{ "query": "authentication flow" }
```

Output:

```json
{
  "projects": [
    {
      "project_id": "project:frontend",
      "repo_name": "acme/frontend",
      "score": 0.92,
      "evidence": ["entity:session", "block:identity_ui"]
    }
  ]
}
```

#### `get_entities`

Input:

```json
{ "query": "session" }
```

Output:

```json
{
  "entities": [
    {
      "entity_id": "entity:session",
      "name": "Session",
      "related_code_nodes": ["code:...", "code:..."]
    }
  ]
}
```

#### `get_codes`

Input:

```json
{ "query": "where is access control enforced" }
```

Output:

```json
{
  "codes": [
    {
      "node_id": "code:...",
      "name": "requireAdmin",
      "file_path": "src/utils/auth.ts",
      "summary": "..."
    }
  ]
}
```

#### `graph_query`

Input:

```json
{
  "start_id": "code:frontend_button",
  "end_block": "data_persistence",
  "max_depth": 8
}
```

Output:

```json
{
  "path": [
    {"node_id": "code:frontend_button", "edge_type": "CALLS"},
    {"node_id": "code:submitOrder", "edge_type": "CALLS"},
    {"node_id": "code:createOrderRecord", "edge_type": "BELONGS_TO_BLOCK"}
  ]
}
```

#### `source_lookup`

Input:

```json
{ "node_ids": ["code:..."] }
```

Output:

```json
{
  "sources": [
    {
      "node_id": "code:...",
      "repo_name": "acme/backend",
      "file_path": "src/routes/auth.ts",
      "range": {"start_line": 10, "end_line": 40},
      "content": "..."
    }
  ]
}
```

### Evaluation Service Shape

We should avoid baking eval logic into ad hoc notebooks or scripts.

Target types:

```python
class EvalQuestion(BaseModel):
    question_id: str
    corpus: str
    question: str
    expected_capability: str
    expected_scope: list[str] = []


class EvalAnswer(BaseModel):
    question_id: str
    system_name: str
    answer_text: str
    evidence_node_ids: list[str]
    evidence_paths: list[dict]


class EvalScore(BaseModel):
    question_id: str
    system_name: str
    accuracy: float
    completeness: float
    coherence: float
    notes: str | None = None
```

Target modules:

- `evals/questions.py`
- `evals/baseline_runner.py`
- `evals/graph_runner.py`
- `evals/scoring.py`

### Regret-SDK Output Shape

The graph system becomes genuinely useful once it can emit a stable planning payload.

Target planning output:

```python
class RegretSurface(BaseModel):
    regret_id: str
    label: str
    root_node_ids: list[str]
    related_blocks: list[str]
    confidence: float


class BlastRadius(BaseModel):
    regret_id: str
    impacted_node_ids: list[str]
    impacted_files: list[str]
    impacted_blocks: list[str]
    impacted_entities: list[str]
    unresolved_zones: list[str]


class SurgeryPlan(BaseModel):
    regret_id: str
    target_outcome: str
    core_targets: list[str]
    adjacent_references: list[str]
    manual_review: list[str]
    excluded_noise: list[str]
    reasoning: list[str]
```

This is the payload that later execution tooling should consume.

### Recommended Near-Term File Moves

To reduce future refactors, the next few structural moves should likely be:

1. split [models.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/models.py) into:
   - `models/structural.py`
   - `models/semantic.py`
   - `models/eval.py`
2. move [scip_typescript.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/scip_typescript.py) and [scip_consume.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/scip_consume.py) into a `scip/` package
3. add a `db/` package before SurrealDB work begins
4. keep [cli.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/cli.py) thin by delegating every command into services

## Baby Steps To Reach A Paper-Grade System

The sequence below is intentionally granular.

### Phase 0: Make The Existing Structural Spine Honest

This phase is about making the current milestone truly work before expanding scope.

#### Step 0.1: Fix SCIP path normalization

Files to change first:

- [scip_consume.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/scip_consume.py)

New helper target:

- `scip/path_normalization.py`

Needed work:

- build a strict canonical URI builder for repo paths
- normalize both Tree-sitter and SCIP paths into the same repo URI scheme before matching
- normalize file loading paths through the same scheme
- re-run consumption on the latest artifact

Acceptance criteria:

- `resolved_code_nodes > 0` on the current reference artifact
- `scip_resolved_nodes > 0` in `test-graph`
- at least one real `CodeNode.scip_id` stops being provisional

#### Step 0.2: Add targeted tests for real-world path normalization

Files:

- [test_scip_consume.py](C:/Users/mac/heart-transplant/backend/tests/test_scip_consume.py)

Needed work:

- add a fixture where SCIP documents use backslashes and structural nodes use forward slashes
- prove the same node resolves after normalization

Acceptance criteria:

- regression test fails before fix and passes after fix

#### Step 0.6: Log parser conflicts explicitly

Files:

- [scip_consume.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/scip_consume.py)

Needed work:

- when SCIP reports a definition and no matching Tree-sitter node exists:
  - do not guess a node boundary
  - write an entry to `orphaned-symbols.json`
- use this artifact as a metric for parser deficiencies

Acceptance criteria:

- every unresolved definition due to missing structural nodes appears in `orphaned-symbols.json`
- the count is reported in `scip-consumed.json`

#### Step 0.3: Preserve both provisional identity and resolved identity cleanly

Files:

- [models.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/models.py)
- [scip_consume.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/scip_consume.py)

Needed work:

- ensure every resolved node keeps:
  - original provisional id
  - resolved SCIP symbol
  - symbol source
- add explicit metadata if needed for auditability

Acceptance criteria:

- no resolved node loses its original provisional identity history

#### Step 0.4: Generate real SCIP-derived edges, not just consumed reports

Files:

- [scip_consume.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/scip_consume.py)
- [models.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/models.py)

Needed work:

- map definition/reference information into graph edges
- add support for at least:
  - `DEFINES`
  - `REFERENCES`
  - `IMPLEMENTS`
- persist them back into the structural artifact

Acceptance criteria:

- `edge_count` grows beyond `CONTAINS`
- `test-graph` can report nonzero SCIP-backed edges

#### Step 0.5: Stop treating “SCIP consumed” as success unless nodes actually resolved

Files:

- [graph_smoke.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/graph_smoke.py)
- [cli.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/cli.py)

Needed work:

- make smoke output emphasize resolution success, not just file presence
- optionally add a failing health check when SCIP exists but resolution is zero

Acceptance criteria:

- the CLI makes it impossible to mistake “SCIP file exists” for “SCIP is integrated”

### Phase 1: Upgrade Structural Extraction To A True Structural Spine

This phase is about making the graph itself worthy of downstream semantic work.

#### Step 1.1: Expand code unit coverage

Files:

- [treesitter_ingest.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/ingest/treesitter_ingest.py)

Needed work:

- extract more than functions
- robustly capture:
  - classes
  - methods
  - interfaces
  - exported functions
  - exported constants that wrap functions
  - route handlers where structurally discoverable

Granularity constraint:

- do not promote block-scoped local variables or purely internal control-flow fragments into first-class graph nodes by default
- only promote structurally addressable units that matter across file, module, service, or architectural boundaries

Acceptance criteria:

- the current Elysia artifact includes non-function node kinds where they exist
- `node_kind_counts` is meaningfully richer than just `function`

#### Step 1.2: Add import-level structural edges

Files:

- [treesitter_ingest.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/ingest/treesitter_ingest.py)
- possibly a new helper module under `backend/src/heart_transplant/ingest/`

Needed work:

- parse import declarations
- add edges like:
  - `IMPORTS_MODULE`
  - `DEPENDS_ON_FILE`
- distinguish local imports from external packages

Acceptance criteria:

- artifact edges describe file-level dependency structure, not only containment

#### Step 1.3: Add file nodes and project nodes explicitly into the persisted model

Files:

- [models.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/models.py)
- [treesitter_ingest.py](C:/Users/mac/heart-transplant/backend/src/heart_transplant/ingest/treesitter_ingest.py)

Needed work:

- stop implying file nodes only through `file://...` edge sources
- persist explicit file-level and project-level nodes

Acceptance criteria:

- graph can be queried without reconstructing file nodes from string ids

#### Step 1.4: Add structural metadata for code neighborhoods

Needed work:

- persist node-to-file, file-to-project, and import neighborhoods in a query-friendly form
- build helper accessors for neighborhood retrieval

Acceptance criteria:

- any `CodeNode` can be expanded into its immediate neighborhood without rescanning source files

#### Step 1.5: Index all vendored repos through the same path

Data set:

- [vendor/github-repos](C:/Users/mac/heart-transplant/vendor/github-repos)

Needed work:

- run canonical ingest over all vendored repos
- capture artifact summaries for each
- note failures and unsupported languages explicitly

Acceptance criteria:

- one repeatable corpus-wide ingest command exists
- all ingest failures are categorized, not silently skipped

### Phase 2: Make SCIP The Identity Backbone

This phase is what turns the graph from “parsed code” into “navigable symbols.”

#### Step 2.1: Replace provisional ids wherever real SCIP symbol identities exist

Goal:

- `CodeNode.scip_id` should become truly canonical when a match is available

Acceptance criteria:

- reference artifact resolves a meaningful share of nodes
- reports include a coverage metric such as:
  - total code nodes
  - nodes with real SCIP ids
  - nodes still provisional

#### Step 2.2: Build symbol-level reference edges

Needed work:

- map SCIP occurrences to:
  - definition edges
  - reference edges
  - symbol-to-symbol or file-to-symbol edges as appropriate

Acceptance criteria:

- a query can answer:
  - “where is this symbol defined?”
  - “where is this symbol referenced?”

#### Step 2.3: Build cross-file navigation from SCIP

Needed work:

- walk symbol references across files
- ensure the graph can follow usage paths across the repo

Acceptance criteria:

- from a route handler symbol, we can traverse into service or library symbols through real graph edges

#### Step 2.4: Build multi-repo symbol identity handling

Needed work:

- index more than one repo
- capture external symbols and shared symbols
- resolve when Repo A references definitions in Repo B, where supported by indexing

Acceptance criteria:

- a real multi-repo example exists in the vendored corpus or a small curated test setup

### Phase 3: Move The Canonical Graph Into SurrealDB

JSON artifacts are good for audit and replay, but not sufficient as the long-term graph backend.

#### Step 3.1: Define the canonical graph schema in SurrealDB

Needed entities:

- system
- project
- file
- code node
- package/module
- semantic block

Needed relations:

- contains
- imports
- defines
- references
- implements
- belongs_to_block
- classified_as

Acceptance criteria:

- schema document exists
- a small loader can insert one artifact into SurrealDB deterministically

#### Step 3.2: Build an artifact-to-Surreal loader

New likely module:

- `backend/src/heart_transplant/db/surreal_loader.py`

Needed work:

- load nodes and edges from a saved artifact
- use stable ids so repeated loads are idempotent

Acceptance criteria:

- reloading the same artifact does not duplicate graph entities

#### Step 3.3: Add graph verification queries

Needed work:

- create a tiny validation suite that checks:
  - code nodes inserted
  - reference edges inserted
  - repo/file containment inserted

Acceptance criteria:

- one command can assert that an artifact is correctly reflected in SurrealDB

#### Step 3.4: Add SurrealDB indexing strategy

Needed work:

- explicitly create indexes on:
  - node id
  - `scip_id`
  - `edge_type`
  - `repo_name`

Acceptance criteria:

- graph path queries do not rely on full table scans
- indexing strategy is documented and versioned with the schema

### Phase 4: Add Semantic Enrichment With Pydantic-AI

This phase should start only after structural neighborhoods are trustworthy.

#### Step 4.1: Define semantic mapping models in Python

Needed work:

- implement the typed mapping models from the verified architecture
- include:
  - primary block
  - confidence
  - reasoning

Acceptance criteria:

- semantic output is validated by Pydantic before persistence

#### Step 4.2: Build a neighborhood-aware classifier

Needed work:

- feed the model:
  - code content
  - file path
  - import neighborhood
  - reference neighborhood
  - nearby package information
- classify into one of the 24 blocks

Acceptance criteria:

- the classifier can stamp at least one vendored repo end to end

#### Step 4.3: Create a gold set for classification quality

Use:

- [docs/evals/vendored-ground-truth.md](C:/Users/mac/heart-transplant/docs/evals/vendored-ground-truth.md)

Needed work:

- manually annotate a subset of nodes/files from vendored repos
- use that as a first semantic benchmark

Acceptance criteria:

- we can measure where block classification is correct, over-broad, or wrong

#### Step 4.4: Persist semantic assignments into SurrealDB

Needed work:

- write semantic block relations into the graph
- include confidence and reasoning

Acceptance criteria:

- query can answer:
  - “which code nodes belong to Access Control?”
  - “which files touch Data Persistence with high confidence?”

### Phase 5: Build The Reactive Graph Tool Layer

This is the bridge from “graph exists” to “agent can use graph.”

#### Step 5.1: Add MCP server skeleton

Likely new module:

- `backend/src/heart_transplant/mcp_server.py`

Needed tools:

- `get_node`
- `get_neighbors`
- `trace_symbol_path`
- `find_block_nodes`
- `get_impact_radius`

Acceptance criteria:

- tools return real graph data from SurrealDB

#### Step 5.2: Add retrieval surfaces similar to the paper’s graph navigation affordances

Needed work:

- project-oriented retrieval
- code-oriented retrieval
- semantic-block-oriented retrieval
- source lookup

Acceptance criteria:

- an operator can answer targeted system questions without raw database access

### Phase 6: Add Continue CLI As The First Operator Surface

Continue should come after the graph is queryable.

#### Step 6.1: Wire Continue to MCP graph tools

Needed work:

- expose the graph through MCP
- prove Continue can use those tools in a real session

Acceptance criteria:

- Continue can answer a graph-backed question using MCP tools rather than static prompt context

#### Step 6.2: Add first “regret to impact radius” flow

Needed work:

- select one concrete vendored use case
- trace from a frontend auth entrypoint to backend auth/data surfaces
- ensure `compute_blast_radius` returns a compressed subgraph suitable for an agent rather than a raw unbounded neighborhood

Acceptance criteria:

- Continue can explain the impact radius using the graph
- the returned subgraph is bounded by configurable node or token limits
- high-degree utility nodes are pruned unless they are architectural seam nodes

### Phase 7: Build A Paper-Style Evaluation Harness

This is the point where we can compare ourselves to paper-quality system behavior.

#### Step 7.1: Create a question set over the vendored corpus

Needed work:

- author a small benchmark of cross-file and cross-repo system questions
- keep it versioned in `docs/evals/` or a dedicated eval package

Good first question categories:

- locate access control
- trace identity flow
- trace request path into data persistence
- identify frontend blocks impacted by backend schema change

Acceptance criteria:

- benchmark is stable and reproducible

#### Step 7.2: Add a baseline

Needed work:

- compare graph-backed answers against a simpler retrieval baseline

Acceptance criteria:

- we can state where graph structure actually helps

#### Step 7.3: Score answer quality

Needed work:

- define a rubric for:
  - accuracy
  - completeness
  - coherence

Acceptance criteria:

- we can track progress numerically instead of subjectively

### Phase 8: Get Better Than The Paper

We should only talk about “better than the paper” after Phase 7 exists.

The likely ways to exceed it are:

1. Better implementation discipline

- durable artifacts
- replayable ingest
- deterministic graph builds
- auditable classification

2. Better architectural ontology

- the 24 universal blocks give us a more explicit architectural vocabulary than generic entity-only navigation

3. Better operator workflow

- Continue + MCP can become a more practical terminal-native workflow than a research-only prototype

4. Better migration/regret use cases

- the paper is about exploration
- this project can go further into impact radius, transplant planning, and eventually safe code-change orchestration

### Phase 8.5: Maximize Current Capabilities

**Purpose**: Pause before Phase 9 and fully mine, stress-test, and demonstrate the current static graph system. This is not a new speculative feature phase. It is an evidence pass that tells us how good the existing Tree-sitter + SCIP + SurrealDB + semantic + MCP + blast-radius stack really is.

**Current Status**:
- Phases 0-5, 7, and 8 have substantial implementations, but release claims should be tied to fresh repo-root hard-gate output on the shipping artifact.
- Phase 6 has a Continue-facing integration module, but still needs local end-to-end operator proof because `cn` / Continue CLI is not currently on PATH.
- The current system is strong enough to evaluate and demo internally, but not yet enough to claim temporal, causal, proactive regret, or closed-loop execution capabilities as product-ready.

**Work Items**:
1. Audit the current system against real artifacts:
   - rerun `pytest`
   - rerun protected hard gates
   - collect `phase-metrics`
   - summarize what is real, partial, blocked, or unproven
2. Expand the gold benchmark:
   - include more files across multiple repos
   - cover more of the 24-block ontology
   - keep a holdout split that is not tuned against during classifier changes
3. Build practical demonstrations:
   - structural ingest and SCIP identity reconciliation
   - semantic block inventory
   - Surreal graph loading and query round-trip
   - MCP tool calls: `get_node`, `get_neighbors`, `trace_symbol_path`, `find_block_nodes`, `get_impact_radius`
   - blast-radius pruning on a meaningful architectural seam
4. Stress-test generalization:
   - run the pipeline on repos outside the current tuned reference path
   - run the ablation review for repo/vendor-specific runtime shortcuts
   - record failures as evidence, not embarrassment
5. Decide Phase 9 readiness:
   - Phase 9 is underway. The next readiness bar is moving from selected Tree-sitter replay to measured temporal answers over known-history fixtures.

**Non-Gamable Gates**:
1. `maximize_gate_reference_reproducible`: A fresh run against the reference artifact must reproduce the protected hard-gate results, with any external dependency failures explicitly named.
2. `maximize_gate_benchmark_breadth`: The gold benchmark must contain at least 25 examples across at least 4 repos and at least 8 distinct functional blocks.
3. `maximize_gate_demo_replay`: At least 5 demonstrations must be runnable from documented commands and must produce machine-readable output artifacts.
4. `maximize_gate_generalization`: At least one holdout repo outside the tuned reference path must ingest, classify, and pass the core structural gates without runtime code changes.
5. `maximize_gate_no_scaffolding`: Runtime code must contain zero repo-specific shortcuts and zero vendor-specific success dependencies. Dataset/test references are allowed only when clearly isolated.

**Exit Criteria**:
- We know exactly what the current system does well.
- We know exactly where it fails.
- The benchmark is broad enough to guide improvement without overfitting.
- Operators have real demos they can rerun.
- Phase 9 has a clear, evidence-backed start line.

---

### Phase 9: Temporal & Evolutionary Understanding

**Purpose**: Move from static snapshots to understanding how architecture evolves over time. Detect architectural drift, successful patterns, painful migrations, and "tribal knowledge" encoded in git history.

**Opinionated Production Implementation**:
- Existing `temporal/` package with `git_miner.py`, `scan.py`, `snapshot.py`, `diff.py`, `metrics.py`, `drift.py`, and `gates.py`
- Use deterministic git commands and replayed Tree-sitter snapshots for selected commits; add SCIP + semantic replay where needed for paper-grade claims
- Store "architectural snapshots" in graph form once replay output is stable; current output is report JSON
- Compute metrics like: block_churn_rate, coupling_tightness_trend, regret_accumulation_score
- Build "pattern success index" based on commit frequency, bug-fix correlation, and test coverage trends

**Key Modules**:
- `temporal/git_miner.py` — canonical commit walker with architectural diffing
- `temporal/snapshot.py` — immutable architectural state per commit
- `temporal/drift.py` — detects when blocks drift from their intended purpose
- `temporal/metrics.py` — produces auditable time-series metrics

**Non-Gamable Gates** (must all pass on a test repo with known history):
1. `temporal_gate_known_changes`: Correctly identifies at least 3 specific historical architectural changes (e.g. "auth moved from middleware to decorator pattern in commit X") with exact commit SHA match. Zero tolerance for hallucinated changes.
2. `temporal_gate_drift_detection`: On a repo with intentional architectural drift introduced in the last 5 commits, must flag the exact files/modules with >0.85 precision and recall.
3. `temporal_gate_metrics_reproducible`: Running `temporal-metrics` on the same repo+commit range must produce bit-for-bit identical output (no randomness, no nondeterminism).

**CLI**: `heart-transplant temporal-scan <repo> --since <date>`

---

### Phase 10: Causal Reasoning & Simulation Layer

**Purpose**: Answer "what if" questions with calibrated confidence. Move from descriptive graph to predictive causal model.

**Opinionated Production Implementation**:
- New `causal/` package built on top of the existing graph + temporal data
- Use Pydantic-AI with structured output + self-consistency checks (not just prompting)
- Maintain a "causal graph" overlay on the structural graph with weighted edges representing change propagation probability
- Simulation engine that can run Monte Carlo rollouts of proposed changes
- Calibration layer that tracks prediction accuracy over time and adjusts confidence scores

**Key Modules**:
- `causal/simulation.py` — core "what-if" engine with traceable reasoning chains
- `causal/calibration.py` — tracks prediction accuracy vs actual outcomes
- `causal/impact_predictor.py` — combines structural, semantic, temporal, and historical data
- `causal/models.py` — strict Pydantic models for simulation requests and results

**Non-Gamable Gates** (run against 20 held-out change scenarios with known outcomes):
1. `causal_gate_prediction_accuracy`: Must achieve >75% accuracy on predicting impact radius for held-out changes (measured by F1 on affected nodes/files). Cannot use the actual change in the prompt.
2. `causal_gate_calibration`: Predicted confidence scores must be well-calibrated (Brier score < 0.15). Overconfident or underconfident predictions fail the gate.
3. `causal_gate_traceability`: Every simulation result must contain a reproducible reasoning trace that a human can audit. No black-box LLM calls allowed in final output.

**CLI**: `heart-transplant simulate-change --change "replace auth0 with better-auth" --confidence-threshold 0.7`

---

### Phase 11: Proactive Regret Surface Detection

**Purpose**: This is the original north star. The system should *proactively* find architectural regrets instead of only answering when asked.

**Opinionated Production Implementation**:
- New `regret/` package that runs periodic scans over the entire corpus
- Combines: 24-block ontology violations, temporal drift, causal risk scores, and historical regret patterns
- Produces a ranked "regret surface" with supporting evidence from multiple layers
- Uses the blast radius engine (Phase 5) but with semantic and temporal pruning
- Stores regret history to detect "regret debt" accumulation over time

**Key Modules**:
- `regret/detector.py` — main scanning engine (runs on schedule or on-demand)
- `regret/patterns.py` — library of known regret patterns (vendor lock-in, scattered auth, etc.)
- `regret/scoring.py` — multi-factor regret scoring with calibrated confidence
- `regret/surgery_planner.py` — turns regret surfaces into sequenced migration plans

**Non-Gamable Gates** (tested on repos with *known* but undisclosed regrets):
1. `regret_gate_blind_detection`: Must surface at least 2 real architectural regrets in a test corpus **without being given any hints** about where to look. Human validator confirms relevance.
2. `regret_gate_surgery_plan_quality`: For each detected regret, must produce a surgery plan that passes human review on completeness, risk ordering, and test strategy. Plan must be machine-readable (RegretSurface + SurgeryPlan models).
3. `regret_gate_no_false_positives`: On a clean, well-architected reference repo, must produce zero high-confidence regrets (score > 0.7). This prevents "everything looks like a nail" behavior.

**CLI**: `heart-transplant regret-scan --min-confidence 0.75 --output surgery-plan.json`

---

### Phase 12: Closed-Loop Execution & Learning

**Purpose**: Move from analysis to action. The system should drive real code changes and learn from outcomes.

**Opinionated Production Implementation**:
- Tight integration between MCP tools, Continue/Cursor APIs, and the regret engine
- Human-in-the-loop workflow with explicit confirmation gates before any edit
- Learning system that updates the causal model and regret patterns based on outcomes
- Automated validation harness that runs tests, linters, and semantic checks after transplants
- "Transplant ledger" that records every change with before/after metrics

**Key Modules**:
- `execution/orchestrator.py` — coordinates planning → edit → validation → learning
- `execution/validator.py` — multi-layered post-edit validation
- `execution/learner.py` — updates models based on outcomes (reinforcement from real results)
- `execution/ledger.py` — immutable record of all transplants

**Non-Gamable Gates** (must succeed on real code changes):
1. `execution_gate_end_to_end_transplant`: Successfully complete a non-trivial transplant (e.g. "migrate from one logging library to another" or "consolidate auth patterns") on a test repo with **zero manual code edits**. All changes driven through the system.
2. `execution_gate_learning_improvement`: After 5 transplants, the system's regret detection or causal predictions must measurably improve on a held-out test set (quantified by regret scoring calibration or prediction accuracy).
3. `execution_gate_safety`: No transplant can introduce new test failures or violate the original semantic block assignments by more than 10%. Safety is non-negotiable.

**CLI**: `heart-transplant execute-transplant --regret-id <id> --dry-run` (then `--execute`)

---

### Phase 13: Multi-Modal & Multi-Layer Understanding

**Purpose**: Understand not just source code, but the entire surrounding system: tests, infrastructure, APIs, observability, documentation.

**Opinionated Production Implementation**:
- New `multimodal/` package with dedicated parsers for tests, Terraform/Helm, OpenAPI, Prometheus rules, runbooks, etc.
- Cross-layer correlation engine that links code → tests → infra → observability
- Unified graph that includes non-code artifacts as first-class nodes (`test:`, `infra:`, `spec:`, `observability:`)
- "Flow understanding" that traces requests, data, async events, and failure modes across all layers

**Key Modules**:
- `multimodal/parsers/` — one parser per artifact type with strict schemas
- `multimodal/correlator.py` — builds cross-layer edges (e.g. code → test → infra)
- `multimodal/flow_tracer.py` — understands end-to-end system flows
- `multimodal/models.py` — unified node types that extend the original CodeNode model

**Non-Gamable Gates**:
1. `multimodal_gate_cross_layer_questions`: Must correctly answer 8 out of 10 questions that require correlating at least 3 different artifact types (e.g. "which observability rule would break if we change this database schema?").
2. `multimodal_gate_test_correlation`: For every production code node, must identify the corresponding test coverage with >80% accuracy on a test corpus with known test-to-code mappings.
3. `multimodal_gate_flow_reconstruction`: Given an OpenAPI spec + code + infra, must reconstruct the end-to-end request flow graph with all major components and failure modes identified.

**CLI**: `heart-transplant multimodal-ingest <directory> --include-tests --include-infra`

---

### Phase 14: Program Surface & Cross-Phase Readiness

**Purpose**: After Phases 9–13, the system risks becoming a bag of siloed capabilities. Phase 14 provides a single readiness index: which modules import cleanly, which CLIs are wired, and where stubs remain. It is the integration layer *before* claiming production operator readiness.
**Purpose**: After Phases 9–13, the system risks becoming a bag of siloed capabilities. Phase 14 provides a single readiness index: which modules import cleanly, which CLIs are wired, and where stubs remain. It is the integration layer *before* claiming production operator readiness.

**Opinionated Production Implementation**:
- `surface/status.py` — `program_surface_status()` reporting import health for maximize gates, temporal scan, and Phases 10–13 entrypoints
- CLI: `heart-transplant program-surface` emits machine-readable JSON
- CI hook: fail if any declared phase symbol is not importable (regression guard)

**Non-Gamable Gates** (lightweight; complements heavier phase gates):
1. `surface_gate_import_health`: Every symbol declared in the program surface manifest must import without error in a clean venv with only production dependencies.
2. `surface_gate_cli_parity`: Every phase with a documented CLI entrypoint must register the same command via `heart_transplant.cli` (no orphan scripts).
3. `surface_gate_stub_contract`: Any command that is still a stub must emit JSON with `"status": "stub"` and must not claim gate passage.

**Exit Criteria**:
- One command answers “what is real vs stub across the roadmap?”
- Release notes and PROJECT.md can point to `program-surface` output as the source of truth.

## Immediate Next Actions

If we want the smallest sequence that moves us forward without fluff, it is:

1. Rerun the full 50-repo corpus after iterative traversal and Rust/Java/C/C++ parser coverage.
2. Rerun the block benchmark after file-surface and secondary-block scoring changes.
3. Expand the scored evidence-QA harness for `answer-with-evidence` and graph traversal commands.
4. Extend temporal replay to SCIP + semantic replay for selected commits.
5. Fix and fixture regret-specific surgery plans, starting with logging inconsistency.
6. Run repo-root hard gates on the shipping artifact and publish exact reproduction inputs.

## Program-Level Exit Criteria

We should not call this effort successful until all three of these are true.

### A. Match As Much Of The LogicLens Paper As Practical

Minimum required capability set:

1. `Structural graph`
- multi-file structural parsing from Tree-sitter
- real symbol identity and references from SCIP
- graph persistence in SurrealDB
- graph traversal across code units, files, and projects

2. `Semantic graph`
- semantic mapping of structural nodes into the 24-block ontology
- node-level confidence and reasoning attached to those classifications
- graph queries that can retrieve by structural role and semantic block

3. `Reactive exploration`
- MCP graph tools over the real graph
- Continue able to answer system questions through those tools
- repeatable evaluation over a question set, not just ad hoc demos

Evidence that A is met:

- a reproducible evaluation harness exists
- graph-backed answers outperform or materially differ from a simpler baseline
- cross-file and at least one cross-repo navigation example work end to end

### B. No Vendor-Specific Or Repo-Specific Scaffolding Used To Fake A

This is a hard constraint.

What is allowed:

- language-specific parsing rules
- generic architectural ontology rules
- generic graph schemas
- generic classifier prompts using the 24-block ontology

What is not allowed as a success dependency:

- per-vendor shortcuts like special-case logic for `supabase`, `auth0`, `better-auth`, `okta`, or similar
- per-repo shortcuts keyed to vendored repos
- handwritten “expected answer” paths for benchmark questions
- hidden patch-up scripts that only make the demo corpus work

How we validate B:

1. `Holdout corpus test`
- add at least one repo outside the current vendored set
- run ingest, classification, and navigation without changing code

2. `Ablation review`
- inspect the implementation and list every place where:
  - vendor names appear
  - repo names appear
  - vendored test fixtures are referenced
- each such reference must be justified as:
  - test-only
  - dataset-only
  - or truly generic

3. `Swap-task portability check`
- run the same structural and semantic pipeline on two or more different subsystem families, not just auth
- examples:
  - auth
  - data persistence
  - telemetry

Only when the system generalizes across those without new special cases can we say B is satisfied.

### C. The Tool Is Strong Enough To Support The Original Regret SDK Goal

The original intent was not just code exploration. It was:

- identify a regret surface (proactively)
- understand how we got here (temporal context)
- simulate what will happen (causal reasoning)
- plan the surgery with confidence
- execute, validate, and learn from the outcome
- understand the full system across code, tests, infra, and observability

**Minimum required capability set (Phases 9-13)**:

1. `Temporal understanding` — track architectural evolution and drift over time
2. `Causal simulation` — answer "what if we changed X?" with calibrated confidence
3. `Proactive regret detection` — surface problems before being asked, with evidence
4. `Closed-loop execution` — drive real transplants and learn from outcomes
5. `Multi-modal understanding` — correlate code with tests, IaC, specs, and observability

**Evidence that C is met**:

- All gates from Phases 9-13 pass on at least one held-out repository
- The system can proactively find, simulate, plan, execute, and validate a non-trivial architectural transplant end-to-end
- Human operators report that the system reduces (rather than increases) cognitive load during large-scale modernization work
- The regret detection engine finds real issues that were not pre-programmed or hinted at in prompts

## Final Claim Check

Before claiming paper-grade or regret-SDK readiness, ask all three:

1. Could a skeptical engineer rerun the validation gates and see the same result?
2. Could the system run on a new repo without adding new vendor-specific code?
3. Could the output actually guide a regret replacement workflow rather than merely describe code?

If any answer is “no,” we are not there yet.

## What We Should Not Do Yet (Updated Guidance)

**Until the repo-root gates and paper checklist support the claim:**

- Do not add more frontend or elaborate UIs
- Do not claim "agentic" capabilities beyond what the MCP tools actually deliver
- Do not talk about multi-repo reasoning as production-ready until Phase 11 regret detection works on a held-out corpus

**Once Phases 0-8 are complete, the focus must shift to:**

- Implementing Phases 9-13 with the same rigor (non-gamable gates)
- Avoid adding demo-only layers or marketing claims before the gates pass
- Maintaining the "no vendor-specific scaffolding" rule from Exit Criteria B

The new phases (9-13) represent the real leap from "impressive analysis tool" to "architectural co-pilot." We only claim that leap after the gates prove it.

## Bottom Line (Updated After April 28 Documentation Sweep)

The current repo has a useful foundation for structural graph construction and the beginning of a LogicLens-style evidence backend. It is not feature-complete against the paper. The current machine-readable checklist says: `1` implemented paper feature, `7` partial, `0` missing.

**Today we have (real):**
- Structural ingest with file surfaces, SCIP identity, orphan promotion, and broader parser coverage
- 24-block semantic classification with neighborhoods, secondary labels, and preserved holdout benchmark baselines
- SurrealDB persistence, MCP tools, blast radius, causal/regret/execution/multimodal first passes
- Canonical graph/evidence commands, a first `evidence-benchmark`, artifact manifests, and a `paper-checklist` status surface
- 50-repo corpus evidence with failure/fix documentation

**What Phases 9-13 must deliver:**
- Temporal memory with measured replay/diff correctness
- Causal simulation with calibrated confidence
- Proactive regret detection with fixture precision and plan specificity
- Closed-loop execution that changes code safely and records validation
- Multi-modal understanding across code, tests, infra, specs, and observability

When all gates pass, this can become a system that accelerates large-scale modernization work while reducing risk. The near-term job is to rerun the corpus, score evidence retrieval, and keep every claim tied to a reproducible artifact.

The posture remains: **rigor first**. Every phase must ship non-gamable gates. We do not claim victory until a skeptical engineer can rerun every gate and get the same result on a new codebase.
