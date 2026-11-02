# Agent review with a live model

Status: ready

This ExecPlan is a living document. Progress, Surprises & Discoveries, Decision Log and Outcomes & Retrospective are kept current as work proceeds. Repo plan rules: none. Starts after: Rules-only review.

## Progress

- [x] (2026-11-02) Round 3 findings applied in this revision. Status is `ready`.
- [x] (2026-11-02) Owner confirmed Q1: `.env.example` keeps `OPENAI_MODEL=gpt-6-luna`; the owner's `.env.local` sets the value for local runs. The plan has no code default for the model.
- [ ] Rules-only review landed. Its names are checked against this plan before Milestone 2: `offers_on_route(snapshot, booking)`, `review_booking` (the per-booking function that runs every per-booking step, including the INVALID_DATA cases, and returns `Rebook`, `Keep` or `Invalid`, each with `reasoning`), `review_snapshot(source, rates, policy)`, the composition entry that takes `environ` and returns the exit code, `SetupError` (fields `error`, `reason`, `fix`) in `composition/`, `Status`, `DecidedBy`, `Recommendation`, `ExchangeRates`, `NoRate`, `ReshopSource`. Any difference is recorded in Surprises & Discoveries and this plan is updated before Milestone 2.
- [ ] Baseline saved before any edit: `uv run --all-extras fare-reshop review --model none > /tmp/reshop-none-before.json` exits 0.
- [ ] Milestone 1 - Confirm the OpenAI request shape and commit the request builder.
- [ ] Owner-run smoke check: one booking, one live request, real key, recorded in the Decision Log before plan 03 starts.
- [ ] Milestone 2 - Model seam, transcript, canonical JSON and prompt.
- [ ] Milestone 3 - Tools and the loop for one booking.
- [ ] Milestone 4 - Safety check, outcome types, the report row and the serializer.
- [ ] Milestone 5 - Tool errors and stable tool output.
- [ ] Milestone 6 - Turn cap, repeated calls and one-booking isolation.
- [ ] Milestone 7 - OpenAI adapter behind the model seam.
- [ ] Milestone 8 - `--model openai` CLI path, setup errors and doctor checks.
- [ ] Milestone 9 - Docs and ADRs for the live model.
- [ ] Milestone 10 - Scripted-fake scenario tests (a, b and c, including the bad pick). Needs plan 01 milestone 11.
- [ ] Definition of done: every checkbox below ticked with its command output recorded here.

Updated at every stopping point. This list, not memory, says where the work is.

## Background / why now

After this plan, a travel agent can run the review with a live OpenAI model. For each booking that has at least one eligible offer, the model picks either one offer to rebook on or keep, and writes a short rationale and a confidence. The model's confidence is its own estimate. It is labeled "model estimate, not calibrated" wherever it appears. The model reads the facts through three read-only tools. Plain code then checks the model's pick against the same rules and money math that the rules-only review uses. Nothing is booked.

A model keep is always reviewed. When an eligible offer exists, the rules found a saving that the model turned down. No code can tell whether that trade-off was right, so a person decides, and the result is `NEEDS_REVIEW` (D19), never `KEEP`. A flagged rebook (for example a schedule change) is still `REBOOK`, and the approval flags show in the FLAGS column of the table.

The model path needs the rules first. Plan 01 gives one per-booking function that runs every rule step and returns `Rebook`, `Keep` or `Invalid`. This plan reuses it, so the steps exist once.

Today the repo has no code. Plan 01 (Rules-only review) must land first.

## User stories

### S2 - Review with a live model

As a travel agent, I want the bookings worth a second look reviewed by a model that weighs the trade-offs and writes a short rationale, so that each recommendation explains itself in plain words.

Walkthrough:

1. The agent copies `.env.example` to `.env.local` and sets `OPENAI_API_KEY` and `OPENAI_MODEL`. Error: the `live` extra is not installed; exit code 2 with "run uv sync --extra live". Error: no key or an empty key; exit code 2 with "OPENAI_API_KEY is not set", before any call. Error: `OPENAI_MODEL` is unset or empty; exit code 2 with "OPENAI_MODEL is not set", before any call.
2. The agent runs `uv run --env-file .env.local fare-reshop review --model openai`.
3. Bookings with no eligible offer are settled by code as in S1, with no model call.
4. For each other booking the model gets a first message naming the booking, then calls tools: `get_booking`, `search_offers`, `check_offer`. Error: a bad tool argument, an unknown tool name or an unknown offer id goes back to the model as a tool error with a hint. Error: the same call twice in a row, or 10 turns without a final answer, ends that booking with `INCOMPLETE_ANALYSIS`. Error: the provider fails (network, timeout, rate limit, server error); that booking gets `INCOMPLETE_ANALYSIS` with `incomplete_reason: provider_error`, and the others continue. A refusal is a final step, not a provider failure: `INCOMPLETE_ANALYSIS` with `incomplete_reason: refusal`. Error: the key is rejected, the model name does not exist, or the key may not use the model; the run stops and exits 2 with a fix line (P18).
5. The model returns rebook with an offer id, or keep, plus a rationale and a confidence. The safety check re-runs the rules and the money math. A rebook whose offer is not on the route, fails a rule or misses the minimum becomes `NEEDS_REVIEW` with the reason. A keep while an eligible offer exists becomes `NEEDS_REVIEW` with "Model and rules disagree", the rules' view and the model's rationale.
6. Output as in S1, with `decided_by: model` for an accepted rebook, the tool trace, the turn count and token usage per booking. When the model's valid choice is not the highest saving, `best_offer_id` names the one that is.

## Scope and non-goals

In scope: capability "review with a live model" from the index, which is story S2 and nothing else. That means the model seam, the three tools, the loop with its limits, the final-answer parsing, the safety check, the prompt file and its version, the trace, the OpenAI adapter, the `--model openai` CLI path with its setup errors, the doctor checks for the live extra, the key and the model name, the scripted-fake scenario tests, and the documentation this plan owns.

