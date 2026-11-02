# Glossary

The terms the code, tests and docs use.

### Booking

One ticketed trip, identified by its booking reference (the PNR code, for example `QX7T2A`). It has one flight segment, a number of passengers, and a ticket with the price paid, the cabin, the refund right, the change fee per passenger and the checked bags included.

### Offer

One fare on sale now for the same origin, destination and departure date as a booking. It carries the same kind of fields as the ticket, plus the seats still available.

### Rule check

One of seven tests that compare an offer with a booking: cabin, refundable, bags, stops, seats, future change fee and exchange rate. Each gives PASS or FAIL with a reason. There is no third result.

### Eligible offer

An offer that passes all seven rule checks and whose nominal saving reaches the minimum saving. Only an eligible offer can be recommended.

### Approval flag

A note on an offer that a person must approve, such as a schedule change or a carrier change. A flag never fails a rule check.

### Nominal saving

The saving in the booking's currency. It is passengers times (old fare per passenger, minus the offer's fare per passenger converted to that currency, minus the old ticket's change fee per passenger). It is computed with exact decimals and rounded once, half-even, to cents.

### Realized saving

The money actually saved after a rebooking is carried out. This project does not compute it.

### Minimum saving

The least nominal saving that counts: 50.00 USD, converted to the booking's currency when needed and rounded once. A saving equal to the minimum counts.

### Exchange rate

A stored rate between two currencies, with the date of the rate, for example 1 EUR = 1.1433 USD on 2026-07-07. One stored rate answers both directions.

### Recommendation

The decision for one booking: rebook, keep, or invalid data. A rebook names the chosen offer, its nominal saving, its approval flags, the reasoning and the rates used. A keep gives the reasoning, the minimum saving and the rates. Invalid data gives the reason the booking could not be reviewed. In a model mode, two more results exist: needs review and incomplete analysis. Each result also says what decided it: the rules, the model or the safety check.

### Needs review

A model-mode result that a person must check before anything changes. The safety check gives it when the model's choice fails a rule, misses the minimum saving or names an unknown offer, or when the model says keep while an eligible offer exists. It shows the rules' view and the model's text side by side.

### Incomplete analysis

A model-mode result with no decision. The booking's model turns ended on the turn cap, a repeated tool call, a bad final answer, a refusal or a provider error. It never counts as a rebook.

### Trace

The record of one booking's model turns in a model-mode result: the prompt version, the number of turns, the token usage, each tool call with its arguments and whether it ran, and the closed code of a provider error, if any.

### Tool

A read-only function the model can ask the code to run in a model mode. There are three: `get_booking`, `search_offers` and `check_offer`. The code binds the booking, so the model never passes a booking reference. The model never runs code, and no tool can change a booking.

### Transcript

The ordered record of one booking's conversation with the model. It holds the booking reference, the number of the next turn, the instructions, the tool specs, the first message, each reply's tool calls and each tool result. It never changes once built. The loop builds a longer copy after each turn. The provider keeps no state, so the transcript is the only state between turns.

### Turn

One call to the model and its reply. A booking's turns count from 1. A reply holds tool calls, final text, a refusal, or a provider failure. A booking gets at most 10 turns.

### Safety check

The plain-code step after the model's final answer. For a rebook, it checks that the chosen offer is on the booking's route and date, then re-runs the rule checks and the nominal saving for that offer, and checks that the saving still meets the minimum saving. It ignores any amount the model writes. A failing choice, or a keep while an eligible offer exists, becomes a result that a person must review.
