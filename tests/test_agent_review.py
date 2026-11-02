import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from decimal import Decimal

import httpx2
import pytest
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)
from openai.types.responses import Response

from fare_reshop_agent.reshopping.cli.json_output import render_json
from fare_reshop_agent.reshopping.cli.table_output import render_table
from fare_reshop_agent.reshopping.composition.color import ColorSetting
from fare_reshop_agent.reshopping.domain.money import Money
from fare_reshop_agent.reshopping.domain.port.reshop_source import ReshopSnapshot
from fare_reshop_agent.reshopping.domain.terms import BookingTerms, ReviewPolicy, booking_terms
from fare_reshop_agent.reshopping.domain.trip import BookingRef, Cabin, Offer, OfferId
from fare_reshop_agent.reshopping.infrastructure.json_fixtures.source import JsonFixtureSource
from fare_reshop_agent.reshopping.infrastructure.openai.provider_errors import (
    ProviderAuthenticationError,
    ProviderModelNotFoundError,
    ProviderPermissionError,
)
from fare_reshop_agent.reshopping.infrastructure.openai.responses_model import (
    OpenAIResponsesModel,
)
from fare_reshop_agent.reshopping.infrastructure.toml.readers import read_exchange_rates
from fare_reshop_agent.reshopping.orchestration.agent_model import (
    NO_USAGE,
    FinalText,
    ModelReply,
    Prompt,
    ProviderErrorCode,
    ProviderFailed,
    Refusal,
    ToolCallItem,
    ToolCallRequest,
    ToolCalls,
    ToolResultItem,
    ToolSpec,
    Transcript,
    Usage,
    UserMessage,
)
from fare_reshop_agent.reshopping.orchestration.booking_loop import (
    Answered,
    IncompleteReason,
    LoopRun,
    Stopped,
    run_booking_loop,
)
from fare_reshop_agent.reshopping.orchestration.booking_tools import BookingTools
from fare_reshop_agent.reshopping.orchestration.canonical_json import JsonValue, canonical_json
from fare_reshop_agent.reshopping.orchestration.final_answer import final_answer_schema
from fare_reshop_agent.reshopping.orchestration.review import (
    ReviewAgent,
    ReviewMode,
    ReviewReport,
    review_snapshot,
    review_with_model,
)

from openai_stub import STUB_SETTINGS, StubResponsesClient, stub_message, stub_response
from sample_data import (
    DEMO_RATES,
    GBP,
    OF_1001,
    POLICY,
    PROMPT_FILE,
    QX7T2A,
    REPO_CONFIG,
    REPO_FIXTURES,
    USD,
    InMemorySource,
    sample,
    sample_booking,
    usd,
    with_bookings,
)
from scripted_model import TURN_USAGE, ScriptedModel, call, calls, final, keep, rebook


def test_canonical_json_sorts_keys_and_rejects_float() -> None:
    value: JsonValue = {
        "b": [1, Decimal("1.50"), Decimal("1E+2"), None, True],
        "a": {"z": 'é "q"', "y": False},
    }

    assert canonical_json(value) == '{"a":{"y":false,"z":"é \\"q\\""},"b":[1,1.50,100,null,true]}'
    with pytest.raises(TypeError, match="float"):
        canonical_json(json.loads('{"price": 1.5}'))


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_canonical_json_rejects_non_finite_decimal(value: Decimal) -> None:
    with pytest.raises(ValueError, match="decimal"):
        canonical_json({"amount": value})


def test_canonical_json_rejects_text_that_is_not_utf8() -> None:
    with pytest.raises(ValueError, match="utf-8"):
        canonical_json(json.loads('{"offer_id": "\\ud800"}'))


def test_prompt_version_is_digest_of_prompt_bytes() -> None:
    data = PROMPT_FILE.read_bytes()

    prompt = Prompt(data=data)

    assert prompt.version == hashlib.sha256(data).hexdigest()
    assert prompt.text == data.decode("utf-8")


def test_tool_calls_reply_needs_a_call() -> None:
    with pytest.raises(ValueError, match="at least one call"):
        ToolCalls(calls=(), text=None, usage=NO_USAGE)


def qx7t2a_tools() -> BookingTools:
    terms = booking_terms(QX7T2A, POLICY, DEMO_RATES)
    assert isinstance(terms, BookingTerms)
    off_route = dataclasses.replace(OF_1001, offer_id=OfferId("OF-0001"), origin="LHR")
    cheaper = dataclasses.replace(OF_1001, offer_id=OfferId("OF-1002"), price=usd("290.00"))
    return BookingTools.for_booking(terms, (cheaper, off_route, OF_1001), DEMO_RATES)


