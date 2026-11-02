import json
import os
import re
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, DecimalException
from pathlib import Path

DEFAULT_RECORDING = Path("recordings/review-run.json")
DEFAULT_FIXTURES = Path("fixtures/pnrs.json")
IN_PRICE_VARIABLE = "IN_USD_PER_MTOK"
OUT_PRICE_VARIABLE = "OUT_USD_PER_MTOK"
TOKENS_PER_PRICE_UNIT = Decimal(1_000_000)
USD_PLACES = Decimal("0.000001")
FILE_ENCODING = "utf-8"
EXIT_BAD_INPUT = 1
PRICE_PATTERN = re.compile(r"[0-9]+(\.[0-9]+)?")


class CostInputError(Exception):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class RunCost:
    model: str
    input_tokens: int
    output_tokens: int
    model_bookings: int
    fixture_bookings: int
    in_price: Decimal
    out_price: Decimal

    def __post_init__(self) -> None:
        for name, price in (("input price", self.in_price), ("output price", self.out_price)):
            if not price.is_finite() or price < 0:
                raise CostInputError(f"the {name} must be a number of at least 0, got {price}")
        if self.model_bookings < 1:
            raise CostInputError("the recording has no turns, so there is no model cost to share")
        if self.fixture_bookings < self.model_bookings:
            raise CostInputError(
                f"the recording has {self.model_bookings} bookings,"
                f" but the fixtures hold only {self.fixture_bookings}"
            )

    @property
    def code_settled_bookings(self) -> int:
        return self.fixture_bookings - self.model_bookings

    @property
    def total_usd(self) -> Decimal:
        spent = self.input_tokens * self.in_price + self.output_tokens * self.out_price
        return spent / TOKENS_PER_PRICE_UNIT

    def line(self) -> str:
        total = self.total_usd
        fields = (
            f"model={self.model}",
            f"input_tokens={self.input_tokens}",
            f"output_tokens={self.output_tokens}",
            f"total_usd={_usd(total)}",
            f"model_bookings={self.model_bookings}",
            f"code_settled_bookings={self.code_settled_bookings}",
            f"per_model_booking_usd={_usd(total / self.model_bookings)}",
            f"fixture_bookings={self.fixture_bookings}",
            f"per_fixture_booking_usd={_usd(total / self.fixture_bookings)}",
        )
        return " ".join(fields)


def run_cost(recording: Path, fixtures: Path, in_price: Decimal, out_price: Decimal) -> RunCost:
    document = _read_json(recording)
    turns = _field(document, "turns", list, str(recording))
    usages = [_field(turn, "usage", dict, f"turn {index}") for index, turn in enumerate(turns)]
    bookings = {_field(turn, "booking", str, f"turn {index}") for index, turn in enumerate(turns)}
    fixture_refs = _fixture_refs(fixtures)
    unknown = sorted(bookings - fixture_refs)
    if unknown:
        raise CostInputError(f"{recording}: booking {unknown[0]} is not in {fixtures}")
    return RunCost(
        model=_field(document, "model", str, str(recording)),
        input_tokens=sum(
            _tokens(usage, "input_tokens", index) for index, usage in enumerate(usages)
        ),
        output_tokens=sum(
            _tokens(usage, "output_tokens", index) for index, usage in enumerate(usages)
        ),
        model_bookings=len(bookings),
        fixture_bookings=len(fixture_refs),
        in_price=in_price,
        out_price=out_price,
    )


def main(arguments: list[str]) -> int:
    recording = Path(arguments[0]) if arguments else DEFAULT_RECORDING
    fixtures = Path(arguments[1]) if len(arguments) > 1 else DEFAULT_FIXTURES
    try:
        cost = run_cost(recording, fixtures, _price(IN_PRICE_VARIABLE), _price(OUT_PRICE_VARIABLE))
        line = _line(cost)
    except CostInputError as err:
        print(f"error: {err}", file=sys.stderr)
        return EXIT_BAD_INPUT
    print(line)
    return 0


def _price(variable: str) -> Decimal:
    text = os.environ.get(variable)
    if not text:
        raise CostInputError(f"set {variable} to the price in USD per 1M tokens")
    if not PRICE_PATTERN.fullmatch(text):
        raise CostInputError(f"{variable} must be a plain decimal number such as 0.75, got {text}")
    return Decimal(text)


def _line(cost: RunCost) -> str:
    try:
        return cost.line()
    except DecimalException as err:
        raise CostInputError(f"the cost is too large to print to six places: {err!r}") from err


def _fixture_refs(fixtures: Path) -> set[str]:
    entries = _field(_read_json(fixtures), "pnrs", list, str(fixtures))
    refs = [
        _field(entry, "pnr", str, f"{fixtures} entry {index}")
        for index, entry in enumerate(entries)
    ]
    if len(set(refs)) != len(refs):
        raise CostInputError(f"{fixtures}: a booking reference appears more than once")
    return set(refs)


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding=FILE_ENCODING), parse_float=Decimal)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as err:
        raise CostInputError(f"cannot read {path}: {err}") from err


def _field[T](record: object, key: str, kind: type[T], where: str) -> T:
    if not isinstance(record, dict) or key not in record:
        raise CostInputError(f"{where}: {key} is missing")
    value = record[key]
    if not isinstance(value, kind) or isinstance(value, bool):
        raise CostInputError(f"{where}: {key} is not of type {kind.__name__}")
    return value


def _tokens(usage: object, key: str, index: int) -> int:
    count = _field(usage, key, int, f"turn {index} usage")
    if count < 0:
        raise CostInputError(f"turn {index} usage: {key} is negative")
    return count


def _usd(amount: Decimal) -> str:
    return str(amount.quantize(USD_PLACES, rounding=ROUND_HALF_EVEN))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
