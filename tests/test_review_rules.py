import dataclasses
import decimal
import json
import shutil
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from fare_reshop_agent.reshopping.domain.evaluation import (
    OfferEvaluation,
    RuleName,
    RuleOutcome,
    RuleResult,
    evaluate_offer,
)
from fare_reshop_agent.reshopping.domain.exchange_rate import (
    Conversion,
    ExchangeRate,
    NoRate,
    RateUse,
)
from fare_reshop_agent.reshopping.domain.money import Currency, Money
from fare_reshop_agent.reshopping.domain.port.exchange_rates import ExchangeRates
from fare_reshop_agent.reshopping.domain.port.reshop_source import (
    DataIssueKind,
    RejectedBooking,
    ReshopSnapshot,
)
from fare_reshop_agent.reshopping.domain.recommendation import (
    Invalid,
    Keep,
    Rebook,
    Recommendation,
    decide,
)
from fare_reshop_agent.reshopping.domain.terms import (
    BookingTerms,
    ReviewPolicy,
    booking_terms,
    convert_minimum,
)
from fare_reshop_agent.reshopping.domain.trip import Booking, BookingRef, Cabin, Offer, OfferId
from fare_reshop_agent.reshopping.infrastructure.file_problem import FileProblem
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import (
    JsonFixtureError,
    JsonFixtureSource,
)
from fare_reshop_agent.reshopping.infrastructure.toml.readers import (
    TomlFileError,
    read_exchange_rates,
    read_policy,
)
from fare_reshop_agent.reshopping.orchestration.review import ReviewReport, review_snapshot

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


def reason_of(evaluation: OfferEvaluation, rule: RuleName) -> str:
    return next(result.reason for result in evaluation.rules if result.rule is rule)


def all_pass(evaluation: OfferEvaluation) -> bool:
    return set(outcomes(evaluation).values()) == {RuleOutcome.PASS}


def terms_of(booking: Booking, rates: ExchangeRates = NO_RATES) -> BookingTerms:
    terms = booking_terms(booking, POLICY, rates)
    assert isinstance(terms, BookingTerms)
    return terms


def evaluate(booking: Booking, offer: Offer, rates: ExchangeRates = NO_RATES) -> OfferEvaluation:
    return evaluate_offer(terms_of(booking, rates), offer, rates)


def is_eligible(booking: Booking, offer: Offer) -> bool:
    return isinstance(decide(terms_of(booking), [evaluate(booking, offer)]), Rebook)


def test_offer_in_lower_cabin_is_rejected() -> None:
    offer = dataclasses.replace(OF_1001, cabin=Cabin.BASIC_ECONOMY)

    evaluation = evaluate(QX7T2A, offer)

    assert result_of(evaluation, RuleName.CABIN) is RuleOutcome.FAIL
    assert reason_of(evaluation, RuleName.CABIN)
    assert not is_eligible(QX7T2A, offer)


def test_losing_refundability_fails_refundable_rule() -> None:
    booking = dataclasses.replace(QX7T2A, refundable=True)

    evaluation = evaluate(booking, OF_1001)

    assert result_of(evaluation, RuleName.REFUNDABLE) is RuleOutcome.FAIL
    assert evaluation.failed_rules == (RuleName.REFUNDABLE,)


def test_fewer_bags_fails_bags_rule() -> None:
    evaluation = evaluate(QX7T2A, dataclasses.replace(OF_1001, checked_bags=0))

    assert result_of(evaluation, RuleName.BAGS) is RuleOutcome.FAIL


def test_extra_stop_fails_stops_rule() -> None:
    evaluation = evaluate(QX7T2A, dataclasses.replace(OF_1001, stops=1))

    assert result_of(evaluation, RuleName.STOPS) is RuleOutcome.FAIL


def test_too_few_seats_fails_seats_rule() -> None:
    booking = dataclasses.replace(QX7T2A, passengers=2, total_paid=usd("960.00"))

    evaluation = evaluate(booking, dataclasses.replace(OF_1001, seats_available=1))

    assert result_of(evaluation, RuleName.SEATS) is RuleOutcome.FAIL


def test_higher_future_change_fee_fails_rule() -> None:
    offer = dataclasses.replace(OF_1001, change_fee_per_passenger=usd("100.01"))

    evaluation = evaluate(QX7T2A, offer)

    assert result_of(evaluation, RuleName.FUTURE_CHANGE_FEE) is RuleOutcome.FAIL


def test_equal_future_change_fee_passes() -> None:
    offer = dataclasses.replace(OF_1001, change_fee_per_passenger=usd("100.00"))

    evaluation = evaluate(QX7T2A, offer)

    assert result_of(evaluation, RuleName.FUTURE_CHANGE_FEE) is RuleOutcome.PASS


def test_schedule_change_adds_approval_flag_without_failing() -> None:
    offer = dataclasses.replace(OF_1001, departure=datetime(2026, 8, 15, 8, 20))

    evaluation = evaluate(QX7T2A, offer)

    assert evaluation.approval_flags == ("schedule_change",)
    assert all_pass(evaluation)


