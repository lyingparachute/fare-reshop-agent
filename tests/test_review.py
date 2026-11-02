import dataclasses
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from fare_reshop_agent.reshopping.domain.evaluation import OfferEvaluation, RuleName, RuleOutcome
from fare_reshop_agent.reshopping.domain.exchange_rate import RateUse
from fare_reshop_agent.reshopping.domain.money import Currency, Money
from fare_reshop_agent.reshopping.domain.port.reshop_source import RejectedBooking, ReshopSnapshot
from fare_reshop_agent.reshopping.domain.recommendation import Invalid, Keep, Rebook
from fare_reshop_agent.reshopping.domain.terms import ReviewPolicy
from fare_reshop_agent.reshopping.domain.trip import Booking, BookingRef, Cabin, OfferId
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import JsonFixtureSource
from fare_reshop_agent.reshopping.infrastructure.toml.readers import read_exchange_rates
from fare_reshop_agent.reshopping.orchestration.agent_review import AgentOutcome
from fare_reshop_agent.reshopping.orchestration.review import ReviewReport, review_snapshot

from sample_data import (
    DEMO_RATES,
    EUR,
    GBP,
    OF_1001,
    POLICY,
    REPO_CONFIG,
    REPO_FIXTURES,
    USD,
    InMemorySource,
    all_pass,
    result_of,
    sample,
    sample_booking,
    usd,
    with_bookings,
)


def review(snapshot: ReshopSnapshot) -> ReviewReport:
    return review_snapshot(InMemorySource(snapshot), DEMO_RATES, POLICY)


def outcomes(report: ReviewReport) -> list[AgentOutcome]:
    return [row.outcome for row in report.results]


def result_for(report: ReviewReport, ref: str) -> AgentOutcome:
    return next(result for result in outcomes(report) if result.ref == ref)


def evaluation_for(result: Rebook | Keep, offer_id: str) -> OfferEvaluation:
    return next(e for e in result.evaluations if e.offer_id == offer_id)


def review_folder(folder: Path) -> ReviewReport:
    return review_snapshot(
        JsonFixtureSource(folder),
        read_exchange_rates(REPO_CONFIG / "exchange_rates.toml"),
        ReviewPolicy(minimum_saving=Money.of("50.00", USD)),
    )


def test_sample_data_matches_expected_results() -> None:
    report = review_folder(REPO_FIXTURES)

    summary = [
        (
            result.ref,
            type(result).__name__,
            result.offer_id if isinstance(result, Rebook) else None,
            str(result.nominal_saving) if isinstance(result, Rebook) else None,
        )
        for result in outcomes(report)
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

    assert [(r.ref, type(r).__name__) for r in outcomes(report)] == [
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

    assert [result.ref for result in outcomes(report)] == [
        "HB6W9E",
        "LM9P4C",
        "QX7T2A",
        "RT5K8B",
        "ZC3N1D",
    ]


def review_scenarios() -> ReviewReport:
    return review_folder(REPO_FIXTURES / "scenarios")


def test_scenario_a_picks_highest_saving_with_schedule_flag() -> None:
    result = result_for(review_scenarios(), "MK3V7P")

    assert isinstance(result, Rebook)
    assert result.offer_id == "OF-6101"
    assert result.nominal_saving == Money(amount=Decimal("170.00"), currency=USD)
    assert result.approval_flags == ("schedule_change",)
    runner_up = evaluation_for(result, "OF-6102")
    assert runner_up.failed_rules == ()
    assert isinstance(runner_up.nominal_saving, Money)
    assert runner_up.nominal_saving == Money(amount=Decimal("80.00"), currency=USD)
    assert runner_up.nominal_saving >= result.minimum_saving
    assert runner_up.approval_flags == ()


def test_scenario_b_carrier_change_is_flag_not_failure() -> None:
    result = result_for(review_scenarios(), "RD9Q2X")

    assert isinstance(result, Rebook)
    assert result.offer_id == "OF-6201"
    assert result.nominal_saving == Money(amount=Decimal("75.00"), currency=USD)
    assert result.approval_flags == ("carrier_change",)
    assert all_pass(evaluation_for(result, "OF-6201"))


def test_scenario_c_failed_refundability_is_not_chosen() -> None:
    result = result_for(review_scenarios(), "WJ6T4N")

    assert isinstance(result, Rebook)
    assert result.offer_id == "OF-6302"
    assert result.nominal_saving == Money(amount=Decimal("60.00"), currency=USD)
    cheaper = evaluation_for(result, "OF-6301")
    assert cheaper.failed_rules == (RuleName.REFUNDABLE,)
    assert cheaper.nominal_saving == Money(amount=Decimal("210.00"), currency=USD)


def test_scenario_d_shared_flight_recommends_each_booking() -> None:
    report = review_scenarios()

    for ref in ("CH8L5F", "FD2N8Z"):
        result = result_for(report, ref)
        assert isinstance(result, Rebook), ref
        assert result.offer_id == "OF-6401"
        assert result.nominal_saving == Money(amount=Decimal("80.00"), currency=USD)
        assert result_of(evaluation_for(result, "OF-6401"), RuleName.SEATS) is RuleOutcome.PASS


def test_scenario_e_seats_failure_keeps() -> None:
    result = result_for(review_scenarios(), "YU6EG1")

    assert isinstance(result, Keep)
    assert result.reasoning.startswith("No offer passes every rule.")
    evaluation = evaluation_for(result, "OF-6501")
    assert evaluation.failed_rules == (RuleName.SEATS,)
    assert evaluation.nominal_saving == Money(amount=Decimal("60.00"), currency=USD)


def test_scenario_expected_results_table_matches() -> None:
    summary = [
        (result.ref, result.status.value, result.offer_id if isinstance(result, Rebook) else None)
        for result in outcomes(review_scenarios())
    ]

    assert summary == [
        ("CH8L5F", "REBOOK", "OF-6401"),
        ("FD2N8Z", "REBOOK", "OF-6401"),
        ("MK3V7P", "REBOOK", "OF-6101"),
        ("RD9Q2X", "REBOOK", "OF-6201"),
        ("WJ6T4N", "REBOOK", "OF-6302"),
        ("YU6EG1", "KEEP", None),
    ]
