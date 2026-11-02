from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from fare_reshop_agent.reshopping.domain.trip import Booking, BookingRef, Offer, OfferId

MIN_SHARING_BOOKINGS = 2


@dataclass(frozen=True, slots=True, kw_only=True)
class SeatShortfall:
    offer_id: OfferId
    seats_available: int
    seats_needed: int
    refs: tuple[BookingRef, ...]

    def __post_init__(self) -> None:
        if self.seats_needed <= self.seats_available:
            raise ValueError(
                f"{self.offer_id} has {self.seats_available} seats for {self.seats_needed}"
                " passengers, so there is no shortfall"
            )
        if len(self.refs) < MIN_SHARING_BOOKINGS:
            raise ValueError("a shortfall is shared by at least two bookings")


def seat_shortfalls(
    claims: Mapping[BookingRef, OfferId],
    bookings: Iterable[Booking],
    offers: Iterable[Offer],
) -> tuple[SeatShortfall, ...]:
    passengers = {booking.ref: booking.passengers for booking in bookings}
    seats = {offer.offer_id: offer.seats_available for offer in offers}
    refs_by_offer: dict[OfferId, list[BookingRef]] = {}
    for ref, offer_id in sorted(claims.items()):
        refs_by_offer.setdefault(offer_id, []).append(ref)
    shortfalls: list[SeatShortfall] = []
    for offer_id, refs in sorted(refs_by_offer.items()):
        needed = sum(passengers[ref] for ref in refs)
        if len(refs) >= MIN_SHARING_BOOKINGS and needed > seats[offer_id]:
            shortfalls.append(
                SeatShortfall(
                    offer_id=offer_id,
                    seats_available=seats[offer_id],
                    seats_needed=needed,
                    refs=tuple(refs),
                )
            )
    return tuple(shortfalls)