def test_carrier_change_adds_approval_flag_without_failing() -> None:
    evaluation = evaluate(QX7T2A, dataclasses.replace(OF_1001, carrier="UA"))

    assert evaluation.approval_flags == ("carrier_change",)
    assert all_pass(evaluation)


def test_qx7t2a_nominal_saving_is_80_usd() -> None:
    evaluation = evaluate(QX7T2A, OF_1001)

    assert evaluation.nominal_saving == usd("80.00")
    assert evaluation.nominal_saving == Money(amount=Decimal("80.00"), currency=USD)


def test_lm9p4c_saving_is_minus_90_usd() -> None:
    booking = dataclasses.replace(
        QX7T2A,
        passengers=2,
        price_per_passenger=usd("350.00"),
        total_paid=usd("700.00"),
        change_fee_per_passenger=usd("75.00"),
    )
    offer = dataclasses.replace(OF_1001, price=usd("320.00"))

    evaluation = evaluate(booking, offer)

    assert evaluation.nominal_saving == Money(amount=Decimal("-90.00"), currency=USD)


def test_minimum_is_checked_after_rounding() -> None:
    booking = dataclasses.replace(
        QX7T2A,
        price_per_passenger=usd("100.00"),
        total_paid=usd("100.00"),
        change_fee_per_passenger=usd("0"),
    )
    offer = dataclasses.replace(OF_1001, price=usd("50.004"), change_fee_per_passenger=usd("0"))

    evaluation = evaluate(booking, offer)

    assert evaluation.nominal_saving == Money(amount=Decimal("50.00"), currency=USD)
    assert is_eligible(booking, offer)


def test_money_rejects_float_input() -> None:
    with pytest.raises(TypeError, match="float"):
        Money.of(80.0, USD)  # type: ignore[arg-type]  # a float on purpose: proves the runtime refusal


def test_money_rejects_bool_input() -> None:
    with pytest.raises(TypeError, match="bool"):
        Money.of(True, USD)


def test_money_accepts_text_and_int() -> None:
    from_text = Money.of("80.00", USD)
    from_int = Money.of(80, USD)

    assert isinstance(from_text.amount, Decimal)
    assert isinstance(from_int.amount, Decimal)
    assert from_text == from_int


def test_adding_two_currencies_raises() -> None:
    with pytest.raises(ValueError, match="USD with EUR"):
        usd("1") + eur("1")


def test_ordering_two_currencies_raises() -> None:
    with pytest.raises(ValueError, match="USD with EUR"):
        _ = usd("1") < eur("1")


def test_equality_across_currencies_raises() -> None:
    with pytest.raises(ValueError, match="USD with EUR"):
        _ = usd("50") == eur("50")


def test_offer_in_other_currency_without_rate_fails_exchange_rate_rule() -> None:
    offer = dataclasses.replace(OF_1001, price=eur("300"))

    evaluation = evaluate(QX7T2A, offer)

    assert result_of(evaluation, RuleName.EXCHANGE_RATE) is RuleOutcome.FAIL
    assert evaluation.nominal_saving == NoRate(source=EUR, target=USD)


def test_offer_in_other_currency_with_rate_uses_inverse_direction() -> None:
    evaluation = evaluate(RT5K8B, OF_3001, DEMO_RATES)

    assert evaluation.nominal_saving == Money(amount=Decimal("363.21"), currency=EUR)
    price_rates = [usage.rate for usage in evaluation.rates if usage.use is RateUse.OFFER_PRICE]
    assert [rate.direction for rate in price_rates] == ["1 EUR = 1.1433 USD"]


def test_minimum_saving_in_eur_is_43_73() -> None:
    minimum = convert_minimum(POLICY, EUR, DEMO_RATES)

    assert isinstance(minimum, Conversion)
    assert minimum.money == Money(amount=Decimal("43.73"), currency=EUR)


def test_exchange_rate_converts_in_both_directions() -> None:
    assert EUR_USD.convert(usd("1.1433")) == Money(amount=Decimal("1"), currency=EUR)
    assert EUR_USD.convert(eur("1")) == Money(amount=Decimal("1.1433"), currency=USD)


def test_booking_total_paid_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="total paid"):
        dataclasses.replace(
            QX7T2A, passengers=2, price_per_passenger=usd("350.00"), total_paid=usd("700.01")
        )


def test_recommendation_picks_highest_saving_then_lower_offer_id() -> None:
    def priced(offer_id: str, price: str) -> OfferEvaluation:
        offer = dataclasses.replace(OF_1001, offer_id=OfferId(offer_id), price=usd(price))
        return evaluate(QX7T2A, offer)

    of_1002 = priced("OF-1002", "290.00")
    of_1001 = priced("OF-1001", "290.00")
    of_1003 = priced("OF-1003", "260.00")
    assert of_1001.nominal_saving == usd("90.00")
    assert of_1003.nominal_saving == usd("120.00")

    with_best = decide(terms_of(QX7T2A), [of_1002, of_1001, of_1003])
    without_best = decide(terms_of(QX7T2A), [of_1002, of_1001])

    assert isinstance(with_best, Rebook)
    assert with_best.offer_id == "OF-1003"
    assert isinstance(without_best, Rebook)
    assert without_best.offer_id == "OF-1001"


