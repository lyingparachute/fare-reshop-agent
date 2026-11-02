import dataclasses
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from fare_reshop_agent.reshopping.domain.evaluation import (
    OfferEvaluation,
    RuleName,
    RuleOutcome,
    RuleResult,
    evaluate_offer,
)
from fare_reshop_agent.reshopping.domain.exchange_rate import Conversion, NoRate, RateUse
from fare_reshop_agent.reshopping.domain.money import Currency, Money
from fare_reshop_agent.reshopping.domain.port.exchange_rates import ExchangeRates
from fare_reshop_agent.reshopping.domain.port.reshop_source import ReshopSnapshot
from fare_reshop_agent.reshopping.domain.recommendation import Keep, Rebook, decide
from fare_reshop_agent.reshopping.domain.terms import BookingTerms, booking_terms, convert_minimum
from fare_reshop_agent.reshopping.domain.trip import Booking, Cabin, Offer, OfferId

from sample_data import (
    DEMO_RATES,
    EUR,
    EUR_USD,
    NO_RATES,
    OF_1001,
    OF_3001,
    POLICY,
    QX7T2A,
    RT5K8B,
    USD,
    all_pass,
    eur,
    result_of,
    usd,
)


def reason_of(evaluation: OfferEvaluation, rule: RuleName) -> str:
    return next(result.reason for result in evaluation.rules if result.rule is rule)


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
