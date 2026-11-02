import dataclasses
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fare_reshop_agent.reshopping.domain.evaluation import OfferEvaluation, RuleName, RuleOutcome
from fare_reshop_agent.reshopping.domain.exchange_rate import ExchangeRate, NoRate
from fare_reshop_agent.reshopping.domain.money import Currency, Money
from fare_reshop_agent.reshopping.domain.port.reshop_source import RejectedBooking, ReshopSnapshot
from fare_reshop_agent.reshopping.domain.terms import ReviewPolicy
from fare_reshop_agent.reshopping.domain.trip import Booking, BookingRef, Cabin, Offer, OfferId
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import JsonFixtureSource

USD = Currency(code="USD")
EUR = Currency(code="EUR")
GBP = Currency(code="GBP")
EUR_USD = ExchangeRate(base=EUR, quote=USD, rate=Decimal("1.1433"), as_of=date(2026, 7, 7))
POLICY = ReviewPolicy(minimum_saving=Money.of("50.00", USD))


class InMemoryRates:
    def __init__(self, rates: Mapping[tuple[Currency, Currency], ExchangeRate]) -> None:
        self._rates = dict(rates)

    def find_rate(self, source: Currency, target: Currency) -> ExchangeRate | NoRate:
        for pair in ((source, target), (target, source)):
            if pair in self._rates:
                return self._rates[pair]
        return NoRate(source=source, target=target)


NO_RATES = InMemoryRates({})
DEMO_RATES = InMemoryRates({(EUR, USD): EUR_USD})


def usd(amount: str) -> Money:
    return Money.of(amount, USD)


def eur(amount: str) -> Money:
    return Money.of(amount, EUR)


QX7T2A = Booking(
    ref=BookingRef("QX7T2A"),
    passengers=1,
    origin="JFK",
    destination="LAX",
    departure=datetime(2026, 8, 15, 8, 0),
    arrival=datetime(2026, 8, 15, 11, 20),
    carrier="AA",
    flight_number="AA118",
    stops=0,
    cabin=Cabin.ECONOMY,
    price_per_passenger=usd("480.00"),
    total_paid=usd("480.00"),
    refundable=False,
    change_fee_per_passenger=usd("100.00"),
    checked_bags=1,
)

OF_1001 = Offer(
    offer_id=OfferId("OF-1001"),
    origin="JFK",
    destination="LAX",
    departure=datetime(2026, 8, 15, 8, 0),
    arrival=datetime(2026, 8, 15, 11, 20),
    carrier="AA",
    flight_number="AA118",
    stops=0,
    cabin=Cabin.ECONOMY,
    price=usd("300.00"),
    refundable=False,
    change_fee_per_passenger=usd("100.00"),
    checked_bags=1,
    seats_available=5,
)

RT5K8B = dataclasses.replace(
    QX7T2A,
    ref=BookingRef("RT5K8B"),
    cabin=Cabin.BUSINESS,
    refundable=True,
    price_per_passenger=eur("2200.00"),
    total_paid=eur("2200.00"),
    change_fee_per_passenger=eur("0.00"),
    checked_bags=2,
)

OF_3001 = dataclasses.replace(
    OF_1001,
    offer_id=OfferId("OF-3001"),
    cabin=Cabin.BUSINESS,
    refundable=True,
    price=usd("2100.00"),
    change_fee_per_passenger=usd("0.00"),
    checked_bags=2,
    seats_available=2,
)


def outcomes(evaluation: OfferEvaluation) -> dict[RuleName, RuleOutcome]:
    return {result.rule: result.outcome for result in evaluation.rules}


def result_of(evaluation: OfferEvaluation, rule: RuleName) -> RuleOutcome:
    return outcomes(evaluation)[rule]


def all_pass(evaluation: OfferEvaluation) -> bool:
    return set(outcomes(evaluation).values()) == {RuleOutcome.PASS}


REPO_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
REPO_CONFIG = REPO_FIXTURES.parent / "config"
PROMPT_FILE = (
    REPO_FIXTURES.parent / "fare_reshop_agent" / "reshopping" / "orchestration" / "review_prompt.md"
)


class InMemorySource:
    def __init__(self, snapshot: ReshopSnapshot) -> None:
        self._snapshot = snapshot

    def read_snapshot(self) -> ReshopSnapshot:
        return self._snapshot


def sample() -> ReshopSnapshot:
    return JsonFixtureSource(REPO_FIXTURES).read_snapshot()


def sample_booking(ref: str) -> Booking:
    return next(b for b in sample().bookings if isinstance(b, Booking) and b.ref == ref)


def with_bookings(*bookings: Booking | RejectedBooking) -> ReshopSnapshot:
    return dataclasses.replace(sample(), bookings=bookings)
