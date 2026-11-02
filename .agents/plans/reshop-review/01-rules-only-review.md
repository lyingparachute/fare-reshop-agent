# Rules-only review

Status: ready

This ExecPlan is a living document. Progress, Surprises & Discoveries, Decision Log and Outcomes & Retrospective are kept current as work proceeds. Repo plan rules: none. Starts after: nothing.

## Progress

- [x] (2026-11-02) Milestone 1: project setup and local checks (uv project, pyproject with the `fare-reshop` script, ruff, mypy strict, pytest with the float trap, the `scripts/check.sh` check script). DoD CLI entry: `1`, `0`. Check script: `4`, `1`. Checks green: `0` (`1 passed`). Critic: four findings fixed (session-wide trap via `pytest_configure`, no blanket ruff ignores, no empty subcommand group, no one-caller `run`).
- [x] (2026-11-02) Milestone 2: domain value objects, the result union (`Rebook`, `Keep`, `Invalid`) and review rules, tested in `tests/test_review_rules.py`. DoD Domain rule names: `28`. Checks green (`50 passed`). Two critic rounds; fixes listed in the Decision Log.
- [x] (2026-11-02) Milestone 3: prototyping exact money text through pydantic, with a promote or discard decision recorded in this plan. Result: discard path one, use path two.
- [x] (2026-11-02) Milestone 4: the fixture JSON adapter for `ReshopSource`, with the rejection and data-issue rules. 11 of the 14 "Fixture and rate names" present (the other 3 are milestone 5). Checks green (`72 passed`). Two critic rounds.
- [x] (2026-11-02) Milestone 5: the TOML rate adapter for `ExchangeRates`, the TOML policy reader, the reader error types, and the two config files. DoD Fixture and rate names: `14`. Checks green (`85 passed`). Two critic rounds (round 2: APPROVE, two small fixes applied).
- [x] (2026-11-02) Milestone 6: review orchestration in `none` mode, with the sample-data oracle test. DoD Orchestration names: `14`. Checks green (`99 passed`). Critic: APPROVE, three small fixes applied.
- [x] (2026-11-02) Milestone 7: composition (the `none` graph, `SetupError`) and the `review` command with JSON output. DoD Default run exits 0: `0`. JSON rates: `3`. JSON dates: `1` and `3`. Checks green (`109 passed`). Critic: fixes applied (setup error tests, key order tests, one status source).
- [x] (2026-11-02) Milestone 8: table output with the REASON column, the three-line error format, exit codes and `--debug`. DoD Table rebooks QX7T2A: `1`; RT5K8B: `1`; Table keeps: `3`; Only two rebooks: `2`; Table reasons: `2` and `1`; Layering: `1`. Checks green (`119 passed`). Critic findings fixed.
- [x] (2026-11-02) Milestone 9: `fare-reshop doctor`, `start.sh` and the first-run tests in `tests/test_cli.py`. DoD Doctor passes: `0`. start.sh asks: `1` and `1`. CLI names: `14`. Checks green (`123 passed`). Critic findings fixed.
- [ ] Milestone 10: `GLOSSARY.md`, the ADR in `docs/adr/`, and the `AGENTS.md` wording changes.
- [ ] Milestone 11: the scenario data set in `fixtures/scenarios/`, the `--data` flag, and the scenario tests (D34, L12).
- [ ] Definition of done: every checkbox below ticked with its command output recorded here.

Updated at every stopping point. This list, not memory, says where the work is.

## Background / why now

After this plan, a person who clones the repo can run `./start.sh` (or, by hand, `uv sync` and `uv run fare-reshop review`) and see one recommendation for each of the five sample bookings. The default run needs no API key, no network and no paid service. Each recommendation says rebook or keep, names the chosen fare, gives the nominal saving in the booking's currency, lists which rules each fare passed or failed, and explains the result in plain words. The two sample rebookings are QX7T2A (80.00 USD saving) and RT5K8B (363.21 EUR saving). Every number comes from plain Python code with exact decimal math. The same run prints JSON for programs or an aligned table for people. Every error names what went wrong, why, and the command that fixes it.

The repo has no Python code yet. The only data-like files are `fixtures/pnrs.json` (5 bookings) and `fixtures/fares_feed.json` (6 offers, captured at 2026-07-08T09:00:00Z). Milestone 11 adds a made-up second data set in `fixtures/scenarios/` (6 bookings, 7 offers) that shows the judgment cases (D34). The commits on the branch only add agent instructions. Every later plan depends on this one: the live model plan needs the rule code and the ports, and the recording plan needs a working default run to record. If this waits, nothing else in the feature can start.

The feature is split into four plans. This plan is the first, and the index in the same folder (`00-INDEX.md`) holds the full design. This plan copies the parts it needs: stories S1, S5 and S7 with their walkthroughs, the decisions it carries, the assumptions it rests on, and the expected results. Nothing in this plan depends on another checked-in plan. The index lists no other plan that conflicts with or overlaps this one.

## User stories

The three stories this plan delivers are copied word for word from the index, together with their walkthroughs. Steps that mention later plans (S5 step 4 mentions recordings) stay as written. This plan does not build what those steps describe.

#### S1 - Rules-only review

As a travel agent, I want one recommendation per booking with the chosen offer, the nominal saving and the rules each offer passed or failed, so that I can decide which bookings to look at without re-checking fares by hand.

Walkthrough:

1. The agent runs `uv run fare-reshop review --model none`. First use: uv creates the environment on the first run. `--data scenarios` runs the made-up scenario set instead of the sample (D34); the default is `sample`.
2. The tool loads the data snapshot (bookings, offers and capture time), the policy file and the exchange-rate file. Error: a missing or unreadable file stops the run with the path and the reason, exit code 2. Error: a booking record with a missing or wrong field, a multi-segment itinerary, a `totalPaid` that does not equal passengers times price, or a departure before the capture time becomes a result with status `INVALID_DATA` and the reason; the other bookings still run. Error: a booking whose currency has no exchange rate from the minimum saving's currency (USD) becomes `INVALID_DATA` with "no exchange rate from USD to <currency>". Error: a bad offer record, or every copy of a duplicated offer id, is left out and listed under `data_issues` with the offer id and the reason; a duplicated booking reference keeps the first record and lists the rest. Money is read as text into `Decimal`, never through a float, and unknown keys fail parsing, except the documented top-level `_comment`. Empty: no bookings prints an empty result list and exit code 0.
3. For each booking, every offer with the same origin, destination and departure date is evaluated: each rule gives PASS or FAIL with a reason, and the nominal saving is computed in the booking's currency. An offer in the booking's currency needs no rate. Error: an offer in another currency with no rate to the booking's currency fails the rule `exchange_rate`. Empty: no offers on the route gives `KEEP` with "no offers on this route and date".
4. An offer is eligible when it passes every rule and its rounded saving meets the minimum. The minimum is 50 USD, converted to the booking's currency with the same exchange-rate port and rounded once. No eligible offer gives `KEEP`, with every offer's evaluation. At least one eligible offer: in `none` mode the code picks the eligible offer with the highest saving (ties broken by offer id) and returns `REBOOK` with `decided_by: rules`, `confidence: null` and a rationale built from the rule results.
5. Output is JSON on stdout with a `schema_version`. `--format table` prints an aligned table for people, in color when the terminal supports it and plain when `NO_COLOR` is set or output is piped.

#### S5 - Swap the exchange-rate source

As a developer, I want exchange rates behind one interface, so that a live rate source is one new adapter and nothing else changes.

Walkthrough:

1. The developer writes a class that satisfies the `ExchangeRates` port and wires it in `composition/`. Nothing in `domain/` or `orchestration/` changes.
2. Error: the source has no rate for a pair; the offer fails the rule `exchange_rate` (S1 step 3).
3. Each converted amount in the output shows the rate, its direction ("1 EUR = 1.1433 USD") and the date of the rate data. The rate sits on the offer evaluation that used it.
4. Changing the rates changes tool results, so an existing recording goes stale and must be re-recorded (S3 step 3).

#### S7 - First run on a fresh machine

As a programmer who has never seen this repo or its tools, I want every missing piece named with the exact command that fixes it, so that I get from clone to a result without guessing.

Walkthrough:

1. The reader runs `./start.sh`. It checks for `uv`. Missing: it says what uv is, prints the official install command, and asks "Install uv now? [y/N]". Only `y` runs it. Anything else stops with the manual command. Nothing is ever installed without that answer.
2. It runs `uv sync` after asking the same way, then `fare-reshop doctor`, then the default review.
3. `fare-reshop doctor` prints one line per check with a mark and, for each failure, the command that fixes it: Python version, installed packages, the `live` extra, `OPENAI_API_KEY` set (never its value), the recording present and matching the data, and the fixture and config files readable. Exit code 0 when everything the default run needs is present.
4. Every CLI error has the same three lines: what went wrong, why, and the command that fixes it. No traceback unless `--debug` is passed.
5. Windows: `./start.sh` needs a POSIX shell; the README gives the same steps as uv commands.

This plan builds the parts of walkthrough step 3 that exist at this point in the build: the installed packages, and the fixture and config files. The Python version is not checked. `uv` refuses to run the package on a Python older than the `requires-python` value in `pyproject.toml` (3.12), so a separate check could never report a failure that the run would not already show. The `live` extra, the key and the recording checks belong to later plans, which add their own doctor checks (D31).

## Scope and non-goals

In scope, each item traceable to a story or to a decision this plan carries:

- S1: the rule checks, eligibility, the nominal saving and minimum saving math, the `none` decision, the `review` command with JSON and table output, and the exit codes (D1, D3, D4, D5, D7, D9, D15).
- S5: the `ExchangeRates` port, the TOML rate adapter with the demo rate, and the rate shown on every converted amount (D6, D12).
- S7: `./start.sh`, `fare-reshop doctor` with the checks listed above, the three-line error format and `--debug` (D31).
- Foundation that S1 needs: the domain value objects, the `ReshopSource` port with the fixture JSON adapter, the TOML policy and rate readers, the `SetupError` type in `composition/`, and the orchestration function (D10, D11, D12, D13, D32).
- Project setup and the local check script (D13, D14).
- Writing the glossary terms and the ADR for this plan (D26), and two wording changes in `AGENTS.md` (L11).
- S1 on the scenario data (D34): the `--data` flag, the scenario data set and its rules-only tests (milestone 11, L12).

Non-goals, each a thing a reader might expect here but must not build now:

- The live model, its tools, the loop and the safety check (plan 02, S2).
- Recording and replay, the `recorded` mode, `--record`, and making `recorded` the default (plan 03, S3, S4).
- The `openai` and `recorded` values of `--model`. In this plan `--model` accepts only `none`.
- The README, `DESIGN.md`, `docs/future-work.md`, the AI-usage note, and the Windows steps in the README (plan 04, S6). Until plan 04 lands, a Windows reader follows the uv commands in this plan's milestone proofs by hand.
- Token and cost budgets, masking of PNRs, a clock port, a computed realized saving, and any booking action (D2, D27, D29, D30).
- Any second rate source. The live rate adapter is a later plan that uses the same port.
- The model on the scenario data. Plan 02 owns the scripted-fake tests for it.

## Context and orientation

The repo is `fare-reshop-agent`, at the repo root. Read `AGENTS.md` and `.claude/rules/python.md` before you write code. The Python rules are binding: `uv` for every command, `ruff`, `mypy --strict`, `pytest`, no `# type: ignore`, no `Any`, no `cast` as a fix, no bare `python`, no `pip`, and never edit `uv.lock` by hand. The folder `.agents/plans/reshop-review/` holds this plan and the index. Do not edit the index.

The current tree has `AGENTS.md`, `README.md`, `docs/future-work.md`, `.claude/rules/` (the Python rules), `fixtures/pnrs.json`, and `fixtures/fares_feed.json`. There is no Python package, no `pyproject.toml`, no tests, and no check script yet. Some tracked-file paths in the index refer to files that a later plan writes; they are not in this tree yet.

Terms, defined here so that every later sentence can use them. A booking is one ticketed trip, identified by its booking reference (the PNR code, for example `QX7T2A`). It has one flight segment, a number of passengers, and a ticket with the price paid, the cabin, whether it is refundable, the change fee per passenger, and the number of checked bags included. An offer is one fare on sale now for the same origin, destination and departure date as a booking, with the same kind of fields. The snapshot is the set of bookings and offers read at one time. The capture time is the time the snapshot was taken, from the offer data (`capturedAt`). A rule check is one of the seven tests that compare an offer with a booking, each giving PASS or FAIL with a reason. An eligible offer passes every rule check and reaches the minimum saving. An approval flag is a note on an offer that a person must approve, such as a schedule change or a carrier change. It does not fail the offer. The nominal saving is the saving this formula gives, in the booking's currency: passengers times (old fare per passenger, minus the offer's fare per passenger in the booking's currency, minus the old ticket's change fee per passenger in the booking's currency). The realized saving is the money actually saved after a rebooking is carried out. This project does not compute it. The name appears only to say that it is not computed. The minimum saving is the least nominal saving that counts: 50.00 USD, converted to the booking's currency when needed. An exchange rate is a stored rate between two currencies, for example 1 EUR = 1.1433 USD. The recommendation is the decision for one booking: status, chosen offer, saving, flags, reasoning and the rates used.

Money means a `Decimal` amount with a currency code. A value object is an immutable domain value that checks its own rules when it is built and raises when the input is bad. A port is an interface the domain declares for something outside it, written as a Python `Protocol`. An adapter is code that implements a port with a real source: the JSON fixture files, a TOML file, or an in-memory fake in a test. The anti-corruption layer is the part of the fixture adapter that turns raw file records into domain values, so that outside shapes never reach the domain. The composition root is the code in `composition/` that builds the objects for one run and reads environment and configuration.

The sample data holds five bookings and six offers. The table below is the acceptance oracle: the output of `review --model none` must match it. Demo rate: 1 EUR = 1.1433 USD, dated 2026-07-07. The minimum is 50.00 USD, or 43.73 EUR for a euro booking. The fixtures do not exercise the seats rule or a higher future change fee; the unit tests do.

| Booking | Offers | Result in `none` mode | Why |
|---|---|---|---|
| QX7T2A | OF-1001 | `REBOOK` OF-1001, saving 80.00 USD | Same flight, same conditions: 1 x (480 - 300 - 100) |
| LM9P4C | OF-2001 | `KEEP` | Fails cabin and bags; saving 2 x (350 - 320 - 75) = -90.00 USD |
| RT5K8B | OF-3001 | `REBOOK` OF-3001, saving 363.21 EUR | 2,100 USD = 1,836.79 EUR; 2,200 - 1,836.79 - 0; future fee 0 USD = 0 EUR passes; 363.21 is above 43.73 |
| ZC3N1D | OF-4001 | `KEEP` | Fails refundability; the 140.00 USD saving is shown but cannot qualify |
| HB6W9E | OF-5001, OF-5002 | `KEEP` | OF-5001 passes all seven rules and saves -90.00 USD, below the 50.00 USD minimum; OF-5002 fails cabin, bags and stops and saves -40.00 USD |

The scenario data set (D34) is made up, all in USD, and exists to show the judgment cases. Its records use the same fields as the sample. Its top-level `_comment` says it holds made-up demo scenarios. All six departures fall between 2026-09-10 and 2026-09-22, after the same capture time, 2026-07-08T09:00:00Z. Every route and date pair is unique except DFW-PHX on 2026-09-18, which two bookings share on purpose. The policy and the rate files are the same for both data sets. Every booking has one segment, stops 0 and the same change fee as its matching offers, so `future_change_fee` passes everywhere. Flight numbers are made up and must match between each booking and its own offers, except where the scenario says the number changes.

Scenario bookings (`fixtures/scenarios/pnrs.json`):