Documentation this plan edits: `AGENTS.md` line 22 (the model's role), and the project overview sentence that plan 01 changed (line 7 when plan 01 lands). Plan 01 removed the words "how confident it is" from that sentence (its L11). This plan adds them back, with the label "model estimate, not calibrated", because the model mode now exists. This plan also writes the `GLOSSARY.md` terms and ADRs 0002 and 0003. Plan 04 owns `README.md` and `DESIGN.md`.

Non-goals: recording a run and replaying it (plan 03); changing the default mode away from `none` (plan 03); token and cost budgets (D27); a model-based prefilter (D27); any tool that writes or books (D2); masking booking data (D30); a second model provider; streaming; reasoning effort above `none` (D21); running bookings in parallel (P3); changing the rule functions, the fixtures, the exchange-rate file or the policy file; editing `.env.example` (the owner owns that file, D21). The rules-only output must stay byte-for-byte the same for `--model none`.

## Context and orientation

This section defines every term the implementer needs. Read it fully before Milestone 1.

### The contract from Rules-only review (exists after Rules-only review lands)

This plan builds on plan 01, which is not built yet. The names below are the ones plan 01 fixes. When plan 01 lands, the Progress check confirms every name.

The package is `fare_reshop_agent/reshopping/`, laid out by D10: `domain/` holds the value objects, `domain/port/` holds the two ports, `orchestration/` holds the review logic, `infrastructure/<technology>/` holds adapters, `composition/` builds the object graph for each mode, and `cli/` parses arguments and prints.

Plan 01 provides these, which this plan uses by name:

- `offers_on_route(snapshot, booking)`: the one route definition. It returns the offers with the same origin, destination and departure date as the booking. This plan uses it for `search_offers`, `check_offer` and the safety check. This plan never writes a second route match.
- `review_booking`: the per-booking function. It runs every per-booking step, including the INVALID_DATA cases, and returns the domain result `Rebook`, `Keep` or `Invalid`, each carrying its `reasoning`. The rules' `Rebook` names the highest-saving eligible offer. This plan calls it for every booking in model modes too.
- `review_snapshot(source, rates, policy)`: maps `review_booking` over the bookings. Plan 01's report uses it in `none` mode.
- The one-offer evaluation function, which takes one booking and one offer and returns an `OfferEvaluation`. The tool `check_offer` and the safety check call it.
- The composition entry, which takes the environment as a `Mapping[str, str]` and returns the exit code. The CLI passes `os.environ`. Plan 02 adds one keyword parameter to it, `model_factory` (P27).
- `SetupError` with the fields `error` (what went wrong), `reason` (why) and `fix` (the command or instruction that fixes it). It lives in `composition/`. The CLI prints the three fields as three lines and exits with code 2.
- The report type and its serializer. Output is JSON with indent 2 and fixed key order. Money in JSON is always an object `{amount, currency}` with `amount` as two-decimal text. Rates are text. The table has REASON and FLAGS columns.

Domain value objects (plan 01, D11) are frozen dataclasses. Plan 01 names `Currency`, `Money`, `Cabin`, `BookingRef`, `OfferId`, `Booking`, `Offer`, `ExchangeRate`, `NoRate`, `RuleName`, `RuleResult`, `OfferEvaluation`, `ReviewPolicy`, `Status`, `DecidedBy`, and the union `Recommendation` of `Rebook`, `Keep` and `Invalid` (D9). The rules are `cabin`, `refundable`, `bags`, `stops`, `seats`, `future_change_fee` and `exchange_rate` (D3), in that order. An offer is eligible when every rule passes and its rounded nominal saving meets the minimum saving (D5).

The `ReshopSource` port (D12) returns one snapshot. The `ExchangeRates` port (D6) returns an `ExchangeRate` or a `NoRate`, never a bare `None`.

The CLI is `fare-reshop review` with `--model`, `--format` and `--record`, and exit codes 0 (done), 1 (internal error), 2 (setup error) and 3 (stale recording). Exit code 3 belongs to plan 03. Every CLI error prints three lines, and a traceback only under `--debug` (D31).

### Outside knowledge, in plain words

The OpenAI Responses API is the HTTP interface this plan uses. A request carries input items (instructions, earlier messages, tool calls and their results) and tool definitions. The reply carries output items. The facts this plan relies on, checked in the current OpenAI documentation and the openai-python SDK documentation:

- A function call item carries a `call_id`, a `name` and an `arguments` value that is a JSON string. The string may be malformed, so this plan treats it as raw text until orchestration parses it.
- A message item carries content parts. Its text is an `output_text` part, and a refusal is a `refusal` part with the refusal text.
- A response has a status. When the output token cap is reached, the status is `incomplete` with the reason `max_output_tokens`.
- `parallel_tool_calls` set to false makes the model return zero or one tool call per reply.
- `store` set to false means the provider keeps no state, so each turn sends the whole transcript.
- The SDK's error classes, all subclasses of `APIError`: `APIConnectionError` (transport failure), with the subclass `APITimeoutError`; `APIStatusError` for every 4xx and 5xx, with the subclasses `BadRequestError` (400), `AuthenticationError` (401), `PermissionDeniedError` (403), `NotFoundError` (404), `RateLimitError` (429) and `InternalServerError` (5xx). Because `APITimeoutError` subclasses `APIConnectionError`, a handler must test it first.
- The client takes a `timeout` option. The SDK retries timeouts, 429 and 5xx responses twice by default. This plan adds no retry of its own.

Function calling lets the model ask for a named function with JSON arguments. The model never runs code. Our code runs the function and sends the result back as an input item that names the call id. The three tools are read-only.

Strict mode is a setting on a tool or on a structured output. The provider then enforces the JSON schema. Our code still checks every argument and every answer, because the repo's Python rules keep parsing in our code.

Structured output is the provider feature that forces the final answer into a JSON schema, set through the text format parameter of the request.

Reasoning effort controls hidden reasoning. This plan sets it to `none` in every request, so no reasoning items come back that would have to be passed on.

Token usage is the input and output token count the provider bills for one request.

A transcript is our own ordered record of one booking's conversation: the booking reference, the turn number, the instructions, the tool specs, a first message that names the booking, each reply's tool calls and each tool result. It is an immutable value that the loop extends after every turn. The transcript is the only state between turns, because `store` is off.

A turn is one call to the model and its reply. A booking's turns are counted from its first call, starting at 1. A reply is one of four kinds: tool calls (one or more function calls), final text, a refusal, or a provider failure.

Call ids link a tool call to its result. The loop assigns each call the id `call_<turn>_<n>`, where the turn and the position n both start at 1. The loop assigns the ids once. The adapter writes the loop's ids into the next request, on both the function call item and its output item. Provider call ids never reach the reply type, the transcript or the recordings in plan 03.

The safety check is the code step after the model's final answer. It re-runs the one-offer evaluation for the offer the model chose, and decides whether the choice may stand.

A digest is a SHA-256 hash of some bytes, written as 64 hexadecimal characters. The prompt version is the digest of the prompt file's bytes.

A seam is the place where production code and a test or a second implementation can be swapped. A port is an interface the domain or orchestration defines, and an adapter implements it against one technology. `AgentModel` is a port in `orchestration/`. The OpenAI class in `infrastructure/openai/` is its adapter.

### Current repo facts

The repo at `/Users/igby/Work/personal/fare-reshop-agent` has `AGENTS.md`, `README.md`, `docs/future-work.md`, `fixtures/pnrs.json`, `fixtures/fares_feed.json`, `.env.example` and `.claude/rules/python.md`. There is no Python package yet.

`AGENTS.md` line 22 today reads "The model may choose which read-only tools to call and write the short rationale." This plan replaces it (Milestone 9).

`.env.example` line 3 reads `OPENAI_MODEL=gpt-6-luna`. That is the owner's value. This plan reads it and never edits the file (P17).

Python rules that bind every change are in `.claude/rules/python.md`. The important ones: `uv` for every command; `ruff`, `mypy --strict` and `pytest` must pass; no `Any`, no `# type: ignore`, no `noqa`, no `cast` as a fix; annotate every function; `pydantic` only in `infrastructure/`; money as `Decimal` built from text, JSON parsed with `parse_float=Decimal`; no I/O, no environment reads and no network at import time; environment variables read only in `composition/`; `print` only in `cli/`; tests are plain pytest functions with bare asserts, run offline, and replace ports with in-memory fakes instead of patching our own code.

### The test seams

Milestone 3 tests the loop for one booking through `run_booking_loop`, a public function of the loop module in `orchestration/`. From Milestone 4 on, the tests use `review_with_model`, the orchestration function this plan adds as a sibling of plan 01's `review_snapshot` (P20). It takes the `ReshopSource`, the `ExchangeRates` port, the `ReviewPolicy`, the `AgentModel` and the `Prompt`.

The scripted fake model is a class in `tests/` that implements the `AgentModel` port. It returns a fixed sequence of replies for each booking and records every transcript it was shown. It is never a runtime option in the package.

The CLI tests call the composition entry with an environment mapping and a model factory, as plan 01's tests call it.

### Terms used in this plan

Eligible offer: an offer that passes every rule and meets the minimum saving. No eligible offer means `KEEP` by rules.

Status values: `REBOOK` (rebook on the chosen offer), `KEEP` (keep the ticket), `NEEDS_REVIEW` (a person must look; the safety check or the rules blocked the model's choice, or the model kept while an eligible offer existed), `INCOMPLETE_ANALYSIS` (the model loop ended without a usable answer, with a reason) and `INVALID_DATA` (the booking or its data failed the boundary checks; no model call).

Mixed reply: a reply that holds tool calls and final text together. It ends the booking as `bad_final_answer`, and none of its calls run.

Approval flag: a warning from a fact, such as a schedule change or a carrier change. It never fails a rule.

Model text: any sentence the model wrote. In model modes every such sentence sits in `reasoning` after the label "Model text:", so a reader can tell it from the code's facts. The code's figures live in their own fields.

## Locked decisions

Every decision below is locked. The implementer does not reopen it. The index rows are copied as they stand after this revision's index changes (see the report of the round 3 pass); the rows that change are D9, D15, D16 and D17. Decisions P1 to P27 are this plan's own picks, where the index is silent. Each P entry names its reason and the options it rejected.

D2. Every result goes to a person. Nothing books, and no write tool exists (index D2, owner decision).

D10. Layout: `fare_reshop_agent/reshopping/` with `domain/`, `domain/port/`, `orchestration/`, `infrastructure/<technology>/`, `composition/` and `cli/`. The model port lives in `orchestration/`, and there is no inbound port (index D10, owner decision).

D13. Python 3.12 or newer, `uv`, `pydantic` v2 only in `infrastructure/`, `pytest`, `ruff`, `mypy --strict`. `openai` is an optional extra named `live`. The model's tool arguments and final answer are parsed in `orchestration/` with `json.loads` and explicit checks (index D13, owner decision).

D14. One local check command, `./scripts/check.sh`, runs `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy` and `uv run pytest -q` in that order, and exits non-zero on the first failure. Every plan's checks run it, and the README documents it. Plan 02 adds `--all-extras` to each of the four commands when the `live` extra lands. Options that lost: four commands typed into each plan's checks, which drift apart, and no single command gating the repo. This plan applies the `--all-extras` addition to each of the four commands, because the `live` extra holds the SDK that mypy and the tests import (P26).

D1. Plain-code rule check first. The model sees only bookings with at least one eligible offer. A safety check runs after the model. (Owner) Options that lost: a model prefilter first, which drops real savings before the free checks run; the model on every booking, which pays for calls code can settle; code decides and the model only writes text, which leaves no agent to show. Prior art: Anthropic, "Building effective agents" (2024).

D9. Output contract, `schema_version: 1`. Top level: `mode`, `as_of` (the snapshot capture time), `data_issues`, `results`. Each result: `pnr`, `status` (`REBOOK`, `KEEP`, `NEEDS_REVIEW`, `INCOMPLETE_ANALYSIS`, `INVALID_DATA`), `rebook` (true only for `REBOOK`), `decided_by` (`rules` for KEEP, INVALID_DATA and every `none`-mode result; `model` for REBOOK from the model; `safety_check` for NEEDS_REVIEW; `null` for INCOMPLETE_ANALYSIS), `incomplete_reason` (`turn_cap`, `repeated_call`, `bad_final_answer`, `refusal`, `provider_error`; null otherwise), `offer_id`, `nominal_saving` and `approval_flags` (all three for the chosen offer; null or empty for KEEP, INVALID_DATA and INCOMPLETE_ANALYSIS; for NEEDS_REVIEW, the offer the model chose, if any), `best_offer_id` (only when the model's valid choice is not the highest saving), `evaluations` (every offer with its rule results, its saving and the exchange rate it used; empty for INVALID_DATA), `minimum_saving` (in the booking's currency), `confidence`, `confidence_note` (model modes, when confidence is set: "model estimate, not calibrated"), `reasoning` (built from rule results when rules decide), `invalid_reason` (INVALID_DATA only), and `trace` (model modes only). No `execution_ready` field, because every result goes to a person (D2). In code, the domain result is a union of frozen types (`Rebook`, `Keep`, `Invalid`); orchestration wraps it with the model outcomes (`ModelRebook`, `NeedsReview`, `Incomplete`) and the trace. The serializer derives `status` from the outcome's type, and `decided_by` from the type, so they cannot disagree. Options that lost: keep `execution_ready` (always false, so noise); a `NEEDS_DATA` status (D4 removed its cause); no schema version (consumers break silently). Changed in this pass: money is an object `{amount, currency}`, and `confidence_note` was added.

D15. CLI: `fare-reshop review` with `--model none|openai|recorded`, `--format json|table` and `--record` (only with `openai`). The default model is `none` until the replay plan lands, then `recorded`. `--record` with any other model is a setup error. Also `fare-reshop doctor` (S7) and `--debug`. Exit codes: 0 done, 1 internal error (a bug; traceback only with `--debug`), 2 setup error (files, policy, missing extra, missing key, missing model, failed recording, bad flags, provider authentication, provider model not found, provider permission denied), 3 stale recording. Options that lost: a web UI, which is out of scope; separate commands per mode, which add surface for the same flow. Changed in this pass: the model-not-found and permission-denied setup errors were added.

D16. The model seam is `AgentModel.next_step(transcript) -> ModelReply`, and every adapter exposes `model_name` (text), which the record-and-replay plan writes into the recording. A `ModelReply` is one of four frozen types: `ToolCalls` (the calls, each with its name and raw argument text, an optional text, and the turn's usage), `FinalText` (the text and the usage), `Refusal` (the refusal text and the usage) and `ProviderFailed` (one code from a closed set). The reply is stateless: the transcript holds everything the model needs. The loop assigns call ids (`call_<turn>_<n>`) once; adapters only translate to and from provider ids. A provider failure is a typed reply, not an exception. The loop, the limits and all parsing live in `orchestration/`. Options that lost: a whole-run seam, which copies the loop into every adapter; a stateful session, which leaks provider response chaining into the seam. Changed in this pass: the reply union has four members, and a reply with calls and text is one `ToolCalls` with its text.

D17. Three tools: `get_booking()`, `search_offers()`, `check_offer(offer_id)`. Code binds the booking, so the model never passes a booking reference. Results are `{ok: true, data, hint}` or `{ok: false, error: {code, message, hint}}`. Tool specs are written by hand in the repo, error messages come from fixed templates, offers are sorted by offer id, and money is an object `{amount, currency}` with `amount` as two-decimal text, so the same input gives the same bytes. Options that lost: six tools, because two always return the same thing and two answer one question; specs generated from pydantic, because they change with the library version. Changed in this pass: the tool is named `check_offer` (plan 01 owns the name `evaluate_offer` for the domain function), and money is the object shape of plan 01.

D18. At most 10 model turns per booking. The same tool with the same arguments twice in a row ends the booking. Bad tool arguments or an unknown offer id go back as a tool error with a hint. A final answer that fails the schema ends the booking. Each end state is `INCOMPLETE_ANALYSIS` with its `incomplete_reason`. All tool calls in one reply run in order and the reply counts as one turn; each call is compared with the call before it for the repeat rule; a reply with tool calls and non-empty text is `bad_final_answer`. A confidence that is not a finite number between 0 and 1 is `bad_final_answer`. No token or cost budget in this slice. (Owner)

D19. The model picks an eligible offer or says keep, and writes the rationale. The safety check re-runs the rules and the money math for the chosen offer. A failing choice becomes `NEEDS_REVIEW` with the reason. A keep while an eligible offer exists becomes `NEEDS_REVIEW` with the rules' view and the model's rationale. A valid choice that is not the highest saving is accepted, and `best_offer_id` names the highest one. (Owner) Why a model keep is always reviewed: the rules found a saving the model turned down, and no code can say whether that trade-off was right, so a person decides. Options that lost: trusting the model's numbers, the core failure mode; forcing the highest saving, which overrides the trade-offs; letting a model keep stand as `KEEP`, because a missed saving would pass unseen.

D20. The final answer is one root object `{decision, offer_id, reasoning, confidence}`: `decision` is `rebook` or `keep`, `offer_id` is required and is text for rebook and `null` for keep, `confidence` is between 0 and 1. Strict structured output enforces the shape; orchestration rejects a rebook without an offer id or a keep with one as `bad_final_answer`. `confidence` is the model's own estimate, labeled uncalibrated, and `null` when rules decided.

D21. The live model is read from `OPENAI_MODEL`; `.env.example` holds the owner's value (`gpt-6-luna`). The agent plan never overwrites it. It runs through the Responses API, with reasoning effort set to `none` in every request. Each turn sends the whole transcript with `store` off. The key comes from the environment; `uv run --env-file .env.local` loads it. Milestone 1 confirms the request shape and the model against the current OpenAI docs. (Owner)

D22. Recording wraps any model adapter, and the digests use one canonical serializer owned by `orchestration/` and shared with the tool results. The recording is one file per data set: `recordings/review-run.json` for `sample` and `recordings/scenarios-run.json` for `scenarios`. This plan only builds that serializer (`canonical_json`, P22) and the tool results that use it. The recording itself is plan 03. (Index D22, owner decision.)

D24. Each model-mode result carries a trace: tool calls with arguments, turn count, token usage and the prompt version. A provider failure prints its closed code (`connection`, `timeout`, `rate_limit`, `server_error`), never provider text. Nothing else is logged in this slice.

D25. The prompt is a Markdown file, `orchestration/review_prompt.md`. Its SHA-256 is the prompt version, and the same file is the instructions sent to the model and digested in recordings.

D26. Docs: `README.md`, `DESIGN.md` with the AI-usage note, `GLOSSARY.md`, `docs/adr/` and `docs/future-work.md`. Each plan writes its own glossary terms and ADRs in its last milestone. The docs plan writes the rest. (Owner)

D27. Scope is the thin slice. Not built: a model-based prefilter, token and cost budgets, and a fixed six-tool set. (Owner)

D28. Plans are tracked in the public repo. Every tracked file, commit message and branch name passes the local leak hooks. (Owner)

D30. Only the configured data sets are read: `sample` and `scenarios` (D34). In model modes, booking and offer facts leave the machine in tool results sent to OpenAI. The fixtures hold no names or contact data (A5), so nothing is masked. `DESIGN.md` states this.

D31. First-run experience (S7): `./start.sh` changes to its own folder, checks for `uv`, asks before installing anything, then runs `uv sync`, `doctor` and the default review. Every CLI error prints what went wrong, why, and the fix, with no traceback unless `--debug`. `NO_COLOR` and the terminal check are read in `composition/`. Each plan adds the doctor checks for what it introduces. (Owner)

D32. The booking reference is a `NewType` named `BookingRef`, and offers use `OfferId`. Output keeps the field name `pnr` because the source data uses it.

D34. A second configured data set, `scenarios`, in `fixtures/scenarios/pnrs.json` and `fixtures/scenarios/fares_feed.json`: the same schema as the real fixtures, made-up demo bookings and offers, a top-level `_comment` that says they are made-up demo scenarios, the same capture time (2026-07-08T09:00:00Z), departures after it and USD throughout. The CLI takes `--data sample|scenarios`, default `sample`. The value names a configured data set and never a free path; an unknown value is an argparse error with exit code 2 and the three-line error format. Expected results are in the scenario table of the index. (Owner)

P1. A refusal is its own kind of reply. A refusal reply carries the refusal text and the turn's usage, and ends the booking as `refusal`. Raising an exception was rejected, because the orchestration would then count it as `provider_error`. The text is stored for the trace and is never shown to a reader as a fact.

P2. Provider failures are typed replies, and the reply union is the only shape the loop matches on. `ModelReply` is one of four frozen types. `ToolCalls` holds the calls, each with its name and raw argument text as the provider sent it, an optional `text` (null when the reply has no text), and the turn's usage. `FinalText` holds the text and the usage. `Refusal` holds the refusal text and the usage. `ProviderFailed` holds one code from the closed set `ProviderErrorCode` (`connection`, `timeout`, `rate_limit`, `server_error`) and carries no usage. The adapter returns `ProviderFailed` for connection failures, timeouts, rate limits and 5xx responses, and raises nothing for them. Authentication, permission and model-not-found failures are not provider failures: the adapter raises typed exceptions for them (P18). Other SDK errors propagate as bugs, and the CLI exits 1. We add no retry policy of our own. Options that lost: a `ModelProviderError` exception for provider failures, which would make a typed outcome look like a bug; mapping authentication failures to `provider_error`, which would hide a bad key behind one booking's status; our own retry layer, which would multiply calls on a rate limit.

P3. Bookings run one after another, in the order the snapshot lists them. Replay in plan 03 depends on a fixed order of model turns. Parallel bookings were rejected, because the order of turns would depend on timing.

P4. A turn is one call to `next_step`, whether it returns a reply or a provider failure. The cap of 10 counts every turn in the booking, the final one included. A 10th reply that asks for tool calls ends the booking as `turn_cap`, and its calls do not run. A failed turn counts toward the cap and adds no usage.

P5. The repeated-call check compares each tool call with the call immediately before it in the same booking, across replies and within one reply, in run order. The key of a call is its tool name plus its argument text: the canonical text (P22) when the arguments parse as a JSON object, and the raw text when they do not. A call whose key equals the key of the call before it ends the booking as `repeated_call`. The check runs before the call executes. Equal calls that are not next to each other are allowed.

P6. Each tool error has one of three codes: `bad_arguments`, `unknown_offer` or `unknown_tool`. Each code has one fixed message and one fixed hint (the Tool contract below). The message may repeat the offending value and nothing else from the model's input. A tool error does not end the booking.

P7. The final answer is parsed with `json.loads(text, parse_float=Decimal, parse_constant=reject)`, where `reject` raises for `NaN`, `Infinity` and `-Infinity`. The parsed value must be a JSON object with exactly the four keys of the final-answer schema. `decision` must be `rebook` or `keep`. A rebook needs a non-empty string `offer_id`. A keep needs `offer_id` to be `null`. `reasoning` must be a non-empty string. `confidence` must be a finite decimal from 0 to 1 inclusive; a boolean is not a number. Any other shape ends the booking as `bad_final_answer`. A `ToolCalls` reply whose `text` is not null also ends the booking as `bad_final_answer`, and none of its calls run (D18). The provider's strict structured output asks for the shape, but D13 keeps parsing in orchestration, so the check stays.

P8. The safety check for a model rebook first asks whether the offer id is one of this booking's offers, using `offers_on_route`. If it is not, the result is `NeedsReview` with the check "offer <id> is not on this route and date", the offer id the model gave, and `nominal_saving` and `approval_flags` null and empty. If it is, the code re-evaluates that offer with the one-offer evaluation function. If a rule fails, the check is "rule <rule name> failed, <the rule's reason>", using the first failing rule in the fixed order. If the rounded saving is below the minimum, the check is "nominal saving is below the minimum saving". In the two failing cases the result is `NeedsReview`, and `offer_id`, `nominal_saving` and `approval_flags` come from the code's evaluation. Otherwise the model's rebook stands as a `ModelRebook`. The model's output has no amount fields, so there is nothing to trust.

P9. Result fields by case, with the reasoning templates. Every template is fixed text; only the named values change.

- Accepted rebook (`ModelRebook`): the chosen offer's id, the code's nominal saving and approval flags, `best_offer_id` (below), `confidence` and `confidence_note`, and `reasoning` = "Model text: " followed by the model's rationale.
- `best_offer_id` for an accepted rebook: the id of the highest-saving eligible offer when the chosen offer is not that offer; null when it is. The highest is the rules' `Rebook` from `review_booking`. Ties go to the lower offer id, as in `none` mode.
- Failed choice (`NeedsReview`): `decided_by` safety_check; `offer_id` is the offer the model chose; `nominal_saving` and `approval_flags` come from the code's evaluation (null and empty when the offer is not on the route); `best_offer_id` is null; `reasoning` = "Safety check: " followed by the check text, then ". Rules view: " followed by the highest eligible offer's id, saving and minimum (the template of the rules' view below), then " Model text: " and the rationale.
- Keep while an eligible offer exists (`NeedsReview`): `offer_id`, `nominal_saving` and `approval_flags` null or empty, `best_offer_id` null, `reasoning` = "Model and rules disagree. " followed by the rules' view, then " Model text: " and the rationale. The rules' view is "Rules view: <offer id> passes every rule and saves <saving>, which meets the minimum of <minimum>."
- Incomplete (`Incomplete`): `decided_by` null, `confidence` null, `offer_id`, `nominal_saving` null, `approval_flags` empty, and `reasoning` from one fixed template per incomplete reason. Its `evaluations` are still filled, because the rules ran before the model.
- The model's confidence appears on `NeedsReview` results whenever the model gave a valid final answer, and is null otherwise.

P10. Decimal text has one formatter rule for the whole model-mode output. Money is a JSON object `{amount, currency}`, with `amount` quantized to two places with `ROUND_HALF_EVEN` (L2 of plan 01) and printed as fixed-point text, so `80.00` prints as "80.00". Rates keep the text the rate file stores. Confidence is text printed from the parsed value, so 0.82 prints as "0.82". Every decimal in model-mode output is a JSON string, confidence included.

P11. Every result in a model mode carries a trace, including bookings that rules settled or that were invalid. Those have zero turns, zero token usage and no tool calls.

P12. The top-level `mode` value is the value given to `--model`, so it is `openai` in this plan.

P13. The prompt file is read in `composition/`, and its bytes are passed into orchestration as a `Prompt` value holding the text and the version. Orchestration does no I/O. The version is the lowercase hexadecimal SHA-256 of those same bytes.

P14. The trace holds, in this key order: `prompt_version` (text), `turns` (every turn, including a failed one), `usage` (`input_tokens` and `output_tokens`, summed over the booking's successful turns), `tool_calls` (each call that ran, in run order, with its `name`, its argument text as in P5 and its `ok` flag), and `provider_error_code` (the closed code, or null).

P15. The doctor checks for the live extra, for `OPENAI_API_KEY` and for `OPENAI_MODEL` are reported as optional. They never change doctor's exit code. The doctor prints "set" or "not set" for the key and the model, and never the value of the key.

P16. `--model openai` replaces the rules-only rejection with the live path. `--record` stays rejected with exit code 2 until plan 03 builds recording.

P17. The live model name comes from `OPENAI_MODEL` and has no default in code. An unset or empty value is a setup error with the fix "set OPENAI_MODEL in .env.local (see .env.example)". A silent default would hide which model answered.

P18. Setup and provider checks, in this order. Before any call: the live extra first (only a `ModuleNotFoundError` whose missing module is `openai` is converted, so a bug in the adapter is not hidden), then the key (empty counts as missing, P19), then the model. During a call, the adapter maps the SDK's `AuthenticationError` (401) to `ProviderAuthenticationError`, `PermissionDeniedError` (403) to `ProviderPermissionError`, and `NotFoundError` (404; the Responses call returns it for an unknown model) to `ProviderModelNotFoundError`. Composition maps each to `SetupError` and the run stops at once, with no report and exit 2. The fixes are: for the key, "set OPENAI_API_KEY in .env.local to a valid key"; for the permission, "give the key access to the model in OPENAI_MODEL in the OpenAI project settings, or set OPENAI_MODEL in .env.local to a model the key can use"; for the model name, "set OPENAI_MODEL in .env.local to a model name that exists (see .env.example)".

P19. An empty `OPENAI_API_KEY` counts as missing, as S2 step 1 says.

P20. The orchestration function that runs the live review is `review_with_model`, a sibling of plan 01's `review_snapshot`. It takes the same three inputs plus the `AgentModel` and the `Prompt`, and returns the one report type. For each booking in snapshot order it calls `review_booking`. A `Keep` or `Invalid` result becomes a row with a zero-turn trace, with no model call (P11). A `Rebook` result means an eligible offer exists: the booking goes to the loop, and the rules' `Rebook` supplies the highest eligible offer for `best_offer_id` and for the rules' view. Options that lost: an optional model argument on plan 01's `review_snapshot`, which makes its behavior depend on a flag; a second copy of the rules, which would drift.

P21. The OpenAI adapter lives in `infrastructure/openai/`. It takes an injected client, built in `composition/`, and never reads the environment. Its tests pass a stub client, so no test reaches the network. It writes the loop's call ids on both the function call item and its output item of the next request. Milestone 1 confirms that the provider accepts caller-chosen call ids in input items. If it does not, Milestone 1 stops.

P22. JSON values are typed with a recursive alias, `type JsonValue = None | bool | int | Decimal | str | list[JsonValue] | dict[str, JsonValue]`. Floats are not in the alias, and `Any` is never used. `canonical_json(value: JsonValue) -> str` lives in `orchestration/`. It sorts keys, uses compact separators, writes UTF-8 without escaping, writes decimals in fixed-point text, and raises `TypeError` on a float. Tool results, the repeat check (P5) and the trace's argument text use it. It is separate from the report serializer (P25), which keeps plan 01's indented output.

P23. Result types and the report row. `NeedsReview` and `Incomplete` are frozen dataclasses in `orchestration/`, next to `ModelRebook`. `AgentOutcome` is the union `Recommendation | ModelRebook | NeedsReview | Incomplete`. The report has one row type, `ReviewRow`, which holds one outcome and an optional trace. In `none` mode the trace is absent and the serializer omits the key. In model modes the trace is always present (P11), so the serializer always writes it. Options that lost: two row types with a union, which would give the row a trace that is sometimes absent by type; a separate report type for model modes, which would give consumers two shapes. Plan 01's domain union is not widened, and Status and DecidedBy gain members (below).

P24. `Transcript` holds the `BookingRef` of the booking the loop is for, the `turn` number of the next model call (counted from 1), the `Prompt`, the tool specs, and an ordered tuple of items: the first user message, each reply's calls (`ToolCallItem`, with its call id, name and argument text) and each tool result (`ToolResultItem`, with its call id and canonical result text). The model never supplies a booking reference.

P25. Output key order and model keys. The report serializer is plan 01's: JSON with indent 2 and the default separators. Result keys follow this full order: `pnr`, `status`, `rebook`, `decided_by`, `incomplete_reason`, `offer_id`, `nominal_saving`, `approval_flags`, `best_offer_id`, `confidence`, `confidence_note`, `reasoning`, `minimum_saving`, `exchange_rates`, `invalid_reason`, `evaluations`, `trace`. In `none` mode the serializer omits `best_offer_id`, `confidence_note` and `trace`, so the output stays byte-for-byte the same as plan 01's. In model modes `best_offer_id` and `trace` are always present, with `best_offer_id` null when it does not apply. `confidence_note` is present only when confidence is set. The `trace` object keeps the key order of P14.

P26. This plan's own application of D14: each of the four check commands starts with `uv run --all-extras`, and `scripts/check.sh` is changed in Milestone 1.

P27. The composition entry of plan 01 takes one more keyword parameter, `model_factory`, a function from the environment mapping to an `AgentModel`. Its default builds the OpenAI adapter, checking the extra, the key and the model first (P18). The rejected-key, unknown-model and permission tests pass a factory that returns a scripted model. This is the one change this plan makes to plan 01's entry signature. Options that lost: patching the adapter's module, which the repo's Python rules forbid; an environment key that reaches the real client, which would call the network in tests.

P28. Milestone 1 is a documentation-and-typecheck step, not a runtime prototype. Its gate is `mypy --strict` on a committed, typed request-builder module, `fare_reshop_agent/reshopping/infrastructure/openai/request_builder.py`, which builds the two request shapes from primitive inputs using the SDK's own parameter types. The module is kept and extended in Milestone 7. Options that lost: a scratch script in `/tmp` with pasted text, because a check on pasted text proves nothing about the repo's code.

P29. Composition constants. `REQUEST_TIMEOUT_SECONDS` (60.0) is passed to the OpenAI client as its timeout. `MAX_OUTPUT_TOKENS` (2000) is passed to the adapter and sent as `max_output_tokens`. Both are named constants in `composition/`, with no magic literal elsewhere. A response with status `incomplete` maps through the normal parsing: its text rarely parses, so it ends the booking as `bad_final_answer`, and any tool calls it holds are run, subject to the usual checks.

## Tool contract (locked)

The three tools are declared by hand in `orchestration/` (D17). Each has `strict: true` and an object schema with `additionalProperties` set to false. Every tool result is serialized with `canonical_json` (P22). Every successful result has `ok` true, a `data` object, and `hint` null. Every failed result has `ok` false and an `error` object with `code`, `message` and `hint`. Money in tool data is an object `{amount, currency}` with `amount` as two-decimal text (plan 01's money shape). Rates are text.

Tool `get_booking`, no arguments. `data` fields: `pnr` (text), `passengers` (integer), `origin` (text), `destination` (text), `departure_date` (text, `YYYY-MM-DD`), `departure` (text, the fixture's naive local time), `carrier` (text), `flight_number` (text), `cabin` (text, one of the five cabin names), `refundable` (boolean), `baggage_pieces` (integer), `stops` (integer), `price_per_passenger` (money), `total_paid` (money), `change_fee_per_passenger` (money).

Tool `search_offers`, no arguments. `data` has one field, `offers`: an array of the offers on this booking's route (`offers_on_route`), sorted by `offer_id`. Each item has `offer_id` (text), `origin` (text), `destination` (text), `departure_date` (text), `departure` (text), `carrier` (text), `flight_number` (text), `cabin` (text), `refundable` (boolean), `baggage_pieces` (integer), `stops` (integer), `seats_available` (integer), `price_per_passenger` (money) and `change_fee_per_passenger` (money).

Tool `check_offer`, one argument `offer_id` (text). `data` is the one-offer evaluation from plan 01, with: `offer_id` (text), `rules` (an array in the fixed rule order, each item with `rule` text, `result` text `PASS` or `FAIL`, and `reason` text), `nominal_saving` (money or null when no rate exists), `approval_flags` (an array of text, possibly empty), `exchange_rates` (an array, one item per conversion, each with `use` text, `rate` text, `direction` text and `as_of` text), `minimum_saving` (money in the booking's currency) and `eligible` (boolean: every rule passes and the rounded saving meets the minimum).

Final answer, the only shape the model may return. It is one root object with exactly these four keys: `decision` (text, `rebook` or `keep`), `offer_id` (text for rebook, null for keep), `reasoning` (text) and `confidence` (number from 0 to 1). The strict schema marks all four as required, sets `additionalProperties` to false, uses an enum for `decision`, and uses the type list `["string", "null"]` for `offer_id`. The schema name is `review_decision`. Orchestration checks every rule of P7 again on the parsed value.

Tool error codes, each with its fixed message and hint. `bad_arguments`: message "Arguments for <tool name> are not valid."; hint "Send a JSON object with exactly the keys in the tool's spec, each of the right type." `unknown_offer`: message "Offer <offer_id> is not on this booking's route and date."; hint "Pick an offer_id from search_offers." `unknown_tool`: message "There is no tool named <tool name>."; hint "Use one of: get_booking, search_offers, check_offer." The `<...>` parts repeat the model's own value and nothing else.

## Alternatives considered

A model call for every booking was rejected under D1. A model that sees every booking pays for calls that the rules can settle, and it can change a rules result.

Parallel model calls were rejected under P3. They would make the order of turns depend on timing, and plan 03 needs a fixed order.

An exception for refusals was rejected under P1. A refusal is a normal answer the provider gives.

A raised exception for provider failures was rejected under P2 and index D16.

Mapping authentication failures to `provider_error` was rejected under P2. One rejected key would then end every booking as incomplete and the run would exit 0 with misleading results.

Adding retries of our own was rejected under P2. The SDK already retries transient errors.

A pydantic model for the tool arguments and the final answer was rejected. D13 keeps pydantic in `infrastructure/`.

Two reply shapes for the final answer were rejected under D20. Strict mode does not accept a union at the root.

A separate report type for model modes was rejected under P23 and P25.

A stored response id to chain turns was rejected under D21. Replay needs the transcript to be the only state.

Turning the trace off for rule-settled bookings was rejected under P11.

Two row types (rules and model) with a union was rejected under P23: the simpler single row with an optional trace gives one shape, and the serializer chooses keys by mode.

Money as a bare decimal string in tool data was rejected under P25 and D17 in favor of plan 01's money object, so one money shape serves tools and output.

A tool named `evaluate_offer` was rejected, because plan 01's domain function already has that name.

## Invariants, risks and open questions

Invariants that must hold at every step. Money is always `Decimal`; a float never enters money math, and the model's numbers are never trusted (D19). No tool writes anything (D2). Every model-mode result goes through the safety check before output, and a provider failure never produces a rebook. A booking that the rules settle never reaches the model. A test never reaches the network and never needs a key. The prompt version is the digest of the bytes the model received. Output is deterministic: results and evaluations are sorted as plan 01 sorts them, the output keys follow P25, decimals are fixed-point text. Tool results and the trace's argument text use `canonical_json`. There is one route function and one one-offer evaluation function, both from plan 01.

Risk: cost of a live run. Assumption A3: one live run costs under 1 USD at the configured model's prices. Milestone 1 records the prices in the Decision Log, and the trace records token usage, so the cost can be checked after a run. If the cost is higher, stop and record the figure in Surprises & Discoveries. Mitigation: the 10-turn cap and the repeated-call check. Rollback: unset the key; the default path needs no key.

Risk: sending booking facts to a third party. Assumption A5: the fixtures are made up and hold no names or contact data (D30). If a later fixture or a real feed carries personal data, stop before any live run and record it.

Risk: the model named by `OPENAI_MODEL` may not exist, may not accept reasoning effort `none`, or may have other prices. Milestone 1 checks the name against the current docs, records its prices, and stops if a check fails.

Risk: the installed `openai` SDK changes its names, error classes or constructor arguments. Mitigation: Milestone 1 records the exact version in the lock file; `uv.lock` is only changed by `uv`. The adapter's tests build the SDK's error classes with the constructor signatures of that version.

Risk: the provider does not accept caller-chosen call ids in input items (P21). Milestone 1 confirms it.

Risk: the model's rationale is weak. Mitigation: the safety check and `NEEDS_REVIEW` (D19), and the label "model estimate, not calibrated" on confidence. The plan does not claim the rationale is correct.

Risk: plan 01 names something differently. The Progress check confirms the names when plan 01 lands.

Risk: a lazy import in tests. The missing-extra test hides the `openai` module and the adapter module by setting their module-table entries to `None`, so the lazy import runs again and fails. If the import does not fail as expected, record what Python raised in Surprises & Discoveries.

Risk: a 404 is not always a bad model name. Mitigation: the fix line names the model variable and the one check the owner can make; the error text says the provider refused the model name.

Open questions: none. Q1 is answered: the owner confirmed `gpt-6-luna` in `.env.example`, and sets the local value in `.env.local`.

## Milestones

### Milestone 1 - Confirm the OpenAI request shape and commit the request builder

This milestone is a documentation-and-typecheck step. It settles the request shape this plan relies on and commits the module that builds it. It does not run the adapter, and it makes no model call.

Goal: the request shape is confirmed against the current OpenAI documentation and the installed `openai` SDK, the configured model is confirmed with its prices, the SDK version is pinned as the optional `live` extra, and the request builder module that Milestone 7 extends is committed and typed.

Work: add `openai` as the optional extra named `live` with `uv add --optional live openai` (D13). Change `scripts/check.sh` so each of its four commands starts with `uv run --all-extras` (P26). Write `fare_reshop_agent/reshopping/infrastructure/openai/request_builder.py`. It builds the keyword arguments of one Responses request from primitive inputs: the model name, the instructions text, the input items, the one function tool spec, the final-answer schema, and the request constants. It sets `store` to false, reasoning effort to `none` and `parallel_tool_calls` to false, and types the result with the SDK's own parameter types. It takes no client and reads no environment. Read the current Responses API reference and the installed SDK's type definitions. Confirm, against the documentation and the SDK's types, the six points below. Read the model name from `OPENAI_MODEL` in `.env.example` and do not edit that file. Record each finding in the Decision Log, starting with the entry "Milestone 1 result", which holds: the SDK version (once, in that entry), the documentation pages read, the date, the exact field names, the model name, its input and output prices per million tokens, and the mypy summary line on a line of its own.

The six confirmations: first, a function tool can be defined with a JSON schema and strict mode on. Second, the final-answer schema (one root object, four required keys, `additionalProperties` false, the nullable `offer_id` written as a type list) is accepted with strict mode on through the text format parameter. Third, `store` can be set to false. Fourth, reasoning effort can be set to `none` for the configured model, and the model appears in the documentation's model list with its prices. Fifth, a function call and its output can carry a caller-chosen call id (P21). Sixth, the usage fields, the shape of a refusal part, the status `incomplete` with its reason, and the SDK's exception classes with their constructor signatures in the installed version, including that the timeout error subclasses the connection error.

Seam: none in this milestone. The fake client that tests use is built in Milestone 7.

Promote criteria, all binary. Promote when all of these hold for the SDK version in `uv.lock`: the Decision Log entry "Milestone 1 result" names, for each of the six confirmations, the documentation page and the exact field name; the mypy strict run passes; and the configured model appears in the documentation's model list, accepts reasoning effort `none`, and has its prices recorded. When all hold, D21 stands and Milestone 2 may start.

Discard criteria: stop if any confirmation fails, if mypy rejects the request builder, or if the configured model is missing or does not accept reasoning effort `none`. Do not start Milestone 2. Record what differs, with the documentation page, in Surprises & Discoveries, and set the plan's Status line to `blocked - <what differs>`. Changing the model or the request shape changes D21, so the owner decides the next step.

Proof: `uv run --all-extras mypy --strict fare_reshop_agent/reshopping/infrastructure/openai/request_builder.py` ends with the line "Success: no issues found in 1 source file", and the Decision Log entry "Milestone 1 result" exists.

### Owner-run smoke check (before plan 03 starts)

This check is run by the owner with a real key. It is not a gate and no agent run can pass it on a clone.

The owner makes one live Responses call for one booking, using request A of Milestone 1 (one user message naming the booking, the `get_booking` tool, reasoning effort `none`, store off) through the request builder and the SDK client, with the key in `.env.local`. The owner records in the Decision Log only: the model name, the status of the response, and the token usage. The key and the response headers are never printed or recorded. The smoke proves the live request shape and the model, which plan 03's recording depends on. It does not prove the whole loop; plan 03's recording run does that.

### Milestone 2 - Model seam, transcript, canonical JSON and prompt

Goal: the types that a loop needs exist and serialize deterministically, and the prompt file is in place. No loop runs yet.

Work: in `orchestration/`, add the `JsonValue` alias and `canonical_json` (P22). Add the `Prompt` value, built from the prompt file's bytes with a function that computes the version (P13). Add the `ModelReply` union of the four frozen types `ToolCalls`, `FinalText`, `Refusal` and `ProviderFailed` (P2), with `ToolCallRequest` (name and raw argument text), `Usage`, and `ProviderErrorCode` as a `StrEnum` with the four codes. Add the `AgentModel` port as a `Protocol` with one method, `next_step(transcript)`. Add the immutable `Transcript` (P24) and its item types. Add `ToolSpec`, the frozen type for a hand-written tool spec. Add the prompt as `orchestration/review_prompt.md`. Its text tells the model to use only the offers that the tools return, to pick an eligible offer or say keep, to write a short rationale in plain words, and to answer only in the required shape. Composition reads the file in Milestone 8.

Seam: the public functions of `orchestration/`, called from `tests/test_agent_review.py`. Prior art: the float trap in plan 01's `tests/conftest.py`.

Tests, in `tests/test_agent_review.py`: `test_canonical_json_sorts_keys_and_rejects_float`, which checks the byte output for a nested value and expects a `TypeError` for a float; and `test_prompt_version_is_digest_of_prompt_bytes`, which checks the version against the SHA-256 of the same bytes read from the prompt file.

Proof: `uv run --all-extras pytest --collect-only -q tests/test_agent_review.py | grep -cE '::(test_canonical_json_sorts_keys_and_rejects_float|test_prompt_version_is_digest_of_prompt_bytes)$'` prints `2`, and `uv run --all-extras pytest -q tests/test_agent_review.py; echo $?` ends with `0`.

### Milestone 3 - Tools and the loop for one booking

Goal: for one booking, the loop asks the model for replies, runs the three tools on their successful path, appends the results, and ends at a final answer that passes P7, or at a stop reason. The loop returns a `LoopRun` and makes no decision yet.

Work: write the three tool specs of the Tool contract, and the code that runs each tool for the booking the review is for. The tools use `offers_on_route` and the one-offer evaluation function. Only successful results are written here; the error paths are Milestone 5. Write `run_booking_loop`, which builds the transcript from the booking reference, the prompt, the tool specs and a first message that names the booking; then asks the model for the next reply. Assign call ids as `call_<turn>_<n>`. Run the calls of a `ToolCalls` reply in order, append each call and its result to the transcript, and count the reply as one turn. A `ToolCalls` reply whose text is not null ends the booking as `bad_final_answer` with no call run (P7). Parse a `FinalText` reply as P7 describes. Handle a `Refusal` reply by ending as `refusal`, and a `ProviderFailed` reply by ending as `provider_error` with its code. The cap and the repeat rule are Milestone 6. The loop returns `LoopRun`, which holds the end (`Answered` with the parsed final answer, or `Stopped` with an incomplete reason) and the trace (P14). The `match` on `ModelReply` covers all four cases, with `assert_never` in the last case.

Seam: `run_booking_loop`, called from `tests/test_agent_review.py` with the scripted fake model. The scripted model records each transcript it is shown. From Milestone 4 on, the seam is `review_with_model`.

Tests, in `tests/test_agent_review.py`: `test_first_message_names_the_booking`, which reads the first item of the transcript the model was shown; `test_call_ids_follow_turn_and_position`, which scripts two calls in one reply and then one call in the next, and expects the ids `call_1_1`, `call_1_2` and `call_2_1`; `test_several_calls_in_one_reply_run_in_order_as_one_turn`, which scripts two different tool calls in one reply and expects both results in the next transcript, in order, and one turn; `test_tool_call_with_final_text_is_bad_final_answer`, which scripts a `ToolCalls` reply with non-null text and expects `bad_final_answer` with no tool run; and `test_non_finite_confidence_is_bad_final_answer`, which scripts final answers with confidence `NaN`, `Infinity` and `-Infinity` in turn and expects `bad_final_answer` for each.

Proof: `uv run --all-extras pytest --collect-only -q tests/test_agent_review.py | grep -cE '::(test_first_message_names_the_booking|test_call_ids_follow_turn_and_position|test_several_calls_in_one_reply_run_in_order_as_one_turn|test_tool_call_with_final_text_is_bad_final_answer|test_non_finite_confidence_is_bad_final_answer)$'` prints `5`, and `uv run --all-extras pytest -q tests/test_agent_review.py; echo $?` ends with `0`.

### Milestone 4 - Safety check, outcome types, the report row and the serializer

Goal: `review_with_model` returns the full report for a model run. Each booking with an eligible offer gets a model decision that the safety check accepts or sends to `NEEDS_REVIEW`. Every other booking gets its rules result from `review_booking` with no model call. Every model-mode row carries a trace. Rules-only output is unchanged.

Work: write the safety check of P8 with its fixed check texts, and build the outcomes as P9 describes. Add `ModelRebook`, `NeedsReview`, `Incomplete`, `AgentOutcome` and `ReviewRow` (P23). Add the members `NEEDS_REVIEW` and `INCOMPLETE_ANALYSIS` to plan 01's `Status`, and `MODEL` and `SAFETY_CHECK` to plan 01's `DecidedBy`. The outcome types carry no status field: the serializer maps each type to its status and decided_by, by an exhaustive `match` with `assert_never`. Write `review_with_model` (P20). Extend plan 01's report serializer with the model keys of P25, the `confidence_note` value from one named constant, and the trace object in the order of P14. Do not change the rules-only output.

Seam: `review_with_model`, called from `tests/test_agent_review.py` with the scripted fake model and the in-memory ports from plan 01. The `Prompt` is built inline in the test from fixed bytes.

Tests, in `tests/test_agent_review.py`: `test_model_rebook_on_eligible_offer_is_accepted`, which scripts a rebook on the eligible offer and expects `REBOOK` with `decided_by: model` and `best_offer_id` null; `test_model_keep_with_eligible_offer_needs_review`, which scripts a keep for a booking with an eligible offer and expects `NEEDS_REVIEW` with "Model and rules disagree", the rules' view and the model's rationale, and `best_offer_id` null; `test_model_choice_failing_a_rule_needs_review`, which scripts a rebook on an offer that fails a rule and expects `NEEDS_REVIEW` with the rule's name and reason; `test_unknown_offer_in_final_answer_needs_review`, which scripts a rebook on an offer id that is not on the route and expects `NEEDS_REVIEW` with "not on this route and date"; `test_best_offer_id_names_highest_saving`, which scripts a valid rebook on a lower-saving eligible offer and expects `best_offer_id` to name the higher one; `test_failed_choice_needs_review_names_best_offer`, which scripts a rebook on an offer that fails a rule and expects `best_offer_id` null and the reasoning to name the highest-saving eligible offer; `test_booking_without_eligible_offer_makes_no_model_call`, which expects the scripted model to be shown no transcript for that booking; `test_confidence_is_labeled_model_estimate`, which expects `confidence_note` "model estimate, not calibrated" when confidence is set and no `confidence_note` key when it is null; `test_trace_has_prompt_version_and_usage`, which checks the trace fields of P14 on a model row; and `test_model_rows_have_fixed_key_order`, which checks the key order of P25 on a model row, with `best_offer_id` after `approval_flags` and `trace` last.

Proof: `uv run --all-extras pytest --collect-only -q tests/test_agent_review.py | grep -cE '::(test_model_rebook_on_eligible_offer_is_accepted|test_model_keep_with_eligible_offer_needs_review|test_model_choice_failing_a_rule_needs_review|test_unknown_offer_in_final_answer_needs_review|test_best_offer_id_names_highest_saving|test_failed_choice_needs_review_names_best_offer|test_booking_without_eligible_offer_makes_no_model_call|test_confidence_is_labeled_model_estimate|test_trace_has_prompt_version_and_usage|test_model_rows_have_fixed_key_order)$'` prints `10`, `uv run --all-extras pytest -q tests/test_agent_review.py; echo $?` ends with `0`, and `uv run --all-extras fare-reshop review --model none | cmp - /tmp/reshop-none-before.json; echo $?` prints `0`.

### Milestone 5 - Tool errors and stable tool output

Goal: bad tool calls go back to the model as readable tool errors with a hint, and the same booking always produces the same tool output bytes.

Work: add the three error codes of P6 with the fixed message and hint templates of the Tool contract. Check tool arguments as P7 describes: `json.loads` with the parse rules of P7, then explicit checks that the object has exactly the keys the spec names, each of the right type. A raw argument text that does not parse as a JSON object is `bad_arguments`. `get_booking` and `search_offers` take no arguments. `check_offer` takes one text argument, `offer_id`. An unknown tool name gets `unknown_tool`. An offer id that is not on the booking's route gets `unknown_offer`. A failing tool call does not end the booking. Every tool result, success or error, is serialized with `canonical_json`, and the `hint` of a success is null.

Seam: `run_booking_loop` and `review_with_model`, with the scripted model.

Tests, in `tests/test_agent_review.py`: `test_bad_tool_arguments_return_hint`, which scripts a call with an extra key and expects the next transcript to hold `bad_arguments` with a non-empty hint, followed by a valid final answer; `test_unknown_offer_id_returns_hint`, which scripts `check_offer` with an id that is not on the route and expects `unknown_offer` with a hint; `test_unknown_tool_name_returns_hint`, which scripts a call to a tool name that does not exist and expects `unknown_tool` with a hint that names the three tools, followed by a valid final answer; and `test_tool_results_are_sorted_and_stable`, which runs the same booking twice and expects the same transcript text both times, with offers in offer id order.

Proof: `uv run --all-extras pytest --collect-only -q tests/test_agent_review.py | grep -cE '::(test_bad_tool_arguments_return_hint|test_unknown_offer_id_returns_hint|test_unknown_tool_name_returns_hint|test_tool_results_are_sorted_and_stable)$'` prints `4`, and `uv run --all-extras pytest -q tests/test_agent_review.py; echo $?` ends with `0`.

### Milestone 6 - Turn cap, repeated calls and one-booking isolation

Goal: a booking that runs out of turns or repeats a call ends as `INCOMPLETE_ANALYSIS` with its reason, and each end state (turn cap, repeated call, bad final answer, refusal, provider failure) ends one booking only, while every other booking still runs.

Work: enforce the cap of P4 and the repeat rule of P5 before each call runs. The loop code for refusal, provider failure and bad final answers was written in Milestone 3; this milestone tests it through `review_with_model`, including the isolation between bookings. The trace keeps `provider_error_code` (P14).

Seam: `review_with_model`, with the scripted model. The scripted model returns a `ProviderFailed` reply on a chosen turn, which is a port fake and not a patch of our code.

Tests, in `tests/test_agent_review.py`: `test_turn_cap_ends_incomplete`, which scripts ten tool-call replies that alternate two different calls (`get_booking`, then `search_offers`, and so on), and expects `turn_cap`, that the model was shown exactly ten turns, and that `repeated_call` did not fire; `test_repeated_call_ends_incomplete`, which scripts the same call in two replies in a row and expects `repeated_call` with no third call run; `test_identical_calls_in_one_reply_are_repeated_call`, which scripts the same call twice in one reply and expects `repeated_call` with the second copy not run; `test_repeated_malformed_call_ends_incomplete`, which scripts the same tool call with the same malformed argument text in two replies in a row and expects `repeated_call`; `test_bad_final_answer_ends_incomplete`, which scripts a final answer with an extra key and expects `bad_final_answer`; `test_refusal_ends_incomplete`, which scripts a refusal reply and expects `refusal`; `test_provider_error_keeps_other_bookings_running`, which scripts a `ProviderFailed` reply on the first of two bookings that need the model, and expects the first to end as `provider_error` while the second still gets its decision; and `test_provider_error_code_is_in_trace`, which scripts a `ProviderFailed` reply with code `timeout` and expects `provider_error_code` to be `timeout` in the trace, with a turn count that includes the failed turn and no usage added for it.

Proof: `uv run --all-extras pytest --collect-only -q tests/test_agent_review.py | grep -cE '::(test_turn_cap_ends_incomplete|test_repeated_call_ends_incomplete|test_identical_calls_in_one_reply_are_repeated_call|test_repeated_malformed_call_ends_incomplete|test_bad_final_answer_ends_incomplete|test_refusal_ends_incomplete|test_provider_error_keeps_other_bookings_running|test_provider_error_code_is_in_trace)$'` prints `8`, and `uv run --all-extras pytest -q tests/test_agent_review.py; echo $?` ends with `0`.

### Milestone 7 - OpenAI adapter behind the model seam

Goal: the `AgentModel` port has a real adapter for the OpenAI Responses API. It sends the request shape confirmed in Milestone 1 and maps the replies, the provider failures and the typed setup failures into the orchestration types. No test reaches OpenAI.

Work: in `infrastructure/openai/`, extend the request builder of Milestone 1 and add one adapter class that implements the port. The adapter takes an injected client, defined as a small protocol of the one call it makes, so a stub can stand in for the SDK (P21). It also takes the model name and the max output tokens as constructor arguments, which composition gives it (P29). Translate the transcript into the request: the prompt text as instructions, the tool specs as strict function tools, the final-answer schema as strict structured output, `store` off, reasoning effort `none`, `parallel_tool_calls` false, the model name and the output cap. Write the loop's call ids on both the function call items and their output items (P21). Translate the reply: each function call item becomes a call with its name and its `arguments` string kept as raw text; the message text (the output text parts, concatenated) becomes the reply's text, or null when empty; a refusal part makes the whole reply a `Refusal` with the refusal text, whatever else it holds; a reply with calls and text becomes `ToolCalls` with its text; a reply with text and no calls becomes `FinalText`, so an empty reply becomes an empty final text that P7 rejects. Translate usage. Map the SDK's errors in this order: `APITimeoutError` to `ProviderFailed` with `timeout`, then `APIConnectionError` to `connection`, then `RateLimitError` to `rate_limit`, then `InternalServerError` to `server_error`. Map `AuthenticationError` to `ProviderAuthenticationError`, `PermissionDeniedError` to `ProviderPermissionError` and `NotFoundError` to `ProviderModelNotFoundError`, each a typed exception with no CLI wording (P18). Let other SDK errors propagate. Add no retry of our own.

Seam: the adapter's injected client protocol, with a stub that records the keyword arguments it was called with and returns or raises scripted values.

Tests, in `tests/test_agent_review.py`: `test_openai_request_sets_store_off_and_no_reasoning`, which checks the recorded call holds `store` false, reasoning effort `none`, strict tools and the strict text format with the four-key root object of the Tool contract; `test_openai_request_sets_parallel_tool_calls_off`, which checks `parallel_tool_calls` false and the output cap; `test_openai_errors_map_to_provider_failed`, which makes the stub raise an instance of each of the four mapped SDK classes in turn, with the timeout class raised as a timeout (so the ordering is tested) and the connection class raised as a connection, and expects the codes `timeout`, `connection`, `rate_limit` and `server_error`; `test_openai_auth_error_raises_typed_error`, `test_openai_permission_denied_raises_typed_error` and `test_openai_not_found_raises_typed_error`, each of which expects the matching typed exception; `test_openai_refusal_maps_to_refusal_step`, which makes the stub return a refusal part and expects a `Refusal` reply with the refusal text; and `test_openai_calls_with_text_map_to_tool_calls_with_text`, which makes the stub return a function call and a message text together and expects a `ToolCalls` reply whose text is that message text.

Proof: `uv run --all-extras pytest --collect-only -q tests/test_agent_review.py | grep -cE '::(test_openai_request_sets_store_off_and_no_reasoning|test_openai_request_sets_parallel_tool_calls_off|test_openai_errors_map_to_provider_failed|test_openai_auth_error_raises_typed_error|test_openai_permission_denied_raises_typed_error|test_openai_not_found_raises_typed_error|test_openai_refusal_maps_to_refusal_step|test_openai_calls_with_text_map_to_tool_calls_with_text)$'` prints `8`, `uv run --all-extras pytest -q tests/test_agent_review.py; echo $?` ends with `0`, and `git grep -lE "^[[:space:]]*(from|import) openai" -- fare_reshop_agent | grep -vcE "infrastructure/openai/|composition/"` prints `0`.

### Milestone 8 - `--model openai` CLI path, setup errors and doctor checks

Goal: `fare-reshop review --model openai` runs the live path. Setup failures stop the run with exit code 2 before any call, or at the first provider authentication, permission or model failure, in the three-line error format. `fare-reshop doctor` reports the live extra, the key and the model as optional, and never prints the key's value.

Work: in `cli/`, accept `--model openai` and hand it to composition. Keep `--record` rejected with exit code 2 (P16). In `composition/`, which is the only place that reads the environment, check the live extra first, the key second and the model third (P18, P17, P19). The default `model_factory` builds the adapter with the client and the model name, and with the constants of P29 (`REQUEST_TIMEOUT_SECONDS`, `MAX_OUTPUT_TOKENS`). Read `review_prompt.md`'s bytes from `orchestration/` and build the `Prompt`. The live run catches the three typed provider exceptions and raises `SetupError` from each, with the fixes of P18, so the CLI exits 2. The CLI prints the three lines. Add the optional doctor lines for the live extra, the key and the model (P15); the doctor asks composition whether each is set and never reads or prints the key's value. Add `model_factory` to the composition entry (P27).

Seam: the composition entry from plan 01, called with arguments, an environment mapping and a model factory, as plan 01's `tests/test_cli.py` calls it. The missing-extra test hides the `openai` module and the adapter module from the import system by setting their entries in the module table to `None`, and does not patch our code.

Tests, in `tests/test_cli.py`: `test_openai_without_key_exits_2`, which calls the entry with an empty environment mapping and `--model openai`, and expects exit code 2, the message `OPENAI_API_KEY is not set` and no call to any client; `test_openai_without_model_exits_2`, which sets a placeholder key in the mapping, leaves `OPENAI_MODEL` out, and expects exit code 2 with "OPENAI_MODEL is not set" before any call; `test_openai_without_live_extra_exits_2`, which hides the `openai` module, sets a placeholder key, and expects exit code 2 with "uv sync --extra live"; `test_rejected_key_exits_2`, which passes a factory returning a scripted model that raises `ProviderAuthenticationError`, and expects exit code 2, the fix line "set OPENAI_API_KEY in .env.local to a valid key" and no report written; `test_unknown_model_exits_2_with_fix`, which does the same with `ProviderModelNotFoundError` and expects the model fix line; `test_permission_denied_exits_2_with_fix`, which does the same with `ProviderPermissionError` and expects the permission fix line; `test_doctor_marks_live_settings_optional`, which runs the doctor with no key and expects exit code 0 and at least three lines containing "optional"; `test_doctor_never_prints_key_value`, which sets a placeholder key and expects the doctor output to contain "OPENAI_API_KEY" and "set", and not the placeholder's value; and `test_key_value_never_appears_in_output_or_files`, which sets a distinctive fake key, runs `doctor`, `review --model none` and `review --model openai` (with the extra hidden, so the run stops before any call), with the working directory set to a `tmp_path`, and checks that the fake value appears in neither the standard output, nor the standard error, nor any file under `tmp_path`.

Proof: `uv run --all-extras pytest --collect-only -q tests/test_cli.py | grep -cE '::(test_openai_without_key_exits_2|test_openai_without_model_exits_2|test_openai_without_live_extra_exits_2|test_rejected_key_exits_2|test_unknown_model_exits_2_with_fix|test_permission_denied_exits_2_with_fix|test_doctor_marks_live_settings_optional|test_doctor_never_prints_key_value|test_key_value_never_appears_in_output_or_files)$'` prints `9`, and `uv run --all-extras pytest -q tests/test_cli.py; echo $?` ends with `0`.

### Milestone 9 - Docs and ADRs for the live model

Goal: the repo's rules about the agent's role and confidence describe the live model accurately, and the two hard-to-reverse decisions of this plan have records in `docs/adr/`.

Work: in `AGENTS.md`, replace line 22 with "The model picks an eligible offer or keep and writes the rationale, and it may call only the read-only tools." In the project overview sentence that plan 01 changed (line 7 when plan 01 lands), add back the words "how confident it is", followed by "(a model estimate, not calibrated, in model modes)", so the sentence names the nominal saving after the change fee and the confidence with its label. Do not change other lines. In `GLOSSARY.md`, add four terms, each under its own `### <Term>` heading in the format plan 01 sets: Tool, Transcript, Turn and Safety check. Write `docs/adr/0002-plain-code-rule-check-and-safety-check.md` for D1 and D19, and `docs/adr/0003-stateless-model-turn-seam.md` for D16. Each ADR has the sections Status (Accepted), Context, Decision, Consequences and Alternatives, in that order, each as a level-2 heading. Consequences include the cost of the safety check and what it means for a reader. Alternatives names the options that lost. Do not change `README.md` or `DESIGN.md`; plan 04 owns them.

Seam: none. This milestone is documentation, checked by the greps in its Proof and by the format rules of the repo.

Proof: `grep -c "picks an eligible offer or keep and writes the rationale" AGENTS.md` prints `1`; `grep -c "model estimate, not calibrated" AGENTS.md` prints `1`; `grep -ciE "^### (tool|transcript|turn|safety check)$" GLOSSARY.md` prints `4`; `ls docs/adr/0002-*.md docs/adr/0003-*.md` prints two paths, and `cat docs/adr/0002-*.md docs/adr/0003-*.md | grep -cE "^## (Status|Context|Decision|Consequences|Alternatives)$"` prints `10`.

### Milestone 10 - Scripted-fake scenario tests

Goal: the safety check and the model's pick are tested on the scenario data set (D34) for the judgment cases where the pick matters, including one booking whose model turn calls a tool before the final answer. No production code is added, and no call reaches a provider.

Work: the tests use the scenario folder that plan 01 milestone 11 creates, read through the real fixture adapter, with the real TOML adapters and the policy built inline, as plan 01's sample oracle does. The scripted fake model returns the replies of each test in order. The expected values come from the scenario table in the index.

Seam: `review_with_model`, with the scripted fake model and the scenario source.

Assertions. `test_scenario_a_model_pick_of_6102_is_accepted` scripts a rebook on OF-6102 for MK3V7P. The result is `REBOOK` with `decided_by` model, offer OF-6102, nominal saving `Decimal("80.00")` in USD, no approval flags, and `best_offer_id` OF-6101. `test_scenario_a_tool_call_then_pick_of_6102_is_accepted` scripts one `check_offer` call on OF-6102 and then the same rebook; the result is the same, and the trace lists one tool call that ran with its `ok` flag true and one turn more than the rebook alone. `test_scenario_b_model_keep_on_rd9q2x_needs_review` scripts a keep for RD9Q2X. The result is `NEEDS_REVIEW` with `decided_by` safety_check, its reasoning starts with "Model and rules disagree", contains "OF-6201" and the model's rationale after "Model text:". `test_scenario_b_model_rebook_on_rd9q2x_shows_carrier_flag` scripts a rebook on OF-6201. The result is `REBOOK` with `decided_by` model, nominal saving `Decimal("75.00")`, approval flags `["carrier_change"]` and `best_offer_id` null. `test_scenario_c_model_pick_of_6301_needs_review` is the bad pick: the model rebooks on OF-6301 for WJ6T4N, which fails `refundable`. The result is `NEEDS_REVIEW` with `decided_by` safety_check, offer OF-6301, nominal saving `Decimal("210.00")`, `best_offer_id` null, and reasoning that starts "Safety check: rule refundable failed", names OF-6302 as the highest eligible offer under "Rules view", and carries the model's rationale after "Model text:". `test_scenario_c_model_pick_of_6302_is_accepted` scripts a rebook on OF-6302. The result is `REBOOK` with nominal saving `Decimal("60.00")` and `best_offer_id` null, because OF-6302 is the only eligible offer.

Proof: `uv run --all-extras pytest --collect-only -q tests/test_agent_review.py | grep -cE '::(test_scenario_a_model_pick_of_6102_is_accepted|test_scenario_a_tool_call_then_pick_of_6102_is_accepted|test_scenario_b_model_keep_on_rd9q2x_needs_review|test_scenario_b_model_rebook_on_rd9q2x_shows_carrier_flag|test_scenario_c_model_pick_of_6301_needs_review|test_scenario_c_model_pick_of_6302_is_accepted)$'` prints `6`, and `uv run --all-extras pytest -q tests/test_agent_review.py; echo $?` ends with `0`.

## Surprises & Discoveries

- Observation: the SDK's error classes, the request parameters and the response item shapes were checked in Context7 on 2026-11-02 and match this plan. The timeout class subclasses the connection class; the status classes are `AuthenticationError` (401), `PermissionDeniedError` (403), `NotFoundError` (404), `RateLimitError` (429) and `InternalServerError` (5xx); the client takes a timeout option; the SDK retries timeouts and 5xx and 429 twice by default; a function call item carries `arguments` as a JSON string; a message carries `output_text` and `refusal` parts; an `incomplete` response carries the reason `max_output_tokens`; `parallel_tool_calls` set to false limits a reply to zero or one call.
  Evidence: Context7 `/openai/openai-python` (error hierarchy, timeouts) and `/websites/developers_openai_api` (function calling, Responses reference). Milestone 1 confirms them against the installed version.
- Observation: plan 03 still names the old shapes, and the cross-plan changes are owed by its writer: its L5 stores tool call `arguments` as a JSON object (it must store the raw text, P2); its Context names `ModelStep` (the reply is `ModelReply` with four members); its L10 returns `ModelStep` from the recorded adapter; its `record_review` entry gives `OPENAI_MODEL` the default `gpt-5.4-mini` (P17 forbids a default); its Context calls the review's row `ModelReview` (it is `ReviewRow`); and its tool list names `evaluate_offer` (it is `check_offer`).
  Evidence: `03-record-and-replay-model-runs.md` Context, L5, L10 and Milestone 2.
- Observation: plan 01 needs three changes owed by its writer: its check-script DoD regex must accept `--all-extras` (P26); its composition entry gains the `model_factory` keyword (P27); its report row is named `ReviewRow` with the trace optional, and its table columns include FLAGS.
  Evidence: plan 01 DoD "Check script" and L7.
- Observation: the index rows D9, D15, D16 and D17 change with this pass (see the Decision Log entry on index rows). Plan 02 copies the changed rows.
  Evidence: the Locked decisions section.

## Decision Log

- Decision: the model reply is one union of four types. `ToolCalls` holds the calls, the raw argument text and an optional text. A `ToolCalls` with non-null text ends the booking as `bad_final_answer` (P2, P7, D18).
  Rationale: a reply can hold tool calls and text together, so one type must hold both, and the rule matches the index.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: `Refusal` carries the refusal text, for the trace. A refusal still ends the booking as `refusal` (P1).
  Rationale: the trace is the only place where the text is needed, and the text is never shown as a fact.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: tool calls carry the raw argument text as the provider sent it. Parsing happens in orchestration. Malformed arguments are a normal tool error, `bad_arguments` (P5, P6).
  Rationale: the recording stores the text the model produced, and the parse rules stay in one place.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the outcome types carry no status field. The serializer maps each type to its status and decided_by by an exhaustive match. `Status` gains `NEEDS_REVIEW` and `INCOMPLETE_ANALYSIS`. `DecidedBy` gains `MODEL` and `SAFETY_CHECK`. An accepted model rebook is its own type, `ModelRebook`, so its decided_by is model by type. A NeedsReview is safety_check by type, and an Incomplete has no decided_by.
  Rationale: status and decided_by cannot disagree when they come from the type. A plain Rebook from the rules cannot tell the serializer that the model made the choice, so the model's rebook needs its own type.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: reasoning templates are fixed. A failed choice reads "Safety check: <check>. Rules view: ... Model text: ...". A keep with an eligible offer reads "Model and rules disagree. Rules view: ... Model text: ...". An accepted rebook reads "Model text: ...". Milestone 10 asserts them.
  Rationale: a reader must see the code's view and the model's words, labeled, and tests must assert the labels.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: `best_offer_id` follows index D9. It is set only when the model's valid choice is not the highest saving. For a failed choice it is null, and the reasoning names the highest eligible offer. Scenario a asserts OF-6101 for the 6102 pick, scenario c asserts null and the name OF-6302 for the 6301 pick.
  Rationale: a failed choice has no valid chosen offer, so the index's rule gives null; the reasoning carries the pointer instead.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the model text is labeled in `reasoning` with "Model text:". The code's figures stay in their own fields. No check compares a money amount in the rationale with the code's saving.
  Rationale: a check that parses amounts out of model prose is brittle and gives false comfort; the label tells the reader which words are the model's, and the figures in their own fields are the ones to trust. The simpler option is chosen.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: `SetupError` lives in `composition/` with the fields `error`, `reason` and `fix`. `review_with_model` reuses `review_booking` for rules-settled and invalid bookings and for the highest eligible offer, so the rule steps exist once. Plan 01's names are used: `offers_on_route`, `review_booking`, `review_snapshot`.
  Rationale: the index's D12 and plan 01's final pass put `SetupError` in composition; one set of steps avoids drift.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: money in tool data and in output is the object `{amount, currency}`, with `amount` as two-decimal text, plan 01's shape. Rates are text. The index's D17 wording "money is a decimal string" is read as the amount's text inside that object.
  Rationale: one money shape across the tools, the output and plan 01 keeps the currency with the amount, as the Python rules require.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the no-key, no-model and no-extra tests call the composition entry with an environment mapping. The rejected-key, unknown-model and permission tests pass a model factory (P27) that returns the scripted model, and the entry returns exit code 2 with the fix line.
  Rationale: the environment is read only in composition, and no test calls the network or patches our code.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: `NotFoundError` (unknown model) and `PermissionDeniedError` map to typed setup errors with exit 2 and fix lines (P18).
  Rationale: a bad model name or a key without access stops every booking the same way a rejected key does, so each must stop the run with a fix and not look like a bug.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the adapter maps `APITimeoutError` before `APIConnectionError`, then `RateLimitError`, then `InternalServerError`, and tests the timeout ordering (P2, Milestone 7).
  Rationale: the timeout class subclasses the connection class.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: Milestone 1 is a documentation-and-typecheck step. Its gate is `mypy --strict` on the committed request builder. The scratch directory and its check are removed.
  Rationale: a check on pasted text proves nothing about the repo's code, and a scratch-folder check adds ceremony without evidence.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: an owner-run smoke check, one booking and one live request with the real key, is recorded in the Decision Log before plan 03 starts. The full loop is verified in plan 03's recording run.
  Rationale: the first live request should be cheap and recorded; the full run costs more and belongs to the recording.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the model call has `parallel_tool_calls` false, a output cap of `MAX_OUTPUT_TOKENS` (2000) and a client timeout of `REQUEST_TIMEOUT_SECONDS` (60.0), all named constants in composition (P29). A reply is still handled per turn (the several-calls test in Milestone 3).
  Rationale: one reply is one turn, the cap bounds cost per call, and the timeout bounds waiting. The values are this plan's picks; the owner may change them with a Decision Log entry.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the confidence is labeled with the output key `confidence_note` set to "model estimate, not calibrated" whenever confidence is set. It is a named constant with one definition in the code.
  Rationale: a number with no label invites reading it as a probability; the label is in the output itself.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the row is one type, `ReviewRow`, with an optional trace. Model modes always set the trace (P11), and the serializer omits the key in `none` mode.
  Rationale: one row shape is simpler than two row types and a union, and the serializer picks keys by mode.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the AGENTS.md overview sentence gets the confidence wording back in model modes with the label. Plan 01 removes it.
  Rationale: plan 01's L11 says the live plan adds it back when its mode lands.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the prompt file is `review_prompt.md` everywhere.
  Rationale: one file name across the plans.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the tool is named `check_offer`.
  Rationale: plan 01's domain function is `evaluate_offer`; a tool with the same name would confuse readers and code search.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the milestones are layered (types, then loop, then safety check, then errors, then adapter, then CLI, then docs, then scenarios). The order follows the dependencies: each milestone needs the types of the one before. Each still ends with its own passing test set and one verifiable outcome.
  Rationale: the loop cannot be built before the reply types, and the adapter cannot be tested before the seam. A vertical order would need the adapter before the loop exists.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the DoD keeps behavior checks only. Name-count checks stay in the milestone proofs, where they prove each named test exists. The `--all-extras` count check and the word-count checks are removed; the check script's own run covers them.
  Rationale: the DoD is for outcomes; existence checks belong to the milestone that writes the tests.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the index rows copied in Locked decisions (D9, D15, D16, D17) follow the index as changed in this pass. The index writer applies the row changes listed in the report.
  Rationale: this plan is a copy of the index rows; the copies must match the index once it is updated.
  Date/Author: 2026-11-02, plan writer (round 3).
- Decision: the plan keeps the owner-run section outside the DoD gate.
  Rationale: a real key cannot be used on a clone, and a gate must run offline.
  Date/Author: 2026-11-02, plan writer.

## Outcomes & Retrospective

Not started.

## Definition of done

Every item below runs offline and without a key, except the owner-run check at the end, which is not a gate.

- [ ] The offline tests pass with no key and no proxy to a real host: `env -u OPENAI_API_KEY HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 uv run --all-extras pytest -q tests/test_agent_review.py tests/test_cli.py; echo $?` prints `0` as its last line. This includes the scenario tests of Milestone 10 and the key-leak test.
- [ ] The checks are green: `./scripts/check.sh; echo $?` prints `0` as its last line, and each of its four commands starts with `uv run --all-extras`.
- [ ] Rules-only output is unchanged: `uv run --all-extras fare-reshop review --model none | cmp - /tmp/reshop-none-before.json; echo $?` prints `0`.
- [ ] A missing key exits 2 before any call: `env -u OPENAI_API_KEY uv run --all-extras fare-reshop review --model openai > /tmp/reshop-openai-nokey.txt 2>&1; echo $?` prints `2`, and `grep -c "OPENAI_API_KEY is not set" /tmp/reshop-openai-nokey.txt` prints `1`.
- [ ] The doctor runs with no key, exits 0 and reports the live settings as optional: `env -u OPENAI_API_KEY uv run --all-extras fare-reshop doctor > /tmp/reshop-doctor.txt 2>&1; echo $?` prints `0`, and `grep -c "optional" /tmp/reshop-doctor.txt` prints at least `3`.
- [ ] The confidence label has one definition in the code and is in the docs: `git grep -l "model estimate, not calibrated" -- fare_reshop_agent | wc -l` prints `1`, and `grep -c "model estimate, not calibrated" AGENTS.md` prints `1`.
- [ ] `AGENTS.md` describes the new role and the confidence: `grep -c "picks an eligible offer or keep and writes the rationale" AGENTS.md` prints `1`, and `grep -c "how confident it is" AGENTS.md` prints `1`.
- [ ] The example file is untouched: `git diff --quiet -- .env.example; echo $?` prints `0`.
- [ ] The OpenAI import stays in the adapter and composition: `git grep -lE "^[[:space:]]*(from|import) openai" -- fare_reshop_agent | grep -vcE "infrastructure/openai/|composition/"` prints `0`.
- [ ] Only composition reads the environment: `git grep -nE "os\.environ|getenv" -- fare_reshop_agent | grep -vc "composition/"` prints `0`.
- [ ] The orchestration and domain do not import pydantic or use float math: `git grep --untracked -n "pydantic\|float(" -- fare_reshop_agent/reshopping/orchestration fare_reshop_agent/reshopping/domain; echo $?` prints `1`.
- [ ] No suppression or `Any` in new code: `git grep --untracked -nP "type: ignore|noqa|\bAny\b|\bcast\(" -- fare_reshop_agent tests; echo $?` prints `1`.
- [ ] The request builder is typed for the SDK: `uv run --all-extras mypy --strict fare_reshop_agent/reshopping/infrastructure/openai/request_builder.py` ends with "Success: no issues found in 1 source file".
- [ ] The plan passes the format check: `/Users/igby/.claude/skills/exec-plan/scripts/check-plan-format .agents/plans/reshop-review/02-agent-review-with-a-live-model.md` prints `1 ok, 0 failing`.
- [ ] No leaks in this plan: `grep -niF -f .private/denylist.txt .agents/plans/reshop-review/02-agent-review-with-a-live-model.md; echo $?` prints `1`.

Owner-run check, not a gate (needs a real key in `.env.local`, so no agent run can pass it on a clone): `uv run --env-file .env.local fare-reshop review --model openai --format table`. Expect five model-mode results with `mode: openai` in JSON, the bookings with no eligible offers as `KEEP`, and FLAGS shown for any flagged rebook. The result can differ between runs, so it is read, not compared byte for byte. The trace's token usage shows the cost against A3. Record the smoke result in the Decision Log (see the owner-run smoke check above).

Revision notes:
- 2026-11-02: first draft written from the design index (D1-D32, A1-A6), with P1-P21 added for the choices the index leaves open. Critic round 1 pending.
- 2026-11-02: critic round 1 fixes applied. The DoD key check is a fake-key test, not a grep (BLOCKER). `SetupError` is embedded from plan 01, not redefined. The live review is the sibling `review_with_model`, and the result types are in P23. Provider failures are typed replies, and authentication failures are setup errors with exit 2 (D15, D16). Call ids and the provider id mapping are fixed (D16). Tool and tool-text cases, repeat detection across calls, non-finite confidence and unknown tool names have tests. `offers_on_route` is the one route definition. `JsonValue` replaces `Any`. Milestone 1 has concrete promote and discard criteria. Real-key checks moved to an owner-run section. AGENTS.md ownership is stated in Scope (D19). Index D16 and D18 wording is copied into Locked decisions.
- 2026-11-02, round 2 (critic round 2 was the last round; its fixes are applied without a third round): the final answer is one root object with a nullable `offer_id` and strict mode (D20, P7). AGENTS.md scope is line 22 only, and line 17 moved to plan 01. Plan 01's functions are named by role, with a Progress check. The tool data fields, hint rule and error codes are locked. The adapter's exception order is timeout, connection, rate limit, server error, with a test for each. The model comes from `OPENAI_MODEL` with no default (P17), the model's checks are in Milestone 1, and `.env.example` is not edited. The SDK-pin check guards the empty case. Milestone 2 is split into seam, loop, and safety check, with Milestones 1 to 9 renumbered. One report type and one output serializer cover all modes, with the key order of P25. The loop assigns call ids. Provider codes are printed in the trace, and auth errors are typed. Minor fixes applied.
- 2026-11-02, round 3 (the final pass; no further critic round is planned by this revision). The reply union is `ToolCalls` (with optional text), `FinalText`, `Refusal` (with its text) and `ProviderFailed`; a mixed reply is `bad_final_answer` and has an adapter test (P2, P7). Tool calls carry raw argument text (P5, P6). Status and decided_by gain their members and the outcome types carry them (Decision Log). Reasoning templates are fixed and tested (P9). `best_offer_id` follows D9, null for a failed choice (P9). `SetupError` is in composition and the plan uses plan 01's names (P20). Money is `{amount, currency}` (D17). The no-key tests use the composition entry with an environment mapping; the rejected-key test uses a model factory (P27). NotFound and PermissionDenied map to typed setup errors (P18). The AGENTS.md overview sentence carries the confidence label again (Milestone 9). Milestone 1 is a documentation-and-typecheck step gated by mypy on a committed request builder (P28). The owner-run smoke check is recorded before plan 03 starts. Parallel tool calls are off, with the output cap and timeout as named constants (P29). The confidence label is `confidence_note` (P25). The row is one type with an optional trace (P23). `review_prompt.md` is used everywhere. The tool is `check_offer`. Plan 03 and plan 01 changes owed are listed in Surprises & Discoveries. The DoD keeps behavior checks only. Layered milestone order is explained in the Decision Log.

2026-11-02, sync: `AgentModel` exposes `model_name`, needed by Record and replay model runs.
