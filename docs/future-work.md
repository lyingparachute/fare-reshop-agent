# Future work

Everything I would add after the first slice, grouped by area. Each item says what changes and why it matters.

Tiers:

- **Now**: in the first slice.
- **Next**: the first things I would build after it.
- **Later**: needs real data, real users or real volume first.

## Money

| Item | Why | Tier |
|---|---|---|
| Exchange rates behind a port, with a stub adapter holding fixed demo rates | Bookings and offers come in different currencies. Swapping in a live rate source then touches one adapter. | Now |
| Live exchange-rate adapter with the rate's source and timestamp in every result | A saving computed from a stale or unnamed rate cannot be checked later. | Next |
| Rounding rules per currency (JPY has no cents, some currencies have three decimals) | `0.01` rounding is wrong for part of the world. | Next |
| Split the fare into base fare, taxes and carrier fees | Taxes are often refunded on exchange while the base fare is not. The real saving depends on the split. | Later |
| Residual value of the old ticket: cash, credit or nothing | A "saving" paid out as an airline voucher that expires is worth less than cash. Today the saving is nominal only. | Later |
| Binding exchange quote from the airline or a booking system (GDS or NDC) before a person approves | The only way to turn a nominal saving into a real one. | Later |

## Fares and itineraries

| Item | Why | Tier |
|---|---|---|
| Multi-segment and round-trip bookings | Most real bookings have more than one flight. Today only one segment is supported. | Next |
| Timezone-aware departure and arrival times | Fixture times have no offset, so trip length and overnight arrivals cannot be computed. | Next |
| Schedule tolerance window, for example "up to 60 minutes earlier or later needs no approval" | Today any time change needs traveler approval, even a 20-minute shift. | Next |
| Airport changes within one city (JFK vs EWR), operating carrier vs codeshare, minimum connection time | Each one is a real way a cheaper fare can be a worse trip. | Later |
| Price lost perks instead of only rejecting them, for example a lost bag counted as its fee | Some travelers would trade a bag for 150 USD. That choice should be visible, not hidden by a hard rule. | Later |

## Policy and preferences

| Item | Why | Tier |
|---|---|---|
| Policy as data: thresholds, hard rules and approval rules in one versioned file | A business user can change "minimum saving" without a code change, and every result names the policy version it used. | Now |
| Policy profiles per client or traveler (a company travel policy, a traveler who never flies before 7:00) | One global rule set does not fit every client. | Later |
| Minimum saving as a percentage or per passenger, not only a flat amount | 50 USD on a 2,000 USD business fare is noise. On a 120 USD fare it matters. | Next |

## The agent

| Item | Why | Tier |
|---|---|---|
| Strict structured output for the final answer, checked against a schema | Malformed output becomes a typed error instead of a parse guess. | Now |
| Offline model adapter, so the default run and the tests need no key or network | Anyone can run it and the tests are repeatable. | Now |
| One result shape for every tool, errors included, and bad tool arguments sent back to the model as a tool error | The model can correct a bad call. A parse error never ends the run by accident. | Now |
| Every tool error carries a hint about what to do next, for example "unknown offer id, call search_offers first" | A bare error code wastes a step. A hint usually fixes the next call. | Now |
| Record real model runs and replay them in tests | Tests then use real model behavior, not a script I wrote. | Next |
| Eval set: labeled bookings with the expected outcome, the tools that must and must not be called, and a call limit, scored on every prompt or model change | The only honest way to know whether a prompt change helped or hurt. | Next |
| Have a model score the written rationale against fixed criteria, separate from the plain-code checks on tool use | Tool choice is checkable in code. Whether the rationale is clear and grounded is not. | Next |
| Run against a local open model through an OpenAI-compatible endpoint | A live-model test with no paid key and no data leaving the machine. | Later |
| Prompt and model version on every result | When quality drops, you can see which change caused it. | Next |
| Budgets per booking: time, tokens and cost, priced from token usage and a versioned price table | Stops one bad loop from costing more than the saving it chases. Provider dashboards do not show cost per booking. | Next |
| Prompt caching for the fixed part of the prompt | The instructions and tool schemas are identical for every booking. Cached input tokens are cheaper. | Later |
| Defense against prompt injection in free-text fare rules | Real fare rules are text from third parties. A rule that says "ignore previous instructions" must not change the outcome. | Later |
| The agent can pause, ask a person for missing data and resume | Some unknowns are cheaper to ask about than to reject. | Later |
| A cheap classifier in front of the agent at high volume, with a sampled audit of what it rejects | Cuts model cost at scale. The audit measures how much real saving it throws away. | Later |

