# Evaluation Report — Run #2

**App:** library-rag-baseline (v1.0-bm25) · **Dataset:** library-benchmark · **Mode:** `end_to_end` · **Status:** `completed`

Tokens: 0 in / 0 out · Estimated cost: $0.0 (estimate)

## Aggregate metrics

| Metric | Value | n | Kind |
|---|---|---|---|
| answer_relevancy | 0.5861 | 38 | heuristic |
| citation_coverage | 0.8684 | 38 | deterministic |
| citation_doc_recall | 0.8857 | 35 | deterministic |
| citation_precision | 1.0000 | 32 | deterministic |
| citation_presence | 1.0000 | 33 | deterministic |
| citation_structural_valid | 1.0000 | 33 | deterministic |
| citation_support | 1.0000 | 33 | deterministic |
| citation_unsupported_rate | 0.0000 | 33 | deterministic |
| claim_attribution | 1.0000 | 33 | deterministic |
| claim_support_rate | 0.9474 | 38 | deterministic |
| completeness | 0.8278 | 28 | reference_based |
| context_precision | 0.2114 | 35 | deterministic |
| context_recall | 1.0000 | 35 | deterministic |
| contradiction_rate | 0.0000 | 28 | deterministic |
| correct_abstention | 0.4000 | 10 | deterministic |
| cost_per_request_usd | 0.0000 | 38 | operational |
| cost_per_successful_answer_usd | 0.0000 | 33 | operational |
| duplicate_chunk_rate | 0.0000 | 38 | operational |
| empty_answer | 0.0000 | 38 | deterministic |
| empty_retrieval | 0.0000 | 38 | operational |
| error_rate | 0.0000 | 38 | operational |
| estimated_cost_usd | 0.0000 | 38 | operational |
| exact_match | 0.0357 | 28 | reference_based |
| failure_rate | 0.0357 | 28 | deterministic |
| faithfulness | 0.8684 | 38 | heuristic |
| generation_latency_ms | 0.6700 | 38 | operational |
| hallucination_rate | 0.1316 | 38 | heuristic |
| hit_at_5 | 1.0000 | 35 | deterministic |
| input_tokens | 0.0000 | 38 | operational |
| latency_ms | 0.7629 | 38 | operational |
| latency_p50_ms | 0.7290 | 38 | operational |
| latency_p95_ms | 1.2090 | 38 | operational |
| latency_p99_ms | 1.5350 | 38 | operational |
| map | 0.9952 | 35 | deterministic |
| missing_source_rate | 0.0000 | 35 | operational |
| mrr | 1.0000 | 35 | deterministic |
| ndcg_at_5 | 0.9977 | 35 | deterministic |
| normalized_match | 0.0357 | 28 | reference_based |
| output_tokens | 0.0000 | 38 | operational |
| over_abstention | 0.0357 | 28 | deterministic |
| precision_at_5 | 0.2114 | 35 | deterministic |
| recall_at_3 | 1.0000 | 35 | deterministic |
| recall_at_5 | 1.0000 | 35 | deterministic |
| request_error | 0.0000 | 38 | operational |
| retrieval_coverage | 1.0000 | 35 | deterministic |
| retrieval_latency_ms | 0.0930 | 38 | operational |
| semantic_similarity | n/a | 0 | embedding_based |
| token_f1 | 0.6777 | 28 | reference_based |
| total_input_tokens | 0.0000 | 38 | operational |
| total_output_tokens | 0.0000 | 38 | operational |

*Kind legend: deterministic = exact formula; reference_based = against a gold answer; heuristic = surface-overlap estimate, not verified ground truth; embedding_based = approximate similarity; judge = LLM opinion signal; operational = measured operational data.*

## Per-question results