def test_offer_change_fee_never_enters_nominal_saving() -> None:
    savings = {
        evaluate(
            QX7T2A, dataclasses.replace(OF_1001, change_fee_per_passenger=usd(fee))
        ).nominal_saving
        for fee in ("0.00", "100.00")
    }

    assert savings == {usd("80.00")}


def test_offer_change_fee_in_other_currency_is_converted() -> None:
    offer = dataclasses.replace(OF_1001, change_fee_per_passenger=eur("100.00"))

    evaluation = evaluate(QX7T2A, offer, DEMO_RATES)

    assert result_of(evaluation, RuleName.FUTURE_CHANGE_FEE) is RuleOutcome.FAIL
    assert "offer 114.33 USD" in reason_of(evaluation, RuleName.FUTURE_CHANGE_FEE)
    fee_rates = [u.rate for u in evaluation.rates if u.use is RateUse.OFFER_CHANGE_FEE]
    assert [rate.direction for rate in fee_rates] == ["1 EUR = 1.1433 USD"]


def test_fee_without_rate_fails_future_fee_rule() -> None:
    offer = dataclasses.replace(OF_1001, change_fee_per_passenger=eur("100.00"))

    evaluation = evaluate(QX7T2A, offer)

    assert result_of(evaluation, RuleName.FUTURE_CHANGE_FEE) is RuleOutcome.FAIL
    reason = reason_of(evaluation, RuleName.FUTURE_CHANGE_FEE)
    assert "EUR" in reason
    assert "USD" in reason
    assert evaluation.nominal_saving == usd("80.00")


def test_float_trap_rejects_decimal_from_float() -> None:
    with pytest.raises(decimal.FloatOperation):
        Decimal(0.1)  # noqa: RUF032  # a float on purpose: proves the trap


def test_booking_fee_in_other_currency_is_converted_and_shown() -> None:
    booking = dataclasses.replace(QX7T2A, change_fee_per_passenger=eur("100.00"))

    terms = terms_of(booking, DEMO_RATES)
    recommendation = decide(terms, [evaluate(booking, OF_1001, DEMO_RATES)])

    assert terms.change_fee.money == usd("114.33")
    assert isinstance(recommendation, Rebook)
    assert recommendation.nominal_saving == usd("65.67")
    assert [(u.use, u.rate.direction) for u in recommendation.rates] == [
        (RateUse.BOOKING_FEE, "1 EUR = 1.1433 USD")
    ]


def test_booking_fee_without_rate_has_no_terms() -> None:
    booking = dataclasses.replace(QX7T2A, change_fee_per_passenger=eur("100.00"))

    assert booking_terms(booking, POLICY, NO_RATES) == NoRate(source=EUR, target=USD)


def test_minimum_conversion_is_listed_with_the_booking_rates() -> None:
    terms = terms_of(RT5K8B, DEMO_RATES)

    assert [(u.use, u.rate.direction) for u in terms.rates] == [
        (RateUse.MINIMUM_SAVING, "1 EUR = 1.1433 USD")
    ]


@pytest.mark.parametrize(
    ("offers", "reasoning"),
    [
        ((), "No offers on this route and date."),
        (
            (dataclasses.replace(OF_1001, price=usd("340.00")),),
            "No offer reaches the minimum. OF-1001 passes all seven rules,"
            " but its saving of 40.00 USD is below the minimum of 50.00 USD.",
        ),
        (
            (
                dataclasses.replace(OF_1001, cabin=Cabin.BASIC_ECONOMY, checked_bags=0),
                dataclasses.replace(OF_1001, offer_id=OfferId("OF-1002"), stops=1),
            ),
            "No offer passes every rule. OF-1001 fails: cabin, bags. OF-1002 fails: stops.",
        ),
    ],
)
def test_keep_reasoning_names_why_no_offer_qualifies(
    offers: tuple[Offer, ...], reasoning: str
) -> None:
    recommendation = decide(terms_of(QX7T2A), [evaluate(QX7T2A, offer) for offer in offers])

    assert isinstance(recommendation, Keep)
    assert recommendation.reasoning == reasoning


def test_saving_equal_to_minimum_rebooks() -> None:
    offer = dataclasses.replace(OF_1001, price=usd("330.00"))

    recommendation = decide(terms_of(QX7T2A), [evaluate(QX7T2A, offer)])

    assert isinstance(recommendation, Rebook)
    assert recommendation.nominal_saving == usd("50.00")
    assert recommendation.reasoning == (
        "Rebook to OF-1001. It passes all seven rules and saves 50.00 USD,"
        " which meets the minimum of 50.00 USD."
    )