## Human review

| Item | Why | Tier |
|---|---|---|
| Every recommendation goes to a person. Nothing books automatically. | The data has no binding quote, so no result can be execution-ready. | Now |
| Review queue that stores each pending review as data: the proposal, the computed numbers and the decision with its reason | Survives restarts, and declines with reasons are the best eval data there is. | Next |
| Re-price right before approval and block if the offer changed | Fares change by the minute. A recommendation from this morning can be wrong by lunch. | Next |
| Auto-rebook for a narrow safe class (same flight, same conditions, saving above a threshold) after a period in shadow mode | Removes manual work where the risk is lowest. Shadow mode first proves the rule against real decisions. | Later |
| Kill switch and idempotent execution | One flag stops all automatic actions, and a retry never books twice. | Later |

## Scale and cost

| Item | Why | Tier |
|---|---|---|
| Plain-code screen before any model call | On the sample data, code settles 4 of 5 bookings for free. The model runs only where judgment is needed. | Now |
| Search fares once per route and date, then share the result across all bookings on it | Thousands of bookings share a few hundred routes. Fare searches are the expensive call. | Next |
| Reshop when a fare changes instead of on a fixed schedule | Work then follows price movement, not the size of the booking book. | Later |
| Rank bookings by expected saving and departure date | The bookings closest to departure with the biggest gaps go first. Time is part of the value. | Later |
| Rate limits, retries with backoff and a circuit breaker per external source | One slow supplier must not stall the whole run. | Later |
| Split errors into retryable and permanent, and store progress per booking | A run over a large book can stop and resume without redoing finished bookings. | Next |

## Observability

| Item | Why | Tier |
|---|---|---|
| One trace per booking with a correlation id, covering screen, tool calls, model output and safety check, recorded at the adapter boundary | Answers "why did this booking get this result" without guessing. | Next |
| Metrics: screen reject rate, safety-check veto rate, model-vs-code disagreement, approval rate, cost and p95 latency per booking | A rising veto rate is the first sign the model or the prompt drifted. | Next |
| Estimated saving vs realized saving, tracked per approved rebooking | The number that says whether the whole system makes money. | Later |
| Redact traveler names and contact data in traces and logs | Traces are kept longer and seen by more people than bookings. | Next |

## Engineering

| Item | Why | Tier |
|---|---|---|
| Hexagonal layout: domain, application, ports, adapters | Domain rules are testable without a model, a network or a file system. | Now |
| Money and policy tests on every sample booking, including the old-vs-new change fee trap | The most expensive bugs in this domain are arithmetic ones. | Now |
| Strict type checking and a linter in CI | Catches the boring bugs before review does. | Next |
| Property-based tests for money math | Finds rounding and sign errors that hand-written cases miss. | Next |
| Contract tests that every adapter for a port passes, stub and real alike | Swapping the stub exchange-rate adapter for a live one stays safe. | Next |
| HTTP API as a second driving adapter next to the CLI | Shows the core does not depend on how it is called. | Later |

## Product ideas

| Item | Why | Tier |
|---|---|---|
| Savings report per agency or client | Turns single results into a number a business can act on. | Later |
| Hotel bookings with the same pipeline | Hotel rates drop too, and the screen, safety check and review steps carry over. | Later |
| Price-drop forecast: wait or rebook now | Rebooking too early can miss a bigger drop later. | Later |
