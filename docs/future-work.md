# Future work

What I would build after this, grouped by area. **Next** items need nothing new. **Later** items need real data, real users or real volume first.

## Money

| Item | Why | When |
|---|---|---|
| A `currency_change` approval flag when the offer and the ticket are in different currencies | An airline may not accept a USD fare for a ticket sold in EUR, and the saving then moves with the rate. RT5K8B is this case. Needs a new recording, because the model sees the flags. | Next |
| A live exchange rate, with its source and time in every result | A saving from an unnamed rate cannot be checked later. | Next |
| Rounding per currency | JPY has no cents, and a few currencies have three decimals. | Next |
| Minimum saving as a percentage or per passenger | 50 USD is noise on a 2,000 USD business fare and a lot on a 120 USD one. | Next |
| Residual value of the old ticket: cash, voucher or nothing | A saving paid as a voucher that expires is worth less than cash. Today every saving is nominal. | Later |
| A binding exchange quote from the airline before a person approves | Without it, every saving is an estimate. | Later |

## Trips

| Item | Why | When |
|---|---|---|
| Multi-segment and round trips | Most real bookings have more than one flight. | Next |
| Time zones on departure and arrival | Fixture times have no offset, so the "departs before the snapshot" check can be off by hours. | Next |
| A schedule window that needs no approval, for example 60 minutes | Today a 20-minute shift needs the same approval as a 5-hour one. | Next |
| Airport changes in one city, codeshares, connection times | Each is a way a cheaper fare can be a worse trip. | Later |
| Seats held against live inventory | The seat check only sees one run. Two runs can still promise the same seats. | Later |

## The model

| Item | Why | When |
|---|---|---|
| A labeled eval set, run on every prompt or model change | Today I cannot tell if a prompt change helped. It also decides whether the model stays at all. | Next |
| Code writes the money sentence, the model writes only the trade-off | The model wrote "saves $80 per passenger" for a booking that saves 80 USD in total. | Next |
| Token, time and cost budgets per booking | Stops one bad loop from costing more than the saving it chases. | Next |
| Prompt caching for the fixed instructions and tool specs | They are the same for every booking. | Later |
| Defense against prompt injection in fare rule text | Fare rules come from third parties. A rule that says "ignore previous instructions" must not change a result. | Later |
| Mask booking data before it reaches the provider or a recording | The fixtures are made up. Real bookings are not. | Later |

## Review and execution

| Item | Why | When |
|---|---|---|
| A review queue that stores each proposal and the person's decision with a reason | Survives restarts, and rejections with reasons are the best eval data. | Next |
| Re-price right before approval and block if the offer changed | A recommendation from the morning can be wrong by the afternoon. | Next |
| Automatic rebooking for a narrow class: same flight, same conditions, saving above a threshold | Removes manual work where the risk is lowest. It runs in shadow mode first, with a kill switch and no double booking on retry. | Later |

## Scale and observability

| Item | Why | When |
|---|---|---|
| One fare search per route and date, shared by all bookings on it | Fare search is the expensive call, and thousands of bookings share a few hundred routes. | Next |
| Retryable and permanent errors, with progress saved per booking | A large run can stop and resume without redoing finished bookings. | Next |
| One trace per booking with a correlation id | Answers "why did this booking get this result" without guessing. | Next |
| Metrics: rule-check reject rate, safety-check veto rate, model and rules disagreement, cost per booking | A rising veto rate is the first sign that the model or the prompt drifted. | Next |
| Nominal saving against realized saving for each approved rebooking | The number that says whether the tool makes money. | Later |
| Reshop when a fare changes, not on a schedule | Work then follows price moves, not the size of the book. | Later |

## Code

| Item | Why | When |
|---|---|---|
| Property-based tests for the money math | They find rounding and sign errors that hand-written cases miss. | Next |
| Contract tests that every adapter for a port must pass | A live exchange-rate adapter can then replace the stub safely. | Next |