def run_qx7t2a(*replies: ModelReply) -> tuple[LoopRun, ScriptedModel]:
    model = ScriptedModel({"QX7T2A": replies})
    return run_booking_loop(qx7t2a_tools(), model, Prompt(data=b"Review the booking.")), model


def test_first_message_names_the_booking() -> None:
    _, model = run_qx7t2a(rebook("OF-1001"))

    first = model.shown[0].items[0]

    assert isinstance(first, UserMessage)
    assert "QX7T2A" in first.text


def test_call_ids_follow_turn_and_position() -> None:
    _, model = run_qx7t2a(
        calls(call("get_booking"), call("search_offers")),
        calls(call("check_offer", '{"offer_id": "OF-1001"}')),
        rebook("OF-1001"),
    )

    call_ids = [item.call_id for item in model.shown[2].items if isinstance(item, ToolCallItem)]

    assert call_ids == ["call_1_1", "call_1_2", "call_2_1"]


def test_several_calls_in_one_reply_run_in_order_as_one_turn() -> None:
    run, model = run_qx7t2a(calls(call("get_booking"), call("search_offers")), rebook("OF-1001"))

    second = model.shown[1]
    results = [json.loads(i.result) for i in second.items if isinstance(i, ToolResultItem)]

    assert [shown.turn for shown in model.shown] == [1, 2]
    assert [result["ok"] for result in results] == [True, True]
    assert results[0]["data"]["pnr"] == "QX7T2A"
    assert [offer["offer_id"] for offer in results[1]["data"]["offers"]] == ["OF-1001", "OF-1002"]
    assert run.trace.turns == len(model.shown)
    assert run.trace.usage == TURN_USAGE + TURN_USAGE
    assert isinstance(run.end, Answered)


def test_tool_call_with_final_text_is_bad_final_answer() -> None:
    run, model = run_qx7t2a(calls(call("get_booking"), text="Rebook on OF-1001."))

    assert run.end == Stopped(reason=IncompleteReason.BAD_FINAL_ANSWER)
    assert run.trace.tool_calls == ()
    assert len(model.shown) == 1


def test_non_finite_confidence_is_bad_final_answer() -> None:
    for constant in ("NaN", "Infinity", "-Infinity"):
        text = (
            '{"decision": "rebook", "offer_id": "OF-1001", "reasoning": "Cheaper.",'
            f' "confidence": {constant}}}'
        )

        run, _ = run_qx7t2a(FinalText(text=text, usage=TURN_USAGE))

        assert run.end == Stopped(reason=IncompleteReason.BAD_FINAL_ANSWER), constant


def test_check_offer_reports_saving_minimum_and_eligibility() -> None:
    _, model = run_qx7t2a(calls(call("check_offer", '{"offer_id": "OF-1001"}')), rebook("OF-1001"))

    result = next(i for i in model.shown[1].items if isinstance(i, ToolResultItem))
    data = json.loads(result.result)["data"]

    assert data["nominal_saving"] == {"amount": "80.00", "currency": "USD"}
    assert data["minimum_saving"] == {"amount": "50.00", "currency": "USD"}
    assert [rule["result"] for rule in data["rules"]] == ["PASS"] * 7
    assert data["eligible"] is True


def test_deeply_nested_final_answer_is_bad_final_answer() -> None:
    depth = 900
    balanced = '{"a":' * depth + "1" + "}" * depth
    for text in ("[" * 100_000, balanced):
        run, _ = run_qx7t2a(FinalText(text=text, usage=TURN_USAGE))

        assert run.end == Stopped(reason=IncompleteReason.BAD_FINAL_ANSWER)


def test_arguments_that_are_not_utf8_stay_raw_in_trace() -> None:
    raw = '{"x": "\\ud800"}'

    run, _ = run_qx7t2a(calls(call("get_booking", raw)), rebook("OF-1001"))

    assert [traced.arguments for traced in run.trace.tool_calls] == [raw]


TEST_PROMPT = Prompt(data=b"Review the booking.")
OF_1002_CHEAPER = dataclasses.replace(
    OF_1001, offer_id=OfferId("OF-1002"), price=usd("290.00"), carrier="UA"
)
OF_1009_BASIC = dataclasses.replace(
    OF_1001, offer_id=OfferId("OF-1009"), cabin=Cabin.BASIC_ECONOMY, price=usd("100.00")
)
MODEL_RESULT_KEYS = [
    "pnr",
    "status",
    "rebook",
    "decided_by",
    "incomplete_reason",
    "offer_id",
    "nominal_saving",
    "approval_flags",
    "best_offer_id",
    "confidence",
    "confidence_note",
    "reasoning",
    "minimum_saving",
    "exchange_rates",
    "invalid_reason",
    "evaluations",
    "trace",
]


