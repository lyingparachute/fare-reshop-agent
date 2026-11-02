from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import NewType

from fare_reshop_agent.reshopping.domain.money import Money

BookingRef = NewType("BookingRef", str)
OfferId = NewType("OfferId", str)


class Cabin(StrEnum):
    BASIC_ECONOMY = "BASIC_ECONOMY"
    ECONOMY = "ECONOMY"
    PREMIUM_ECONOMY = "PREMIUM_ECONOMY"
    BUSINESS = "BUSINESS"
    FIRST = "FIRST"

    @property
    def rank(self) -> int:
        return tuple(Cabin).index(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class Route:
    origin: str
    destination: str
    departure_date: date


@dataclass(frozen=True, slots=True, kw_only=True)
class Booking:
    ref: BookingRef
    passengers: int
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    carrier: str
    stops: int
    cabin: Cabin
    price_per_passenger: Money
    total_paid: Money
    refundable: bool
    change_fee_per_passenger: Money
    checked_bags: int

    def __post_init__(self) -> None:
        if not self.ref:
            raise ValueError("a booking needs a booking reference")
        _require_count(self.passengers, "passengers")
        if self.passengers < 1:
            raise ValueError(f"passengers must be at least 1, got {self.passengers}")
        _require_naive(self.departure, "departure")
        _require_naive(self.arrival, "arrival")
        _require_not_negative_count(self.stops, "stops")
        _require_not_negative_count(self.checked_bags, "checked bags")
        _require_not_negative_money(self.price_per_passenger, "price per passenger")
        _require_not_negative_money(self.total_paid, "total paid")
        _require_not_negative_money(self.change_fee_per_passenger, "change fee per passenger")
        if self.total_paid.currency != self.price_per_passenger.currency:
            raise ValueError(
                f"total paid is in {self.total_paid.currency}"
                f" but the price is in {self.price_per_passenger.currency}"
            )
        if self.total_paid != self.price_per_passenger.times(self.passengers):
            raise ValueError(
                f"total paid {self.total_paid} is not {self.passengers}"
                f" x {self.price_per_passenger}"
            )

    @property
    def route(self) -> Route:
        return Route(
            origin=self.origin,
            destination=self.destination,
            departure_date=self.departure.date(),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Offer:
    offer_id: OfferId
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    carrier: str
    stops: int
    cabin: Cabin
    price: Money
    refundable: bool
    change_fee_per_passenger: Money
    checked_bags: int
    seats_available: int

    def __post_init__(self) -> None:
        if not self.offer_id:
            raise ValueError("an offer needs an offer id")
        _require_naive(self.departure, "departure")
        _require_naive(self.arrival, "arrival")
        _require_not_negative_count(self.stops, "stops")
        _require_not_negative_count(self.checked_bags, "checked bags")
        _require_not_negative_count(self.seats_available, "seats available")
        _require_not_negative_money(self.price, "price")
        _require_not_negative_money(self.change_fee_per_passenger, "change fee per passenger")

    @property
    def route(self) -> Route:
        return Route(
            origin=self.origin,
            destination=self.destination,
            departure_date=self.departure.date(),
        )


def _require_naive(moment: datetime, name: str) -> None:
    if moment.tzinfo is not None:
        raise ValueError(f"{name} must be a local time without a time zone, got {moment}")


def _require_count(count: int, name: str) -> None:
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeError(f"{name} must be a whole number, got {count!r}")


def _require_not_negative_count(count: int, name: str) -> None:
    _require_count(count, name)
    if count < 0:
        raise ValueError(f"{name} must be zero or more, got {count}")


def _require_not_negative_money(money: Money, name: str) -> None:
    if money.is_negative():
        raise ValueError(f"{name} must not be negative, got {money}")