@pytest.mark.parametrize(
    ("build", "error"),
    [
        (lambda: Currency(code="usd"), "three uppercase letters"),
        (lambda: Money.of("1_000", USD), "plain decimal text"),
        (lambda: Money.of("1e3", USD), "plain decimal text"),
        (lambda: dataclasses.replace(QX7T2A, passengers=0, total_paid=usd("0")), "at least 1"),
        (lambda: dataclasses.replace(QX7T2A, stops=-1), "stops must be zero or more"),
        (lambda: dataclasses.replace(OF_1001, seats_available=-1), "seats available"),
        (lambda: dataclasses.replace(OF_1001, price=usd("-1")), "price must not be negative"),
        (
            lambda: dataclasses.replace(QX7T2A, departure=datetime(2026, 8, 15, tzinfo=UTC)),
            "without a time zone",
        ),
        (
            lambda: dataclasses.replace(EUR_USD, rate=Decimal("0")),
            "positive Decimal",
        ),
        (lambda: dataclasses.replace(EUR_USD, quote=EUR), "two currencies"),
        (
            lambda: RuleResult(rule=RuleName.CABIN, outcome=RuleOutcome.PASS, reason=""),
            "needs a reason",
        ),
        (
            lambda: dataclasses.replace(evaluate(QX7T2A, OF_1001), rules=()),
            "every rule in order",
        ),
        (
            lambda: ReshopSnapshot(
                captured_at=datetime(2026, 7, 8, 9, tzinfo=timezone(timedelta(hours=5))),
                bookings=(),
                offers=(),
                data_issues=(),
            ),
            "in UTC",
        ),
    ],
)
def test_value_objects_refuse_bad_input(build: Callable[[], object], error: str) -> None:
    with pytest.raises(ValueError, match=error):
        build()


def test_counts_refuse_bool() -> None:
    with pytest.raises(TypeError, match="whole number"):
        dataclasses.replace(QX7T2A, passengers=True)


REPO_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SAMPLE_BOOKINGS = 5
SAMPLE_OFFERS = 6

type JsonObject = dict[str, object]


def copied_fixtures(tmp_path: Path) -> Path:
    folder = tmp_path / "fixtures"
    folder.mkdir(parents=True)
    for name in ("pnrs.json", "fares_feed.json"):
        shutil.copyfile(REPO_FIXTURES / name, folder / name)
    return folder


def edit_json(path: Path, change: Callable[[JsonObject], None]) -> None:
    document = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    change(document)
    path.write_text(json.dumps(document, default=exact_float), encoding="utf-8")


def exact_float(value: object) -> float:
    if not isinstance(value, Decimal):
        raise TypeError(f"cannot write {value!r} as JSON")
    number = float(value)
    if Decimal(repr(number)) != value:
        raise ValueError(f"{value} would lose digits as a JSON float; edit the text instead")
    return number


def copy_record(record: JsonObject) -> JsonObject:
    copied = json.loads(json.dumps(record, default=exact_float), parse_float=Decimal)
    assert isinstance(copied, dict)
    return copied


def nested(record: JsonObject, *keys: str) -> JsonObject:
    for key in keys:
        found = record[key]
        assert isinstance(found, dict)
        record = found
    return record


def records(document: JsonObject, key: str) -> list[JsonObject]:
    found = document[key]
    assert isinstance(found, list)
    return found


def first_booking(document: JsonObject) -> JsonObject:
    return records(document, "pnrs")[0]


def first_offer(document: JsonObject) -> JsonObject:
    return records(document, "offers")[0]


def snapshot_with(
    tmp_path: Path, file_name: str, change: Callable[[JsonObject], None]
) -> ReshopSnapshot:
    folder = copied_fixtures(tmp_path)
    edit_json(folder / file_name, change)
    return JsonFixtureSource(folder).read_snapshot()


def rejected_bookings(snapshot: ReshopSnapshot) -> list[RejectedBooking]:
    return [b for b in snapshot.bookings if isinstance(b, RejectedBooking)]


def issue_kinds(snapshot: ReshopSnapshot) -> list[tuple[DataIssueKind, str]]:
    return [(issue.kind, issue.record_id) for issue in snapshot.data_issues]


def test_fixture_money_is_read_as_exact_decimal(tmp_path: Path) -> None:
    folder = copied_fixtures(tmp_path)
    path = folder / "fares_feed.json"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace('"amount": 300.00', '"amount": 1234567.123456789', 1), encoding="utf-8"
    )

    offers = JsonFixtureSource(folder).read_snapshot().offers

    assert offers[0].price.amount == Decimal("1234567.123456789")
    assert str(offers[0].price.amount) == "1234567.123456789"