def qx7t2a_snapshot(*extra_offers: Offer) -> ReshopSnapshot:
    snapshot = with_bookings(sample_booking("QX7T2A"))
    return dataclasses.replace(snapshot, offers=(OF_1001, *extra_offers))


def review_by_model(
    snapshot: ReshopSnapshot, scripts: Mapping[str, Sequence[ModelReply]]
) -> tuple[ReviewReport, ScriptedModel]:
    model = ScriptedModel(scripts)
    agent = ReviewAgent(model=model, prompt=TEST_PROMPT, mode=ReviewMode.OPENAI)
    return review_with_model(InMemorySource(snapshot), DEMO_RATES, POLICY, agent), model


def json_result(report: ReviewReport, ref: str) -> dict[str, object]:
    results = json.loads(render_json(report))["results"]
    return next(result for result in results if result["pnr"] == ref)


def text_of(result: dict[str, object], key: str) -> str:
    value = result[key]
    assert isinstance(value, str)
    return value


def qx7t2a_result(*replies: ModelReply, extra_offers: Sequence[Offer] = ()) -> dict[str, object]:
    report, _ = review_by_model(qx7t2a_snapshot(*extra_offers), {"QX7T2A": replies})
    return json_result(report, "QX7T2A")


def test_model_rebook_on_eligible_offer_is_accepted() -> None:
    result = qx7t2a_result(rebook("OF-1001", "Same flight, lower fare."))

    assert result["status"] == "REBOOK"
    assert result["decided_by"] == "model"
    assert result["offer_id"] == "OF-1001"
    assert result["nominal_saving"] == {"amount": "80.00", "currency": "USD"}
    assert result["best_offer_id"] is None
    assert result["reasoning"] == "Model text: Same flight, lower fare."


def test_model_keep_with_eligible_offer_needs_review() -> None:
    result = qx7t2a_result(keep("A change is not worth it."))

    assert result["status"] == "NEEDS_REVIEW"
    assert result["decided_by"] == "safety_check"
    assert result["offer_id"] is None
    assert result["best_offer_id"] is None
    assert result["reasoning"] == (
        "Model and rules disagree. Rules view: OF-1001 passes every rule and saves 80.00 USD,"
        " which meets the minimum of 50.00 USD. Model text: A change is not worth it."
    )


def test_model_choice_failing_a_rule_needs_review() -> None:
    result = qx7t2a_result(rebook("OF-1009"), extra_offers=(OF_1009_BASIC,))

    assert result["status"] == "NEEDS_REVIEW"
    assert result["decided_by"] == "safety_check"
    assert result["offer_id"] == "OF-1009"
    assert result["nominal_saving"] == {"amount": "280.00", "currency": "USD"}
    assert text_of(result, "reasoning").startswith(
        "Safety check: rule cabin failed, offer cabin BASIC_ECONOMY is below the booked cabin"
    )


def test_unknown_offer_in_final_answer_needs_review() -> None:
    result = qx7t2a_result(rebook("OF-9999"))

    assert result["status"] == "NEEDS_REVIEW"
    assert result["offer_id"] == "OF-9999"
    assert result["nominal_saving"] is None
    assert result["approval_flags"] == []
    assert text_of(result, "reasoning").startswith(
        "Safety check: offer OF-9999 is not on this route and date."
    )


def test_best_offer_id_names_highest_saving() -> None:
    result = qx7t2a_result(rebook("OF-1001"), extra_offers=(OF_1002_CHEAPER,))

    assert result["status"] == "REBOOK"
    assert result["offer_id"] == "OF-1001"
    assert result["best_offer_id"] == "OF-1002"


def test_failed_choice_needs_review_names_best_offer() -> None:
    result = qx7t2a_result(rebook("OF-1009"), extra_offers=(OF_1009_BASIC, OF_1002_CHEAPER))

    assert result["best_offer_id"] is None
    assert "Rules view: OF-1002 passes every rule and saves 90.00 USD" in text_of(
        result, "reasoning"
    )
    assert text_of(result, "reasoning").endswith("Model text: Cheaper fare, same flight.")


def test_booking_without_eligible_offer_makes_no_model_call() -> None:
    report, model = review_by_model(
        sample(), {"QX7T2A": [rebook("OF-1001")], "RT5K8B": [rebook("OF-3001")]}
    )

    assert {transcript.booking_ref for transcript in model.shown} == {"QX7T2A", "RT5K8B"}
    hb6w9e = json_result(report, "HB6W9E")
    assert hb6w9e["status"] == "KEEP"
    assert hb6w9e["trace"] == {
        "prompt_version": TEST_PROMPT.version,
        "turns": 0,
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "tool_calls": [],
        "provider_error_code": None,
    }


