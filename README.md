# fare-reshop-agent

Airfares often drop after you buy the ticket. If the same seat gets cheaper, you can sometimes rebook and keep the difference. That only pays off when the saving beats the change fee, and when the new fare does not quietly take something away, like checked baggage or a refund option.

This project is an agent that checks booked flights against fares on sale now. For each booking it returns one recommendation: rebook or keep, which fare, why, how confident it is, and the net saving after fees.

## Why an agent, and why not only an LLM

Most of the decision is arithmetic and rules, and money math should not depend on a model. Plain code handles matching offers to bookings, currency, per-passenger totals, change fees and hard rules like "never drop to a lower cabin". The model only explains a choice and flags trade-offs that the code cannot score. It never produces the saving figure.

## What "worth it" means here

A cheaper offer is not a saving by default. An offer is rejected or marked down when it:

- costs more than the old fare once you add the change fee for every passenger
- moves you to a lower cabin, for example economy to basic economy
- drops checked baggage or refundability that the booking had
- changes the schedule or adds a stop
- uses a different currency than the booking and has no exchange rate to check against
- has fewer seats left than the booking has passengers

## Sample data

`fixtures/` holds a small offline snapshot:

- `pnrs.json`: 5 booked trips (JFK-LAX, SFO-ORD, LHR-JFK, MIA-BOG, SEA-DEN), with 1 or 2 passengers each, in USD and EUR.
- `fares_feed.json`: 6 fares on sale now for the same routes and dates.

The rule attributes of each fare (cabin, refundability, change fee, included bags) are in the data, so no network or airline API is needed.

## Status

Work in progress. The design notes go in `DESIGN.md`, and the prototype runs offline without an API key. Run instructions and sample output will land here with the code.
