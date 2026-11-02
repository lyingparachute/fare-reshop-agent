# 1. Value objects now, review aggregate later

## Status

Accepted

## Context

The tool reads bookings and offers from data it does not own, decides once per booking, and changes nothing. No booking, offer or result is ever updated after it is built. An aggregate exists to protect rules that hold while state changes. Here no state changes, so there is nothing for an aggregate to guard.

## Decision

Booking, offer, money, exchange rate, offer evaluation and recommendation are immutable value objects. Booking, offer, money and exchange rate check their own rules when they are built and refuse bad input. An evaluation and a recommendation hold only values those checks already passed. There is no aggregate and no write repository.

A future review aggregate is described here but not built. It would own the life of one review once a person can act on it: accept, reject or rebook. That adds state that changes, and with it rules to protect.

## Consequences

The domain has no identity tracking, no save step and no write port. Tests build values in code and compare them by value. When a person can act on a recommendation, the review aggregate becomes the place for that state, and this record is revisited.

## Alternatives

A booking as the aggregate root that holds its recommendation. It lost because bookings never change in this tool, so the root would guard no rule, and the project does not own booking data.