def test_confidence_is_labeled_model_estimate() -> None:
    report, _ = review_by_model(
        sample(), {"QX7T2A": [rebook("OF-1001")], "RT5K8B": [rebook("OF-3001")]}
    )

    model_rebook = json_result(report, "QX7T2A")
    rules_keep = json_result(report, "HB6W9E")
    assert model_rebook["confidence"] == "0.82"
    assert model_rebook["confidence_note"] == "model estimate, not calibrated"
    assert rules_keep["confidence"] is None
    assert "confidence_note" not in rules_keep


def test_trace_has_prompt_version_and_usage() -> None:
    result = qx7t2a_result(
        calls(call("check_offer", '{ "offer_id" : "OF-1001" }')), rebook("OF-1001")
    )

    assert result["trace"] == {
        "prompt_version": hashlib.sha256(b"Review the booking.").hexdigest(),
        "turns": 2,
        "usage": {"input_tokens": 200, "output_tokens": 40},
        "tool_calls": [{"name": "check_offer", "arguments": '{"offer_id":"OF-1001"}', "ok": True}],
        "provider_error_code": None,
    }


def test_model_rows_have_fixed_key_order() -> None:
    result = qx7t2a_result(rebook("OF-1001"))

    assert list(result) == MODEL_RESULT_KEYS


def test_table_shows_flags_in_model_modes_only() -> None:
    snapshot = qx7t2a_snapshot(OF_1002_CHEAPER)
    model_report, _ = review_by_model(snapshot, {"QX7T2A": [rebook("OF-1002")]})
    rules_report = review_snapshot(InMemorySource(snapshot), DEMO_RATES, POLICY)

    model_lines = render_table(model_report, ColorSetting.OFF).splitlines()
    rules_lines = render_table(rules_report, ColorSetting.OFF).splitlines()

    assert model_lines[0].split() == ["PNR", "STATUS", "OFFER", "SAVING", "FLAGS", "REASON"]
    assert model_lines[1].split()[:6] == [
        "QX7T2A",
        "REBOOK",
        "OF-1002",
        "90.00",
        "USD",
        "carrier_change",
    ]
    assert rules_lines[0].split() == ["PNR", "STATUS", "OFFER", "SAVING", "REASON"]


def test_model_choice_below_minimum_needs_review() -> None:
    small_saving = dataclasses.replace(OF_1001, offer_id=OfferId("OF-1003"), price=usd("340.00"))

    result = qx7t2a_result(rebook("OF-1003"), extra_offers=(small_saving,))

    assert result["status"] == "NEEDS_REVIEW"
    assert result["nominal_saving"] == {"amount": "40.00", "currency": "USD"}
    assert text_of(result, "reasoning").startswith(
        "Safety check: nominal saving is below the minimum saving. Rules view: OF-1001"
    )


def test_model_choice_without_exchange_rate_needs_review() -> None:
    in_pounds = dataclasses.replace(
        OF_1001,
        offer_id=OfferId("OF-1004"),
        price=Money.of("100.00", GBP),
        change_fee_per_passenger=Money.of("50.00", GBP),
    )

    result = qx7t2a_result(rebook("OF-1004"), extra_offers=(in_pounds,))

    assert result["status"] == "NEEDS_REVIEW"
    assert result["nominal_saving"] is None
    assert text_of(result, "reasoning").startswith(
        "Safety check: rule future_change_fee failed, no exchange rate from GBP to USD"
        " for the offer's price."
    )


def tool_results(transcript: Transcript) -> list[dict[str, object]]:
    return [json.loads(i.result) for i in transcript.items if isinstance(i, ToolResultItem)]


def test_bad_tool_arguments_return_hint() -> None:
    run, model = run_qx7t2a(
        calls(call("check_offer", '{"offer_id": "OF-1001", "extra": 1}')), rebook("OF-1001")
    )

    assert tool_results(model.shown[1]) == [
        {
            "ok": False,
            "error": {
                "code": "bad_arguments",
                "message": "Arguments for check_offer are not valid.",
                "hint": (
                    "Send a JSON object with exactly the keys in the tool's spec,"
                    " each of the right type."
                ),
            },
        }
    ]
    assert [traced.ok for traced in run.trace.tool_calls] == [False]
    assert isinstance(run.end, Answered)


def test_unknown_offer_id_returns_hint() -> None:
    _, model = run_qx7t2a(calls(call("check_offer", '{"offer_id": "OF-9999"}')), rebook("OF-1001"))

    assert tool_results(model.shown[1]) == [
        {
            "ok": False,
            "error": {
                "code": "unknown_offer",
                "message": "Offer OF-9999 is not on this booking's route and date.",
                "hint": "Pick an offer_id from search_offers.",
            },
        }
    ]


