# Browser Runtime Trajectory

The beta console now treats the hosted backend as the credible launch runtime and the browser runtime as a deliberate adapter target, not a second product.

## Runtime Contract

Every runtime must emit the same receipts:

- `structural-artifact.json`
- `semantic-artifact.json`
- `artifact-manifest.json`
- graph-integrity summary
- runtime capabilities
- feedback/evidence records

## Hosted Runtime Now

The hosted beta path runs behind `heart-transplant beta-serve`.

- accepts only public GitHub `owner/name` or `github.com` URLs
- clones with shallow Git history
- runs Tree-sitter ingest from the Python backend
- runs deterministic block classification without OpenAI
- writes an artifact manifest
- runs graph integrity
- returns bounded graph/block/file-surface output to the browser

Long term, architecture Q&A surfaces should return **EvidenceBundle-shaped** receipts consistent with the Phase 17 local harness (`evidence-benchmark` on the committed fixture — see `README.md` / `PROJECT.md`).

The unauthenticated endpoint intentionally does not run package installs, private local paths, OpenAI calls, or arbitrary shell commands from repository content.

## Browser Runtime Later

The browser adapter should keep the same artifact contract.

- repo source: GitHub API or `isomorphic-git`
- parser runtime: Tree-sitter WASM grammars
- graph store: SurrealDB WASM or a compatible graph-store adapter
- classifier: TypeScript port of deterministic block classifier
- SCIP consume: protobuf decoding in TypeScript
- semantic indexing: TypeScript compiler API first, heavier language toolchains later

## Decision

Use hosted backend analysis for private beta trust and accuracy. Keep the UI pointed at a stable runtime interface so the browser-only adapter can replace individual capabilities without changing what the product promises.