| PNR | Route | Departure | Flight | Cabin | Passengers | Price per passenger | Total paid | Change fee per passenger | Bags | Refundable |
|---|---|---|---|---|---|---|---|---|---|---|
| MK3V7P | ORD-DEN | 2026-09-10T07:00:00 | UA301 | ECONOMY | 1 | 500.00 | 500.00 | 80.00 | 1 | no |
| RD9Q2X | BOS-ATL | 2026-09-12T08:15:00 | DL1450 | ECONOMY | 1 | 300.00 | 300.00 | 75.00 | 1 | no |
| WJ6T4N | SEA-SFO | 2026-09-14T12:00:00 | AS1 | ECONOMY | 1 | 600.00 | 600.00 | 90.00 | 1 | yes |
| CH8L5F | DFW-PHX | 2026-09-18T09:30:00 | AA1290 | ECONOMY | 2 | 300.00 | 600.00 | 60.00 | 1 | no |
| FD2N8Z | DFW-PHX | 2026-09-18T09:30:00 | AA1290 | ECONOMY | 2 | 300.00 | 600.00 | 60.00 | 1 | no |
| YU6EG1 | PDX-LAS | 2026-09-22T06:50:00 | UA1622 | ECONOMY | 3 | 180.00 | 540.00 | 40.00 | 1 | no |

Arrival times: MK3V7P 10:30:00, RD9Q2X 10:40:00, WJ6T4N 14:20:00, CH8L5F and FD2N8Z 11:45:00, YU6EG1 09:20:00.

Scenario offers (`fixtures/scenarios/fares_feed.json`). Every offer has stops 0. The offer's change fee equals the booking's fee on the same route.

| Offer | Route and date | Departure to arrival | Flight | Carrier | Cabin | Price per passenger | Refundable | Change fee | Bags | Seats |
|---|---|---|---|---|---|---|---|---|---|---|
| OF-6101 | ORD-DEN 2026-09-10 | 07:40 to 11:10 | UA305 | UA | ECONOMY | 250.00 | no | 80.00 | 1 | 6 |
| OF-6102 | ORD-DEN 2026-09-10 | 07:00 to 10:30 | UA301 | UA | ECONOMY | 340.00 | no | 80.00 | 1 | 6 |
| OF-6201 | BOS-ATL 2026-09-12 | 08:15 to 10:40 | WN2210 | WN | ECONOMY | 150.00 | no | 75.00 | 1 | 4 |
| OF-6301 | SEA-SFO 2026-09-14 | 12:00 to 14:20 | AS1 | AS | ECONOMY | 300.00 | no | 90.00 | 1 | 5 |
| OF-6302 | SEA-SFO 2026-09-14 | 12:00 to 14:20 | AS1 | AS | ECONOMY | 450.00 | yes | 90.00 | 1 | 5 |
| OF-6401 | DFW-PHX 2026-09-18 | 09:30 to 11:45 | AA1290 | AA | ECONOMY | 200.00 | no | 60.00 | 1 | 3 |
| OF-6501 | PDX-LAS 2026-09-22 | 06:50 to 09:20 | UA1622 | UA | ECONOMY | 120.00 | no | 40.00 | 1 | 2 |

The expected results in `none` mode. Each value is passengers x (old fare per passenger - offer fare per passenger - old change fee per passenger), computed with `Decimal` and rounded half-even once. Every value is a whole-cent amount, so the rounding changes nothing here. The minimum is 50.00 USD.

| Booking | Offers | Result in `none` mode | Why |
|---|---|---|---|
| MK3V7P | OF-6101, OF-6102 | `REBOOK` OF-6101, saving 170.00 USD, approval flag `schedule_change` | OF-6101 saves 1 x (500 - 250 - 80) = 170.00 and moves the departure 40 minutes. OF-6102 saves 1 x (500 - 340 - 80) = 80.00 with no flag. Both are eligible, so a model may pick OF-6102 (scenario a). |
| RD9Q2X | OF-6201 | `REBOOK` OF-6201, saving 75.00 USD, approval flag `carrier_change` | 1 x (300 - 150 - 75) = 75.00. The only offer changes the airline from DL to WN; the flag is shown, the rule does not fail (scenario b). |
| WJ6T4N | OF-6301, OF-6302 | `REBOOK` OF-6302, saving 60.00 USD | OF-6301 saves 1 x (600 - 300 - 90) = 210.00 but fails `refundable`. OF-6302 keeps the refund right and saves 1 x (600 - 450 - 90) = 60.00 (scenario c). |
| CH8L5F | OF-6401 | `REBOOK` OF-6401, saving 80.00 USD | 2 x (300 - 200 - 60) = 80.00. Seats: 3 offered, 2 needed, passes. |
| FD2N8Z | OF-6401 | `REBOOK` OF-6401, saving 80.00 USD | The same flight and numbers as CH8L5F. Each booking is checked alone, so both are recommended, though together they need 4 seats and the offer has 3 (scenario d; the limit is D35). |
| YU6EG1 | OF-6501 | `KEEP` | Fails `seats`: 3 passengers, 2 seats. The money alone would pass: 3 x (180 - 120 - 40) = 60.00 is above the minimum (scenario e). |

The JSON field names in the fixtures are case-sensitive and must be read exactly: `pnr`, `passengers`, `itinerary` (a list with one segment: `origin`, `destination`, `departure`, `arrival`, `carrier`, `flightNumber`, `stops`, `cabin`, `fareBasis`), `ticket` (`pricePerPassenger`, `totalPaid`, `cabin`, `refundable`, `changeFeePerPassenger`, `baggageIncludedPieces`), each money field as `{"amount": number, "currency": code}`. Offers have `offerId`, `route` (`origin`, `destination`, `departureDate`), `carrier`, `flightNumber`, `departure`, `arrival`, `stops`, `cabin`, `fareBasis`, `price`, `refundable`, `changeFeePerPassenger`, `baggageIncludedPieces`, `seatsAvailable`. The top-level `_comment` key appears in both files and is documentation only.

The existing seams for tests are the ones this plan creates. The test seam for rules and the review is the orchestration function, given in-memory fakes of the `ReshopSource` and `ExchangeRates` ports defined in the test files. The seam for the command line is the installed `fare-reshop` script, run as a subprocess. Build its path from the directory that holds the running Python interpreter (`Path(sys.executable).parent / "fare-reshop"`), so the test runs the same environment without nesting `uv run`. Failure cases copy the fixtures and config into a `tmp_path` directory, change one file, and run the script with that directory as the working directory. Tests never use `mock.patch` on our own code.

Library facts the implementer must confirm before writing code. Milestone 3 reads the installed version of `pydantic` (the version resolved in `uv.lock`) and its documentation for that version, before any pydantic model is written. Do not write a pydantic API from memory. The points to check are: how JSON numbers become `Decimal` values (the exact text must survive; no binary float may appear), how `extra="forbid"` and `frozen=True` behave, and how a field alias such as `_comment` is declared. Use the standard library `tomllib` for TOML. Use `argparse` for the command line. Check the uv installation page for the official install command before writing `start.sh`, because the command can change between uv releases.

## Locked decisions

Every decision below is carried into this plan from the index, by its id, with its reason. The reasons are the index's reasons, with the options that lost and the prior art. The plan-level locks after the index decisions (L1 to L11) are choices this plan makes to fill gaps the index leaves open. The implementer must not reopen any of them.

**D1.** Plain-code rule check first. The model sees only bookings with at least one eligible offer. A safety check runs after the model. (Owner) Reason: a model prefilter first drops real savings before the free checks run, and a model on every booking pays for calls that code can settle. If code decides and the model only writes text, no agent is left to show. Prior art: Anthropic, "Building effective agents" (2024): add model steps only where they pay off. In this plan only the rule check applies; the model and the safety check arrive in plan 02.

**D2.** Every result goes to a person. Nothing books, and no write tool exists. (Owner) Reason: auto-rebooking a narrow safe class was rejected because no binding quote exists in the data, so nothing is safe to execute.

**D3.** Hard rules, each PASS or FAIL with a reason: `cabin` (ranked BASIC_ECONOMY < ECONOMY < PREMIUM_ECONOMY < BUSINESS < FIRST; lower fails), `refundable` (losing it fails), `bags` (fewer fails), `stops` (more fails), `seats` (fewer than passengers fails), `future_change_fee` (the offer's change fee, converted to the booking's currency, above the old ticket's change fee fails), `exchange_rate` (an offer in another currency with no rate to the booking's currency fails; same currency needs no rate). A schedule change or a carrier change does not fail; each adds an approval flag. (Owner) Reason: scoring trade-offs needs traveler preferences the project does not have. Failing schedule changes would drop a same-day 20-minute shift.

**D4.** Every field is required at the boundary, and the rules only ever see PASS or FAIL. A booking that fails parsing, has more than one segment, has a `totalPaid` that is not passengers times price, departs before the capture time, or has no rate to convert the minimum becomes an `INVALID_DATA` result. An offer that fails parsing, or every copy of a duplicated offer id, is left out and listed in `data_issues`; a duplicated booking reference keeps the first record and lists the rest. Money is parsed from text into `Decimal`. Unknown keys fail parsing, except the documented top-level `_comment` field of each fixture file. Stops, bags and seats must be zero or more. (Owner) Reason: an UNKNOWN third state in every rule was rejected, because the data can be required up front; failing the whole run on one bad record was rejected, because one typo would hide every other result. The parse-don't-validate idea (Alexis King, 2019) is the basis. Changed after critic round 1: "unknown keys are ignored" became fail parsing, because the repo's Python rules require models that forbid extra keys (L3). The documented top-level `_comment` key is the one exception.

**D5.** One minimum saving per booking, 50 USD, read from `config/policy.toml` (A1). For a booking in another currency it is converted through the `ExchangeRates` port and rounded once. The saving after rounding is compared with it. (Owner) Reason: one amount per currency was rejected because the owner wants one baseline. A percentage of the fare was rejected because there is no business input on it yet. A per-passenger minimum undercounts group savings.

**D6.** Exchange rates sit behind an `ExchangeRates` port. The demo adapter reads fixed rates from `config/exchange_rates.toml`, each with a base, a quote, a rate and an `as_of` date, and derives the inverse direction. The demo rate is 1 EUR = 1.1433 USD, dated 2026-07-07 (A2). Each converted amount shows the rate, its direction and that date, nothing else. `AGENTS.md` changes "an exchange rate from the data" to "an exchange rate from the ExchangeRates port"; milestone 10 makes that edit and a DoD item checks it. The sample needs one stored pair, EUR/USD, because the adapter derives the inverse direction. That one entry covers the RT5K8B offer price, its change fee and the 50 USD minimum. (Owner) Reason: refusing different currencies hides a real saving on RT5K8B. Rates hard-coded in Python were rejected, because rates are data and belong in a file. The money pattern (Fowler, Patterns of Enterprise Application Architecture) is the basis.