def test_unknown_tool_name_returns_hint() -> None:
    run, model = run_qx7t2a(calls(call("book_flight")), rebook("OF-1001"))

    assert tool_results(model.shown[1]) == [
        {
            "ok": False,
            "error": {
                "code": "unknown_tool",
                "message": "There is no tool named book_flight.",
                "hint": "Use one of: get_booking, search_offers, check_offer.",
            },
        }
    ]
    assert isinstance(run.end, Answered)


def test_tool_results_are_sorted_and_stable() -> None:
    script = (
        calls(call("get_booking"), call("search_offers")),
        calls(call("check_offer", '{"offer_id": "OF-1002"}')),
        rebook("OF-1001"),
    )

    _, first = run_qx7t2a(*script)
    _, second = run_qx7t2a(*script)

    assert first.shown == second.shown
    offers = tool_results(first.shown[1])[1]
    assert isinstance(offers, dict)
    assert offers["data"] == {
        "offers": [
            offer_data("OF-1001", "300.00", "AA"),
            offer_data("OF-1002", "290.00", "AA"),
        ]
    }


def offer_data(offer_id: str, price: str, carrier: str) -> dict[str, object]:
    return {
        "offer_id": offer_id,
        "origin": "JFK",
        "destination": "LAX",
        "departure_date": "2026-08-15",
        "departure": "2026-08-15T08:00:00",
        "carrier": carrier,
        "flight_number": "AA118",
        "cabin": "ECONOMY",
        "refundable": False,
        "baggage_pieces": 1,
        "stops": 0,
        "seats_available": 5,
        "price_per_passenger": {"amount": price, "currency": "USD"},
        "change_fee_per_passenger": {"amount": "100.00", "currency": "USD"},
    }


@pytest.mark.parametrize("arguments", ['{"offer_id": 7}', "not json", "{}", '["OF-1001"]'])
def test_check_offer_arguments_of_wrong_shape_are_bad_arguments(arguments: str) -> None:
    _, model = run_qx7t2a(calls(call("check_offer", arguments)), rebook("OF-1001"))

    error = tool_results(model.shown[1])[0]["error"]

    assert isinstance(error, dict)
    assert error["code"] == "bad_arguments"


@pytest.mark.parametrize("number", ["1e99999999999999999999", "1e999999999", "1" * 40])
def test_out_of_range_numbers_end_one_call_or_answer(number: str) -> None:
    arguments = f'{{"offer_id": "OF-1001", "x": {number}}}'
    answer = (
        '{"decision": "rebook", "offer_id": "OF-1001", "reasoning": "Cheaper.",'
        f' "confidence": {number}}}'
    )

    tool_run, model = run_qx7t2a(calls(call("check_offer", arguments)), rebook("OF-1001"))
    answer_run, _ = run_qx7t2a(FinalText(text=answer, usage=TURN_USAGE))

    error = tool_results(model.shown[1])[0]["error"]
    assert isinstance(error, dict)
    assert error["code"] == "bad_arguments"
    assert isinstance(tool_run.end, Answered)
    assert answer_run.end == Stopped(reason=IncompleteReason.BAD_FINAL_ANSWER)


def incomplete(*replies: ModelReply) -> tuple[dict[str, object], ScriptedModel]:
    report, model = review_by_model(qx7t2a_snapshot(), {"QX7T2A": replies})
    result = json_result(report, "QX7T2A")
    assert result["status"] == "INCOMPLETE_ANALYSIS"
    assert result["decided_by"] is None
    return result, model


def traced_names(result: dict[str, object]) -> list[str]:
    trace = result["trace"]
    assert isinstance(trace, dict)
    return [traced["name"] for traced in trace["tool_calls"]]


def test_turn_cap_ends_incomplete() -> None:
    names = ["get_booking", "search_offers"] * 5

    result, model = incomplete(*(calls(call(name)) for name in names))

    assert result["incomplete_reason"] == "turn_cap"
    assert [shown.turn for shown in model.shown] == list(range(1, 11))
    assert traced_names(result) == names[:9]


def test_repeated_call_ends_incomplete() -> None:
    result, model = incomplete(
        calls(call("get_booking")), calls(call("get_booking")), calls(call("search_offers"))
    )

    assert result["incomplete_reason"] == "repeated_call"
    assert [shown.turn for shown in model.shown] == [1, 2]
    assert traced_names(result) == ["get_booking"]


def test_identical_calls_in_one_reply_are_repeated_call() -> None:
    result, _ = incomplete(calls(call("get_booking"), call("get_booking")))

    assert result["incomplete_reason"] == "repeated_call"
    assert traced_names(result) == ["get_booking"]


