import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import override

CURRENCY_CODE_LENGTH = 3
CENT = Decimal("0.01")
DECIMAL_TEXT = re.compile(r"-?[0-9]+(\.[0-9]+)?")


def decimal_from_text(text: str, subject: str) -> Decimal:
    if not DECIMAL_TEXT.fullmatch(text):
        raise ValueError(f"{subject} {text!r} is not plain decimal text")
    return Decimal(text)


@dataclass(frozen=True, slots=True, kw_only=True)
class Currency:
    code: str

    def __post_init__(self) -> None:
        if len(self.code) != CURRENCY_CODE_LENGTH or not (
            self.code.isascii() and self.code.isalpha() and self.code.isupper()
        ):
            raise ValueError(f"currency code must be three uppercase letters, got {self.code!r}")

    @override
    def __str__(self) -> str:
        return self.code


@dataclass(frozen=True, slots=True, kw_only=True, eq=False)
class Money:
    amount: Decimal
    currency: Currency

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError(f"money amount must be a Decimal, got {type(self.amount).__name__}")
        if not self.amount.is_finite():
            raise ValueError(f"money amount must be finite, got {self.amount}")

    @classmethod
    def of(cls, amount: Decimal | str | int, currency: Currency) -> "Money":
        if isinstance(amount, bool) or not isinstance(amount, Decimal | str | int):
            raise TypeError(
                f"money amount must be a Decimal, text or an integer, got {type(amount).__name__}"
            )
        if isinstance(amount, str):
            return cls(amount=decimal_from_text(amount, "money amount"), currency=currency)
        return cls(amount=Decimal(amount), currency=currency)

    def is_negative(self) -> bool:
        return self.amount < 0

    def rounded(self) -> "Money":
        cents = self.amount.quantize(CENT, rounding=ROUND_HALF_EVEN)
        return Money(amount=cents.copy_abs() if cents.is_zero() else cents, currency=self.currency)

    def times(self, factor: int) -> "Money":
        return Money(amount=self.amount * factor, currency=self.currency)

    def __add__(self, other: "Money") -> "Money":
        return Money(amount=self.amount + self._same_currency(other).amount, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        return Money(amount=self.amount - self._same_currency(other).amount, currency=self.currency)

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == self._same_currency(other).amount

    @override
    def __hash__(self) -> int:
        return hash((self.amount, self.currency))

    def __lt__(self, other: "Money") -> bool:
        return self.amount < self._same_currency(other).amount

    def __le__(self, other: "Money") -> bool:
        return self.amount <= self._same_currency(other).amount

    def __gt__(self, other: "Money") -> bool:
        return self.amount > self._same_currency(other).amount

    def __ge__(self, other: "Money") -> bool:
        return self.amount >= self._same_currency(other).amount

    @override
    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"

    def _same_currency(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError(f"cannot combine {self.currency} with {other.currency}")
        return other
