# Agent context

Read this before you change anything in the repo.

## Project

`fare-reshop-agent` compares booked flights with fares on sale now. For each booking it returns one recommendation: rebook or keep, which fare, why, how confident it is, and the net saving after fees.

It must run offline. No API key, network or paid service is needed for the default run or the tests. A live LLM mode is optional and must fail closed: a missing key, a provider error or a bad reply never produces a positive recommendation.

## Data

- `fixtures/pnrs.json`: booked trips. Prices are per passenger. `totalPaid` covers all passengers.
- `fixtures/fares_feed.json`: a snapshot of offers, captured at `capturedAt`. Prices are per passenger.
- Never edit `fixtures/` to make code or tests pass. Tests that need other data build it in the test or in `tests/`.
- `ticket.changeFeePerPassenger` is the fee to change the booked ticket today. An offer's `changeFeePerPassenger` is the fee for changing that new fare later. Never use one in place of the other.
- Currencies differ between bookings. Never compare amounts in different currencies without an exchange rate from the data.

## Where the LLM is allowed

- Plain code owns money math, currency checks, offer matching and the no-downgrade rules. Use `Decimal` for money.
- The model may choose which read-only tools to call and write the short rationale.
- A deterministic check re-reads the booking and the offer before any output. It recomputes the saving and rejects unknown offer IDs. It ignores amounts the model reports.
- No tool can change a booking.

## Conventions

- English for code, docs and commit messages.
- One-line commit messages.
- Every behavior change ships with a test that runs offline.
- `DESIGN.md` holds design decisions and open questions. `README.md` holds how to run it and sample output.
- Python rules live in `.claude/rules/python.md`. Read them before you write or review Python.