def test_repeated_malformed_call_ends_incomplete() -> None:
    result, _ = incomplete(calls(call("check_offer", "{oops")), calls(call("check_offer", "{oops")))

    assert result["incomplete_reason"] == "repeated_call"
    assert traced_names(result) == ["check_offer"]


def test_bad_final_answer_ends_incomplete() -> None:
    answer: dict[str, JsonValue] = {
        "decision": "rebook",
        "offer_id": "OF-1001",
        "reasoning": "Cheaper.",
        "confidence": Decimal("0.9"),
        "extra": True,
    }

    result, _ = incomplete(final(answer))

    assert result["incomplete_reason"] == "bad_final_answer"
    assert result["reasoning"] == (
        "The model's final answer did not have the required shape."
        " A person must review this booking."
    )


def test_refusal_ends_incomplete() -> None:
    result, _ = incomplete(Refusal(text="I cannot help with that.", usage=TURN_USAGE))

    assert result["incomplete_reason"] == "refusal"
    assert result["confidence"] is None


def test_provider_error_keeps_other_bookings_running() -> None:
    report, _ = review_by_model(
        sample(),
        {
            "QX7T2A": [ProviderFailed(code=ProviderErrorCode.CONNECTION)],
            "RT5K8B": [rebook("OF-3001")],
        },
    )

    failed = json_result(report, "QX7T2A")
    assert (failed["status"], failed["incomplete_reason"]) == (
        "INCOMPLETE_ANALYSIS",
        "provider_error",
    )
    assert json_result(report, "RT5K8B")["status"] == "REBOOK"


def test_provider_error_code_is_in_trace() -> None:
    result, _ = incomplete(
        calls(call("get_booking")), ProviderFailed(code=ProviderErrorCode.TIMEOUT)
    )

    assert result["trace"] == {
        "prompt_version": TEST_PROMPT.version,
        "turns": 2,
        "usage": {"input_tokens": 100, "output_tokens": 20},
        "tool_calls": [{"name": "get_booking", "arguments": "{}", "ok": True}],
        "provider_error_code": "timeout",
    }


def test_equal_calls_that_are_not_adjacent_are_allowed() -> None:
    reply = calls(call("get_booking"), call("search_offers"), call("get_booking"))

    run, _ = run_qx7t2a(reply, rebook("OF-1001"))

    assert [traced.name for traced in run.trace.tool_calls] == [
        "get_booking",
        "search_offers",
        "get_booking",
    ]
    assert isinstance(run.end, Answered)


def test_mixed_reply_on_the_last_turn_is_bad_final_answer() -> None:
    names = ["get_booking", "search_offers"] * 5
    replies = [calls(call(name)) for name in names[:9]]

    result, _ = incomplete(*replies, calls(call("get_booking"), text="Rebook."))

    assert result["incomplete_reason"] == "bad_final_answer"


STUB_REQUEST = httpx2.Request("POST", "https://api.openai.com/v1/responses")
STUB_TRANSCRIPT = Transcript(
    booking_ref=BookingRef("ABC123"),
    turn=2,
    prompt=TEST_PROMPT,
    tool_specs=(
        ToolSpec(
            name="check_offer",
            description="Check one offer.",
            parameters={
                "type": "object",
                "properties": {"offer_id": {"type": "string"}},
                "required": ["offer_id"],
                "additionalProperties": False,
            },
        ),
    ),
    items=(
        UserMessage(text="Review booking ABC123."),
        ToolCallItem(call_id="call_1_1", name="check_offer", arguments='{"offer_id":"OF1"}'),
        ToolResultItem(call_id="call_1_1", result='{"ok":true}'),
    ),
)


def stub_status_error(error_class: type[APIStatusError], status: int) -> APIStatusError:
    return error_class(
        "provider error",
        response=httpx2.Response(status, request=STUB_REQUEST),
        body=None,
    )


def openai_model(outcome: Response | APIError) -> tuple[OpenAIResponsesModel, StubResponsesClient]:
    client = StubResponsesClient(outcome=outcome)
    return OpenAIResponsesModel(client=client, settings=STUB_SETTINGS), client


def test_openai_request_sets_store_off_and_no_reasoning() -> None:
    model, client = openai_model(stub_response([stub_message()]))

    model.next_step(STUB_TRANSCRIPT)

    [request] = client.requests
    assert request["store"] is False
    assert request["reasoning"] == {"effort": "none"}
    assert request["instructions"] == "Review the booking."
    spec = STUB_TRANSCRIPT.tool_specs[0]
    assert request["tools"] == [
        {
            "type": "function",
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
            "strict": True,
        }
    ]
    assert request["text"] == {
        "format": {
            "type": "json_schema",
            "name": "review_decision",
            "schema": final_answer_schema(),
            "strict": True,
        }
    }
    assert request["input"] == [
        {"type": "message", "role": "user", "content": "Review booking ABC123."},
        {
            "type": "function_call",
            "call_id": "call_1_1",
            "name": "check_offer",
            "arguments": '{"offer_id":"OF1"}',
        },
        {"type": "function_call_output", "call_id": "call_1_1", "output": '{"ok":true}'},
    ]


