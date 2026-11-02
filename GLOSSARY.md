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

The decision for one booking: rebook, keep, or invalid data. A rebook names the chosen offer, its nominal saving, its approval flags, the reasoning and the rates used. A keep gives the reasoning, the minimum saving and the rates. Invalid data gives the reason the booking could not be reviewed.
