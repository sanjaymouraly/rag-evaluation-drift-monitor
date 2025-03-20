# Metrics and their limitations

Every metric the platform computes declares three things:

* a **kind** (its provenance),
* the **evidence it requires**,
* what it means when that evidence is missing.

Run `GET /api/metrics/catalogue` (or `python -m app.cli metrics`) for the
machine-readable version of this page. The kinds are:

| Kind | Meaning |
|---|---|
| `deterministic` | An exact formula over the supplied evidence. |
| `reference_based` | Computed against a human-authored reference answer. |
| `heuristic` | A surface-overlap **estimate**. Not verified ground truth. |
| `embedding_based` | Similarity from an embedding model. Approximate. |
| `judge` | An LLM-as-a-judge **opinion signal**. Not proof of correctness. |
| `operational` | Measured operational data (latency, tokens, cost). |

**Missing evidence is never replaced by a value.** A metric that cannot be
computed returns `null` with a `missing_reason`, and the run-level aggregate
reports `n = 0` for it. The release gate treats that as *insufficient
evidence*, never as a pass.

---

## Retrieval metrics

Require relevance labels (`relevant_doc_ids`, optionally graded via
`relevance_grades`). Without labels these metrics are `null`.

| Metric | Definition | Known-value example |
|---|---|---|
| `precision_at_5` | share of the 5 retrieved documents that are labelled relevant | top-5 = `[a,b,c,d,e]`, relevant `{b,d}` → `0.4` |
| `recall_at_5` | share of the relevant documents found in the top 5 | relevant `{b,d,f}` → `2/3` |
| `recall_at_3` | same, at k=3 | |
| `hit_at_5` | 1.0 when at least one relevant document is in the top 5 | |
| `mrr` | reciprocal rank of the first relevant document | first hit at rank 2 → `0.5` |
| `map` | mean of the precision at every relevant rank, divided by \|relevant\| | hits at ranks 2 and 4 → `0.5` |
| `ndcg_at_5` | normalised discounted cumulative gain (supports graded relevance) | ideal order → `1.0` |
| `context_precision` | share of the retrieved context that is relevant | |
| `context_recall` | share of the relevant documents present in the retrieved context | |
| `retrieval_coverage` | share of relevant documents found anywhere in the retrieved list | |
| `empty_retrieval` | 1.0 when the retriever returned nothing | |
| `duplicate_chunk_rate` | share of retrieved chunks that are duplicates | |
| `missing_source_rate` | share of labelled relevant documents that are absent from the corpus | |

**Limitations.** Precision depends on the corpus size: with one relevant
document among twelve and k = 5, the maximum achievable precision@5 is 0.2.
Compare precision across runs only when the corpus and `top_k` are unchanged —
the run snapshot records both.

## Answer metrics

| Metric | Kind | Requires |
|---|---|---|
| `exact_match` | reference_based | a reference answer |
| `normalized_match` | reference_based | a reference answer |
| `token_f1` | reference_based | a reference answer |
| `completeness` | reference_based | a reference answer |
| `faithfulness` | **heuristic** | retrieved context |
| `claim_support_rate` | deterministic | retrieved context |
| `hallucination_rate` | **heuristic** | retrieved context |
| `answer_relevancy` | **heuristic** | the question |
| `semantic_similarity` | embedding_based | a reference answer + an embedder |
| `correct_abstention` | deterministic | an unanswerable item |
| `over_abstention` | deterministic | an answerable item |
| `contradiction_rate` | deterministic | a reference answer |
| `empty_answer` | deterministic | — |

**Faithfulness** is the fraction of answer sentences whose content tokens are
covered by the retrieved context (threshold 0.6). It is a *surface* check: an
answer can be unfaithful while sharing words with the context, and it can be
faithful while paraphrasing beyond the token overlap. Use it for *regression
signal*, not as proof.

**Hallucination rate** is the complement: the share of answer sentences that
are *not* grounded. It is a heuristic for the same reason.

**Contradiction rate** detects a specific, verifiable failure: the answer
states a number that the reference answer does not contain. It does not detect
contradictions in qualitative claims.

**Correct abstention** is only defined for unanswerable items (the reference
answer is not needed). **Over abstention** is only defined for answerable
items. A benchmark that mixes both therefore reports two different `n` values,
which is intentional.

