---
paths:
  - "**/*.py"
  - "pyproject.toml"
---

# Python rules

Python 3.12+, `uv`, `ruff`, `mypy --strict`, `pytest`. Linters already enforce style. These rules cover what they miss.

## Tooling

- Use `uv` for everything: `uv add <pkg>`, `uv run <cmd>`. Never `pip`, never bare `python`, never edit `uv.lock` by hand.
- Before you call work done, run `uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest -q`. All green, or it is not done.
- Never silence a check to get green. No `# type: ignore`, `# noqa`, `cast` or `Any` as a fix. If one is truly needed, scope it to one error code and give the reason on the same line.
- Before you call a third-party API (`pydantic`, `openai`), check the installed version and its docs. Do not write an API from memory.
- Add a dependency only when the standard library cannot do the job.

## Types

- Annotate every function. Use `list[str]`, `X | None` and the `type` statement. Never `typing.List`, `Optional` or `Union`.
- Parameters take abstract types (`Sequence`, `Mapping`, `Iterable` from `collections.abc`). Returns give concrete types.
- No `Any`. A value that can be anything is `object`. Never pass `dict[str, Any]` between modules: define a dataclass.
- IDs are `NewType` (`OfferId`, `BookingRef`), so a booking ref cannot go where an offer ID belongs.
- Closed sets are `StrEnum` or `Literal`. Branch on them with `match` and end with `case _: assert_never(x)`.
- Mark overriding methods with `@override`. Ports are `Protocol` classes.

## Data

- Domain values are `@dataclass(frozen=True, slots=True, kw_only=True)`. Check invariants in `__post_init__` and raise on bad input. Use tuples, not lists, inside frozen classes.
- `pydantic` lives only in `infrastructure/`. Parse there, convert to domain dataclasses, and never let a pydantic model reach the domain. Models set `extra="forbid"` and `frozen=True`.
- No mutable default arguments. Use `field(default_factory=...)`.
- Required data has no fallback. Never `.get(key, default)`, `or 0` or `or ""` on a field that must exist. A missing field is an error, not a zero.

## Money

- Build `Decimal` from `str` or `int`, never from `float`. `Decimal(0.1)` is wrong.
- Parse JSON with `Model.model_validate_json(text)`, or `json.loads(text, parse_float=Decimal)`. Plain `json.loads` turns prices into floats before you see them.
- Round once, at the step `DESIGN.md` names, with `quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)`. Never call `round()` on money.
- An amount always travels with its currency. Adding or comparing two currencies raises.
- `tests/conftest.py` must trap `decimal.FloatOperation`, so any float that leaks into money math fails the tests.

## Errors

- Expected outcomes (a rejected offer, invalid booking data) are return values: a union of frozen dataclasses. Exceptions are for bugs and setup failures.
- Catch the narrowest exception that can happen. No bare `except:`, no `except Exception:` outside the CLI entry point, never `except ...: pass`.
- Re-raise with `raise NewError(...) from err`, so the cause survives.
- Never use `assert` to check runtime input. `python -O` removes it. Raise instead.
- Do not guard against states the types rule out. No `if x is None` on a value typed as never `None`.

## Structure

- No I/O, no env reads and no network at import time. Environment variables are read only in `composition/`.
- No module-level mutable state. No `datetime.now()` in the domain: pass the time in.
- `print` only in `cli/`. Everywhere else, return data.
- Files: `pathlib.Path` and `encoding="utf-8"` on every read and write.
- Output is deterministic. Sort before you print or hash. Never rely on set order.
- No speculative code: no base class with one subclass, no `Manager` or `Helper` classes, no unused parameters "for later".
- No docstring that repeats the signature. Comment only a reason the code cannot show.

## Tests

- Plain `pytest` functions with bare `assert`. No `unittest` classes.
- Test through a module's public function. Replace ports with in-memory fakes. Never `mock.patch` our own code.
- Compare money exactly: `== Decimal("80.00")`. Never `pytest.approx` on money.
- Use `@pytest.mark.parametrize` for case tables and `pytest.raises(Err, match=...)` for errors.
- Name tests after the behavior: `test_offer_in_lower_cabin_is_rejected`.
- Tests run offline. A test that needs a network or an API key is a bug.
- Never change a test only to make it pass. If the test is wrong, say why in the same change.
