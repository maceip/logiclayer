# Codes tool lexical abstention calibration

## Goal

Choose `DEFAULT_CODES_MIN_SCORE` (`evidence.py`) so `query_codes` **abstains** on nonsense queries while **retrieving** symbol/code surfaces on fixture repos.

## Normalization

`_normalized_lexical_score` uses `_text_score(query, haystack) / (max(|terms|, 1) + NORMALIZED_LEXICAL_DENOM_BIAS)` with `NORMALIZED_LEXICAL_DENOM_BIAS = 3.0`.

## Confidence mapping

`confidence = min(0.92, CODES_CONFIDENCE_INTERCEPT + CODES_CONFIDENCE_SLOPE * top_rank_score)` with intercept **0.35** and slope **0.55**.

## Empirical grid (fixture corpus)

Evaluated against **active** rows in `docs/evals/evidence_questions.json` scoped to `repo_name=test/logiclens` using `answer_with_evidence` (same router as production benchmark):

| min_score | Unsupported abstention (3 rows) | Positive hits (codes/block rows) |
|-----------|-----------------------------------|-------------------------------------|
| 0.12      | passes                          | passes                              |
| **0.18**  | passes                          | borderline short-token queries may abstain |
| 0.22      | passes                          | marginal loss on short-token queries |

## Chosen value

**`DEFAULT_CODES_MIN_SCORE = 0.12`**

- Maximizes separation between nonsense abstentions (`zzz…`) and borderline symbol queries (`sessionguard`, multi-token prompts) on the multi-file fixture.
- Previous **0.18** caused legitimate codes prompts whose normalized score landed **~0.125** (single-token overlap) to abstain spuriously.

## Alternatives

| Value | Trade-off |
|-------|-----------|
| **0.18** | Fewer false-positive code hits; more false abstentions on short queries |
| **0.12** | Matches fixture abstention rows while retaining phrase overlap behavior |
| **0.10** | Aggressive retrieval; risk of weak matches on noisy corpora |

When ingest improves token overlap per query, revisit using `evidence-benchmark` on `docs/evals/evidence_questions.json`.