def test_openai_request_sets_parallel_tool_calls_off() -> None:
    model, client = openai_model(stub_response([stub_message()]))

    model.next_step(STUB_TRANSCRIPT)

    [request] = client.requests
    assert request["parallel_tool_calls"] is False
    assert request["max_output_tokens"] == STUB_SETTINGS.max_output_tokens
    assert request["model"] == "gpt-test"


def test_openai_errors_map_to_provider_failed() -> None:
    cases: list[tuple[APIError, ProviderErrorCode]] = [
        (APITimeoutError(STUB_REQUEST), ProviderErrorCode.TIMEOUT),
        (APIConnectionError(request=STUB_REQUEST), ProviderErrorCode.CONNECTION),
        (stub_status_error(RateLimitError, 429), ProviderErrorCode.RATE_LIMIT),
        (stub_status_error(InternalServerError, 503), ProviderErrorCode.SERVER_ERROR),
    ]

    replies = [openai_model(error)[0].next_step(STUB_TRANSCRIPT) for error, _ in cases]

    assert replies == [ProviderFailed(code=code) for _, code in cases]


def test_openai_auth_error_raises_typed_error() -> None:
    model, _ = openai_model(stub_status_error(AuthenticationError, 401))

    with pytest.raises(ProviderAuthenticationError, match="API key"):
        model.next_step(STUB_TRANSCRIPT)


def test_openai_permission_denied_raises_typed_error() -> None:
    model, _ = openai_model(stub_status_error(PermissionDeniedError, 403))

    with pytest.raises(ProviderPermissionError, match="configured model"):
        model.next_step(STUB_TRANSCRIPT)


def test_openai_not_found_raises_typed_error() -> None:
    model, _ = openai_model(stub_status_error(NotFoundError, 404))

    with pytest.raises(ProviderModelNotFoundError, match="configured model"):
        model.next_step(STUB_TRANSCRIPT)


def test_openai_refusal_maps_to_refusal_step() -> None:
    model, _ = openai_model(
        stub_response(
            [
                stub_message(
                    {"type": "output_text", "text": "Partial.", "annotations": []},
                    {"type": "refusal", "refusal": "I cannot help with that."},
                )
            ]
        )
    )

    reply = model.next_step(STUB_TRANSCRIPT)

    assert reply == Refusal(
        text="I cannot help with that.", usage=Usage(input_tokens=120, output_tokens=30)
    )


def test_openai_calls_with_text_map_to_tool_calls_with_text() -> None:
    model, _ = openai_model(
        stub_response(
            [
                stub_message({"type": "output_text", "text": "Checking OF1.", "annotations": []}),
                {
                    "type": "function_call",
                    "id": "fc_1",
                    "call_id": "provider_call_9",
                    "name": "check_offer",
                    "arguments": '{"offer_id": "OF1"',
                    "status": "completed",
                },
            ]
        )
    )

    reply = model.next_step(STUB_TRANSCRIPT)

    assert reply == ToolCalls(
        calls=(ToolCallRequest(name="check_offer", arguments='{"offer_id": "OF1"'),),
        text="Checking OF1.",
        usage=Usage(input_tokens=120, output_tokens=30),
    )


STUB_USAGE = Usage(input_tokens=120, output_tokens=30)
STUB_CALL = {
    "type": "function_call",
    "id": "fc_1",
    "call_id": "provider_call_1",
    "name": "get_booking",
    "arguments": "{}",
    "status": "completed",
}


def stub_text(text: str) -> dict[str, object]:
    return {"type": "output_text", "text": text, "annotations": []}


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ([], FinalText(text="", usage=STUB_USAGE)),
        ([stub_message()], FinalText(text="", usage=STUB_USAGE)),
        ([stub_message(stub_text("a"), stub_text("b"))], FinalText(text="ab", usage=STUB_USAGE)),
        (
            [STUB_CALL],
            ToolCalls(
                calls=(ToolCallRequest(name="get_booking", arguments="{}"),),
                text=None,
                usage=STUB_USAGE,
            ),
        ),
        (
            [STUB_CALL, stub_message({"type": "refusal", "refusal": "No."})],
            Refusal(text="No.", usage=STUB_USAGE),
        ),
    ],
)
def test_openai_reply_shapes_map_to_reply_types(
    output: list[dict[str, object]], expected: ModelReply
) -> None:
    model, _ = openai_model(stub_response(output))

    assert model.next_step(STUB_TRANSCRIPT) == expected


