import json
from decimal import Decimal

type JsonValue = bool | int | Decimal | str | list[JsonValue] | dict[str, JsonValue] | None

TEXT_ENCODING = "utf-8"


def canonical_json(value: JsonValue) -> str:
    match value:
        case None:
            return "null"
        case str():
            return _text(value)
        case bool() | int():
            return json.dumps(value)
        case Decimal():
            if not value.is_finite():
                raise ValueError(f"canonical JSON has no text for the decimal {value}")
            return format(value, "f")
        case list():
            return "[" + ",".join(canonical_json(item) for item in value) + "]"
        case dict():
            members = (
                f"{_text(key)}:{canonical_json(item)}" for key, item in sorted(value.items())
            )
            return "{" + ",".join(members) + "}"
        case _:
            raise TypeError(f"canonical JSON does not accept {type(value).__name__}, such as float")


def _text(text: str) -> str:
    try:
        text.encode(TEXT_ENCODING)
    except UnicodeEncodeError as err:
        raise ValueError(
            f"canonical JSON text must be valid {TEXT_ENCODING}: {err.reason}"
        ) from err
    return json.dumps(text, ensure_ascii=False)
