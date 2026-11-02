---
status: accepted
date: 2026-11-02
---

# ADR 0002: Rules run before the model, and a safety check runs after it

## Context

Most of a rebooking decision is arithmetic and yes-or-no rules: cabin, bags, refundability, stops, seats, fees, currency. Plain code gets these right every time, for free. A model can get them wrong, and a wrong saving that reaches a person is the worst failure this tool can have.

Some choices have no rule. One offer saves 170 USD and moves the flight by 40 minutes. Another saves 80 USD with no change. Which is better depends on the traveler, and the data says nothing about the traveler. That trade-off, and explaining it to the person who approves the change, is the one part of the job where a model can help.

## Decision

Plain code checks every offer against every rule first. A booking with no eligible offer is settled as `KEEP` and never reaches the model.

For a booking with at least one eligible offer, the model picks one of them or says keep. It also writes a short reason and a confidence. Its answer contains no amounts.

A safety check in plain code then re-reads the booking and the chosen offer, and runs the rules and the saving again. The results:

- A valid pick is `REBOOK`. If it is not the biggest saving, `best_offer_id` names the biggest one.
- A pick that fails a rule, misses the minimum or does not exist is `NEEDS_REVIEW`.
- A keep while an eligible offer exists is `NEEDS_REVIEW`. The rules found a saving and the model turned it down, so a person decides.

Once every booking has a result, a seat check looks across them. If several bookings would rebook onto one offer and it cannot seat them all, each of them becomes `NEEDS_REVIEW`. This check also runs in the rules-only mode.

## Consequences

- Bookings the rules settle cost nothing. On the sample data that is 3 of 5.
- Every amount in a structured field (`nominal_saving`, `minimum_saving`, each offer's saving) comes from code.
- The model's reasoning is free text, and it can still state a wrong amount ([example in DESIGN.md](../../DESIGN.md#what-the-recorded-runs-show)). The output marks that text with "Model text:", and the structured field is the one to trust.
- The model cannot turn a rules `KEEP` into a rebook. It can only choose among offers the rules accepted, or send the booking to a person.
- In both recorded runs, the model picked the offer the rules ranked first. Nothing measures yet whether its picks beat "take the biggest saving".
- Revisit when a labeled eval set exists. If the model's picks add nothing over the biggest saving, drop it and generate the reason text from the rule results. If free-text fare rules or traveler preferences enter the data, the model's role grows.

## Alternatives rejected

| Alternative | Why not |
| --- | --- |
| A model screens bookings before the rules | It can drop real savings, and it pays for work the rules do for free. |
| The model decides every booking | It pays for calls the rules settle, and it could overturn a correct rules result. |
| Code always takes the biggest saving, and the model only writes text | It hides the trade-off between a saving and a schedule or carrier change. I kept this as the fallback if an eval shows the model adds nothing. |
| Trust amounts the model reports | Wrong figures from a model are the failure this design exists to prevent. |
| Accept the model's keep as the final result | A missed saving would pass with no one looking at it. |
