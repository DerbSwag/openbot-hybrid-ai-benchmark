
# Benchmark methodology

Use the same synthetic case, revision, rubric, scoring rules and evaluation protocol across modes. Predeclare sample counts, time and token budgets, allowed tools, model versions/settings, runtime and hardware, context limits and intervention policy. Record the actual agents participating. Score failures and missing outcomes using the same denominators in each mode.

For an orchestration comparison, include a Single Cloud baseline using the same primary decision model and tokenizer as Hybrid and match case, rubric and protocol IDs. Keep decoding settings, available tools, limits, time budgets and inputs matched where feasible. Verify this from the protocol independently of matching IDs. This comparison controls for the decision model. Local versus Cloud and the effect of other Hybrid models still require separate interpretation.

| Metric | Calculation |
| --- | --- |
| Accuracy | Sum weights for matching claim values with the required evidence. Expected weights remain in the denominator; unexpected claim IDs add one possible point each without credit. No output is unscored. Report coverage as scored runs divided by all started runs, beside completion. A zero score denominator means undefined. |
| End-to-end latency | Start of the run to its terminal outcome, including coordination and waits; retain total milliseconds and count per provenance, so mean is total/count where count is positive. Unknown latencies are counted separately. |
| Token consumption | Sum cached input, uncached input and output separately for all executed invocations across agents, with coverage per provenance and missing counts per category. |
| Completion | Completed runtime status plus all rubric deliverables with their required evidence. Report completed/all started, with unknown and partial counts. |
| Context overflow | Runs with at least one qualifying event divided by all started, alongside unknown telemetry and counts of the five event types. One run counts once regardless of its number of events. The reported ratio is a lower bound where unknowns exist. |
| Estimated API cost | For covered Cloud invocations, apply `(cached×rate + uncached×rate + output×rate)/1,000,000` using decimal arithmetic, versioned synthetic USD rate snapshots and distinct expected/estimated sums. Missing rates or token counts are reported with coverage. Local and rejected invocations are nonapplicable. Subscription charges are separate. |
| Security compliance | A violation event fails; a complete attestation with no violations passes; incomplete evidence is unknown. This describes the recorded run, and requires independent evidence for any real assessment. |
| Human intervention | Count distinct approval events separately from failure-related interventions. The initial task prompt is outside this count. |

## Independent golden arithmetic

`fixtures/synthetic/golden/summary.json` is handwritten expected arithmetic independent of evaluator outputs. Provenance vectors use expected, estimated, measured order and carry missing-value counts. The checked-in corpus includes two records for each mode.

| Mode | Accuracy; coverage; completion | Latency and tokens | Overflow; cost; security; human |
| --- | --- | --- | --- |
| Local | 3/3 scored; 1/2 covered; 1/2 complete, one unknown | 120 ms expected and one unknown; expected token totals 0/40/10, estimated 0/70/0 with only uncached observed | 1/2; no API-priced invocation; 1 pass and 1 unknown; 0 approvals and 0 failure interventions |
| Cloud | (3 + 2)/(3 + 3); 2/2 covered; 1/2 complete, one partial | 200 ms expected and 300 ms estimated; token totals 20/60/30 expected and 10/30/5 estimated | 0/2 with one compaction; expected USD (20 + 120 + 120)/1M = 0.00026, estimated (10 + 60 + 20)/1M = 0.00009; 1 pass and 1 simulated failure; 0 approvals and 1 failure intervention |
| Hybrid | 3/3 scored; 1/2 covered; 0/2 complete, one partial | (320 + 20) ms expected; expected tokens 5/(25 + 95)/(8 + 15), one invocation unreported | 2/2, one event of each class except compaction; expected USD (5 + 190 + 60)/1M = 0.000255, one Cloud invocation missing data; 2 passes; 1 approval and 2 failure interventions |

Token triples are cached input, uncached input and output. Runtime truncation with unknown output, incomplete output without runtime truncation, missing VRAM, all three budget boundaries and each context event are explicitly represented or asserted. These are fixture expectations, so no performance ranking or measured cost can be inferred.
