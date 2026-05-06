# Trending Top 50 EC2 First Synthesis - 2026-04-27

Purpose: preserve the first one-at-a-time EC2 smell test exactly as it behaved, bugs and all.

This corpus has two jobs:

1. Marketing / trust: show that the system has been exercised against recognizable, current, popular repositories instead of hand-picked toys.
2. Quality gate pressure: keep a recurring, machine-readable bar that fails when ingest crashes, parser coverage is misleading, or a run reports zero-node "successes."

This run used the 50-repo manifest in `docs/evals/trending-repos-top50-2026-04-27.json`:

- top 10 TypeScript daily trending repos
- top 10 Rust daily trending repos
- top 10 Go daily trending repos
- top 10 C++ daily trending repos
- top 10 Java daily trending repos

The runner cloned one repository at a time on EC2 host `16xl`, ran `heart_transplant.cli ingest-local`, ran `phase-metrics --classify-if-missing` when ingest succeeded, recorded JSONL, and deleted the working clone before moving to the next repository.

**Note (2026-05):** This corpus exercises **ingest + block metrics** across many repos; it is not the same as the **Phase 17** evidence-benchmark fixture (single committed `test/logiclens` artifact for architecture Q&A scoring). See `README.md` / `PROJECT.md`.

## Preserved Artifacts

- `docs/evals/trending-top50-ec2-results-2026-04-27.jsonl`
- `docs/evals/trending-top50-ec2-summary-2026-04-27.json`
- Local ignored run log copy: `.heart-transplant/reports/trending-top50-ec2-run-2026-04-27.log`

## Headline

| Metric | Value |
| --- | ---: |
| Repositories attempted | 50 |
| Successful ingest + phase metrics | 47 |
| Ingest failures | 3 |
| Manifest languages | 5 |
| Repositories per language | 10 |

## Status By Manifest Language

| Manifest language | Attempted | OK | Failed | Zero-code-node OK artifacts |
| --- | ---: | ---: | ---: | ---: |
| TypeScript | 10 | 9 | 1 | 0 |
| Rust | 10 | 10 | 0 | 0 |
| Go | 10 | 9 | 1 | 0 |
| C++ | 10 | 9 | 1 | 0 |
| Java | 10 | 10 | 0 | 6 |

Important interpretation: "manifest language" is GitHub Trending's category, not necessarily what our backend parsed during this first run. At the time, the backend parsed TypeScript/TSX/JavaScript/Python/Go/Prisma. After this synthesis, first-class Rust, Java, C, and C++ parser coverage landed. Several Rust/C++/Java-category repos in the preserved run produced nodes only because they contained supported-language tooling, bindings, scripts, examples, or web surfaces.

## Node And Edge Totals By Manifest Language

| Manifest language | Successful artifacts | Code nodes | Edges |
| --- | ---: | ---: | ---: |
| TypeScript | 9 | 161,386 | 252,979 |
| Rust | 10 | 38,170 | 52,263 |
| Go | 9 | 82,216 | 131,312 |
| C++ | 9 | 87,803 | 119,862 |
| Java | 10 | 8,907 | 14,477 |

## Largest Successful Artifacts

| Rank | Manifest language | Repo | Code nodes | Edges | Parser backends |
| ---: | --- | --- | ---: | ---: | --- |
| 2 | TypeScript | `openclaw/openclaw` | 78,368 | 124,834 | `go,javascript,python,typescript` |
| 34 | C++ | `tensorflow/tensorflow` | 70,971 | 91,968 | `go,javascript,python` |
| 5 | TypeScript | `ruvnet/ruflo` | 39,322 | 50,170 | `javascript,python,typescript` |
| 18 | Rust | `denoland/deno` | 29,921 | 37,576 | `javascript,tsx,typescript` |
| 30 | Go | `gastownhall/gascity` | 19,190 | 27,078 | `go,javascript,python,typescript` |
| 27 | Go | `dolthub/dolt` | 16,884 | 24,614 | `go,javascript,prisma,python,typescript` |
| 24 | Go | `go-gitea/gitea` | 15,659 | 30,715 | `go,javascript,typescript` |
| 6 | TypeScript | `CherryHQ/cherry-studio` | 12,449 | 24,253 | `javascript,python,tsx,typescript` |
| 28 | Go | `5rahim/seanime` | 11,513 | 19,193 | `go,javascript,tsx,typescript` |
| 22 | Go | `gastownhall/beads` | 9,259 | 15,679 | `go,javascript,python,typescript` |