def test_malformed_booking_is_rejected_with_reason(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        first_booking(document)["passengers"] = "two"

    snapshot = snapshot_with(tmp_path, "pnrs.json", change)

    rejected = rejected_bookings(snapshot)
    assert [r.ref for r in rejected] == ["QX7T2A"]
    assert "passengers" in rejected[0].reason
    assert sum(isinstance(b, Booking) for b in snapshot.bookings) == SAMPLE_BOOKINGS - 1


def test_multi_segment_booking_is_rejected(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        itinerary = first_booking(document)["itinerary"]
        assert isinstance(itinerary, list)
        itinerary.append(itinerary[0])

    rejected = rejected_bookings(snapshot_with(tmp_path, "pnrs.json", change))

    assert [r.ref for r in rejected] == ["QX7T2A"]
    assert "2 segments" in rejected[0].reason


def test_bad_offer_is_listed_in_data_issues(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        first_offer(document)["price"] = "abc"

    snapshot = snapshot_with(tmp_path, "fares_feed.json", change)

    assert issue_kinds(snapshot) == [(DataIssueKind.OFFER_REJECTED, "OF-1001")]
    assert "OF-1001" not in {offer.offer_id for offer in snapshot.offers}


def test_duplicate_offer_ids_are_all_left_out(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        records(document, "offers")[1]["offerId"] = "OF-1001"

    snapshot = snapshot_with(tmp_path, "fares_feed.json", change)

    assert "OF-1001" not in {offer.offer_id for offer in snapshot.offers}
    assert len(snapshot.offers) == SAMPLE_OFFERS - 2
    assert issue_kinds(snapshot) == [
        (DataIssueKind.OFFER_DUPLICATE, "OF-1001"),
        (DataIssueKind.OFFER_DUPLICATE, "OF-1001"),
    ]


def test_duplicate_booking_keeps_first_record(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        copy = copy_record(first_booking(document))
        nested(copy, "ticket", "pricePerPassenger")["amount"] = 999
        records(document, "pnrs").append(copy)

    snapshot = snapshot_with(tmp_path, "pnrs.json", change)

    kept = [b for b in snapshot.bookings if isinstance(b, Booking) and b.ref == "QX7T2A"]
    assert [b.price_per_passenger for b in kept] == [usd("480.00")]
    assert issue_kinds(snapshot) == [(DataIssueKind.BOOKING_DUPLICATE, "QX7T2A")]


def test_unknown_field_rejects_that_record(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        first_booking(document)["notes"] = "window seat"

    rejected = rejected_bookings(snapshot_with(tmp_path, "pnrs.json", change))

    assert [r.ref for r in rejected] == ["QX7T2A"]
    assert "notes" in rejected[0].reason


def test_comment_key_is_ignored() -> None:
    snapshot = JsonFixtureSource(REPO_FIXTURES).read_snapshot()

    assert len(snapshot.bookings) == SAMPLE_BOOKINGS
    assert all(isinstance(b, Booking) for b in snapshot.bookings)
    assert len(snapshot.offers) == SAMPLE_OFFERS
    assert snapshot.data_issues == ()


def test_negative_stops_bags_or_seats_rejects_record(tmp_path: Path) -> None:
    cases: list[tuple[str, Callable[[JsonObject], None]]] = [
        ("stops", lambda d: first_offer(d).__setitem__("stops", -1)),
        ("bags", lambda d: first_offer(d).__setitem__("baggageIncludedPieces", -1)),
        ("seats", lambda d: first_offer(d).__setitem__("seatsAvailable", -1)),
    ]
    for name, change in cases:
        snapshot = snapshot_with(tmp_path / name, "fares_feed.json", change)

        assert issue_kinds(snapshot) == [(DataIssueKind.OFFER_REJECTED, "OF-1001")], name


def test_comment_inside_a_record_is_unknown_key(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        first_offer(document)["_comment"] = "a note"

    snapshot = snapshot_with(tmp_path, "fares_feed.json", change)

    assert issue_kinds(snapshot) == [(DataIssueKind.OFFER_REJECTED, "OF-1001")]


def test_missing_fixture_raises_json_fixture_error(tmp_path: Path) -> None:
    with pytest.raises(JsonFixtureError) as raised:
        JsonFixtureSource(tmp_path / "nowhere").read_snapshot()

    assert raised.value.problem is FileProblem.MISSING


def test_offer_with_route_date_unlike_its_departure_is_rejected(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        route = first_offer(document)["route"]
        assert isinstance(route, dict)
        route["departureDate"] = "2026-08-16"

    snapshot = snapshot_with(tmp_path, "fares_feed.json", change)

    assert issue_kinds(snapshot) == [(DataIssueKind.OFFER_REJECTED, "OF-1001")]


@pytest.mark.parametrize(
    ("file_name", "text", "fact"),
    [
        ("pnrs.json", "{not json", "Expecting property name"),
        ("pnrs.json", '{"_comment": "no bookings key"}', "pnrs: Field required"),
        ("fares_feed.json", '{"capturedAt": "2026-07-08T09:00:00", "offers": []}', "capturedAt"),
    ],
)
def test_malformed_fixture_file_raises_json_fixture_error(
    tmp_path: Path, file_name: str, text: str, fact: str
) -> None:
    folder = copied_fixtures(tmp_path)
    (folder / file_name).write_text(text, encoding="utf-8")

    with pytest.raises(JsonFixtureError, match=fact) as raised:
        JsonFixtureSource(folder).read_snapshot()

    assert raised.value.problem is FileProblem.MALFORMED


def test_unreadable_fixture_raises_json_fixture_error(tmp_path: Path) -> None:
    folder = copied_fixtures(tmp_path)
    (folder / "pnrs.json").unlink()
    (folder / "pnrs.json").mkdir()

    with pytest.raises(JsonFixtureError) as raised:
        JsonFixtureSource(folder).read_snapshot()

    assert raised.value.problem is FileProblem.UNREADABLE


def test_records_without_readable_id_are_listed_by_position(tmp_path: Path) -> None:
    folder = copied_fixtures(tmp_path)
    edit_json(folder / "pnrs.json", lambda d: first_booking(d).__setitem__("pnr", ""))
    edit_json(folder / "fares_feed.json", lambda d: first_offer(d).__delitem__("offerId"))

    snapshot = JsonFixtureSource(folder).read_snapshot()

    assert issue_kinds(snapshot) == [
        (DataIssueKind.BOOKING_REJECTED, "pnrs[0]"),
        (DataIssueKind.OFFER_REJECTED, "offers[0]"),
    ]


def test_departure_must_be_a_full_local_time(tmp_path: Path) -> None:
    def change(document: JsonObject) -> None:
        itinerary = first_booking(document)["itinerary"]
        assert isinstance(itinerary, list)
        itinerary[0]["departure"] = "2026-08-15"

    rejected = rejected_bookings(snapshot_with(tmp_path, "pnrs.json", change))

    assert [r.ref for r in rejected] == ["QX7T2A"]
    assert "is not a time like 2026-08-15T08:00:00" in rejected[0].reason


@pytest.mark.parametrize(
    ("file_name", "field", "text", "rejected_id"),
    [
        ("pnrs.json", "departure", "2026-8-15T8:0:0", "QX7T2A"),
        ("fares_feed.json", "departure", "2026-8-15T8:00:00", "OF-1001"),
        ("fares_feed.json", "departureDate", "2026-8-15", "OF-1001"),
    ],
)
def test_times_without_zero_padding_are_rejected(
    tmp_path: Path, file_name: str, field: str, text: str, rejected_id: str
) -> None:
    def change(document: JsonObject) -> None:
        if file_name == "pnrs.json":
            itinerary = first_booking(document)["itinerary"]
            assert isinstance(itinerary, list)
            itinerary[0][field] = text
        elif field == "departureDate":
            nested(first_offer(document), "route")[field] = text
        else:
            first_offer(document)[field] = text

    snapshot = snapshot_with(tmp_path, file_name, change)

    rejected_ids = [r.ref for r in rejected_bookings(snapshot)] + [
        issue.record_id for issue in snapshot.data_issues
    ]
    assert rejected_ids == [rejected_id]


def test_capture_time_without_zero_padding_is_malformed(tmp_path: Path) -> None:
    folder = copied_fixtures(tmp_path)
    edit_json(
        folder / "fares_feed.json", lambda d: d.__setitem__("capturedAt", "2026-07-08T9:00:00Z")
    )

    with pytest.raises(JsonFixtureError, match="capturedAt"):
        JsonFixtureSource(folder).read_snapshot()


REPO_CONFIG = REPO_FIXTURES.parent / "config"


def copied_config(tmp_path: Path) -> Path:
    folder = tmp_path / "config"
    shutil.copytree(REPO_CONFIG, folder)
    return folder


def replace_text(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_rate_file_rate_is_read_as_exact_text(tmp_path: Path) -> None:
    path = copied_config(tmp_path) / "exchange_rates.toml"
    replace_text(path, 'rate = "1.1433"', 'rate = "1.14330000000001"')

    rate = read_exchange_rates(path).find_rate(USD, EUR)

    assert isinstance(rate, ExchangeRate)
    assert rate.rate == Decimal("1.14330000000001")
    assert rate.direction == "1 EUR = 1.14330000000001 USD"


def test_missing_pair_returns_no_rate() -> None:
    rates = read_exchange_rates(REPO_CONFIG / "exchange_rates.toml")

    assert rates.find_rate(GBP, USD) == NoRate(source=GBP, target=USD)


def test_bad_policy_file_raises_toml_file_error(tmp_path: Path) -> None:
    path = copied_config(tmp_path) / "policy.toml"
    replace_text(path, 'amount = "50.00"', 'amount = "fifty"')

    with pytest.raises(TomlFileError) as raised:
        read_policy(path)

    assert raised.value.problem is FileProblem.MALFORMED
    assert raised.value.fact


def test_repo_config_holds_the_demo_rate_and_minimum() -> None:
    rate = read_exchange_rates(REPO_CONFIG / "exchange_rates.toml").find_rate(EUR, USD)

    assert rate == EUR_USD
    assert read_policy(REPO_CONFIG / "policy.toml") == POLICY


@pytest.mark.parametrize(
    ("reader", "file_name", "old", "new"),
    [
        (read_exchange_rates, "exchange_rates.toml", 'rate = "1.1433"', "rate = 1.1433"),
        (read_exchange_rates, "exchange_rates.toml", 'as_of = "2026-07-07"', 'as_of = "2026-7-7"'),
        (read_exchange_rates, "exchange_rates.toml", 'quote = "USD"', 'quote = "USD"\nnote = "x"'),
        (read_exchange_rates, "exchange_rates.toml", "[[rates]]", "[[rates]"),
        (
            read_exchange_rates,
            "exchange_rates.toml",
            'as_of = "2026-07-07"',
            'as_of = "2026-07-07"\n\n[[rates]]\nbase = "USD"\nquote = "EUR"\n'
            'rate = "0.87"\nas_of = "2026-07-07"',
        ),
        (read_policy, "policy.toml", 'currency = "USD"', 'currency = "usd"'),
        (read_policy, "policy.toml", 'currency = "USD"', 'currency = "USD"\nnote = "x"'),
        (read_policy, "policy.toml", 'amount = "50.00"', 'amount = "-50.00"'),
    ],
)
def test_bad_config_file_raises_toml_file_error(
    tmp_path: Path, reader: Callable[[Path], object], file_name: str, old: str, new: str
) -> None:
    path = copied_config(tmp_path) / file_name
    replace_text(path, old, new)

    with pytest.raises(TomlFileError) as raised:
        reader(path)

    assert raised.value.problem is FileProblem.MALFORMED


def test_missing_config_file_raises_toml_file_error(tmp_path: Path) -> None:
    with pytest.raises(TomlFileError) as raised:
        read_policy(tmp_path / "policy.toml")

    assert raised.value.problem is FileProblem.MISSING


class InMemorySource:
    def __init__(self, snapshot: ReshopSnapshot) -> None:
        self._snapshot = snapshot

    def read_snapshot(self) -> ReshopSnapshot:
        return self._snapshot


def sample() -> ReshopSnapshot:
    return JsonFixtureSource(REPO_FIXTURES).read_snapshot()


def sample_booking(ref: str) -> Booking:
    return next(b for b in sample().bookings if isinstance(b, Booking) and b.ref == ref)


def review(snapshot: ReshopSnapshot) -> ReviewReport:
    return review_snapshot(InMemorySource(snapshot), DEMO_RATES, POLICY)


def result_for(report: ReviewReport, ref: str) -> Recommendation:
    return next(result for result in report.results if result.ref == ref)


def with_bookings(*bookings: Booking | RejectedBooking) -> ReshopSnapshot:
    return dataclasses.replace(sample(), bookings=bookings)


def evaluation_for(result: Rebook | Keep, offer_id: str) -> OfferEvaluation:
    return next(e for e in result.evaluations if e.offer_id == offer_id)


def test_sample_data_matches_expected_results() -> None:
    report = review_snapshot(
        JsonFixtureSource(REPO_FIXTURES),
        read_exchange_rates(REPO_CONFIG / "exchange_rates.toml"),
        ReviewPolicy(minimum_saving=Money.of("50.00", USD)),
    )

    summary = [
        (
            result.ref,
            type(result).__name__,
            result.offer_id if isinstance(result, Rebook) else None,
            str(result.nominal_saving) if isinstance(result, Rebook) else None,
        )
        for result in report.results
    ]
    assert summary == [
        ("HB6W9E", "Keep", None, None),
        ("LM9P4C", "Keep", None, None),
        ("QX7T2A", "Rebook", "OF-1001", "80.00 USD"),
        ("RT5K8B", "Rebook", "OF-3001", "363.21 EUR"),
        ("ZC3N1D", "Keep", None, None),
    ]


def test_qx7t2a_rebooks_of_1001_for_80_usd() -> None:
    result = result_for(review(sample()), "QX7T2A")

    assert isinstance(result, Rebook)
    assert result.offer_id == "OF-1001"
    assert result.nominal_saving == Money(amount=Decimal("80.00"), currency=USD)


def test_rt5k8b_rebooks_of_3001_for_363_21_eur() -> None:
    result = result_for(review(sample()), "RT5K8B")

    assert isinstance(result, Rebook)
    assert result.offer_id == "OF-3001"
    assert result.nominal_saving == Money(amount=Decimal("363.21"), currency=EUR)
    assert result.minimum_saving == Money(amount=Decimal("43.73"), currency=EUR)
    assert [(u.use, u.rate.direction) for u in result.rates] == [
        (RateUse.MINIMUM_SAVING, "1 EUR = 1.1433 USD")
    ]


def test_lm9p4c_keeps_because_cabin_and_bags_fail() -> None:
    result = result_for(review(sample()), "LM9P4C")

    assert isinstance(result, Keep)
    assert result.reasoning.startswith("No offer passes every rule.")
    assert evaluation_for(result, "OF-2001").failed_rules == (RuleName.CABIN, RuleName.BAGS)


def test_zc3n1d_keeps_because_refundability_fails() -> None:
    result = result_for(review(sample()), "ZC3N1D")

    assert isinstance(result, Keep)
    assert result.reasoning.startswith("No offer passes every rule.")
    assert evaluation_for(result, "OF-4001").failed_rules == (RuleName.REFUNDABLE,)


def test_hb6w9e_keeps_because_no_offer_reaches_the_minimum() -> None:
    result = result_for(review(sample()), "HB6W9E")

    assert isinstance(result, Keep)
    assert result.reasoning.startswith("No offer reaches the minimum.")
    assert "OF-5001" in result.reasoning
    assert "-90.00 USD" in result.reasoning
    assert "50.00 USD" in result.reasoning


def test_no_offers_on_route_is_keep() -> None:
    snapshot = dataclasses.replace(
        sample(), offers=tuple(o for o in sample().offers if o.offer_id != "OF-1001")
    )

    result = result_for(review(snapshot), "QX7T2A")

    assert isinstance(result, Keep)
    assert result.evaluations == ()
    assert result.reasoning == "No offers on this route and date."


def test_departure_before_capture_is_invalid_data() -> None:
    early = dataclasses.replace(
        sample_booking("QX7T2A"),
        departure=datetime(2026, 7, 1, 10, 0),
        arrival=datetime(2026, 7, 1, 13, 0),
    )
    on_capture = dataclasses.replace(
        sample_booking("LM9P4C"),
        departure=datetime(2026, 7, 8, 9, 0),
        arrival=datetime(2026, 7, 8, 12, 0),
    )

    report = review(with_bookings(early, on_capture))

    assert result_for(report, "QX7T2A") == Invalid(
        ref=BookingRef("QX7T2A"), reason="departs before the capture time"
    )
    assert not isinstance(result_for(report, "LM9P4C"), Invalid)


def test_missing_rate_for_minimum_is_invalid_data() -> None:
    booking = dataclasses.replace(
        sample_booking("QX7T2A"),
        price_per_passenger=Money.of("480.00", GBP),
        total_paid=Money.of("480.00", GBP),
        change_fee_per_passenger=Money.of("100.00", GBP),
    )

    result = result_for(review(with_bookings(booking)), "QX7T2A")

    assert result == Invalid(ref=BookingRef("QX7T2A"), reason="no exchange rate from USD to GBP")


def test_missing_pair_is_invalid_data_not_crash() -> None:
    booking = dataclasses.replace(
        sample_booking("QX7T2A"), change_fee_per_passenger=Money.of("100", Currency(code="JPY"))
    )

    report = review(with_bookings(booking, sample_booking("LM9P4C")))

    assert result_for(report, "QX7T2A") == Invalid(
        ref=BookingRef("QX7T2A"), reason="no exchange rate from JPY to USD"
    )
    assert isinstance(result_for(report, "LM9P4C"), Keep)


def test_invalid_booking_does_not_stop_other_bookings() -> None:
    rejected = RejectedBooking(ref=BookingRef("QX7T2A"), reason="passengers: bad")
    others = tuple(b for b in sample().bookings if isinstance(b, Booking) and b.ref != "QX7T2A")

    report = review(with_bookings(rejected, *others))

    assert [(r.ref, type(r).__name__) for r in report.results] == [
        ("HB6W9E", "Keep"),
        ("LM9P4C", "Keep"),
        ("QX7T2A", "Invalid"),
        ("RT5K8B", "Rebook"),
        ("ZC3N1D", "Keep"),
    ]
    assert result_for(report, "QX7T2A") == Invalid(
        ref=BookingRef("QX7T2A"), reason="passengers: bad"
    )


def test_empty_snapshot_gives_empty_results() -> None:
    assert review(with_bookings()).results == ()


def test_offer_in_lower_cabin_is_not_chosen_even_if_cheapest() -> None:
    cheap_basic = dataclasses.replace(
        OF_1001, offer_id=OfferId("OF-1009"), cabin=Cabin.BASIC_ECONOMY, price=usd("100.00")
    )
    snapshot = dataclasses.replace(
        with_bookings(sample_booking("QX7T2A")), offers=(cheap_basic, OF_1001)
    )

    result = result_for(review(snapshot), "QX7T2A")

    assert isinstance(result, Rebook)
    assert result.offer_id == "OF-1001"


def test_results_are_sorted_by_pnr() -> None:
    report = review(with_bookings(*reversed(sample().bookings)))

    assert [result.ref for result in report.results] == [
        "HB6W9E",
        "LM9P4C",
        "QX7T2A",
        "RT5K8B",
        "ZC3N1D",
    ]