**Semantic similarity** requires an embedding function. The offline default is
a feature-hash vector, which is *not* semantic — it only matches surface
tokens. Use a real embedding model (or a configured provider) for a meaningful
value, and check the `kind` field when reading the number.

## Citation metrics

The platform deliberately separates two questions that are often conflated.

| Metric | Question it answers |
|---|---|
| `citation_presence` | did the answer cite anything at all? |
| `citation_structural_valid` | does the citation point at a document/chunk that exists in the corpus? |
| `citation_support` | is the cited content genuine evidence for the answer? |
| `citation_unsupported_rate` | share of citations that are unsupported, irrelevant or invalid |
| `citation_precision` | share of citations that point at an expected/relevant document |
| `citation_doc_recall` | share of the expected documents that the answer actually cites |
| `claim_attribution` | share of answer claims attributed to a supporting citation |
| `citation_coverage` | share of answer claims covered by at least one citation |

### How a citation is classified

Each citation gets exactly one outcome:

| Outcome | Meaning |
|---|---|
| `supported` | the quote was found verbatim in the cited chunk **and** the chunk supports at least one answer claim |
| `irrelevant` | the quote exists in the chunk but supports no claim of the answer |
| `unsupported` | the quote was not found in the chunk, or the chunk supports no claim |
| `structural_invalid` | the cited document/chunk does not exist, or belongs to another document |

**A citation that names an existing document id is not automatically
accurate.** `citation_structural_valid` and `citation_support` are two
different numbers, and only the second one says something about the evidence.

Quotes are compared after normalisation (case, punctuation and articles are
folded). When a citation carries source offsets (`char_start` / `char_end`),
the quoted text is additionally compared against the characters at those
offsets, so a citation cannot claim a span that does not contain the quote.

## Operational metrics

| Metric | Meaning |
|---|---|
| `latency_ms` | end-to-end latency of one RAG call |
| `retrieval_latency_ms` / `generation_latency_ms` | stage breakdown |
| `latency_p50_ms` / `latency_p95_ms` / `latency_p99_ms` | percentiles over the run |
| `input_tokens` / `output_tokens` | measured from the provider response when available |
| `estimated_cost_usd` | measured tokens × configured prices — **always an estimate** |
| `cost_per_request_usd` | total cost ÷ number of requests |
| `cost_per_successful_answer_usd` | total cost ÷ number of non-abstained, non-error answers |
| `failure_rate` | share of answerable items with token F1 < 0.3 |
| `error_rate` | share of items whose request failed |
| `request_error` | 1.0 when the request failed |

`usage_exact` is recorded per result: it is `true` only when the provider
reported real token usage. When it is `false` the cost is an estimate based on
a character heuristic, and the run is flagged with `cost_is_estimate: true`.

## LLM-judge metrics (optional)

Judges are **optional** and always labelled `judge`.

| Dimension | Rubric |
|---|---|
| `faithfulness` | is the answer supported by the context? |
| `answer_relevancy` | does the answer address the question? |
| `correctness` | does the answer agree with the reference? |
| `citation_support` | do the citations support the answer claims? |

Every verdict stores the rubric version, the model, the raw output and the
token usage. A human reviewer can record `agree` / `disagree`.

**Agreement between judges is not objective proof of correctness.** The platform
stores judge scores next to the deterministic metrics, never instead of them.

## Aggregation

Run-level metrics are reported as `{value, n, kind, std}`:

* `value` — the mean over the items that contributed,
* `n` — **how many** items contributed (this is the evidence count),
* `kind` — the provenance,
* `std` — the standard deviation over those items.

Breakdowns by `category` and by `cohort` are provided for every metric, which
is what makes per-category release gates possible.

## Choosing thresholds

The default policy in the demo uses example values (faithfulness ≥ 0.60,
recall@5 ≥ 0.80, relative drop ≤ 0.05, …). **They are examples, not industry
standards.** Derive your own thresholds from your own benchmark:

1. measure the baseline distribution of a metric over several runs,
2. set the absolute floor a bit below the observed median,
3. set the relative limit from the observed run-to-run noise (the platform
   reports the paired CI and the effect size for exactly this purpose),
4. keep the sample-count minimum high enough that the interval is meaningful.