## First-Run Failures

All three failures were `ingest_failed` and shared the same root symptom: recursive Tree-sitter traversal exceeded Python's recursion limit on deep parse trees.

| Index | Manifest language | Repo | Failure |
| ---: | --- | --- | --- |
| 10 | TypeScript | `Vendicated/Vencord` | `RecursionError: maximum recursion depth exceeded` in `treesitter_ingest.py` traversal |
| 21 | Go | `microsoft/typescript-go` | `RecursionError: maximum recursion depth exceeded` in `treesitter_ingest.py` traversal |
| 36 | C++ | `FreeCAD/FreeCAD` | `RecursionError: maximum recursion depth exceeded` in `treesitter_ingest.py` traversal |

Follow-up fix landed: Tree-sitter and import-extractor walkers now use iterative stack traversal instead of recursive descent, with a regression test for a deeply nested TypeScript parse tree. The original first-run result above remains the baseline smell test and should not be rewritten by reruns.

## Zero-Code-Node OK Artifacts

These runs technically succeeded but produced no code nodes. This is a coverage smell, not a semantic success.

| Index | Manifest language | Repo | Parser backends |
| ---: | --- | --- | --- |
| 41 | Java | `yuliskov/SmartTube` | `typescript` |
| 44 | Java | `Creators-of-Create/Create` | none |
| 45 | Java | `JingMatrix/Vector` | none |
| 46 | Java | `cryptomator/cryptomator` | none |
| 49 | Java | `woheller69/FreeDroidWarn` | none |
| 50 | Java | `MCRcortex/voxy` | none |

Follow-up fix landed: ingest now includes first-class parser coverage for Rust, Java, C, and C++ source files, with focused regression tests for Java, Rust, and C++ node extraction. This addresses the zero-node-success failure mode at the parser-coverage layer; the first synthesis remains preserved as the historical baseline until the full 50-repo corpus is rerun.

## What This Proves

- The EC2 runner can exercise 50 popular repos sequentially without keeping all clones on disk.
- The app can ingest and score large real-world repos; the largest successful artifacts exceeded 70k code nodes.
- The first synthesis is already useful as a stress test for runtime, memory, parser coverage, and graph scale.

## Quality Gate Command

The preserved first synthesis intentionally fails the strict quality gate:

```powershell
cd backend
.\.venv-win\Scripts\python.exe -m heart_transplant.cli corpus-gate ..\docs\evals\trending-top50-ec2-results-2026-04-27.jsonl
```

Expected first-synthesis result:

- `attempted = 50`
- `ok = 47`
- `ingest_failed = 3`
- `zero_node_ok = 6`
- strict status: `fail`

That failure is the point. For marketing/trust we can say we ran the 50-repo corpus and preserved the result. For engineering quality, the same corpus tells us exactly what must improve before the result becomes a launch gate.

## What It Exposes

- Parser coverage was not aligned with the requested language set during the preserved run. Rust, C++, and Java parser coverage has since landed and needs a full corpus rerun.
- Deep parse trees can break recursive traversal. This is now a concrete P1 ingestion hardening item.
- Phase metrics can be expensive on large artifacts: `openclaw/openclaw` and `tensorflow/tensorflow` each spent about nine minutes in metrics.
- "OK" does not always mean useful. Zero-node artifacts must be separated from successful architecture understanding.

## Immediate Next Assessment Questions

1. Does the post-fix rerun eliminate the three ingest crashes and the six zero-node successes?
2. Should zero-node artifacts fail the smell-test gate instead of reporting `ok`?
3. Should phase metrics skip Surreal/semantic work for zero-node artifacts?
4. Should large-repo metrics be sampled, capped, or split into a structural pass and semantic pass?
5. Which of these 50 repos should become stable recurring benchmark fixtures rather than volatile daily-trending samples?
