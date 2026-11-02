---
status: accepted
date: 2026-11-02
---

# ADR 0001: Each run starts fresh and stores no review state

## Context

The tool reads bookings and fares, and prints one recommendation per booking. It changes no booking and saves no result. A real reshop service would need memory between runs. It would track which recommendations a person approved or rejected, avoid sending the same booking twice, and compare the promised saving with the real one.

Building that memory now means a database, a schema and a review workflow. None of those can be tested against a fixed snapshot of five bookings.

## Decision

Each run is a pure function of its inputs: bookings, fares, policy and exchange rates in, recommendations out. Nothing is stored between runs. Bookings, offers, money and results are immutable, and each one validates itself when it is created.

A review record is the planned next step. It would hold one recommendation through its life: proposed, approved or rejected with a reason, and executed.

## Consequences

- Without a live model, the same input always gives the same output. That is what makes the recorded replay ([ADR 0004](0004-recorded-replay-default.md)) and the tests possible.
- A second run recommends the same rebooking again. A person sees no history of what they already decided.
- Nothing measures the realized saving, so nobody can tell yet whether the tool makes money.
- Rejection reasons, which are the best data for improving the rules and the prompt, are lost.
- Revisit when a person can act on a recommendation. Then the review record holds that state, and the rules about it live there.

## Alternatives rejected

| Alternative | Why not |
| --- | --- |
| Store results in a local file or SQLite now | Nothing reads them yet, so the schema would be a guess. |
| Model the booking as the object that holds its recommendation | The tool never changes a booking, and the booking data belongs to someone else. |