**D7.** Nominal saving = passengers x (old fare per passenger - offer fare per passenger converted to the booking's currency - change fee of the old ticket per passenger). `Decimal` throughout, rounded half-even to 2 places once, before the minimum check and output. The offer's change fee is a future fee and never enters the formula. (Owner, rounding by the model) Reason: floats drift in money math. Rounding each step compounds the error. Checking the minimum before rounding is wrong: 49.996 prints as 50.00 and would still fail, so the minimum is checked after rounding.

**D8.** Terms: booking, offer, rule check, eligible offer, approval flag, nominal saving, minimum saving, exchange rate, recommendation. Realized saving is named only to say it is not computed. (Owner) Reason: PNR is the identifier of a booking, so it is not the noun for one. The data calls the thing an offer, so offer is used, not fare. Both terms are defined in Context and written to the glossary in milestone 10.

**D9.** Output contract, `schema_version: 1`. Top level: `mode`, `as_of` (the snapshot capture time), `data_issues`, `results`. Each result: `pnr`, `status` (`REBOOK`, `KEEP`, `NEEDS_REVIEW`, `INCOMPLETE_ANALYSIS`, `INVALID_DATA`), `rebook` (true only for `REBOOK`), `decided_by` (`rules` for KEEP, INVALID_DATA and every `none`-mode result; `model` for REBOOK from the model; `safety_check` for NEEDS_REVIEW; `null` for INCOMPLETE_ANALYSIS), `incomplete_reason` (`turn_cap`, `repeated_call`, `bad_final_answer`, `refusal`, `provider_error`; null otherwise), `offer_id`, `nominal_saving` and `approval_flags` (all three for the chosen offer; null or empty for KEEP, INVALID_DATA and INCOMPLETE_ANALYSIS; for NEEDS_REVIEW, the offer the model chose, if any), `best_offer_id` (only when the model's valid choice is not the highest saving), `evaluations` (every offer with its rule results, its saving and the exchange rate it used; empty for INVALID_DATA), `minimum_saving` (in the booking's currency), `confidence`, `reasoning` (built from rule results when rules decide), `invalid_reason` (INVALID_DATA only), and `trace` (model modes only). No `execution_ready` field, because every result goes to a person (D2). Reason: keeping `execution_ready` would be noise, since it is always false. A `NEEDS_DATA` status is not needed, because D4 removed its cause. Consumers break silently when the schema changes without a version. Refined by L1: the rate fields carry lists, not single values, so that every converted amount shows its rate. Nothing reads this output yet, so the change costs nothing. In code, the domain result is a union of frozen types, `Rebook`, `Keep` and `Invalid`; the serializer derives `status`, `rebook` and `decided_by` from the type, so they cannot disagree. In this plan `Status` holds only `REBOOK`, `KEEP` and `INVALID_DATA`, and `DecidedBy` holds only `RULES`; plans 02 and 03 add their members.

**D10.** Layout: `fare_reshop_agent/reshopping/` with `domain/` (and `domain/port/` for the data and rate ports), `orchestration/`, `infrastructure/<technology>/`, `composition/` and `cli/`. `composition/` builds the object graph for each mode (`none`, `openai`, `recorded`, recording). The model port lives in `orchestration/`, because its types are agent-loop concepts, not domain ones. There is no inbound port: the CLI calls one composition function. (Owner) Reason: an `adapters/` folder name was rejected by the owner. An inbound port protocol was rejected because it has one caller, so the seam would be hypothetical. Wiring inside `cli/` was rejected because it mixes argument parsing with object graphs for four modes. The hexagonal architecture idea (Cockburn, 2005) is the basis. In this plan only the `none` graph exists.

**D11.** Booking, offer, money, exchange rate, offer evaluation and recommendation are immutable value objects. There is no aggregate and no write repository. The future Review aggregate is documented, not built. (Owner) Reason: a booking as aggregate root holding the recommendation was rejected, because bookings never change, so there is no rule to protect, and the project does not own that data. The aggregate rule from Vernon's Implementing Domain-Driven Design (rule 1) is the basis for deferring it. The ADR in milestone 10 records this.

**D12.** One data port, `ReshopSource`, with one method that returns a snapshot: bookings, offers, the capture time and data issues. The fixture adapter reads the two JSON files and translates them into domain objects (the anti-corruption layer). Tests use an in-memory adapter, so the seam has two adapters. The policy and rate files are read by the TOML readers in `infrastructure/toml/`, and the fixture file by the JSON reader in `infrastructure/json_fixtures/`. Each reader raises its own typed error with no CLI wording: `JsonFixtureError` and `TomlFileError`, each holding the path, a `FileProblem` (`MISSING`, `UNREADABLE` or `MALFORMED`, defined in `infrastructure/file_problem.py`) and a short fact. `composition/` maps those errors to one `SetupError` (what, why, fix), defined in `composition/setup_error.py`, and `cli/` renders it in the three-line format. `cli/` never imports `infrastructure/`. File positions and parse messages become data issues in the fixture adapter and never reach the domain. Reason: two ports, one per source, were rejected because neither has a second adapter, so the split would be speculative. No port was rejected because the owner asked for swappable sources. The anti-corruption layer idea (Evans, Domain-Driven Design) is the basis. Plan 02 relies on three names from this decision: the reader error types, `SetupError` and its home in `composition/`.

**D13.** Python 3.12 or newer, `uv`, `pydantic` v2 only in `infrastructure/`, `pytest`, `ruff`, `mypy --strict`. `openai` is an optional extra named `live`. No other runtime dependency: tables and color use the standard library. The model's tool arguments and final answer are parsed in `orchestration/` with `json.loads` and explicit checks into frozen dataclasses, because the repo's Python rules keep pydantic in `infrastructure/` and these are three small shapes. All code follows `.claude/rules/python.md`. (Owner) Reason: a standard-library-only fixture reader was rejected because hand-rolled validation of two nested files is error-prone. Pydantic in orchestration was rejected because it breaks the repo's Python rules. The `rich` library for tables was rejected, because the rules allow a dependency only when the standard library cannot do the job. In this plan, `openai` is not added; its extra arrives in plan 02.

**D14.** One local check command, `./scripts/check.sh`, runs `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy` and `uv run pytest -q` in that order, and exits non-zero on the first failure. Every plan's checks run it, and the README documents it. Plan 02 adds `--all-extras` to each of the four commands when the `live` extra lands. Reason: four commands typed into each plan's checks would drift apart, and no single command would gate the repo.

**D15.** CLI: `fare-reshop review` with `--model none|openai|recorded`, `--format json|table` and `--record` (only with `openai`). The default model is `none` until the replay plan lands, then `recorded`. `--record` with any other model is a setup error. Also `fare-reshop doctor` (S7) and `--debug`. Exit codes: 0 done, 1 internal error (a bug; traceback only with `--debug`), 2 setup error (files, policy, missing extra, missing key, failed recording, bad flags, provider authentication), 3 stale recording (reserved for plan 03). Reason: a web UI is out of scope. Separate commands per mode were rejected because they add surface for the same flow. Refined by L7: in this plan only `none` is accepted for `--model`, only `json` is accepted for `--format` until milestone 8 adds `table`, `--record` does not exist yet, and exit code 3 is reserved for plan 03.

**D26.** Docs: `README.md`, `DESIGN.md` with the AI-usage note, `GLOSSARY.md`, `docs/adr/` and `docs/future-work.md`. Each plan writes its own glossary terms and ADRs in its last milestone. The docs plan writes the rest. (Owner) Reason: one long README was rejected because it mixes setup with design. This plan writes `GLOSSARY.md` and one ADR in milestone 10.

**D27.** Scope is the thin slice. Not built: a model-based prefilter, token and cost budgets, and a fixed six-tool set. `DESIGN.md` says why. (Owner) Reason: each of these was argued down in the grilling, and building them would be too large for the time.

**D28.** Plans are tracked in the public repo. Every tracked file, commit message and branch name passes the local leak hooks. (Owner) Reason: keeping plans private loses the record of how the work was done. Milestone 10 and the Definition of done apply the denylist check to every file this plan writes.

**D29.** The review runs as of the snapshot's capture time, taken from the offer data. There is no clock port. A booking departing before that time is `INVALID_DATA` (D4). Reason: a system clock was rejected, because every fixture departure is before today, so every booking would be invalid. A clock port was rejected, because it would have one real value and so the seam would be hypothetical.

**D31.** First-run experience (S7): `./start.sh` changes to its own folder first, checks for `uv`, asks before installing anything, then runs `uv sync`, `doctor` and the default review. `fare-reshop doctor` lists every check with its fix command. Every CLI error prints what went wrong, why, and the fix, with no traceback unless `--debug`. `NO_COLOR` and whether standard output is a terminal are read in `composition/`, which passes a color setting to `cli/`. Each plan adds the doctor checks for what it introduces. (Owner) Reason: a silent install was rejected, because the owner forbids changes without confirmation. A Makefile was rejected because it is not on every machine and hides the real commands. README-only steps were rejected because a reader who skips the README then hits a traceback. The rustup and Homebrew installers ask before they change the system; that is the model.

**D32.** The booking reference is a `NewType` named `BookingRef`, and offers use `OfferId`, as the repo's Python rules require. Output keeps the field name `pnr` because the source data uses it. Reason: a plain string would let a booking reference go where an offer id belongs.

**D34.** A second configured data set, `scenarios`, in `fixtures/scenarios/pnrs.json` and `fixtures/scenarios/fares_feed.json`: the same schema as the real fixtures, made-up demo bookings and offers, a top-level `_comment` that says they are made-up demo scenarios, the same capture time (2026-07-08T09:00:00Z), departures after it and USD throughout. The CLI takes `--data sample|scenarios`, default `sample`. The value names a configured data set and never a free path; an unknown value is an argparse error with exit code 2 and the three-line error format. Expected results are in the scenario table in Context. (Owner) Reason: a free path to any file lets a run read data nobody reviewed, and the recording would not know which data it covers. A combined data file would change the sample oracle. Scenarios inside the real fixtures would change the owner's sample data.

**L1. Output shape for this plan.** The output is printed as JSON with an indent of 2 and the default separators, so that each key appears on its own line as `"key": value`. The top-level keys, in this order: `schema_version` (1), `mode` (the text `none`), `as_of` (the capture time as the file writes it, UTC with a `Z` suffix), `data_issues` and `results`. Each data issue has `kind`, `id` and `reason`. The kinds are `booking_rejected`, `offer_rejected`, `offer_duplicate` and `booking_duplicate`. The `id` is the record's own identifier when it can be read, and otherwise its position in the file, written like `offers[3]`. Data issues keep file order. Each result has these keys in this order: `pnr`, `status`, `rebook`, `decided_by`, `incomplete_reason` (always null in this plan), `offer_id`, `nominal_saving`, `approval_flags`, `confidence` (always null in this plan), `reasoning`, `minimum_saving`, `exchange_rates`, `invalid_reason` and `evaluations`. Results are sorted by `pnr`. The keys `best_offer_id` and `trace` belong to model modes and are not emitted in this plan. Each evaluation has `offer_id`, `rules` (in the fixed order cabin, refundable, bags, stops, seats, future_change_fee, exchange_rate; each with `rule`, `result` as PASS or FAIL, and `reason`), `nominal_saving` (null when no rate exists), `exchange_rates` (one entry for each conversion made, the price and the change fee, or an empty list when neither needs one), and `approval_flags`. Evaluations are sorted by `offer_id`. A money value is an object with `amount` as text with two decimal places and `currency`. The `exchange_rates` lists at result level hold the conversions on the booking side, and their entries have `use` (`minimum_saving` or `booking_fee`). The entries in each evaluation's list have `use` set to `offer_price` for the price or `offer_change_fee` for the change fee. Every rate entry has `rate` as text, `direction` as text such as `1 EUR = 1.1433 USD`, and `as_of` as ISO text in the form `YYYY-MM-DD`. The direction always names the stored pair, even when the conversion divides by the rate. The reason is that the stored pair is the demo rate the owner expects to see, and a reader can check it against the file. Reason for lists over single values: D6 requires every converted amount to show its rate, and the booking fee and the minimum can each use their own rate.

The output has one status-specific shape for each of the three statuses this plan emits. A REBOOK result has an offer id, a nominal saving, an approval flags list (possibly empty), reasoning, a minimum saving, and at least one evaluation; its `invalid_reason` is null. A KEEP result has a null offer id, a null nominal saving, an empty approval flags list, reasoning, a minimum saving, and the evaluations for every offer on the route (an empty list when there is none); its `invalid_reason` is null. An INVALID_DATA result has a null offer id, a null nominal saving, an empty approval flags list, null reasoning, a null minimum saving, an empty exchange rates list, an empty evaluations list, and the `invalid_reason` text. For REBOOK and KEEP the `exchange_rates` list is empty when the booking is in USD. Every result of this plan has `decided_by` set to `rules`, `confidence` null and `incomplete_reason` null.

**L2. Money and rounding.** A `Money` is built from a `Decimal`, from text, or from an integer. Text and integers are converted to `Decimal` at construction. A float or a bool is refused with a `TypeError`, so no float enters money math. The nominal saving is computed at full `Decimal` precision and rounded half-even to 2 places once, at the end. Half-even means a value exactly halfway rounds to the nearest even last digit: 2.345 becomes 2.34, and 2.355 becomes 2.36. The helper that does this is the only rounding in the domain. The converted minimum is also rounded once, to 2 places, after its conversion. Intermediate conversions are not rounded. Money with a different currency is handled as `.claude/rules/python.md` requires: adding raises, and comparing (equality and ordering) raises. Code that needs to know whether two amounts share a currency compares their currencies first. Rules never compare raw amounts in two currencies: they convert through the `ExchangeRates` port first, and a missing rate is a typed rule result (FAIL with a reason, or `INVALID_DATA` for the minimum), never an exception. The raise on `Money` is only a guard for code that skipped that step; `Money` holds no rates, so it cannot convert by itself. A saving meets the minimum when the rounded saving is greater than or equal to the minimum, so equality passes. A negative amount in a fixture (a price or fee below zero) is invalid data for that record. Money text in output is the amount with exactly two decimal places (`80.00`, `-90.00`, `363.21`), followed by a space and the currency code in the table, and as an object in JSON. An amount that rounds to zero prints as `0.00`, never as `-0.00`.

**L3. Data acceptance rules.** A record must match the fixture shape exactly. The pydantic models for the two fixture files forbid unknown keys and are frozen. The one exception is the top-level `_comment` key of each file, which is declared so that it is accepted and ignored. Inside a record, `_comment` is an unknown key. D4 and the Python rules now agree, so no conflict remains. A record whose identifier is unreadable (a booking without a readable `pnr`, an offer without a readable `offerId`) is listed as a data issue with its position, because there is no key to report it under. Parser messages stay in the fixture adapter: it turns each one into a short reason text, so no parser error or parser type reaches the domain. A booking with a readable `pnr` and any other problem becomes an `INVALID_DATA` result with the reason. The booking checks are these: passengers is a whole number of at least one; stops and baggage pieces are zero or more; money amounts are not negative; the currency of the ticket price and of the total paid match; the itinerary has exactly one segment; `totalPaid` equals passengers times the price per passenger; the cabin, the money and the times parse. Problems found by the value objects themselves are caught in the adapter and turned into a rejected booking. The departure check and the rate checks run in orchestration, because they need the capture time and the rate port. A departure is before the capture time when its local clock text, read as a naive time, is earlier than the capture time converted to naive UTC. Equal times are not before. The fixture departure texts have no time zone, so this comparison is an assumption (see the risks section). An offer with a readable `offerId` and any other problem is listed under `data_issues` with kind `offer_rejected`. The offer's stops, baggage pieces and seats must be zero or more. Every copy of a duplicated offer id is left out and listed with kind `offer_duplicate`. For a duplicated booking reference, the first record is kept and each later copy is listed with kind `booking_duplicate`. An offer whose change fee is in another currency than its price is not rejected: the fee is converted through the `ExchangeRates` port when the future change fee rule runs (L4), and a missing rate fails that rule. A booking whose change fee has a different currency from its ticket price is converted to the ticket currency with the rate port (A6). If no rate exists, the booking is `INVALID_DATA` with "no exchange rate from <fee currency> to <ticket currency>". A missing pair is never a crash: that booking gets the `INVALID_DATA` result, and the other bookings and offers still run. The reason string for the minimum is exact: "no exchange rate from USD to <currency>".

**L4. Rule semantics and decision.** The booking's cabin is the cabin on its ticket, and the offer's cabin is the offer's cabin. Cabin ranks are BASIC_ECONOMY below ECONOMY below PREMIUM_ECONOMY below BUSINESS below FIRST; an offer ranked lower than the booking fails. The refundable rule fails when the booking is refundable and the offer is not. The bags rule fails when the offer includes fewer checked pieces than the booking. The stops rule fails when the offer has more stops than the booking. The seats rule fails when the offer's available seats are fewer than the booking's passengers. The future change fee rule converts the offer's change fee per passenger to the booking's currency and fails when it is greater than the booking's change fee per passenger, which is also in the booking currency. The exchange rate rule fails when the offer's price or its change fee is in another currency than the booking and no rate exists. When the price has no rate, the nominal saving is null and the future change fee rule also fails. When only the change fee has no rate, the future change fee rule fails with a reason that names the missing rate, and the saving is still computed, because the formula never uses the offer's fee. Each approval flag is set by a fact, not by a rule. The schedule-change flag, named `schedule_change`, is set when the offer's departure or arrival text differs from the booking's. The carrier-change flag, named `carrier_change`, is set when the carrier code differs. Flags are sorted by name, and they never change a rule's result. An offer is eligible when all seven results are PASS, the nominal saving is not null, and the rounded saving is at least the minimum. The minimum is the policy's 50.00 USD converted to the booking currency and rounded once. Among eligible offers, the chosen one has the highest saving, and ties are broken by the lower offer id, compared as text. An offer on the route is matched when its origin, destination and departure date equal the booking's, using the departure date of the booking's segment. The rules-only mode sets `confidence` to null.

Reasoning text is built from fixed templates, and the templates are the only text a reader sees for these results. A REBOOK reads: "Rebook to {offer}. It passes all seven rules and saves {saving}, which meets the minimum of {minimum}." KEEP has three cases, checked in this order. (a) No offer on the route and date: "No offers on this route and date." (b) At least one offer passes all seven rules, but none reaches the minimum: "No offer reaches the minimum. {offer} passes all seven rules, but its saving of {saving} is below the minimum of {minimum}." Here {offer} is the offer with the highest saving among those that pass all seven rules, ties broken by the lower offer id. (c) No offer passes all seven rules: "No offer passes every rule. " followed by one clause for each offer that lists its failed rule names, for example "OF-2001 fails: cabin, bags." INVALID_DATA carries the reason from L3 or L4 and no reasoning. Amounts in the text use the output money format of L2, with the currency code.

**L5. Ports and the snapshot.** The `ReshopSource` port is a `Protocol` in `domain/port/`, with one method, `read_snapshot`, that returns a `ReshopSnapshot`. The snapshot is a frozen value holding the capture time as an aware UTC datetime, a tuple of bookings where each entry is either a valid `Booking` or a `RejectedBooking` (a booking reference and a reason), a tuple of valid `Offer` values, and a tuple of data issues. The `ExchangeRates` port is a `Protocol` in `domain/port/` with one method, `find_rate`, that takes two currency codes and returns either an `ExchangeRate` or an explicit `NoRate` value. The method must never return a bare `None`. The `ExchangeRate` value object stores the base, the quote, the rate as a `Decimal` (read from text), and the `as_of` date. It converts an amount through a method named `convert`, in either direction: when converting from the quote to the base it divides by the rate, and when converting from the base to the quote it multiplies. The port answers for a pair stored in either direction. The domain imports nothing from `infrastructure/`, `composition/` or `cli/`, and nothing reads the clock.

**L6. Layout and configuration files.** The importable package is `fare_reshop_agent`, with the business package `reshopping` inside it, as D10 requires. Inside `reshopping`: `domain/`, `domain/port/`, `orchestration/`, `infrastructure/` with one folder per technology (`infrastructure/json_fixtures/` for the fixture JSON reader, and `infrastructure/toml/` for the policy and rate readers, which share the one TOML technology), `composition/` and `cli/`. The console script `fare-reshop` in `pyproject.toml` points at the entry function in `cli/`. The data and config files are read relative to the working directory, which is the repo root for the normal run. Their paths are `fixtures/pnrs.json`, `fixtures/fares_feed.json`, `config/policy.toml` and `config/exchange_rates.toml`. There are no path flags. `composition/` is the only code that reads the environment, and in this plan it reads only `NO_COLOR` and the terminal check. The rate file stores each rate as a TOML string such as `rate = "1.1433"`, never as a number, because TOML numbers become binary floats. The `as_of` value of each rate is an ISO date string such as `"2026-07-07"`. The policy file holds the minimum saving as an amount string and a currency code, `"50.00"` and `"USD"`. Both TOML files reject unknown keys, and each may carry a top-level `_comment` key.

**L7. Command-line behavior.** The `review` subcommand accepts `--model` with the single value `none`. Its `--format` option accepts `json` only until milestone 8, which adds `table`; a value not yet built is refused, never accepted silently. The default format is `json`. The `doctor` subcommand runs the checks in milestone 9. The `--debug` flag is accepted after any subcommand. Every failure prints three lines to standard error: a line starting with `error:` that says what went wrong, a line starting with `reason:` that says why, and a line starting with `fix:` that holds a command or an instruction. This includes argument errors: argparse errors exit with code 2 and print in the same three-line format, with the fix line naming the help command. The one exception is an unknown `--data` value, whose fix line names the valid values (milestone 11), because that is the more direct fix. File-level problems (a missing or unreadable file, invalid JSON, a missing top-level key, a bad policy or rate file) use the setup exit code 2. `composition/` builds their `SetupError` from the reader error, with the path in `error`. The `reason` says why: for a missing file, that the file does not exist and that paths are read relative to the working directory, which must be the repo root. The `fix` for every file-level problem runs from the repo root and inspects the file without changing it: "run from the repo root, then inspect with `git status` and `git diff -- <path>`". No fix line discards a change. Unexpected internal errors use exit code 1, and their fix is `uv run fare-reshop review --debug`. The entry point is the only place that catches broad exceptions. With `--debug`, the full traceback is printed after the three lines. Without it, no traceback is printed. Exit codes: 0 for success, including an empty snapshot; 2 for setup errors and bad arguments; 1 for internal errors. Exit code 3 is reserved for plan 03. The table format prints the columns PNR, STATUS, OFFER, SAVING and REASON, with `-` in any empty cell. The saving column shows the money as the amount, a space and the currency code. The REASON cell is the first sentence of `reasoning` for KEEP, the `invalid_reason` text for INVALID_DATA, and `-` for REBOOK. The REASON column is never truncated. Data issues print after the table, one line each. Color is used only when standard output is a terminal and the `NO_COLOR` variable is not set, and it applies only to the status word. `composition/` reads `NO_COLOR` and the terminal check, and passes a two-value color setting (a `StrEnum` with `ON` and `OFF`, defined in `composition/`) to `cli/`, which never reads the environment. Output is printed only from `cli/`.

**L8. First-run script and doctor.** `start.sh` is a POSIX shell script at the repo root, executable and committed with that mode. It works in this order. It first changes to the folder that holds the script, so every command runs from the repo root. Then it checks whether `uv` is on the path. If not, it prints what uv is, the official install command confirmed against the uv installation page at implementation time, and the question `Install uv now? [y/N]`. Only the answer `y` runs the install. Any other answer, or end of input, prints the manual command and exits with code 1. After an install, it checks for `uv` again, and if it is still not found, it says to open a new terminal and run the script again, then exits with code 1. Next it asks `Run uv sync now? [y/N]` with the same rules, and on a no, it prints `uv sync` as the manual step and exits with code 1. It then runs `uv run fare-reshop doctor` and stops with that exit code if the doctor fails. Last, it runs `uv run fare-reshop review`. It never runs an install or a sync without a `y` answer. The doctor checks, one line each, starting with `[ok]` or `[FAIL]`: the `fare_reshop_agent` package and `pydantic` import; each fixture and config file is readable. The Python version is not a doctor check, for the reason given in S7. The checks run in `composition/`, which returns their results, and `cli/` renders them. Each failed check is followed by a line starting with `fix:`. The fix for an import problem is `uv sync`. The fix for an unreadable file is the inspection instruction of L7, which never discards a change. The doctor exits 0 when every check passes and 2 otherwise. Doctor output is a status report, not an error, so the three-line error format does not apply to it.

**L9. Test layout.** There are two test modules plus `tests/conftest.py`. `tests/test_review_rules.py` covers the domain, the adapters and the orchestration. `tests/test_cli.py` covers the command line, the doctor and `start.sh`. `tests/conftest.py` turns on the `decimal.FloatOperation` trap for the whole test session, so that any float entering money math raises. Tests are plain functions with bare asserts, use `pytest.raises` with `match` for errors, and use `@pytest.mark.parametrize` for case tables. Money is compared exactly. Test fakes implement the two ports inside the test files and are in-memory. Adapter tests run against the real repo files, or against copies in `tmp_path`. All tests run offline. Mypy strict covers the package and the tests.

**L10. Plan-level alternatives that were not chosen.** The project does not put every test in one file, because the index names two files and the split follows the seams. The command line does not take path flags, because that adds surface the index does not ask for. The domain does not import pydantic, because the repo's Python rules keep it in `infrastructure/`. The rate file is not a Python module, because D6 says rates are data.

**L11. AGENTS.md wording.** Milestone 10 changes two sentences in `AGENTS.md`. The sentence in the data section that says "an exchange rate from the data" becomes "an exchange rate from the ExchangeRates port" (D6). In the project overview, the sentence that says "how confident it is, and the net saving after fees" becomes "and the nominal saving after the change fee", and the words "how confident it is" are removed, because the rules-only mode gives no confidence. The live model plan adds the confidence wording back when its mode lands. Reason: the overview would otherwise promise a net figure and a confidence that this plan does not produce.

**L12. Data set selection (milestone 11).** `composition/` maps each data set name to its folder: `fixtures/` for `sample` and `fixtures/scenarios/` for `scenarios`. Each folder holds the same two file names, `pnrs.json` and `fares_feed.json`, and the policy and rate files are shared. The fixture adapter reads the two fixed names from the folder it is given; if milestone 4 built it from two file paths, only the composition call changes. The output does not name the data set: the D9 output shape stays as it is, and `mode` is the only mode field. A data set name outside the configured set is refused by the parser before any file is read.

## Alternatives considered

The index's own rejected options are listed under each decision above. This plan adds these choices. A path flag for the data and config files was rejected: it adds command-line surface that no story asks for, and the working directory is the repo root in every documented run. A single shared test file was rejected: the index names two test files, and the split keeps the rule tests apart from the command-line tests. Reading the rate as a number in TOML was rejected: TOML numbers are read as binary floats, which breaks the exact-money rule. Pydantic models that allow extra keys were rejected: D4 now says unknown keys fail parsing, and the Python rules require forbidding them. Replacing pydantic with the standard library in the fixture adapter was proposed in critic round 1 and dismissed: the owner approved pydantic (D13), and the Python rules name it as the infrastructure parser. The prototype's fallback path (milestone 3) keeps pydantic for validation and uses the standard JSON parser only to read the number text. A checked-in network call to fetch rates was rejected: rates are data for this plan, and the offline rule applies. Making the `none` decision choose by the first eligible offer, instead of the highest saving, was rejected: S1 step 4 names the highest saving. Putting the Python-version check in the doctor was rejected for the reason in S7. Letting `--format table` or other unbuilt values pass silently until their milestone was rejected, because a silent accept is a failure that looks like success.

## Invariants, risks and open questions

Invariants that must hold at every step. Every number is an exact `Decimal`, and no float enters money math, which the test trap enforces. The rules only see PASS or FAIL. A booking or offer that cannot be parsed never reaches a rule. The same input produces the same bytes of output, because results and evaluations are sorted, rule order is fixed, and nothing reads the clock or the set order. No code path writes to a booking, a fare or any file the user does not ask for. The run needs no network, no environment variable and no API key. Each domain value object checks its own invariants when it is built.

Risks and mitigations. The main risk is pydantic turning JSON numbers into binary floats or rounding their text. The mitigation is milestone 3, which decides between the two parse paths before any fixture model is written, and the test that reads a price with many significant digits and expects the same digits back (`test_fixture_money_is_read_as_exact_decimal`). The second risk is a rate file that stores a float. The mitigation is the rule that the rate is a TOML string, and the test that the adapter returns the exact text (`test_rate_file_rate_is_read_as_exact_text`). The third risk is that a real record carries a key the fixtures do not have, and the whole record is rejected. The mitigation is the test that a record with an extra key becomes a rejection, and the test that `_comment` is accepted only at the top level. The fourth risk is the naive time comparison in L3. The mitigation is that no fixture departure is near the capture time, and a test pins the strict "before" rule (`test_departure_before_capture_is_invalid_data`). The fifth risk is that the official uv install command changes. The mitigation is to read the uv docs before writing `start.sh`, and to name the command in the script's output only once. The sixth risk is Windows. This plan's `start.sh` needs a POSIX shell, and the Windows steps belong to the README, which plan 04 writes. The gap is named here, so the owner knows that a Windows reader has no written steps until plan 04 lands. The seventh risk is the demo rate's date. The rate is dated 2026-07-07, the last reference rate published before the 2026-07-08T09:00:00Z capture time, so it was public when the fares were captured; the output shows its date.

Retry and rollback. Every milestone's steps are safe to run twice. `uv sync` and the check commands are repeatable. File writes overwrite the same content. `start.sh` asks before each change, so a second run only repeats the questions. To roll back a milestone, revert its commit; no later data depends on a partial state, because nothing is stored.

Assumptions the plan proceeds on, from the index's assumption table:

- A1: One minimum saving, 50 USD, converted to the booking's currency (43.73 EUR at the demo rate). The owner confirmed it. It drives D5 and the expected results table.
- A2: The demo rate is 1 EUR = 1.1433 USD, the ECB euro reference rate for 7 July 2026, dated 2026-07-07 (owner answer, 2026-11-02). It is the last rate published before the fare snapshot's capture time (2026-07-08T09:00:00Z), because the ECB publishes around 16:00 CET, so the rate was public when the fares were captured. It is a fixed demo value, not a live quote. Plans name the source in A2 only, and the public docs name none. It drives D6 and the RT5K8B result. Changing the rate changes the RT5K8B saving and the count of rate lines in the DoD.
- A4: Replaced by S7 and D31. The repo does not assume `uv`; `./start.sh` finds it missing and asks before installing it. Readers use macOS or Linux; Windows readers follow the uv commands in the README, which plan 04 writes.
- A6: The owner confirmed that a booking's change fee is in the same currency as its ticket price, as in all five fixtures. If not, the fee is converted too, as L3 specifies. It drives D7.

Open questions. None block this plan. The naive time comparison (L3) is the only one that may need an owner answer later, when real feeds carry time zones.

## Milestones

### Milestone 1 - Project setup and local checks

Goal: a clean clone runs `uv sync`, `./scripts/check.sh` passes, and the `fare-reshop` command prints its help.

Work: create `pyproject.toml` at the repo root with the project name, Python 3.12 as the minimum (`requires-python`), the package `fare_reshop_agent`, and the console script `fare-reshop` that points at the entry function in `fare_reshop_agent/reshopping/cli/`. Add `pytest`, `ruff` and `mypy` as development dependencies with `uv add --dev`. Configure ruff and mypy in `pyproject.toml`, with mypy in strict mode and covering the package and the tests. Create `tests/conftest.py`, which turns on the float trap described in L9 for the whole session. Create `tests/test_cli.py` with the one test named below. Create the `fare_reshop_agent/reshopping/cli/` package with an entry function that builds an argument parser with the program name `fare-reshop` and prints its help when no subcommand is given. Commit `uv.lock`, which `uv` generates; do not write it by hand. Create `scripts/check.sh`, a POSIX shell script that changes to the repo root, sets `set -eu`, and runs these four commands, one per line and in this order: `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`, and `uv run pytest -q`. The first failing command stops the script with its exit code. Make the file executable and commit it with mode 755.

Seam: the installed script, run as a subprocess, as described in Context. The test is `test_console_entry_point_prints_help` in `tests/test_cli.py`. It fails before the entry point exists and passes after.

Proof: the DoD items labeled CLI entry, Check script and Checks green pass. The last of them runs `./scripts/check.sh`, and its pytest step reads `1 passed`.

### Milestone 2 - Domain value objects and review rules

Goal: the domain can decide one booking against one offer, with exact money math, the seven rule checks, the minimum saving, eligibility and the choice of the best eligible offer. It reads no file and prints nothing.

Work: under `fare_reshop_agent/reshopping/domain/`, add these immutable value objects, each a frozen, slotted, keyword-only dataclass that checks its own invariants when built: `Currency` (three uppercase letters), `Money` (a `Decimal` amount and a currency; it accepts a `Decimal`, text or an integer, refuses a float or a bool, and follows the currency rules of L2), `Cabin` (a `StrEnum` with the five values and their ranks), `BookingRef` and `OfferId` (`NewType` names as D32 requires), `Booking` (one segment, passengers, ticket money, the total-paid invariant from L3, and the departure text, which must parse as a naive time), `Offer` (route, times, carrier, cabin, refundable flag, checked pieces, stops, seats, and a price and a change fee, each with its own currency, with stops, baggage pieces and seats zero or more), and `ExchangeRate` (described in L5). Add the two ports in `domain/port/` as `Protocol` classes: `ExchangeRates` with `find_rate`, and the `ReshopSource` port with `read_snapshot` and its snapshot value types, so that the next milestones only add adapters. Add `RuleName` (a `StrEnum` with the seven names in L4), `RuleResult` (PASS or FAIL with a reason), `OfferEvaluation`, `ReviewPolicy` (holding the minimum saving as `Money` in USD), `Status` (a `StrEnum` with REBOOK, KEEP and INVALID_DATA, as D9 says for this plan), `DecidedBy` (a `StrEnum` with RULES only), and `Recommendation`, a union of the frozen types `Rebook`, `Keep` and `Invalid` (D9). Add three public domain functions. `evaluate_offer(booking, offer, rates)` returns an `OfferEvaluation`. `convert_minimum(policy, currency, rates)` returns the minimum as `Money` in the given currency, rounded once, or a `NoRate` value. `decide(booking, evaluations, minimum)` returns the recommendation under the eligibility and choice rules of L4. Rounding is a single named helper that applies the rule in L2. Do not reference pydantic, json or files in this milestone.

Seam: `tests/test_review_rules.py`, calling the three public domain functions with a test fake of the `ExchangeRates` port that holds a small in-memory table of rates. Tests build the booking and the offer in code with the values of the sample records (QX7T2A for the booking, OF-1001 for the offer, unless the test says otherwise) and change one field per test. This is prior art for every later test in the file.

Assertions. Each named test checks the exact value below, so a stub body cannot pass. `test_offer_in_lower_cabin_is_rejected` sets the offer cabin to BASIC_ECONOMY; the cabin result is FAIL with a non-empty reason, and the offer is not eligible. `test_losing_refundability_fails_refundable_rule` sets the booking refundable and the offer not; the refundable result is FAIL and the other six are PASS. `test_fewer_bags_fails_bags_rule` sets the offer to 0 checked pieces against the booking's 1; the bags result is FAIL. `test_extra_stop_fails_stops_rule` sets the offer to 1 stop against 0; the stops result is FAIL. `test_too_few_seats_fails_seats_rule` uses 2 passengers and an offer with 1 seat; the seats result is FAIL. `test_higher_future_change_fee_fails_rule` sets the booking fee to 100.00 USD and the offer fee to 100.01 USD; the future_change_fee result is FAIL. `test_equal_future_change_fee_passes` uses an offer fee of 100.00 USD; that result is PASS. `test_schedule_change_adds_approval_flag_without_failing` sets the offer departure to 08:20 against the booking's 08:00; the flags equal `("schedule_change",)` and all seven results are PASS. `test_carrier_change_adds_approval_flag_without_failing` sets the offer carrier to UA against the booking's AA; the flags equal `("carrier_change",)` and all seven results are PASS. `test_qx7t2a_nominal_saving_is_80_usd` evaluates QX7T2A against OF-1001; the nominal saving equals `Decimal("80.00")` in USD. `test_lm9p4c_saving_is_minus_90_usd` uses 2 passengers at 350.00 USD with a 75.00 USD fee against OF-2001 at 320.00 USD; the nominal saving equals `Decimal("-90.00")` in USD. `test_minimum_is_checked_after_rounding` uses a booking price of 100.00 USD with a zero fee and an offer price of 50.004 USD with a zero fee; the saving before rounding is 49.996, the rounded saving equals `Decimal("50.00")`, and the offer is eligible against the 50.00 USD minimum. `test_money_rejects_float_input` passes `80.0` as the amount and expects a `TypeError`. `test_money_rejects_bool_input` passes `True` as the amount and expects a `TypeError`. `test_money_accepts_text_and_int` builds `Money("80.00", USD)` and `Money(80, USD)`; both amounts are `Decimal` values and the two values are equal. `test_adding_two_currencies_raises` adds 1 USD and 1 EUR and expects a `ValueError`. `test_ordering_two_currencies_raises` compares 1 USD with 1 EUR using `<` and expects a `ValueError`. `test_equality_across_currencies_raises` compares 50 USD with 50 EUR and expects a `ValueError`. `test_offer_in_other_currency_without_rate_fails_exchange_rate_rule` gives the offer a price of 300 EUR against a USD booking with an empty rate table; the exchange_rate result is FAIL and the nominal saving is absent. `test_offer_in_other_currency_with_rate_uses_inverse_direction` uses the RT5K8B booking (2200 EUR, fee 0 EUR) against OF-3001 (2100 USD, fee 0 USD) with the table holding EUR/USD 1.1433; the nominal saving equals `Decimal("363.21")` in EUR, and the price rate line's direction is "1 EUR = 1.1433 USD". `test_minimum_saving_in_eur_is_43_73` converts 50 USD to EUR with the same table; the result equals `Decimal("43.73")` in EUR. `test_exchange_rate_converts_in_both_directions` uses the stored EUR/USD 1.1433; converting 1.1433 USD to EUR gives exactly 1 EUR, and converting 1 EUR to USD gives exactly 1.1433 USD. `test_booking_total_paid_mismatch_raises` builds a booking with 2 passengers, a price of 350.00 and a total paid of 700.01; it expects a `ValueError`. `test_recommendation_picks_highest_saving_then_lower_offer_id` gives three eligible offers, OF-1002 at 90.00, OF-1001 at 90.00 and OF-1003 at 120.00; `decide` chooses OF-1003, and with OF-1003 removed it chooses OF-1001. `test_offer_change_fee_never_enters_nominal_saving` runs OF-1001 with an offer fee of 0.00 and again with 100.00; the nominal saving is 80.00 USD both times. `test_offer_change_fee_in_other_currency_is_converted` gives the offer a fee of 100.00 EUR with the table holding EUR/USD 1.1433 against a USD booking with a 100.00 USD fee; the offer fee becomes 114.33 USD, the future_change_fee result is FAIL, and the fee's rate line direction is "1 EUR = 1.1433 USD". `test_fee_without_rate_fails_future_fee_rule` gives the offer a fee of 100.00 EUR with an empty table against a USD booking; the future_change_fee result is FAIL with a reason that names EUR and USD, and the nominal saving is still 80.00 USD for OF-1001's 300.00 USD price. `test_float_trap_rejects_decimal_from_float` calls `Decimal(0.1)` and expects `decimal.FloatOperation` from the trap.

Proof: the DoD item "Domain rule names" lists the 28 names of this milestone and expects `28`. The Checks green item confirms the file passes.

### Milestone 3 - Prototyping: exact money text through pydantic

Goal: decide, before any fixture model is written, whether pydantic keeps the exact text of a many-digit JSON price when the field is a `Decimal`. The decision is recorded in this plan, and milestone 4 follows it.

Work: from the repo root, run `uv add pydantic`, which adds the runtime dependency. Read the installed version with `uv run python -I -c "import importlib.metadata as m; print(m.version('pydantic'))"`, and read the pydantic documentation for that version on how JSON numbers become `Decimal` values. Create an empty scratch directory with `mktemp -d`, outside the repo, and write one script there. The script sets the `decimal.FloatOperation` trap in the current decimal context. It defines a model with `extra="forbid"` and `frozen=True` and one field, `amount` of type `Decimal`. Path one: it parses the JSON text `{"amount": 1234567.123456789012345}` with `model_validate_json`, and checks that `str(model.amount)` equals `1234567.123456789012345` and that no `FloatOperation` was raised. Path two: it reads the same text with `json.loads(text, parse_float=Decimal)`, validates the resulting object with `model_validate`, and makes the same two checks. Run the script from the repo root with `uv run python -I <script path>`.

Promote path one when its check passes. Discard it when its check fails, and then milestone 4 uses path two: `json.loads(text, parse_float=Decimal)` followed by pydantic validation of the result, so pydantic still validates every record. Record the decision as one bullet in Surprises & Discoveries that starts `- Prototype result: promote` or `- Prototype result: discard`, with the installed pydantic version and the exact text the chosen path printed. Add the matching line to the Decision Log.

Seam: none. This is a throwaway script outside the repo. It is not committed.

Proof: the DoD item "Prototype result recorded" passes.

### Milestone 4 - Fixture JSON adapter for the source port

Goal: the two fixture files load into domain values, and a bad record becomes a rejection or a data issue in the result instead of a crash.

Work: under `fare_reshop_agent/reshopping/infrastructure/json_fixtures/`, add frozen pydantic models for `pnrs.json` and `fares_feed.json`, each forbidding extra keys except the declared top-level `_comment` (L3). Parse with the path milestone 3 recorded, and keep every money amount exact. The reader converts each record into a domain value. A domain raise becomes a rejected booking or a rejected offer, and the reader applies the duplicate rules and writes the data issues, as L3 and L5 describe. The adapter implements `read_snapshot` of the `ReshopSource` port. A missing file, an unreadable file, invalid JSON or a missing top-level key raises `JsonFixtureError`, which holds the path, a `FileProblem` and a short fact written by the adapter (D12). Create `fare_reshop_agent/reshopping/infrastructure/file_problem.py` with the `FileProblem` StrEnum (`MISSING`, `UNREADABLE`, `MALFORMED`), which milestone 5 also uses. Parser messages stay in the adapter: each one becomes a short fact, and no parser error or parser type reaches the domain.

Seam: the fixture adapter, called directly from `tests/test_review_rules.py`, reading the real repo files for the sample checks and `tmp_path` copies for each bad-record case. This is prior art for the rejection tests later.

Assertions. `test_fixture_money_is_read_as_exact_decimal` copies the fixtures and changes one price to 1234567.123456789; the money's amount equals `Decimal("1234567.123456789")` exactly. `test_malformed_booking_is_rejected_with_reason` changes one booking's passengers to the text "two"; the snapshot holds one `RejectedBooking` with that booking's reference and a non-empty reason, and the other four bookings load. `test_multi_segment_booking_is_rejected` gives one booking two itinerary segments; that booking is rejected with a reason that names the segments. `test_bad_offer_is_listed_in_data_issues` sets one offer's price to the text "abc"; the data issues hold one entry of kind `offer_rejected` with that offer's id. `test_duplicate_offer_ids_are_all_left_out` duplicates an offer id; neither copy is in the offers, and two `offer_duplicate` issues appear. `test_duplicate_booking_keeps_first_record` duplicates QX7T2A with a different price in the second copy; the first copy is kept, and one `booking_duplicate` issue appears. `test_unknown_field_rejects_that_record` adds a key named `notes` to one booking; that booking is rejected. `test_comment_key_is_ignored` reads the real files; the snapshot holds five bookings, six offers and no data issues. `test_negative_stops_bags_or_seats_rejects_record` is parametrized over stops, bags and seats, each set to -1 in turn; the record is rejected each time. `test_comment_inside_a_record_is_unknown_key` adds a `_comment` key inside one offer; that offer is listed as `offer_rejected`. `test_missing_fixture_raises_json_fixture_error` points the adapter at a path that does not exist; the error carries `FileProblem.MISSING`.

Proof: the DoD item "Fixture and rate names" lists the 14 names of milestones 4 and 5 and expects `14`.

### Milestone 5 - TOML rate and policy readers

Goal: the rate file and the policy file load into domain values, and a bad file raises a typed error that composition can map.

Work: under `fare_reshop_agent/reshopping/infrastructure/toml/`, add the rate reader, which implements the `ExchangeRates` port, and the policy reader. The rate reader reads `config/exchange_rates.toml`, where each entry has a base, a quote, a rate as a text value, and an `as_of` date string, and it answers for a pair stored in either direction (L5). The policy reader reads `config/policy.toml` and returns the minimum saving as `Money` in USD inside a `ReviewPolicy`. Both readers reject unknown keys and allow a top-level `_comment` (L6). A missing file, an unreadable file or malformed content raises `TomlFileError`, which holds the path, a `FileProblem` and a short fact (D12). Create `config/exchange_rates.toml` with the demo rate EUR/USD, `"1.1433"`, dated `"2026-07-07"`, and create `config/policy.toml` with the minimum saving `"50.00"` in `"USD"`. Nothing calls the policy reader until composition in milestone 7.

Seam: the rate reader and the policy reader, called directly from `tests/test_review_rules.py`, reading the real config files for the sample checks and `tmp_path` copies for the bad-file cases.

Assertions. `test_rate_file_rate_is_read_as_exact_text` copies the config and sets the rate to `"1.14330000000001"`; the stored rate equals `Decimal("1.14330000000001")` exactly, and the direction text of a conversion keeps every digit. `test_missing_pair_returns_no_rate` asks the reader for GBP to USD; the answer is `NoRate`, not an exception. `test_bad_policy_file_raises_toml_file_error` sets the policy amount to the text "fifty"; the reader raises `TomlFileError` with `FileProblem.MALFORMED` and a non-empty fact.

Proof: the DoD item "Fixture and rate names" expects `14` for these and the milestone 4 names.

### Milestone 6 - Review orchestration in none mode

Goal: one orchestration function turns a source, a rate port and a policy into the full review of a snapshot, with rules-only decisions. Its output matches the expected results table in Context.

Work: under `fare_reshop_agent/reshopping/orchestration/`, add the function `review_snapshot(source, rates, policy)` that runs the review. Its inputs are the `ReshopSource`, the `ExchangeRates` port and the `ReviewPolicy`. It reads one snapshot and builds the review report, which holds the mode `none`, the capture time, the data issues in file order, and the results sorted by `pnr`. For each booking, in this order: a rejected booking becomes an `INVALID_DATA` result with its reason; a departure before the capture time becomes `INVALID_DATA` with the reason "departs before the capture time"; a booking whose change fee needs a rate with no rate becomes `INVALID_DATA` with the exact reason from L3; a booking whose minimum saving needs a rate with no rate becomes `INVALID_DATA` with "no exchange rate from USD to <currency>". Otherwise, the function calls `convert_minimum`, matches the offers on the same route and date, evaluates each one in the order of offer id, calls `decide`, and builds the recommendation with its reasoning from the fixed templates of L4. The result carries the rates used on the booking side, as L1 requires. The function prints nothing and reads no file.

Seam: the orchestration function, called from `tests/test_review_rules.py` with test fakes of the source and rate ports. The same file also has one test that uses the real fixture adapter and the real TOML adapter, constructed directly in the test with the policy built inline, as the sample oracle.

Assertions. `test_sample_data_matches_expected_results` checks the status, the offer and the saving of all five bookings against the table in Context. `test_qx7t2a_rebooks_of_1001_for_80_usd` expects REBOOK, offer OF-1001 and saving `Decimal("80.00")` in USD. `test_rt5k8b_rebooks_of_3001_for_363_21_eur` expects REBOOK, offer OF-3001, saving `Decimal("363.21")` in EUR and minimum saving `Decimal("43.73")` in EUR. `test_lm9p4c_keeps_because_cabin_and_bags_fail` expects KEEP, reasoning that starts "No offer passes every rule.", and OF-2001 with cabin and bags both FAIL. `test_zc3n1d_keeps_because_refundability_fails` expects KEEP, reasoning that starts "No offer passes every rule.", and OF-4001 with refundable the only FAIL. `test_hb6w9e_keeps_because_no_offer_reaches_the_minimum` expects KEEP, reasoning that starts "No offer reaches the minimum." and names OF-5001, its saving "-90.00 USD" and the minimum "50.00 USD". `test_no_offers_on_route_is_keep` removes the offers of one booking's route; the result is KEEP, the evaluations are empty and the reasoning is "No offers on this route and date.". `test_departure_before_capture_is_invalid_data` sets one departure to 2026-07-01T10:00:00 against the capture time 2026-07-08T09:00:00Z; the result is INVALID_DATA with the reason "departs before the capture time". The same test sets a departure equal to the capture time and expects that booking not to be invalid. `test_missing_rate_for_minimum_is_invalid_data` uses a booking in GBP with no rate table entry; the result is INVALID_DATA with the reason "no exchange rate from USD to GBP". `test_missing_pair_is_invalid_data_not_crash` uses a booking whose change fee is in JPY with no rate; the result is INVALID_DATA with the reason "no exchange rate from JPY to USD", and the run completes. `test_invalid_booking_does_not_stop_other_bookings` makes one booking malformed; the other four still produce their expected results. `test_empty_snapshot_gives_empty_results` uses a snapshot with no bookings; the results list is empty. `test_offer_in_lower_cabin_is_not_chosen_even_if_cheapest` uses an ECONOMY booking with a cheaper BASIC_ECONOMY offer and a pricier eligible ECONOMY offer; the chosen offer is the eligible ECONOMY one. `test_results_are_sorted_by_pnr` supplies the bookings in reverse order; the results come out in pnr order.

Proof: the DoD item "Orchestration names" lists the 14 names of this milestone and expects `14`.

### Milestone 7 - Composition and the review command with JSON output

Goal: `uv run fare-reshop review --model none` prints the JSON report of L1 and exits 0 for a valid snapshot, including an empty one.

Work: under `fare_reshop_agent/reshopping/composition/`, add `SetupError` in `setup_error.py`, a keyword-only exception with the three text fields `error`, `reason` and `fix`. Add the `none` object graph and one function that runs the review. The function calls the policy reader on `config/policy.toml`, creates the TOML rate reader and the fixture source, and calls `review_snapshot`. It catches `JsonFixtureError` and `TomlFileError` and raises `SetupError` from them with `raise ... from err`, with the wording rules of L7 and the inspection fix line. It also computes the color setting with a pure function `color_setting(environ, is_terminal)`, which returns off when `NO_COLOR` is set or the output is not a terminal, and on otherwise. The function passes `os.environ` and the terminal check to it, so composition is the only code that reads the environment. Under `cli/`, build the argument parser with the `review` and `doctor` subcommands (only `review` is functional here; `doctor` gets its body in milestone 9), with `--model` accepting only `none` and `--format` accepting only `json` (L7). Render the JSON exactly as L1 specifies, with indent 2. The table and the three-line error printing are milestone 8. Until then, a setup error may still end in a traceback, and milestone 8 removes that. `cli/` imports `composition/` and never `infrastructure/`. Only `cli/` prints.

Seam: the installed script, run as a subprocess from the repo root for the success cases, and from a `tmp_path` copy of the repo's data and config for the empty case. The tests are in `tests/test_cli.py`.

Assertions. `test_review_json_has_schema_version_one` parses the output as JSON and expects `schema_version` 1, `mode` "none", and the top-level keys in the order of L1. `test_json_output_is_deterministic` runs the command twice and expects identical bytes. `test_empty_bookings_exit_0` copies the repo's data with an empty bookings list and expects exit code 0 and an empty `results` list.

Proof: the DoD items "CLI names", "Default run exits 0", "JSON rates" and "JSON dates" pass.

### Milestone 8 - Table output, the error format and exit codes

Goal: `--format table` prints the review for people, and every failure prints the three-line error format with the exit code of L7.

Work: under `cli/`, add the table renderer for the columns PNR, STATUS, OFFER, SAVING and REASON, following L7 for empty cells, the money format, the REASON rule, data issues after the table, and color on the status word only when composition says color is on. Accept `--format table` now. Map argument errors from argparse to the three-line format with exit code 2, and make `--model` values other than `none` a bad argument. Map `SetupError` from composition to the three lines with exit code 2. Map any other exception at the entry point to the three lines with exit code 1, the fix `uv run fare-reshop review --debug`, and print the traceback after them only when `--debug` is passed. The entry point is the only place that catches broad exceptions. Only `cli/` prints.

Seam: the installed script, run as a subprocess, as in milestone 7. The failure cases copy the repo's data and config into `tmp_path`, change one file, and run from that directory.

Assertions. `test_table_output_has_no_color_when_piped` runs the table format through a pipe and expects no escape codes in the output. `test_no_color_variable_turns_color_off` runs on a terminal stand-in with `NO_COLOR` set and expects no escape codes. `test_error_format_for_missing_fixture_has_three_lines` removes the fixture file and expects exactly three lines starting with `error:`, `reason:` and `fix:`, with exit code 2, and the fix line mentions `git diff` and not `git checkout`. `test_error_format_hides_traceback_without_debug` triggers a setup error and expects no line that starts with "Traceback". `test_debug_flag_prints_traceback` triggers an internal error stand-in through `--debug` and expects a traceback after the three lines. `test_error_format_for_unknown_model` passes `--model openai` and expects exit code 2 with the three lines. `test_missing_policy_file_exits_2` removes `config/policy.toml` and expects exit code 2 with the three lines.

Proof: the DoD items "Table rebooks QX7T2A", "Table rebooks RT5K8B", "Table keeps", "Only two rebooks", "Table reasons", "CLI names" and "Checks green" pass.

### Milestone 9 - Doctor and the first-run start script

Goal: a fresh clone runs `./start.sh`. The script asks before every install and sync, runs the doctor, and ends with the default review. The doctor lists each check and the command that fixes each failure.

Work: add the doctor checks of L8 in `composition/`, which returns one result for each check, and give the `doctor` subcommand in `cli/` the rendering: one `[ok]` or `[FAIL]` line for each check and a `fix:` line under each failure. Its exit codes are 0 when all checks pass and 2 otherwise. Write `start.sh` at the repo root as a POSIX shell script, made executable, with the flow in L8: the uv check and install question, the sync question, the doctor, then the review. Read answers with `read` from standard input, and treat end of input as no. Confirm the official uv install command against the uv documentation before writing it into the script. Name the script's manual steps in its output, so that a declined question still shows the exact command to run by hand.

Seam: `tests/test_cli.py`, with the doctor run as a subprocess in the repo root and in `tmp_path` copies with one file missing. The script is run as a subprocess with `PATH` set to `/usr/bin:/bin` and standard input closed, so that uv is not found and nothing is installed.

Assertions. `test_doctor_passes_on_synced_checkout` runs the doctor in the repo root and expects every line to start with `[ok]` and exit code 0. `test_doctor_names_fix_for_missing_fixture` removes `fixtures/pnrs.json` from a copy and expects a `[FAIL]` line for that file, a `fix:` line that mentions `git diff -- fixtures/pnrs.json`, and exit code 2. `test_start_script_asks_before_install` runs the script with the restricted `PATH` and closed input; the output contains `Install uv now? [y/N]`, the exit code is 1, and no install command runs.

Proof: the DoD items "Doctor passes", "start.sh asks" and "CLI names" pass.

### Milestone 10 - Glossary, design record and AGENTS.md wording

Goal: the terms and the one hard-to-reverse design decision are written down for readers, and `AGENTS.md` names the port, not the data, and states the nominal saving without a confidence for rules-only.

Work: create `GLOSSARY.md` at the repo root with one `### <Term>` heading for each of the ten terms: Booking, Offer, Rule check, Eligible offer, Approval flag, Nominal saving, Realized saving, Minimum saving, Exchange rate and Recommendation. Each entry is a plain-English definition in two or three sentences, using the definitions in Context, and Realized saving says that it is not computed. Create `docs/adr/0001-value-objects-and-deferred-review-aggregate.md` in plain Markdown with the sections Status (Accepted), Context, Decision, Consequences and Alternatives, recording D11: domain values are immutable value objects, and the Review aggregate is deferred. The Alternatives section names the booking-as-aggregate-root option and why it lost. Neither file may link to a plan file, because plans are retired after they land and the link would go stale. Make the two `AGENTS.md` changes of L11. Before this milestone is done, the denylist check from D28 runs on every file it writes.

Seam: none. These are documentation files, checked by the grep proofs in the DoD.

Proof: the DoD items "Glossary", "ADR" and "AGENTS.md" pass.

### Milestone 11 - Scenario data set and the --data flag

Goal: `uv run fare-reshop review --data scenarios` reviews the six made-up scenario bookings, and each judgment case in the scenario table has a named test with its exact result. The sample run does not change.

Work: create `fixtures/scenarios/pnrs.json` and `fixtures/scenarios/fares_feed.json` from the two scenario tables in Context, with the top-level `_comment` described in D34 and the same field layout as the sample files. Do not edit `fixtures/pnrs.json` or `fixtures/fares_feed.json`. Under `composition/`, map the data set names to folders as L12 says. In `cli/`, add `--data` to the `review` subcommand with `choices` of `sample` and `scenarios` and the default `sample`. Milestone 8's argparse mapping prints an unknown value in the three-line format with exit code 2: `error: unknown data set 'nope'`, the reason that only the configured sets exist, and the fix `use --data sample or --data scenarios`. Add the scenario folder's two files to the doctor's readable-files check of L8, so `doctor` names a missing scenario file with its fix.

Seam: `tests/test_review_rules.py` calls the orchestration function with the real fixture adapter on `fixtures/scenarios/`, with the real TOML adapters and the policy built inline, as the sample oracle does. `tests/test_cli.py` runs the installed script as a subprocess from the repo root.

Assertions. `test_scenario_a_picks_highest_saving_with_schedule_flag` expects MK3V7P to be REBOOK with offer OF-6101, saving `Decimal("170.00")` in USD and approval flags `["schedule_change"]`, and expects OF-6102 to be eligible with saving `Decimal("80.00")` and no flags. `test_scenario_b_carrier_change_is_flag_not_failure` expects RD9Q2X to be REBOOK with offer OF-6201, saving `Decimal("75.00")` and approval flags `["carrier_change"]`, with all seven rule results PASS. `test_scenario_c_failed_refundability_is_not_chosen` expects WJ6T4N to be REBOOK with offer OF-6302 and saving `Decimal("60.00")`; OF-6301 has the refundable result FAIL, saving `Decimal("210.00")` and is not eligible. `test_scenario_d_shared_flight_recommends_each_booking` expects CH8L5F and FD2N8Z each to be REBOOK with offer OF-6401 and saving `Decimal("80.00")`, with the seats result PASS in both. `test_scenario_e_seats_failure_keeps` expects YU6EG1 to be KEEP, with OF-6501's seats result FAIL, its saving `Decimal("60.00")` shown, and reasoning that starts "No offer passes every rule.". `test_scenario_expected_results_table_matches` checks all six bookings' statuses and offers against the table in Context in one place.

In `tests/test_cli.py`, `test_data_scenarios_prints_six_results` runs `review --data scenarios` and expects exit code 0 and six results. `test_data_default_is_sample` expects the output of no `--data` flag to equal the output of `--data sample`, byte for byte. `test_unknown_data_set_exits_2_three_lines` runs `--data nope` and expects exit code 2 and exactly three lines starting with `error:`, `reason:` and `fix:`.

Proof: the DoD items "Scenario rule names", "Scenario CLI names" and "Scenario table" pass.

## Surprises & Discoveries

- Observation: the index's rate-count wording has changed. An earlier draft of the S5 proof asked for "at least 1" rate line; the current index no longer does. This plan pins the exact count, 3. The RT5K8B booking shows the demo rate three times: on the offer's price conversion, on the conversion of the offer's zero change fee, and on the converted minimum. "At least 1" would also pass with a broken output, so the exact count is the stronger check.
  Evidence: the DoD item "JSON rates" expects `3` from `grep -c '"rate": "1.1433"'`.
- Observation: the index's D4 first said unknown keys are ignored, which clashed with the repo's Python rules. Critic round 1 changed D4 to fail parsing, so the clash is closed.
  Evidence: `.claude/rules/python.md`, section Data, says "Models set extra='forbid'"; D4 now says unknown keys fail parsing, and L3 follows it.
- Observation: the index's S7 walkthrough mentions the README for Windows steps, but the README is written by plan 04.
  Evidence: the index's build order gives S6 to plan 04, and S7 step 5 refers to the README. This plan names the gap in its risks.
- Observation: the index's S7 step 3 lists a Python version check, which this plan drops.
  Evidence: `requires-python` in `pyproject.toml` makes `uv` refuse older interpreters before the doctor runs (S7, L8).
- Observation: the setup error type's home moved from infrastructure to composition, because the index's D12 now maps readers' errors to `SetupError` in `composition/`.
  Evidence: D12 and milestone 7; `cli/` never imports `infrastructure/` (DoD item "Layering").

- Observation: the RT5K8B saving in EUR and the EUR minimum, in two test names and one DoD item, were not recomputed when the rate changed to 1.1433. The names and the DoD item now carry the values that the Decimal arithmetic gives at that rate.
  Evidence: `test_rt5k8b_rebooks_of_3001_for_363_21_eur`, `test_minimum_saving_in_eur_is_43_73` and the DoD item "Table rebooks RT5K8B". At 1.1433 the offer is 1,836.79 EUR, the saving is 363.21 EUR, and the minimum is 43.73 EUR (ROUND_HALF_EVEN, 2 places).

- Prototype result: discard. pydantic 2.14.2 (pydantic-core 2.50.2) reads a JSON number into a `Decimal` field through a binary float, so `model_validate_json` printed `1234567.123456789` for `1234567.123456789012345`. Path two, `json.loads(text, parse_float=Decimal)` followed by `model_validate`, printed `1234567.123456789012345` with no `FloatOperation`. The fixture adapter uses path two.
  Evidence: scratch script run with `uv run python -I`; output `path one 1234567.123456789 FAIL`, `path two 1234567.123456789012345 PASS`. A `Field(alias="_comment")` on a model with `extra="forbid"` accepted the top-level `_comment` key. Docs read: the pydantic-core JSON input code turns a JSON float into text through a 64-bit float before it builds the `Decimal`, which explains the lost digits. `.claude/rules/python.md` now names path two only.

- Observation: the two import checks of L8 (`fare_reshop_agent` and `pydantic`) cannot fail through the CLI, because the CLI imports both before `doctor` runs, and `uv run` syncs the environment first. They stay because L8 locks them.
  Evidence: `uv run fare-reshop doctor` prints `[ok]` for both on every run; the failure branch is reachable only when the package is imported without its dependencies.

## Decision Log

- Decision: money accepts a `Decimal`, text or an integer, refuses a float or a bool, and raises on adding or comparing two currencies, equality included (L2, milestone 2). A round-2 critic proposed that equality return False; dismissed, because `.claude/rules/python.md` (the owner's rule) says comparing two currencies raises.
  Rationale: the round-2 finding, kept consistent with `.claude/rules/python.md`, which says comparing two currencies raises.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: HB6W9E is a KEEP for the reason that no offer reaches the minimum. OF-5001 passes all seven rules and misses the minimum. The reasoning template for that case names the offer, the saving and the minimum (L4). The test is `test_hb6w9e_keeps_because_no_offer_reaches_the_minimum`, which replaces the earlier name everywhere.
  Rationale: the earlier name said every offer fails, which is false for OF-5001.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: setup-error fix lines never discard changes. They say to run from the repo root and inspect with `git status` and `git diff -- <path>`. The missing-file reason names the working-directory requirement (L7).
  Rationale: `git checkout --` would throw away a user's edit to a fixture or config file.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: readers raise their own typed errors (`JsonFixtureError`, `TomlFileError`) with no CLI wording. Composition maps them to `SetupError` (what, why, fix), which lives in `composition/`. `cli/` renders it and never imports `infrastructure/` (D12, L7, milestones 4, 5 and 7).
  Rationale: the index's D12 now says so. Plan 02 relies on the reader error types, `SetupError` and its home in composition.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: the demo rate date is 2026-07-07, the day before the fare snapshot's capture date, not 2026-11-02 (A2, D6). The rate value stays 1.1433, and the expected figures follow from it: RT5K8B is 1,836.79 EUR with a 363.21 EUR saving, and the minimum is 43.73 EUR. The DoD checks the rate date on each rate line (DoD "JSON dates").
  Rationale: owner answer, 2026-11-02. The owner chose the snapshot's date for the rate.
  Date/Author: 2026-11-02, plan author, owner answer.
- Decision: each named rule and money test states its exact input and expected value (milestones 2, 4, 5 and 6). The end-to-end table greps stay as the behavior proof.
  Rationale: a named test with a stub body must not pass the DoD.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: a prototyping milestone (milestone 3) runs before the fixture adapter. It decides whether pydantic keeps the exact text of a many-digit `Decimal`. Promote keeps pydantic's own parsing. Discard uses `json.loads(text, parse_float=Decimal)` with pydantic validation of the result.
  Rationale: the parse path is a real unknown, and the Risks section depends on it.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: the plan has ten milestones (eleven since milestone 11 was added). The fixture adapter (4) is separate from the rate and policy readers (5). Composition with JSON output (7) is separate from table output and error mapping (8). Milestone numbers in Progress, DoD and cross-references follow.
  Rationale: each milestone now has one concern and one verifiable outcome, and fits one context window.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: table output has a REASON column. Its value is the first sentence of `reasoning` for KEEP, the `invalid_reason` for INVALID_DATA, and `-` for REBOOK. The DoD checks that the sample's KEEP reasons appear in the table (L7, milestone 8).
  Rationale: the table should show why a booking was kept. The sample has no INVALID_DATA result, so the check uses KEEP.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: milestone proofs point at DoD items and do not claim that `pytest -q` prints test names. The `-k` proof in milestone 3 is removed. The DoD counts names with `--collect-only`.
  Rationale: `pytest -q` prints dots, not names. A `-k` filter can pass when the named test does not exist.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: the Decision Log no longer says the index lacks exit code 1. The index's D15 lists exit code 1 for internal errors, and L7 follows it.
  Rationale: the earlier claim was wrong.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: the Surprises entry about "at least 1" now describes the current index, which pins the count to 3 (Surprises).
  Rationale: the earlier wording described an index that has since changed.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: the doctor has no Python-version check. `uv` refuses to run the package below `requires-python`, so the check could not report a failure the run would not already show (S7, L8).
  Rationale: a check that cannot fail is noise.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: argparse errors exit with code 2 and print in the three-line format (L7).
  Rationale: the index's exit code 2 covers bad flags (D15), and the three-line format applies to every CLI error.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: `Status` holds only REBOOK, KEEP and INVALID_DATA, and `DecidedBy` holds only RULES. Plans 02 and 03 add their members (D9, milestone 2).
  Rationale: an enum member this plan never emits is a value that cannot be tested.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: rounding is half-even, with the examples 2.345 to 2.34 and 2.355 to 2.36. An amount that rounds to zero prints as `0.00` (L2).
  Rationale: the examples remove any doubt about the rule, and no negative zero may appear in output.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: the rate `as_of` is ISO text in the TOML file and in the output (L1, L6).
  Rationale: a TOML date would be parsed into a date object, and the output would have to convert it back. Text keeps the file and the output identical.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: the per-status shape of each result is written in L1, for REBOOK, KEEP and INVALID_DATA.
  Rationale: each status has a fixed set of null or empty keys, and a reader must be able to check them.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: the test layout is two test modules plus `tests/conftest.py` (L9, milestone 1, DoD "Test modules").
  Rationale: the earlier wording said "exactly two test files" and left out `conftest.py`.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: `AGENTS.md` changes two sentences: "an exchange rate from the data" and the overview line about "how confident it is" and "the net saving after fees". The overview gives the nominal saving after the change fee, with no confidence for rules-only (L11, milestone 10, DoD "AGENTS.md").
  Rationale: the overview promised a net figure and a confidence that this plan does not produce.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: the check script DoD checks its four command lines exactly, not a word count (DoD "Check script").
  Rationale: a word count can pass with a changed command.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: no workflow file is written. The four checks run through `scripts/check.sh`, and the owner gate on a hosted run is removed.
  Rationale: owner answer, 2026-11-02. One tracked local script is the one check command, so every plan's checks name the same gate.
  Date/Author: 2026-11-02, plan author, owner answer.
- Decision: `--format` accepts only `json` until milestone 8 adds `table` (L7, D15).
  Rationale: a value that is accepted but not built fails silently.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: the setup error is `SetupError` in `composition/setup_error.py`, not in infrastructure (D12, milestone 7).
  Rationale: see the D12 decision above.
  Date/Author: 2026-11-02, plan author, after critic round 2.
- Decision: A2 names the rate's source. No other part of this plan names it.
  Rationale: owner answer, 2026-11-02: plans may name the source in A2 only (D28, A2).
  Date/Author: 2026-11-02, plan author, owner answer.
- Decision: unexpected internal errors exit with code 1, as the index's D15 lists (L7).
  Rationale: exit code 2 means a setup error the user can fix. A bug is a different kind of failure, and the calling script must be able to tell the two apart.
  Date/Author: 2026-11-02, plan author.
- Decision: file paths are read relative to the working directory, with no path flags (L6).
  Rationale: every documented run starts at the repo root, and path flags would add command-line surface that no story asks for.
  Date/Author: 2026-11-02, plan author.
- Decision: `start.sh` exits with code 1 when the user declines an install or a sync, and treats end of input as a decline (L8).
  Rationale: the user stopped the setup. Exit code 1 says the setup is incomplete without marking it as a bug.
  Date/Author: 2026-11-02, plan author.
- Decision: the Windows steps are not written in this plan (Non-goals, Risks).
  Rationale: the README is plan 04's output, and the index assigns it there.
  Date/Author: 2026-11-02, plan author.
- Decision: the rates file holds one stored pair, EUR/USD, and the adapter derives USD to EUR (D6, L5).
  Rationale: one entry covers every conversion the sample needs: the RT5K8B offer price, its zero change fee and the 50 USD minimum. Other pairs are added to the file when a fixture needs them.
  Date/Author: 2026-11-02, plan author, after critic round 1.
- Decision: a missing pair never stops the run. A booking that needs it becomes `INVALID_DATA` with its reason, and an offer that needs it fails the `exchange_rate` rule (L3, L4).
  Rationale: one bad or incomplete record must not hide the other results (D4). Tests: `test_missing_pair_is_invalid_data_not_crash` and `test_offer_in_other_currency_without_rate_fails_exchange_rate_rule`.
  Date/Author: 2026-11-02, plan author, after critic round 1.
- Decision: `NO_COLOR` and the terminal check are read in `composition/`, which passes a color setting to `cli/` (D31, L7).
  Rationale: the Python rules allow environment reads only in composition. A pure function that takes the environment mapping and the terminal flag can be tested without a terminal.
  Date/Author: 2026-11-02, plan author, after critic round 1.
- Decision: replacing pydantic with the standard library in the fixture adapter is dismissed.
  Rationale: the owner approved pydantic (D13), and the Python rules name it as the infrastructure parser. The round-1 critic proposed the replacement, and this entry records why it was not made.
  Date/Author: 2026-11-02, plan author, after critic round 1.
- Decision: unknown keys reject the record, except the top-level `_comment` key of each fixture file (L3). L6 applies the same unknown-key rule to the two TOML files.
  Rationale: D4 now says unknown keys fail parsing, which matches the Python rules that forbid extra keys. Inside a record, `_comment` is an unknown key.
  Date/Author: 2026-11-02, plan author, after critic round 1.
- Decision: the output rate fields are lists, `exchange_rates`, at result level and at evaluation level, and each entry names its use (L1).
  Rationale: D6 requires every converted amount to show its own rate. The booking fee and the minimum can each use a different rate. Nothing reads this output yet, so the change to D9's single field costs nothing.
  Date/Author: 2026-11-02, plan author.
- Decision: a rate's direction text names the stored pair, even when the conversion divides (L1).
  Rationale: the stored pair is the rate the owner expects to see, and a reader can check it against `config/exchange_rates.toml`.
  Date/Author: 2026-11-02, plan author.
- Decision: a departure is compared with the capture time as a naive time, with the capture time converted to naive UTC (L3).
  Rationale: the fixture departure texts carry no time zone, and no fixture departure is near the capture time, so this choice changes no sample result. Real feeds would need a zone, and that is recorded as a risk.
  Date/Author: 2026-11-02, plan author.
- Decision: an offer whose change fee is in another currency is converted through the `ExchangeRates` port, not rejected (L3, L4).
  Rationale: an offer in another currency is converted, not refused (D3, D6). Each conversion has its own rate line on the evaluation (L1).
  Date/Author: 2026-11-02, plan author.
- Decision: a record whose identifier cannot be read is listed as a data issue with its position in the file as the id (L3, L1).
  Rationale: a result needs a `pnr`, so a booking without one cannot become an `INVALID_DATA` result. The position keeps the issue findable.
  Date/Author: 2026-11-02, plan author.
- Decision: the booking's cabin is the cabin on its ticket (L4).
  Rationale: the ticket is what the traveler paid for. The itinerary cabin is parsed and required, and for every fixture it equals the ticket cabin.
  Date/Author: 2026-11-02, plan author.
- Decision: a schedule change is a difference in the departure or arrival text, and a carrier change is a difference in the carrier code (L4).
  Rationale: these are the facts the index's D3 names. A flight-number change alone does not count, so the flag stays tied to the times and the operator.
  Date/Author: 2026-11-02, plan author.
- Decision: when the offer's price has no rate, the nominal saving is null and the exchange rate and future change fee rules fail. When only the change fee has no rate, those two rules fail and the saving is still computed (L4).
  Rationale: the saving uses the offer's price in the booking's currency and never uses the offer's fee, so a missing fee rate does not change the saving. A fail is safer than a guess, and the reasons tell the reader what to fix.
  Date/Author: 2026-11-02, plan author.
- Decision: a saving meets the minimum when it is equal or greater, and ties between eligible offers go to the lower offer id (L2, L4).
  Rationale: the index says "meets the minimum", and it names the tie rule for the highest saving.
  Date/Author: 2026-11-02, plan author.
- Decision: results are sorted by `pnr`, and evaluations by `offer_id` (L1).
  Rationale: the output must be deterministic, and sorting by key does not depend on the file order.
  Date/Author: 2026-11-02, plan author.
- Decision: in this plan `--model` accepts only `none`, and `--record` does not exist (L7).
  Rationale: the index's D15 lists the full set, but later plans add each value with its own behavior. Accepting a value before it works would be a silent failure.
  Date/Author: 2026-11-02, plan author.
- Decision: the seventh risk now covers the timing of the demo rate, not a date gap. The rate is a fixed demo value for the snapshot's day.
  Rationale: owner answer, 2026-11-02. The rate date matches the snapshot, so the output shows one date for both.
  Date/Author: 2026-11-02, plan author, owner answer.
- Decision: the RT5K8B test name, the EUR minimum test name and the RT5K8B DoD item carry the figures at 1.1433: 363.21 EUR and 43.73 EUR.
  Rationale: a test name or check with an old figure would describe a result the code no longer gives.
  Date/Author: 2026-11-02, plan author, owner answer.
- Decision: milestone 1 writes `scripts/check.sh`, and every all-checks DoD item runs it. The four commands are the ones named in milestone 1 and in the Check script DoD item.
  Rationale: one local command is the tracked gate for every plan.
  Date/Author: 2026-11-02, plan author, owner answer.

- Decision: the scenario data set is a second configured set, `scenarios`, selected with `--data`, and its six bookings and seven offers are the table in Context (D34, L12).
  Rationale: owner answer, 2026-11-02. The sample data cannot show a model choice that is not the highest saving, a model keep, a failed refundability rule, a shared flight or a seats failure without changing the sample oracle.
  Date/Author: 2026-11-02, plan author, owner answer.
- Decision: the output does not name the data set (L12).
  Rationale: the D9 output shape is a contract with schema_version 1, and a new key would change it. The data set is visible in the command.
  Date/Author: 2026-11-02, plan author.
- Decision: `--data` is parsed with `choices`, so an unknown name fails before any file is read, and the argparse error takes the three-line format of milestone 8.
  Rationale: a free path is rejected by D34; a name outside the set is a bad argument, not a missing file.
  Date/Author: 2026-11-02, plan author.
- Decision: milestone 11 is the last milestone, not a renumbered step between 7 and 8.
  Rationale: renumbering would break the milestone references in the Progress list and the DoD proofs. It depends on milestones 6 to 8 and is built last.
  Date/Author: 2026-11-02, plan author.
- Decision: the doctor checks the two scenario files (L8).
  Rationale: milestone 9 lists every fixture file the default run needs, and the scenario run needs these two.
  Date/Author: 2026-11-02, plan author.
- Decision: the DoD item for the RT5K8B table line expects 363.21 EUR, not 358.54 EUR.
  Rationale: the figure follows the 1.1433 rate from the owner answer of 2026-11-02; the old value was missed when the rate changed and contradicted the test names.
  Date/Author: 2026-11-02, plan author.
- Decision: D34 is copied into the Locked decisions; D35 is not, because its limits belong to the design document in plan 04.
  Rationale: each plan copies only the index decisions it carries.
  Date/Author: 2026-11-02, plan author.

- Decision: milestone 11 was folded in after critic round 2 and had no critic round of its own. The owner dismissed the missing round and chose to implement. Six spot-check defects were fixed before work started: the milestone 11 heading level, the `--data` fix line versus L7, the rate date in the Decision Log, the milestone count, "the other five" in milestone 6, and a false claim about `AGENTS.md` in milestone 10.
  Rationale: owner answer, 2026-11-02, when asked at the start of implementation: "Fix + implement all".
  Date/Author: 2026-11-02, implementer, owner answer.

- Decision: money is built with the factory `Money.of(amount, currency)`, which accepts a `Decimal`, plain decimal text or an integer, and refuses a float, a bool and text such as `1_000` or `1e3`. The dataclass constructor takes a `Decimal` only.
  Rationale: a field typed `Decimal` cannot accept text under mypy strict without widening the field type. Critic round 1 asked for one constructor path; dismissed for that reason.
  Date/Author: 2026-11-02, implementer.

- Decision: the domain signatures differ from milestone 2's text. `booking_terms(booking, policy, rates)` returns `BookingTerms` (the booking, its change fee converted to the booking currency, and the converted minimum) or `NoRate`. `evaluate_offer(terms, offer, rates)` and `decide(terms, evaluations)` take those terms. `convert_minimum` returns a `Conversion` (the rounded money and the rate it used) or `NoRate`. Orchestration maps a `NoRate` from `booking_terms` to `INVALID_DATA` with `NoRate.reason`.
  Rationale: critic round 1: the booking fee was converted once per offer and its rate reached `decide` from a second source. One terms value per booking holds each conversion once, and its rates feed the result-level `exchange_rates` list of L1.
  Date/Author: 2026-11-02, implementer.

- Decision: the reasoning templates of L4 live in the domain `decide`, not in orchestration.
  Rationale: which KEEP case applies is decision logic, and the text names the same offer `decide` ranks.
  Date/Author: 2026-11-02, implementer.

- Decision: `OfferEvaluation.nominal_saving` is `Money | NoRate`, never null. The serializer writes null for `NoRate`.
  Rationale: typed absence, as the repo rules require.
  Date/Author: 2026-11-02, implementer.

- Decision: `Offer` stores origin and destination, and its route date is derived from its departure time. The fixture adapter rejects an offer whose `route.departureDate` differs from the date of its `departure`.
  Rationale: critic round 1: two stored facts that could disagree.
  Date/Author: 2026-11-02, implementer.

- Decision: `ReviewPolicy` does not force USD. The minimum's currency is read from `config/policy.toml`.
  Rationale: D5's 50 USD is the value of that file. A domain check for one currency would duplicate the file. Critic round 2 asked to record this.
  Date/Author: 2026-11-02, implementer.

- Decision: named tests in the DoD greps are plain functions, not parametrized, because the DoD pattern `::name$` does not match parametrized ids. Extra tests outside the DoD lists may be parametrized.
  Rationale: the DoD counts must stay binary.
  Date/Author: 2026-11-02, implementer.

- Decision: ruff selects `TRY` with one ignore, `TRY003`, with its reason in `pyproject.toml`. Critic round 2 asked for per-line suppressions instead; dismissed.
  Rationale: the Python rules ask value objects to raise on bad input with a reason that becomes a data issue. 22 same-line suppressions would be noise for a rule the project does not want.
  Date/Author: 2026-11-02, implementer.

- Decision: `test_minimum_is_checked_after_rounding` checks the rounded saving (50.00) and the eligibility, not the unrounded 49.996.
  Rationale: the unrounded saving is not public; rounding happens inside the evaluation.
  Date/Author: 2026-11-02, implementer.

- Decision: milestone 3 prototype: discard pydantic's own JSON parsing; the fixture adapter parses with `json.loads(text, parse_float=Decimal)` and validates the result with `model_validate`.
  Rationale: path one lost digits (see Surprises & Discoveries).
  Date/Author: 2026-11-02, implementer.

- Decision: the fixture adapter is `JsonFixtureSource(folder)`, reading `pnrs.json` and `fares_feed.json` from the folder it is given (L12). Each record is validated on its own; an expected rejection is a returned value inside the adapter, not an exception. Times must have the exact shapes `YYYY-MM-DDTHH:MM:SS` (local), `YYYY-MM-DDTHH:MM:SSZ` (capture time) and `YYYY-MM-DD` (route date).
  Rationale: L3 says a record must match the fixture shape exactly; critic rounds 1 and 2 showed that `fromisoformat` and plain `strptime` accept other shapes.
  Date/Author: 2026-11-02, implementer.

- Decision: `JsonFixtureError` and the later `TomlFileError` share a base, `FileReadError`, and one `read_text` helper in `infrastructure/file_problem.py`.
  Rationale: both carry the same path, problem and fact (D12), and composition maps both the same way.
  Date/Author: 2026-11-02, implementer.

- Decision: the tests stay in the two modules of L9, even past 400 lines. Critic round 1 asked to split `tests/test_review_rules.py`; dismissed.
  Rationale: L9 locks two test modules and the DoD "Test modules" item expects three files.
  Date/Author: 2026-11-02, implementer.

- Decision: the rate reader is `read_exchange_rates(path)`, which returns a `TomlExchangeRates` holding the parsed rates, and the policy reader is `read_policy(path)`. A pair listed twice in either direction, a negative minimum, a rate stored as a TOML number and an unknown key are all `MALFORMED`. File reading, model validation and exact time parsing are shared helpers in `infrastructure/file_problem.py`.
  Rationale: critic round 1: one read-validate-map flow for both readers, and a negative minimum would let a loss pass the minimum check.
  Date/Author: 2026-11-02, implementer.

- Decision: `review_snapshot(source, rates, policy)` returns a `ReviewReport` (mode, capture time, data issues, results sorted by booking reference). `ReviewMode` holds only `none`; plans 02 and 03 add members.
  Rationale: the report is the one value the CLI renders; the mode belongs to the run, not the domain.
  Date/Author: 2026-11-02, implementer.

- Decision: the `doctor` subcommand is registered in milestone 9 with its body, and `color_setting` arrives in milestone 8 with the table, its only user.
  Rationale: a registered no-op subcommand would exit 0 without doing anything, and a function with no caller is dead code until then.
  Date/Author: 2026-11-02, implementer.

- Decision: each result type carries its status as a class constant (`Rebook.status` is `REBOOK`, and so on), and the renderers read it from there.
  Rationale: D9 says the status comes from the type; one constant per type gives one source for the JSON and the table.
  Date/Author: 2026-11-02, implementer.

- Decision: the seats rule reason reads `N seats available, M needed`.
  Rationale: the first wording printed `1 passengers`.
  Date/Author: 2026-11-02, implementer.

- Decision: `test_error_format_hides_traceback_without_debug` triggers an internal error, not a setup error: a fixture file of 100 000 `[` characters makes the standard JSON parser raise `RecursionError`. The same stand-in drives `test_debug_flag_prints_traceback`.
  Rationale: a setup error never prints a traceback, so a test built on one would pass without checking anything. The stand-in needs no test-only hook in the product code.
  Date/Author: 2026-11-02, implementer.

- Decision: `color_setting(environ, is_terminal)` and `standard_output_color()` live in `composition/color.py`; the table colors only the status word and pads outside the escape codes. Error text is collapsed to one line per label, so the three-line format holds for any message.
  Rationale: L7 and critic findings on multi-line messages and padding inside escapes.
  Date/Author: 2026-11-02, implementer.

- Decision: the doctor and the review read one list of files, `REVIEW_FILES` in `composition/review.py`; the doctor checks readability only, as L8 says. `start.sh` defines the uv install command once, confirmed against the uv installation docs: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
  Rationale: critic: a second hand-kept list would drift when milestone 11 adds the scenario files.
  Date/Author: 2026-11-02, implementer.

## Outcomes & Retrospective

Not started. Filled at major milestones and at completion.

## Definition of done

Each check runs from the repo root. Before ticking a box, run its command and record the output in Progress. Each item has a label, which the milestone proofs use.

- [ ] **CLI entry**: `uv run fare-reshop --help | head -n 1 | grep -c '^usage: fare-reshop'` prints `1`, and `uv run fare-reshop --help >/dev/null; echo $?` prints `0`.
- [ ] **Check script**: `test -x scripts/check.sh && grep -cxE 'uv run (ruff format --check \.|ruff check \.|mypy|pytest -q)' scripts/check.sh` prints `4`, and `grep -cx 'set -eu' scripts/check.sh` prints `1`.
- [ ] **Test modules**: `ls tests/*.py | wc -l` prints `3` (`conftest.py` and the two test modules).
- [ ] **Prototype result recorded**: `grep -cE '^- Prototype result: (promote|discard)' .agents/plans/reshop-review/01-rules-only-review.md` prints `1`.
- [ ] **Domain rule names**: `uv run pytest --collect-only -q tests/test_review_rules.py | grep -cE '::(test_offer_in_lower_cabin_is_rejected|test_losing_refundability_fails_refundable_rule|test_fewer_bags_fails_bags_rule|test_extra_stop_fails_stops_rule|test_too_few_seats_fails_seats_rule|test_higher_future_change_fee_fails_rule|test_equal_future_change_fee_passes|test_schedule_change_adds_approval_flag_without_failing|test_carrier_change_adds_approval_flag_without_failing|test_qx7t2a_nominal_saving_is_80_usd|test_lm9p4c_saving_is_minus_90_usd|test_minimum_is_checked_after_rounding|test_money_rejects_float_input|test_money_rejects_bool_input|test_money_accepts_text_and_int|test_adding_two_currencies_raises|test_ordering_two_currencies_raises|test_equality_across_currencies_raises|test_offer_in_other_currency_without_rate_fails_exchange_rate_rule|test_offer_in_other_currency_with_rate_uses_inverse_direction|test_minimum_saving_in_eur_is_43_73|test_exchange_rate_converts_in_both_directions|test_booking_total_paid_mismatch_raises|test_recommendation_picks_highest_saving_then_lower_offer_id|test_offer_change_fee_never_enters_nominal_saving|test_offer_change_fee_in_other_currency_is_converted|test_fee_without_rate_fails_future_fee_rule|test_float_trap_rejects_decimal_from_float)$'` prints `28`.
- [ ] **Fixture and rate names**: `uv run pytest --collect-only -q tests/test_review_rules.py | grep -cE '::(test_fixture_money_is_read_as_exact_decimal|test_malformed_booking_is_rejected_with_reason|test_multi_segment_booking_is_rejected|test_bad_offer_is_listed_in_data_issues|test_duplicate_offer_ids_are_all_left_out|test_duplicate_booking_keeps_first_record|test_unknown_field_rejects_that_record|test_comment_key_is_ignored|test_negative_stops_bags_or_seats_rejects_record|test_comment_inside_a_record_is_unknown_key|test_missing_fixture_raises_json_fixture_error|test_rate_file_rate_is_read_as_exact_text|test_missing_pair_returns_no_rate|test_bad_policy_file_raises_toml_file_error)$'` prints `14`.
- [ ] **Orchestration names**: `uv run pytest --collect-only -q tests/test_review_rules.py | grep -cE '::(test_sample_data_matches_expected_results|test_qx7t2a_rebooks_of_1001_for_80_usd|test_rt5k8b_rebooks_of_3001_for_363_21_eur|test_lm9p4c_keeps_because_cabin_and_bags_fail|test_zc3n1d_keeps_because_refundability_fails|test_hb6w9e_keeps_because_no_offer_reaches_the_minimum|test_no_offers_on_route_is_keep|test_departure_before_capture_is_invalid_data|test_missing_rate_for_minimum_is_invalid_data|test_missing_pair_is_invalid_data_not_crash|test_invalid_booking_does_not_stop_other_bookings|test_empty_snapshot_gives_empty_results|test_offer_in_lower_cabin_is_not_chosen_even_if_cheapest|test_results_are_sorted_by_pnr)$'` prints `14`.
- [ ] **CLI names**: `uv run pytest --collect-only -q tests/test_cli.py | grep -cE '::(test_console_entry_point_prints_help|test_review_json_has_schema_version_one|test_json_output_is_deterministic|test_empty_bookings_exit_0|test_table_output_has_no_color_when_piped|test_no_color_variable_turns_color_off|test_error_format_for_missing_fixture_has_three_lines|test_error_format_hides_traceback_without_debug|test_debug_flag_prints_traceback|test_error_format_for_unknown_model|test_missing_policy_file_exits_2|test_doctor_passes_on_synced_checkout|test_doctor_names_fix_for_missing_fixture|test_start_script_asks_before_install)$'` prints `14`.
- [ ] **Scenario rule names**: `uv run pytest --collect-only -q tests/test_review_rules.py | grep -cE '::(test_scenario_a_picks_highest_saving_with_schedule_flag|test_scenario_b_carrier_change_is_flag_not_failure|test_scenario_c_failed_refundability_is_not_chosen|test_scenario_d_shared_flight_recommends_each_booking|test_scenario_e_seats_failure_keeps|test_scenario_expected_results_table_matches)$'` prints `6`.
- [ ] **Scenario CLI names**: `uv run pytest --collect-only -q tests/test_cli.py | grep -cE '::(test_data_scenarios_prints_six_results|test_data_default_is_sample|test_unknown_data_set_exits_2_three_lines)$'` prints `3`.
- [ ] **Scenario table**: `uv run fare-reshop review --data scenarios --model none --format table | grep -cE '(MK3V7P|RD9Q2X|WJ6T4N|CH8L5F|FD2N8Z).*REBOOK'` prints `5`, and `uv run fare-reshop review --data scenarios --model none --format table | grep -cE 'YU6EG1.*KEEP'` prints `1`.
- [ ] **Checks green**: `./scripts/check.sh >/dev/null; echo $?` prints `0`.
- [ ] **Default run exits 0**: `uv run fare-reshop review --model none >/dev/null; echo $?` prints `0`.
- [ ] **JSON rates**: `uv run fare-reshop review --model none | grep -c '"rate": "1.1433"'` prints `3`, one line each for the OF-3001 price, its change fee and the converted minimum.
- [ ] **JSON dates**: `uv run fare-reshop review --model none | grep -c '"as_of": "2026-07-08T09:00:00Z"'` prints `1`, and `uv run fare-reshop review --model none | grep -c '"as_of": "2026-07-07"'` prints `3`. The second pattern ends in a closing quote, so it does not match the snapshot line and the two counts never overlap. The three rate lines carry the rate date (Risks).
- [ ] **Table rebooks QX7T2A**: `uv run fare-reshop review --model none --format table | grep -cE 'QX7T2A.*REBOOK.*80\.00 USD'` prints `1`.
- [ ] **Table rebooks RT5K8B**: `uv run fare-reshop review --model none --format table | grep -cE 'RT5K8B.*REBOOK.*363\.21 EUR'` prints `1`.
- [ ] **Table keeps**: `uv run fare-reshop review --model none --format table | grep -cE '(LM9P4C|ZC3N1D|HB6W9E).*KEEP'` prints `3`.
- [ ] **Only two rebooks**: `uv run fare-reshop review --model none --format table | grep -c 'REBOOK'` prints `2`.
- [ ] **Table reasons**: `uv run fare-reshop review --model none --format table | grep -cF 'No offer passes every rule.'` prints `2` (LM9P4C and ZC3N1D), and `uv run fare-reshop review --model none --format table | grep -cF 'No offer reaches the minimum.'` prints `1` (HB6W9E).
- [ ] **Doctor passes**: `uv run fare-reshop doctor >/dev/null; echo $?` prints `0`.
- [ ] **start.sh asks**: `env PATH=/usr/bin:/bin ./start.sh </dev/null | grep -c 'Install uv now? \[y/N\]'` prints `1`, and `env PATH=/usr/bin:/bin ./start.sh </dev/null >/dev/null 2>&1; echo $?` prints `1`.
- [ ] **Layering**: `grep -rE 'infrastructure' fare_reshop_agent/reshopping/cli/ >/dev/null; echo $?` prints `1`, so `cli/` never names `infrastructure`.
- [ ] **Domain imports**: `grep -rEn '^(from|import) (pydantic|json|tomllib|fare_reshop_agent\.reshopping\.(infrastructure|composition|cli))' fare_reshop_agent/reshopping/domain/ >/dev/null; echo $?` prints `1`.
- [ ] **Glossary**: `grep -cE '^### (Booking|Offer|Rule check|Eligible offer|Approval flag|Nominal saving|Realized saving|Minimum saving|Exchange rate|Recommendation)$' GLOSSARY.md` prints `10`.
- [ ] **ADR**: `grep -cE '^## (Status|Context|Decision|Consequences|Alternatives)$' docs/adr/0001-value-objects-and-deferred-review-aggregate.md` prints `5`.
- [ ] **AGENTS.md**: `grep -c 'from the ExchangeRates port' AGENTS.md` prints `1`, `grep -c 'nominal saving after the change fee' AGENTS.md` prints `1`, and `grep -cE 'net saving after fees|how confident it is' AGENTS.md` prints `0`.
- [ ] **No leaks, tracked files**: `git grep -i -F -f .private/denylist.txt; echo $?` prints `1`. The denylist is local and gitignored.
- [ ] **No leaks, plan file**: `grep -niF -f .private/denylist.txt .agents/plans/reshop-review/01-rules-only-review.md; echo $?` prints `1`.
- [ ] **No leaks, commit messages**: `git log --all --format=%B | grep -ciF -f .private/denylist.txt` prints `0`.

Revision notes:

- 2026-11-02: first draft from the review index, with stories S1, S5 and S7, the decisions this plan carries, and assumptions A1, A2, A4 and A6. Critic round 1 pending.
- 2026-11-02: critic round 1 fixes applied; status is now critic round 2 pending.
  - D4: unknown keys fail parsing; top-level `_comment` is the only exception; stops, bags and seats must be zero or more. Tests added in milestone 3 (`test_negative_stops_bags_or_seats_rejects_record`, `test_comment_inside_a_record_is_unknown_key`); `test_unknown_field_rejects_that_record` and `test_comment_key_is_ignored` already existed.
  - NO_COLOR and the terminal check are read in `composition/`, which passes a color setting to `cli/` (D31, L6, L7, milestone 5).
  - The rates file holds one EUR/USD entry, which covers the sample's conversions; a missing pair makes the booking INVALID_DATA and never crashes (D6, L3, milestone 4 test).
  - An offer whose change fee is in another currency is converted through the port, not rejected (L3, L4, milestone 2 tests). The rate line count changes from 2 to 3 (milestone 5 proof, DoD).
  - The policy and rate readers live in `infrastructure/`; `composition/` only wires them; `SetupError` (fields `error`, `reason`, `fix`) is the named contract for plan 02 (D12, L3, L6, milestone 3).
  - The domain result is a union of `Rebook`, `Keep` and `Invalid`; the serializer derives status, rebook and decided_by from it (D9, milestone 2).
  - Exit codes are 0, 1, 2 and 3 as index D15 lists them; the D15 pointer to L7 is corrected from L8 (D15, L7).
  - DoD items that name tests now name every test and count the names with `--collect-only`; the new names cover the per-booking results, the change fee trap, the unknown key rule, the missing pair, the negative counts and the float trap (milestones 2 to 5, DoD).
  - AGENTS.md wording change is owned by milestone 7, and a DoD item checks it (D6).
  - Dismissed, with reason in the Decision Log and Alternatives: replacing pydantic with the standard library in the fixture adapter.
  - Minor: milestone 3 now places the setup error in infrastructure, as D12 says; start.sh changes to its own folder (D31, L8); milestone 7 runs the denylist check (D28); the S1 `_comment` sentence copies the index; Progress lines for milestones 2, 3 and 5 mention the new pieces.
- 2026-11-02, round 2 fixes (the last critic round; the earlier notes above use the numbering of their time). Each change has its own Decision Log entry.
  - Money accepts a `Decimal`, text or an integer, refuses a float or a bool, and raises on any cross-currency add or compare, as the Python rules say (L2, milestone 2, DoD).
  - HB6W9E is a KEEP because no offer reaches the minimum. Its template names OF-5001, its saving and the minimum. The test is renamed `test_hb6w9e_keeps_because_no_offer_reaches_the_minimum` everywhere (L4, milestone 6, DoD).
  - Setup-error fix lines never discard changes. They run from the repo root and inspect with `git status` and `git diff -- <path>` (L7, L8).
  - Readers raise `JsonFixtureError` and `TomlFileError`. Composition maps them to `SetupError` in `composition/`. `cli/` never imports `infrastructure/` (D12, milestones 4, 5 and 7, DoD "Layering").
  - Demo rate date was set to 2026-11-02, then changed to the snapshot's date; see the 2026-11-02 owner answers note below (A2, Risks, DoD "JSON dates").
  - Each named rule and money test states its exact input and expected value (milestones 2, 4, 5 and 6).
  - Prototyping milestone 3 decides the pydantic parse path before the fixture adapter, with binary criteria and a recorded result (milestone 3, DoD "Prototype result recorded").
  - Milestones split into ten: the fixture adapter (4) apart from the rate and policy readers (5); composition with JSON (7) apart from table and errors (8). Headings, Progress, DoD and cross-references renumbered.
  - Table output has a REASON column, and the DoD checks the KEEP reasons in it (L7, milestone 8, DoD "Table reasons").
  - Minor fixes: milestone proofs point at DoD items, the `-k` proof is gone, the Decision Log and Surprises claims about the index are corrected, the Python-version doctor check is dropped (S7, L8), argparse errors exit 2 in the three-line format, `Status` and `DecidedBy` hold only the members this plan emits, half-even has examples and `-0.00` prints as `0.00`, rate `as_of` is ISO text, a per-status shape is written in L1, the test layout is two modules plus `conftest.py`, L11 covers the two AGENTS.md changes with a DoD check, and the check-script DoD checks its exact command lines.
  - A2 no longer names the rate's source, because the index keeps the source out of public docs.

2026-11-02, owner question: should two currencies be converted before a compare? Yes, and the rules already do: L2 now says so in one place. `Money` keeps the raise as a guard, per `.claude/rules/python.md`.

2026-11-02, owner answers: rate date and local checks. The demo rate is dated 2026-07-07, the day before the fare snapshot's capture date, in D6, A2, L6, milestone 5, the expected results, the risks and the DoD. The RT5K8B figures follow from the rate: 1,836.79 EUR, a 363.21 EUR saving and a 43.73 EUR minimum. The test names and the DoD item that carried the earlier figures (327.17 EUR and 44.59 EUR) now carry the current ones. The workflow file is out of scope; milestone 1 writes `scripts/check.sh` instead, and every all-checks DoD item runs it. The owner gate section is removed, because it held only the hosted run. The seventh risk is rewritten, and the pointer to the owner gate is removed.

2026-11-02, owner answer: the demo rate is the day before the snapshot, 1 EUR = 1.1433 USD dated 2026-07-07. Figures and test names updated (363.21 EUR, 1,836.79 EUR, 43.73 EUR, 114.33 USD). The stale risk about a Python-rule conflict is removed, because L2 follows the rule.

2026-11-02, owner answer: demo scenarios and documented limits. The owner approved the scenario data set and the `--data` flag (D34, L12, milestone 11), and the documented limits in the design document (D35), which plan 04 carries. This plan adds the scenarios and their tests only. The stale RT5K8B table value (358.54 EUR) is corrected to 363.21 EUR in the Definition of done.

2026-11-02, implementation start: the owner dismissed the missing critic round for milestone 11 and asked to implement all milestones. Six spot-check defects were fixed (see the Decision Log entry of the same date).
