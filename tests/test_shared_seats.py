import dataclasses

import pytest

from fare_reshop_agent.reshopping.domain.shared_seats import SeatShortfall, seat_shortfalls
from fare_reshop_agent.reshopping.domain.trip import Booking, BookingRef, OfferId

from sample_data import OF_1001, sample_booking

OF_1001_ID = OfferId("OF-1001")


def booking(ref: str, passengers: int) -> Booking:
    base = sample_booking("QX7T2A")
    return dataclasses.replace(
        base,
        ref=BookingRef(ref),
        passengers=passengers,
        total_paid=base.price_per_passenger.times(passengers),
    )


def test_bookings_that_need_more_seats_than_the_offer_has_share_a_shortfall() -> None:
    bookings = [booking("AAA111", 2), booking("BBB222", 2)]
    offer = dataclasses.replace(OF_1001, seats_available=3)

    shortfalls = seat_shortfalls(
        {BookingRef("BBB222"): OF_1001_ID, BookingRef("AAA111"): OF_1001_ID}, bookings, [offer]
    )

    assert shortfalls == (
        SeatShortfall(
            offer_id=OF_1001_ID,
            seats_available=3,
            seats_needed=4,
            refs=(BookingRef("AAA111"), BookingRef("BBB222")),
        ),
    )


def test_bookings_that_fit_together_have_no_shortfall() -> None:
    bookings = [booking("AAA111", 2), booking("BBB222", 2)]
    offer = dataclasses.replace(OF_1001, seats_available=4)

    claims = {BookingRef("AAA111"): OF_1001_ID, BookingRef("BBB222"): OF_1001_ID}

    assert seat_shortfalls(claims, bookings, [offer]) == ()


def test_one_booking_alone_is_left_to_the_seats_rule() -> None:
    offer = dataclasses.replace(OF_1001, seats_available=1)

    claims = {BookingRef("AAA111"): OF_1001_ID}

    assert seat_shortfalls(claims, [booking("AAA111", 3)], [offer]) == ()


def test_shortfall_needs_more_passengers_than_seats() -> None:
    with pytest.raises(ValueError, match="no shortfall"):
        SeatShortfall(
            offer_id=OF_1001_ID,
            seats_available=4,
            seats_needed=4,
            refs=(BookingRef("AAA111"), BookingRef("BBB222")),
        )


def test_shortfall_needs_two_bookings() -> None:
    with pytest.raises(ValueError, match="at least two bookings"):
        SeatShortfall(
            offer_id=OF_1001_ID, seats_available=1, seats_needed=2, refs=(BookingRef("AAA111"),)
        )