def test_openai_reply_without_usage_fails_loudly() -> None:
    response = stub_response([stub_message()]).model_copy(update={"usage": None})
    model, _ = openai_model(response)

    with pytest.raises(ValueError, match="no token usage"):
        model.next_step(STUB_TRANSCRIPT)


SCENARIO_RULES_PICKS = {
    "CH8L5F": "OF-6401",
    "FD2N8Z": "OF-6401",
    "MK3V7P": "OF-6101",
    "RD9Q2X": "OF-6201",
    "WJ6T4N": "OF-6302",
}


def scenario_result(ref: str, *replies: ModelReply) -> dict[str, object]:
    scripts: dict[str, Sequence[ModelReply]] = {
        other: [rebook(offer_id)] for other, offer_id in SCENARIO_RULES_PICKS.items()
    }
    scripts[ref] = replies
    agent = ReviewAgent(model=ScriptedModel(scripts), prompt=TEST_PROMPT, mode=ReviewMode.OPENAI)
    report = review_with_model(
        JsonFixtureSource(REPO_FIXTURES / "scenarios"),
        read_exchange_rates(REPO_CONFIG / "exchange_rates.toml"),
        ReviewPolicy(minimum_saving=Money.of("50.00", USD)),
        agent,
    )
    return json_result(report, ref)


def test_scenario_a_model_pick_of_6102_is_accepted() -> None:
    result = scenario_result("MK3V7P", rebook("OF-6102"))

    assert result["status"] == "REBOOK"
    assert result["decided_by"] == "model"
    assert result["offer_id"] == "OF-6102"
    assert result["nominal_saving"] == {"amount": "80.00", "currency": "USD"}
    assert result["approval_flags"] == []
    assert result["best_offer_id"] == "OF-6101"


def test_scenario_a_tool_call_then_pick_of_6102_is_accepted() -> None:
    alone = scenario_result("MK3V7P", rebook("OF-6102"))
    checked_call = call("check_offer", '{"offer_id":"OF-6102"}')

    result = scenario_result("MK3V7P", calls(checked_call), rebook("OF-6102"))

    assert {key: value for key, value in result.items() if key != "trace"} == {
        key: value for key, value in alone.items() if key != "trace"
    }
    trace = result["trace"]
    alone_trace = alone["trace"]
    assert isinstance(trace, dict)
    assert isinstance(alone_trace, dict)
    assert trace["tool_calls"] == [
        {"name": "check_offer", "arguments": '{"offer_id":"OF-6102"}', "ok": True}
    ]
    assert trace["turns"] == alone_trace["turns"] + 1


def test_scenario_b_model_keep_on_rd9q2x_needs_review() -> None:
    result = scenario_result("RD9Q2X", keep("The carrier change is not worth it."))

    assert result["status"] == "NEEDS_REVIEW"
    assert result["decided_by"] == "safety_check"
    reasoning = text_of(result, "reasoning")
    assert reasoning.startswith("Model and rules disagree")
    assert "OF-6201" in reasoning
    assert reasoning.endswith("Model text: The carrier change is not worth it.")


def test_scenario_b_model_rebook_on_rd9q2x_shows_carrier_flag() -> None:
    result = scenario_result("RD9Q2X", rebook("OF-6201"))

    assert result["status"] == "REBOOK"
    assert result["decided_by"] == "model"
    assert result["nominal_saving"] == {"amount": "75.00", "currency": "USD"}
    assert result["approval_flags"] == ["carrier_change"]
    assert result["best_offer_id"] is None


def test_scenario_c_model_pick_of_6301_needs_review() -> None:
    result = scenario_result("WJ6T4N", rebook("OF-6301", "Biggest saving on the same flight."))

    assert result["status"] == "NEEDS_REVIEW"
    assert result["decided_by"] == "safety_check"
    assert result["offer_id"] == "OF-6301"
    assert result["nominal_saving"] == {"amount": "210.00", "currency": "USD"}
    assert result["best_offer_id"] is None
    reasoning = text_of(result, "reasoning")
    assert reasoning.startswith("Safety check: rule refundable failed")
    assert "Rules view: OF-6302 passes every rule" in reasoning
    assert reasoning.endswith("Model text: Biggest saving on the same flight.")


def test_scenario_c_model_pick_of_6302_is_accepted() -> None:
    result = scenario_result("WJ6T4N", rebook("OF-6302"))

    assert result["status"] == "REBOOK"
    assert result["nominal_saving"] == {"amount": "60.00", "currency": "USD"}
    assert result["best_offer_id"] is None