| # | Category | Recall@5 | F1 | Faithfulness* | Citation support | Answer |
|---|---|---|---|---|---|---|
| 1 | factual | 1.0 | 0.774194 | 1.0 | 1.0 | The angle of the waggle run relative to gravity encodes the direction of the food relative to the sun. |
| 2 | factual | 1.0 | 0.774194 | 1.0 | 1.0 | The duration of the waggle phase encodes the distance to the food, with longer dances signalling farther sources. |
| 3 | factual | 1.0 | 0.3125 | 1.0 | 1.0 | A returning forager performs a waggle dance on the vertical comb to advertise a food source. |
| 4 | factual | 1.0 | 0.777778 | 1.0 | 1.0 | The largest tidal barrage in the world is the Sihwa Lake station in South Korea, with an installed capacity of 254 megaw |
| 5 | factual | 1.0 | 0.846154 | 1.0 | 1.0 | Tidal energy is predictable because tides follow the gravitational cycles of the moon and sun. |
| 6 | factual | 1.0 | 0.488889 | 1.0 | 1.0 | Tidal stream generators work like underwater wind turbines placed in fast-moving tidal currents. |
| 7 | factual | 1.0 | 0.4 | 1.0 | 1.0 | Lactic acid bacteria produce lactic and acetic acids, which give sourdough its tangy flavour and improve its keeping qua |
| 8 | factual | 1.0 | 0.875 | 1.0 | 1.0 | A ripe starter typically doubles in volume within four to eight hours after feeding at room temperature. |
| 9 | factual | 1.0 | 0.896552 | 1.0 | 1.0 | Bakers judge readiness with the float test, where a spoonful of ripe starter floats in water. |
| 10 | factual | 1.0 | 0.666667 | 1.0 | 1.0 | Gear inches combine the ratio with wheel diameter to express how far the bicycle travels with one crank revolution. |
| 11 | factual | 1.0 | 0.0 | 0.0 | None | I don't have enough information in the provided sources to answer this question. |
| 12 | factual | 1.0 | 0.93617 | 1.0 | 1.0 | Lucena position is a basic winning technique in a rook endgame with the stronger side building a bridge with the rook to |
| 13 | factual | 1.0 | 0.903226 | 1.0 | 1.0 | Philidor position is a fundamental drawn rook endgame where the defending rook cuts the enemy king off. |
| 14 | factual | 1.0 | 0.695652 | 1.0 | 1.0 | Volcanologists monitor ground deformation with GPS instruments and satellite radar to detect magma moving underground. |
| 15 | factual | 1.0 | 0.827586 | 1.0 | 1.0 | The Volcanic Explosivity Index measures eruption size on a logarithmic scale based mainly on erupted volume. |
| 16 | factual | 1.0 | 0.666667 | 1.0 | 1.0 | A typical interlibrary loan request is fulfilled within one to three weeks depending on the lending library. |
| 17 | factual | 1.0 | 0.785714 | 1.0 | 1.0 | Fixing a dripping tap can save more than five thousand litres of water per household each year. |
| 18 | factual | 1.0 | 0.833333 | 1.0 | 1.0 | A broken rail interrupts the track circuit and automatically sets signals to danger. |
| 19 | factual | 1.0 | 0.857143 | 1.0 | 1.0 | Moving-block signalling calculates safe separation continuously from each train's reported position and speed. |
| 20 | factual | 1.0 | 0.363636 | 1.0 | 1.0 | A typical night of sleep consists of four to six cycles, each lasting about ninety minutes. |
| 21 | factual | 1.0 | 1.0 | 1.0 | 1.0 | Rapid eye movement sleep is the stage most strongly associated with vivid dreaming. |
| 22 | factual | 1.0 | 0.8 | 1.0 | 1.0 | The 3-2-1 backup rule recommends three copies of data, on two different media, with one copy stored off site. |
| 23 | factual | 1.0 | 0.692308 | 1.0 | 1.0 | Cloud storage alone is not considered an archive because accounts can lapse or providers can change terms. |
| 24 | factual | 1.0 | 0.434783 | 1.0 | 1.0 | The three sisters method grows corn, beans, and squash together, with beans fixing nitrogen in the soil. |
| 25 | factual | 1.0 | 0.583333 | 1.0 | 1.0 | Marigolds are planted near tomatoes because their roots release compounds that suppress some nematodes. |
| 26 | multi-hop | 1.0 | 0.742857 | 1.0 | 1.0 | The three sisters method grows corn, beans, and squash together, with beans fixing nitrogen in the soil. |
| 27 | multi-hop | 1.0 | 0.514286 | 1.0 | 1.0 | Bakers judge readiness with the float test, where a spoonful of ripe starter floats in water. |
| 28 | multi-hop | 1.0 | 0.526316 | 1.0 | 1.0 | The duration of the waggle phase encodes the distance to the food, with longer dances signalling farther sources. |
| 29 | unanswerable | 1.0 | None | 1.0 | 1.0 | The largest tidal barrage in the world is the Sihwa Lake station in South Korea, with an installed capacity of 254 megaw |
| 30 | unanswerable | None | None | 0.0 | None | I don't have enough information in the provided sources to answer this question. |
| 31 | unanswerable | None | None | 1.0 | 1.0 | Low-flow showerheads reduce water use by mixing air into the stream while keeping pressure comfortable. |
| 32 | missing-context | 1.0 | None | 1.0 | 1.0 | Gear inches combine the ratio with wheel diameter to express how far the bicycle travels with one crank revolution. |
| 33 | missing-context | 1.0 | None | 1.0 | 1.0 | Fixing a dripping tap can save more than five thousand litres of water per household each year. |
| 34 | adversarial | 1.0 | None | 0.0 | None | I don't have enough information in the provided sources to answer this question. |
| 35 | adversarial | 1.0 | None | 0.0 | None | I don't have enough information in the provided sources to answer this question. |
| 36 | ambiguous | None | None | 0.0 | None | I don't have enough information in the provided sources to answer this question. |
| 37 | ambiguous | 1.0 | None | 1.0 | 1.0 | A typical interlibrary loan request is fulfilled within one to three weeks depending on the lending library. |
| 38 | contradictory | 1.0 | None | 1.0 | 1.0 | The largest tidal barrage in the world is the Sihwa Lake station in South Korea, with an installed capacity of 254 megaw |

*Faithfulness is a heuristic token-overlap estimate, not verified ground truth. LLM-judge metrics are opinion signals and are labelled as such.
