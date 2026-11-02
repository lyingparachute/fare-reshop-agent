# Record and replay model runs

Status: ready - the live recording milestones need the owner's key

This ExecPlan is a living document. Progress, Surprises & Discoveries, Decision Log and Outcomes & Retrospective are kept current as work proceeds. Repo plan rules: none. Starts after: Rules-only review (plan 01) and Agent review with a live model (plan 02). The contracts this plan uses from them are listed in Context and Locked decisions. If one of them differs when work starts, stop and report the difference before writing code.

## Progress

- [ ] Milestone 1 - Canonical serializer and digests
- [ ] Milestone 2 - Recording wrapper with a scripted model
- [ ] Milestone 3 - Atomic writer, file schema and the `--record` flag
- [ ] Milestone 4 - Replay reader and header check
- [ ] Milestone 5 - Recorded adapter and turn checks
- [ ] Milestone 6 - Leftover check and exit codes
- [ ] Milestone 7 - Commit the sample recording
- [ ] Milestone 8 - Replay becomes the default and doctor checks the recording
- [ ] Milestone 9 - Glossary, ADR 0004 and the re-record runbook
- [ ] Milestone 10 - Scenario recording: the second paid run, the replay and the committed checks for both data sets (D34). Needs the scenario folder from plan 01 milestone 11.

Updated at every stopping point. This list, not memory, says where the work is.

## Background / why now

After this plan, anyone who clones the repo can run `uv run fare-reshop review` with no key and no network and still see what a real language model decided for each booking. The maintainer records one live run per data set: `recordings/review-run.json` for the sample data and `recordings/scenarios-run.json` for the scenario data (D34). The default run replays the sample file, and `--data scenarios` replays the other. Replay runs the real review loop. The tools read the fixtures for real, and only the model's replies come from the file. Each recorded turn carries a digest of the exact transcript the model saw, so a replay that asks a different question than the recording answered fails loudly instead of reusing an old answer.

Today the repo has no code. Its sample data is in `fixtures/pnrs.json` (5 bookings) and `fixtures/fares_feed.json` (6 offers, captured 2026-07-08T09:00:00Z). Without this plan, the default run either hides the model from anyone without a key (default `none`) or needs a key every time. The owner's real run costs one paid call per turn. A3 bounds one run under 1 USD.

Terms used in this plan:

- A booking is a booked flight with its price and change fee. An offer is a fare on sale now.
- A turn is one call to the model for one booking. The turn number is an integer on the transcript. It starts at 1 for each booking and counts every model call for that booking, a failed call included.
- A transcript is the complete input of one turn: the booking reference, the turn number, the instructions (the prompt text), the tool specs, a first message naming the booking, and every earlier call with its result.
- A reply is what the model returned on one turn. It is one of plan 02's `ModelReply` types: `ToolCalls` (one or more calls, with the text the reply carried or none), `FinalText`, `Refusal`, or `ProviderFailed`. A mixed reply is a `ToolCalls` reply that carries text. The loop ends that booking as `bad_final_answer` and runs none of its calls.
- A call id is the label `call_<turn>_<n>` that the loop assigns to each call, where n is the call's place in its reply counted from 1. Provider call ids and request ids are never stored.
- A recording is the JSON file that holds a header and every turn of one run. The header holds six digests and the model name. The model name is shown on replay and never compared.
- A digest is the lowercase hex SHA-256 of the UTF-8 bytes of a canonical text. The same input always gives the same digest, and any changed byte gives a different one.
- A projection is the explicit function that turns one domain value into the JSON value that gets digested. It uses literal key strings.
- The canonical serializer is `canonical_json` (plan 02 P22). It sorts keys, writes no spaces between tokens, writes UTF-8 without escaping non-ASCII characters, writes each `Decimal` as a quoted fixed-point string, and refuses floats.
- An atomic write writes the whole new file to a temporary file in the same folder, flushes it to disk, and renames it over the old file. A reader sees the old file or the new one, never a mix.
- Replay means running the real review loop while each model reply comes from the recording. Stale means a recording no longer matches the inputs or the questions that produced it. `StaleRecording` is the error for that.
- A provider failure is a network error, timeout, rate limit or server error from the model provider. The model returns it as the value `ProviderFailed` with a closed code, never as an exception. A refusal is not a provider failure.
- A leftover turn is a recorded turn that the replayed run never asked for.

Python rules in `.claude/rules/python.md` bind all code in this plan. Read that file before writing any Python.

## User stories

Stories S3 and S4 copy the walkthroughs in `.agents/plans/reshop-review/00-INDEX.md`. The wording of the errors and fix commands differs from the index, as the Decision Log records.

### S3 - Offline replay of a recorded run

As anyone who clones the repo, I want the default run to replay a recorded model run with no key and no network, so that I see real model behavior for free.

Walkthrough:

1. The user runs `uv run fare-reshop review`. The default mode is `recorded`. It reads the recording of the chosen data set: `recordings/review-run.json` for `sample`, `recordings/scenarios-run.json` for `scenarios` (D34, L8). Error: the file is missing; exit code 2 with three lines: "error: no recording at recordings/review-run.json", "reason: the recorded run replays that committed file, and this checkout does not have it", "fix: uv run fare-reshop review --data sample --model none".
2. The real loop runs. Tools run against the fixtures. Only the model's replies come from the file.
3. Error: exit code 3 with `StaleRecording`. A header digest differs: the message names each input that changed (pnrs, fares_feed, policy, rates, prompt or tools). A turn's transcript digest differs: the message names the booking and the turn. A booking needs a turn the file does not have: the message names the booking and the turn as missing. A booking finished with recorded turns left over: the message names each leftover booking and turn. The last line is the re-record command for the data set (L12).
4. Output is the same shape as S2, with `mode: recorded`. Bookings settled by rules need no turns and are not in the file. The trace of each replayed booking shows `recorded_model` and `recorded_usage` in place of the live usage field (L11).

### S4 - Record a run

As the maintainer, I want to record one live run into a file, so that the offline replay shows what the real model did.

Walkthrough:

1. The maintainer runs `uv run --env-file .env.local --extra live fare-reshop review --data <set> --model openai --record`.
2. Turns are kept in memory as the run goes. Each holds the booking, the turn number, the digest of what the model saw, the reply it returned and its token usage. No key, request ids or headers are kept.
3. Success means the run had no provider failure. Bookings that ended on a loop limit or a refusal still count as recorded, and replay reproduces them. Then the file is written atomically, replacing the old one, and its path is printed on stderr. Stdout still carries only the JSON result.
4. Error: the first provider failure stops the run at once. The run makes no further model call, nothing is written, the old recording stays, and the run exits with code 2. Stdout is empty. Stderr has three lines: "error: booking <ref>: recording stopped", "reason: <closed code>" (`connection`, `timeout`, `rate_limit` or `server_error`), and "fix: <re-record command>" (L12).

## Scope and non-goals

In scope, for S3: the recorded adapter that replays turns and runs tools for real; the header check and the turn checks that raise `StaleRecording`; the leftover check; the exit code 3 mapping; the `recorded` mode with its missing and unreadable recording errors; the default switch to `recorded`; the doctor check for the recordings; the `.gitattributes` file; the two committed recording files. For S4: the recording wrapper around the model; the in-memory turns; the canonical serializer, the projections and the digests; the file schema and the atomic write; the `--record` flag; the stop at the first provider failure; the no-secrets test; the live runs that make the committed files. For the scenario data set (D34): the scenario recording and its checks (Milestone 10). For the docs of this slice: two glossary terms, ADR 0004 and the re-record runbook (D26, D33).

Non-goals: masking booking references (D30; the fixtures are synthetic, A5). Recording raw HTTP traffic, provider call ids, request ids or headers. A `.partial` file or any second write path. Token or cost budgets (D27). Storing the model's reasoning items (D21). A flag to choose the recording path; the path follows the data set. Recording in `none` or `recorded` mode. Recording a run that continues after a provider failure. Changing the rules, the rate adapter, the tools or the prompt. README and DESIGN.md (plan 04 owns them). A live rate source (S5). Editing a fixture or config file to make a test pass.

## Context and orientation

This plan builds on plan 01 and plan 02 as they stand after their final passes. The names below are the names those plans use. Items marked "new in this plan" do not exist yet.

Contracts from plan 01 (rules-only review):

- Layout (D10): the package is `fare_reshop_agent/reshopping/`, with `domain/`, `domain/port/`, `orchestration/`, `infrastructure/<technology>/`, `composition/` and `cli/`.
- `ReshopSource` returns one snapshot: the valid bookings, the valid offers, the capture time and the data issues. This plan also needs the references of the records the parser rejected. Plan 01 must expose them (Surprises & Discoveries).
- `ExchangeRates` is the port (D6). The TOML rate reader returns the parsed rate entries as a tuple (new requirement, Surprises & Discoveries). Composition reads that tuple once and passes it to the rate adapter and to the rates projection. The port keeps its shape.
- The TOML policy reader returns `ReviewPolicy`.
- `SetupError` lives in `composition/` with the fields `error`, `reason` and `fix`. Composition maps every typed reader and writer error to it. `cli/` prints the three fields as lines labeled `error:`, `reason:` and `fix:`, and exits 2 (D31).
- The composition entry takes `environ: Mapping[str, str]` and returns the exit code. Plan 02 adds `model_factory` to it (P27).
- The rules-only path is `review_snapshot(source, rates, policy)`. Its output does not change, and this plan does not call it.
- Money in JSON is an object `{amount, currency}` with `amount` as fixed-point text.
- The data set flag is `--data sample|scenarios` (D34). The local check command is `./scripts/check.sh`. No CI job runs it.
- Data and config files are read relative to the working directory, which is the repo root in a normal run. The prompt file is read from the package, not from the working directory.

Contracts from plan 02 (agent review with a live model):

- `review_with_model(source, rates, policy, model, prompt)` is the live review. It returns the one report type of plan 02, whose rows are `ModelRow` (one outcome and one trace), `RulesRow`, and their union `ReviewRow`.
- `AgentModel` is a Protocol with `next_step(transcript) -> ModelReply`. It also exposes `model_name`, the model's name as text (new requirement, Surprises & Discoveries).
- `ModelReply` is the union of four frozen types. `ToolCalls` holds `ToolCallRequest` values (name and raw argument text), an optional `text` (null when the reply has none), and `usage`. `FinalText` holds `text` and `usage`. `Refusal` holds `text` and `usage`. `ProviderFailed` holds one `ProviderErrorCode` and no usage. There is no `ModelStep` and no `ModelReview`.
- `Usage` holds `input_tokens` and `output_tokens`, both integers.
- `ProviderErrorCode` is a `StrEnum` with `connection`, `timeout`, `rate_limit` and `server_error`.
- `Prompt` holds the prompt text and its version. The version is the lowercase hex SHA-256 of the prompt file's bytes (P13).
- `Transcript` holds the `BookingRef`, the `turn` as an integer, the `Prompt`, the tool specs, and an ordered tuple of items: the first user message, `ToolCallItem` values (call id, name, raw argument text), and `ToolResultItem` values (call id, canonical result text) (P24).
- `JsonValue` and `canonical_json(value: JsonValue) -> str` live in `orchestration/` (P22).
- The trace (P14) has these keys in order: `prompt_version`, `turns`, `usage`, `tool_calls`, `provider_error_code`.
- The tools are `get_booking`, `search_offers` and `check_offer`. `check_offer` is plan 02's name for the one-offer tool. Earlier drafts called it `evaluate_offer`.
- The loop assigns call ids as `call_<turn>_<n>` (Context of plan 02).
- The model name comes from `OPENAI_MODEL`, with no default in code (P17). Plan 02's model factory checks the live extra, the key and the model name before any call (P18). `ProviderAuthenticationError` and the other setup errors are defined in `infrastructure/openai/`.
- The prices of the configured model are recorded in the "Milestone 1 result" Decision Log entry of plan 02.

Terms that plan 02 defines and this plan uses: the report, the trace, `ModelRow`, `RulesRow`, the call id, the safety check.

Working directory and paths (plan 01 L6): the recording paths are relative to the working directory, like the data and config files. There is no path flag.

Composition entry points (new in this plan). Each one reads the policy file and the rates file from the working directory, and reads the prompt from the package. Each returns a value or raises a typed error that composition maps to `SetupError`.

- `record_review(source, recording_path, model)` takes the bookings and offers source, the path of the recording to write, and an `AgentModel` that the caller built. It computes the header, wraps the model, runs `review_with_model`, and returns `RecordedRun` (the report and the path written) or `RecordingStopped`.
- `replay_review(source, recording_path)` takes no environment. It returns the report with `mode: recorded`, or raises `StaleRecording`.
- `check_recording(source, recording_path)` returns `RecordingCheck`: either ok, or the changed inputs, or a read error. The doctor prints it.
- `recording_path(data_set)` maps a `DataSet` to its path (L8).
- `re_record_command(data_set)` returns the re-record command for that data set (L12).

`DataSet` is a `StrEnum` in `composition/` with the values `sample` and `scenarios`. The CLI's `--data` flag reads its choices from it.

Environment (L8): only plan 02's model factory reads `OPENAI_MODEL` and the key. `record_review`, `replay_review` and `check_recording` take no environment, so replay and the doctor read no key and no model name.

Test layout. All tests of this plan live in `tests/test_recording.py`. Plan 01's test rules set no exact number of test files, so this file needs no exception. Each test that runs the CLI runs the installed script as a subprocess, as plan 01's CLI tests do. Each review invocation in the tests is written on one line, so a grep can see whether it names `--model`. A test that needs changed data or config copies the inputs into `tmp_path` and calls `monkeypatch.chdir(tmp_path)`, or runs the subprocess there. No test edits a repo file.

## Locked decisions

Each decision below is copied from the feature index by its id, or is this plan's own lock (L1 to L17). Where the index and this plan differ, the Decision Log says so.

D15. CLI: `fare-reshop review` with `--model none|openai|recorded`, `--format json|table`, `--record` (only with `openai`) and `--data sample|scenarios`. The default model is `recorded` after Milestone 8. `--record` with any other model exits 2 and prints `record needs --model openai` on stderr. Exit codes: 0 done, 1 internal error (traceback only with `--debug`), 2 setup error (files, policy, missing extra, missing key, missing model, failed or stopped recording, bad flags, provider authentication), 3 stale recording. Applied here: the missing, unreadable, stopped and failed-write recording errors exit 2; the stale error exits 3.

D16. The model seam is `AgentModel.next_step(transcript) -> ModelReply`. The reply is stateless. The transcript holds everything the model sees. The loop assigns call ids once. A provider failure is a typed reply, not an exception. Applied here: the wrapper reads the booking and the turn from the transcript. It never assigns, parses or re-applies a call id.

D22. Recording wraps any model adapter. Turns are kept in memory and written atomically only after a run with no provider failure, to one file per data set (`recordings/review-run.json` for `sample`, `recordings/scenarios-run.json` for `scenarios`). The file is UTF-8 with sorted keys and an indent of 2. `infrastructure/` owns the file schema. `orchestration/` owns the canonical serializer and one projection per digested value, so renaming a field does not stale a recording. Money in digests is normalized to two decimal places. The header has one digest per input: the booking and offer data (`pnrs` and `fares_feed`), `policy`, `rates`, `prompt` and `tools`. The model name is a plain field that replay shows and does not compare. The turns are keyed by booking and turn number, each with the digest of the transcript the model saw, the reply and its token usage. Digests are SHA-256 over the canonical text. The prompt file is read as bytes with no newline translation, and `.gitattributes` keeps both the prompt and the recordings at LF. The default suite checks that each committed recording's header matches the committed data, and that replaying each committed recording raises no `StaleRecording` and leaves no leftover turn. While recording, the run stops at the first provider failure and writes nothing. Replay runs the tools for real and raises `StaleRecording` on a header mismatch, a digest mismatch, a missing turn or a leftover turn. Reason: vcrpy cassettes and their record modes show the pattern. Whole HTTP traffic leaks headers and ids and ties replay to the SDK. Replay without digests answers questions that are no longer asked. A `.partial` file is a second write path with no reader.

D23. After the replay plan, the default mode is `recorded` and the recordings are committed. `none` stays the rules-only mode. Applied here in Milestone 8, after the committed sample file exists (L16).

D24. Each model-mode result carries a trace with the tool calls and their arguments, the turn count, the token usage and the prompt version. In recorded mode the trace shows the recorded model name and the recorded usage. A provider failure prints its closed code (`connection`, `timeout`, `rate_limit`, `server_error`), never provider text. Applied here: a stopped recording prints the booking and the closed code on stderr (L13).

D25. The prompt is a Markdown file in `orchestration/`. Its SHA-256 is the prompt version, and the same bytes are the instructions sent to the model and the prompt digest in the header.

D26. Docs: `README.md`, `DESIGN.md`, `GLOSSARY.md`, `docs/adr/` and `docs/future-work.md`. Each plan writes its own glossary terms and ADRs in its last milestone. Applied here: Milestone 9 adds `Recording` and `Stale recording` to `GLOSSARY.md`, writes ADR 0004 and writes the re-record runbook.

D27. The thin slice. No budgets are added to the recording or the replay, and no tool is added.

D28. Plans are tracked in the public repo. Every tracked file, commit message and branch name passes the local leak hooks. Applied here: the DoD checks the recordings, the glossary, ADR 0004, the runbook and this plan against the denylist.

D30. Only the configured data sets are read: `sample` and `scenarios` (D34). Booking and offer facts leave the machine in tool results sent to OpenAI, and the same facts are stored in the committed recordings. The fixtures hold no names or contact data (A5), so nothing is masked. `DESIGN.md` says so and lists masking as needed before real data. Applied here: a recording stores only the replies, the usage, the model name and the digests (L5). The DoD checks the committed files for strings that are not fixture facts (Milestone 7).

D31. First-run experience: `./start.sh` checks for `uv`, asks before installing anything, and then runs `uv sync`, `doctor` and the default review. `fare-reshop doctor` lists every check with its fix command. Every CLI error prints three lines labeled `error:`, `reason:` and `fix:`, with no traceback unless `--debug` is passed. Applied here: the stale, missing, unreadable and stopped recording errors print these lines. Doctor gains one recording check per data set, and its failure line names the re-record command.

D33. Only the owner re-records. The default suite holds `test_committed_recording_matches_data` and `test_committed_recording_replays`, so `./scripts/check.sh` fails locally when a recorded input or a rule changes, until the owner re-records. The runbook says how to re-record and what it costs. The script makes no model call and needs no key. Applied here: the failure message of those tests names the re-record command and says that a change to the prompt, the tool specs or the review rules needs the owner's re-record.

D34. A second configured data set, `scenarios`, in `fixtures/scenarios/pnrs.json` and `fixtures/scenarios/fares_feed.json`. The CLI takes `--data sample|scenarios`, default `sample`. The value names a configured data set and never a free path. Each data set has its own recording file. Applied here: Milestone 10 commits `recordings/scenarios-run.json`.

L1. Placement. The canonical serializer, the projections, the digest functions, the header value, the recorded turn value, the recording value, the recording wrapper, the replay adapter, the header comparison, `StaleRecording` and `RecordingStopped` live in `orchestration/`. They do no file I/O and read no environment variables. Reason: the loop's concepts live in orchestration (D10), and a wrapper that wrote files would give orchestration I/O.

L2. Model seam. The recording wrapper is the `AgentModel` that `review_with_model` receives. The replay adapter takes the same place. The prompt is the `Prompt` value that `review_with_model` takes, and the prompt digest of the header is `Prompt.version`. The wrapper passes each inner reply back to the loop unchanged. A `ProviderFailed` reply is kept as the stop, and every later call returns that same failure without calling the inner model. The wrapper's `model_name` is the inner model's name. Reason: the loop must not change, and the stop makes no further paid call.

L3. Outcome of a recording run. The wrapper's outcome is one of two values. `RecordingCompleted` holds the complete `RecordedTurns` value. `RecordingStopped` holds the booking and the closed code of the first failure. Composition returns `RecordedRun` (the report and the path written) on completion and `RecordingStopped` otherwise. The CLI maps `RecordingStopped` to exit 2 and three stderr lines. Reason: a stopped run has no complete record, so it must not write.

L4. Header. Composition computes the six digests once per run:

- `pnrs` from the bookings and the rejected references of the snapshot,
- `fares_feed` from the offers and the capture time,
- `policy` from the policy,
- `rates` from the rate entries,
- `prompt` from `Prompt.version`,
- `tools` from the tool specs.

`RecordingHeader` is a frozen dataclass with those six digest fields. `HeaderInput` is a `StrEnum` with the six members in that order. The pure function `changed_inputs(current, recorded)` in orchestration returns the `HeaderInput` values whose digests differ, in enum order. The wrapper stores the header. Replay compares it with the file's header before the first turn. Reason: composition is the only layer that reads files, so one computed header cannot disagree with itself.

L5. The file. The top-level keys are exactly `schema_version` (the integer 1), `model` (the model name as text), `header` (an object with the six digest strings under the keys of L4) and `turns`. The `turns` array is sorted by booking reference, then turn number. Each turn is an object with exactly `booking`, `turn` (an integer), `transcript_digest`, `reply` and `usage`. The `usage` object holds `input_tokens` and `output_tokens` as integers. The `reply` object has a `kind` with one of three values:

- `tool_calls` holds `text` (the text the reply carried, or null) and `calls`, in the order the model returned them. Each call holds `name` and `arguments`, where `arguments` is the raw argument text exactly as the model sent it, as a JSON string. A mixed reply is a `tool_calls` reply with non-null `text`.
- `final` holds `text`, the final answer as the model returned it.
- `refusal` holds `text`, the refusal as the model returned it.

Nothing else is stored. There are no call ids, request ids, headers or raw response bodies. Reason: `schema_version` follows D9; six digests name the part that changed; sorting makes the file deterministic; raw argument text lets a malformed reply round-trip and digest as sent.

L6. Canonical serializer, projections and digests. `canonical_json` takes a `JsonValue`. It sorts keys at every level, writes no spaces or line breaks between tokens, writes UTF-8 without escaping, writes each `Decimal` as a quoted string of its `format(value, "f")` text without normalizing it, writes counts as integers, and raises `TypeError` on a float. Money is not normalized there.

The money projection is the one place that normalizes money. A `Money` value becomes the object `{"amount": <text with exactly two decimal places>, "currency": <code>}`. A value with more than two decimal places raises `ValueError`, so no digest rounds money silently. The projections of the bookings, offers and policy use it for every money field.

Each digested value has one projection in `orchestration/`. Each reads the domain fields by name and writes them under literal key strings:

- `pnrs`: `{"bookings": [...], "rejected": [...]}`. The bookings are sorted by reference and carry every field of the parsed booking, with money projected. The rejected list holds the sorted references of the records the parser rejected.
- `fares_feed`: `{"capture_time": <UTC ISO text>, "offers": [...]}`. The offers are the valid offers, sorted by offer id, each with every field of the parsed offer.
- `rates`: the list of rate entries sorted by base then quote, each `{"base", "quote", "rate", "as_of"}`. The rate is a `Decimal` written as text, and `as_of` is an ISO date.
- `policy`: every field of `ReviewPolicy`, with money projected.
- `tools`: the tool specs sorted by name, each with every field.
- `transcript`: `{"booking", "turn", "instructions", "tools", "items"}`. The items are `{"kind": "user", "text"}` for the first message, `{"kind": "call", "call_id", "name", "arguments"}` where `arguments` is the raw text, and `{"kind": "result", "call_id", "result"}` where `result` is the canonical result text.

A digest is the lowercase hex SHA-256 of the UTF-8 bytes of the canonical text of its projection. The `prompt` digest is `Prompt.version` (plan 02 P13). Each turn's `transcript_digest` is the digest of the transcript projection exactly as the model received it. The text of a `tool_calls` reply is stored in the file but is not sent back to the model, so the transcript projection does not include it.

A renamed domain field changes no digest, because the key strings are literals. A changed key string changes the digest. Reason: parsed values are what the tools and the model see. Raw bytes would stale a recording on formatting changes, and a dataclass dump would stale every recording on a rename.

L7. File bytes and the writer. The file text comes from the file models in `infrastructure/json_files/`. It is produced with `json.dumps` using sorted keys, an indent of 2, no ASCII escaping, and one final newline. The writer encodes that text as UTF-8 bytes and writes them to a temporary file in the target's folder. It flushes and fsyncs the file, then renames it over the target with `os.replace`. A failed write removes the temporary file and raises a typed write error with the path and the reason. The writer creates the folder when it is missing. The digests use the compact canonical text of L6, never the file text.

L8. Recording path and data sets. `recording_path(data_set)` maps `sample` to `recordings/review-run.json` and `scenarios` to `recordings/scenarios-run.json`, relative to the working directory. There is no flag for the path. The data set picks the pair of data files and the recording. Reason: the default run, the doctor and the committed files must read one known path for each data set.

L9. Turn numbers and call ids. The transcript carries the turn number as an integer, set by the loop. A booking's first model call has turn 1. The loop assigns the call ids once, when it builds the transcript from a reply (plan 02). The wrapper reads the booking and the turn from the transcript. It does not assign, parse or re-apply a call id, and it stores no call ids. On replay the loop assigns the same ids, because the turn and the position are the same. Each later turn's transcript digest covers the earlier ids, so a change to the id rule is caught. Reason: the wrapper sits before the loop's id step, so it cannot see the ids.

L10. Replay. `RecordedModel` is a pure lookup over the immutable `RecordedTurns` value. It keys entries by booking and turn. On each call it reads the booking and the turn from the transcript, looks up the entry, computes the transcript digest and compares. A missing entry raises `StaleRecording` with a `MissingTurn` reason. A different digest raises it with a `DigestMismatch` reason. Otherwise it returns the stored reply. `StaleRecording` carries a tuple of `StaleReason` values, each one of four frozen types: `HeaderChanged` (one `HeaderInput`), `DigestMismatch`, `MissingTurn` and `LeftoverTurn` (each with its booking and turn). Before the loop, `replay_review` runs the header check and raises `HeaderChanged` values for each changed input. After the loop, composition runs the leftover check: for each stored entry with booking B and turn t, the entry is leftover when t is greater than the turn count that the report's trace gives B (zero when the report has no row for B). Each leftover raises `LeftoverTurn`. The loop never catches `StaleRecording`.

Why a stale recording is a setup failure: the file answers questions that the current inputs no longer ask, so no valid review can come from it. The owner must re-record. D15 gives it exit 3, and the Python rules keep setup failures as exceptions.

L11. Replay trace fields. A pure function in orchestration, `recorded_trace(trace, recorded_model)`, turns the plan 02 trace of a replayed booking into the recorded variant. The variant has these keys in order: `prompt_version`, `turns`, `recorded_model` (the model name from the file), `recorded_usage` (the usage of the booking's stored turns, with `input_tokens` and `output_tokens`), `tool_calls`, and `provider_error_code` (always null in recorded mode). The variant has no `usage` key, so the usage appears once. The model name is shown and never compared (D22). Reason: a trace with two usage figures invites a reader to add them. This variant is the recorded-mode form that S3 names. D24 names only the model name, and the index's S3 names both fields; this plan follows S3.

L12. Messages and fix commands. Every error prints three lines labeled `error:`, `reason:` and `fix:` (D31).

- A stale recording names the changed inputs, or the booking and turn, in the `error:` line. The `reason:` line says in plain words what it means. The `fix:` line is `re_record_command(data_set)`.
- A missing or unreadable recording names its path in the `error:` line. The `fix:` line is `uv run fare-reshop review --data <set> --model none`.
- `re_record_command(data_set)` returns `uv run --env-file .env.local --extra live fare-reshop review --data <set> --model openai --record`. The same function supplies the fix of the stopped run (L13), the fix of the `--record` gate (Milestone 3), and the fix of the doctor's recording line.

Reason: each error names one thing to do, and every re-record command is the same command for its data set, so the owner copies one string.

L13. Stopped recording message. A stopped recording prints three lines on stderr: `error:` "booking <ref>: recording stopped", `reason:` the closed code, and `fix:` the re-record command for the data set. Stdout is empty. The line never contains provider text (D24).

L14. Line endings. The `.gitattributes` file at the repo root pins LF for `fare_reshop_agent/reshopping/orchestration/review_prompt.md` and for `recordings/*.json`. The prompt digest covers the file's exact bytes. A checkout that turned LF into CRLF would make a different prompt and stale every recording. The code does not normalize line endings. The prompt is read as bytes and decoded as UTF-8 with no newline translation.

L15. Provider failure during recording. The first `ProviderFailed` ends the recording run as L2 and L3 describe. Without `--record`, plan 02's rule applies: the failure ends only its booking, and the other bookings continue. Reason: a recording with a gap would replay as a stale run.

L16. Default mode. The default mode becomes `recorded` only in Milestone 8, after the sample file is committed (D23). Reason: a default that replays a missing file fails every default run.

L17. Tests. Each test calls one public function and names it. Tests use the scripted fake model for the orchestration, the in-memory `ReshopSource` for changed data, and temporary copies for changed files and recordings. Tests never use `mock.patch` on our own code. Tests read the real recording paths only in the committed-file tests of Milestones 7 and 10, which read the files and never write them. No test reads the API key.

## Alternatives considered

Recording whole HTTP traffic was rejected, because it stores headers and request ids and ties replay to the SDK (D22).

Digesting the raw fixture bytes was rejected. A comment key or a changed line break would stale every recording, while the tools never read those bytes.

A single digest for all inputs was rejected. It cannot say which input changed, and the stale message must name the input.

Writing the file from inside the wrapper was rejected, because it would give `orchestration/` I/O and let a test double write to disk. The wrapper returns a value, and infrastructure writes it.

Streaming turns to a `.partial` file was rejected by D22. It adds a second write path with no reader.

Raising an exception to stop a recording at the first provider failure was rejected. The stop is a value (`RecordingStopped`), so the loop's types stay honest.

Making a stale recording a per-booking outcome was rejected. A stale file invalidates every booking, so a partial report would look trustworthy.

Storing provider call ids was rejected, because they change from run to run. Storing the loop's call ids was rejected, because the wrapper sits before the loop assigns them and storing them would need a second place that gives ids. L9 covers the ids through the transcript digests.

Continuing the other bookings after a provider failure during a recording was rejected, because the file would hold a gap (L15).

A path flag was rejected. One path per data set keeps the default run, the doctor and the committed files in agreement (L8).

Keeping the default at `none` until the file is committed was chosen over flipping it with the replay code (L16).

Recording in `none` mode was rejected, because `none` makes no model call.

Putting the file text conversion in the domain or in orchestration was rejected. The file format is infrastructure, so the schema lives in `infrastructure/json_files/` (L7).

Taking the rate entries from a new `ExchangeRates` list method was rejected. It would change plan 01's port and the in-memory fake. Composition reads the entries once with the rate reader instead (L4, L6).

A stored argument object (parsed JSON) was rejected. A malformed argument has no object form, and the digest must cover the text as sent (L5).

Reading `OPENAI_MODEL` with a fallback in `record_review` was rejected. Required data has no fallback (plan 02 P17). The model name now comes from the model object.

## Invariants, risks and open questions

Invariants that hold throughout. Replay never opens a network connection. `replay_review` and `check_recording` take no environment mapping and read no key and no model name. A recording's turns are used only when all six header digests match and each turn's transcript digest matches the transcript the loop built. A partly matching recording is stale, not partly used. Tools always run for real during replay, and only the model's replies come from the file. The file never holds a key, a request id, a header, a raw response body, or any text beyond the reply text, the tool argument text as the model sent it, the usage, the model name and the digests. Recording and replay call the same projection and digest functions, so a difference between them is a bug, not a stale file. The loop's provider-failure handling never catches `StaleRecording`. A recording run makes no model call after its first provider failure (L2). Writes are atomic: after a crash, the file is the old one or the new one. Money never enters the file, and token counts are integers. The files keep LF line endings (L14).

Assumption A3, from the index: the owner's key is in `.env.local` before Milestone 7, and one recording costs under 1 USD at the configured model's prices. The prices are the ones recorded in the "Milestone 1 result" entry of plan 02, which this plan does not repeat in its own text. Milestone 7 copies them into the Decision Log (Milestone 7 Work), and the cost check reads that copy. Risk: the key is missing. Mitigation: Milestone 7 stops before any call, and the implementer asks the owner to set `OPENAI_API_KEY` in `.env.local`. The implementer never writes a recording by hand, never uses the fake model to make one, and never prints the key. Risk: the real run is over budget. Mitigation: the cost check is a DoD item. If it fails, do not commit the file, and report the token counts to the owner. Safe retry: a second run overwrites the file atomically, but it costs money, so the implementer asks before any second paid run.

Assumption A5, from the index: the fixtures are synthetic and hold no names or contact data. Risk: a real name or contact sits in a fixture. Mitigation: Milestone 7 inspects the file by eye, and a script checks every string. If real data appears, stop and ask the owner before committing.

Risk: a recording goes stale after a change to the bookings, offers, policy, rates, prompt or tool specs. The header catches these changes, and the test `test_committed_recording_matches_data` names the changed input. A change to the review rules in code does not change the header. It changes the tool results, so the transcript digests change, and `test_committed_recording_replays` raises `StaleRecording`. Both tests run in `./scripts/check.sh` (D33). Safe retry: re-recording overwrites the file atomically, and only the owner runs it (runbook, Milestone 9).

Risk: plan 02 lands without a reply type that holds optional text, without `model_name` on `AgentModel`, or without the names of Context. Mitigation: check these at the start of Milestone 2 and stop to report if they differ. The recording of a mixed reply (L5) and the recorded model name depend on them. Do not add a second reply type or an optional field in this plan.

Risk: plan 01 does not expose the rejected references or does not return the rate entries as a tuple. Mitigation: stop and report before Milestone 3, because the header (L4) depends on both.

Risk: plan 02's trace type cannot take the recorded-mode variant (L11). Mitigation: stop and report. Do not add optional fields to the trace.

Risk: plan 02 lands with provider ids that differ from the `call_<turn>_<n>` ids of the loop. Mitigation: stop and report instead of adapting this plan (L9).

Risk: the key is missing or the real run fails for good, so the default switch never happens. Mitigation: the no-key path below.

Risk: tests that run the CLI without `--model` change behavior in Milestone 8. Mitigation: each such test gets an explicit `--model none`, the Surprises & Discoveries section lists each one, and the DoD greps for a review call without `--model`. No assertion is weakened to pass.

Risk: the model's recorded decisions differ from the rules-only table in the index. This is expected: the recording holds what the model did. The replay checks for a stale file, not for the rules-only table.

Risk: a changed model name is not caught. This is intended by D22. The name is shown in the trace, not compared.

Risk: the no-secrets test cannot prove that no secret exists anywhere. It proves that the sentinel and a request id copied from the stub never reach the file, stdout or stderr. The Milestone 7 string check covers the committed files.

The no-key path. If the owner's key is absent or the real run cannot succeed, the plan stops at Milestone 7 and reports the state to the owner. Milestones 1 to 6 and 9 need no key. Milestone 8 needs no key for its `check_recording` and doctor parts, which Milestone 8 may build before Milestone 7 with a temporary recording. Its default switch waits for Milestone 7. Do not commit a fake or hand-made file into `recordings/`, because the default would then replay an answer no real model gave. Report and wait for the key.

Open questions: none for the owner. The index records none. The cross-plan requirements above must hold when this plan starts.

## Milestones

### Milestone 1 - Canonical serializer and digests

Goal: `canonical_json`, the money projection, the six projections of L6 (with the transcript projection), and their digest functions exist in `orchestration/`. No file is written and no model is called. The header of L4 is not built here; Milestone 3 builds it.

Work: `canonical_json` follows L6. The money projection follows L6. Each projection reads the domain fields by name and writes them under literal keys. The rates projection takes the rate entries that composition reads (L4). Each digest function is the lowercase hex SHA-256 of the canonical text of one projection. Nothing reads a file. Nothing reads the environment.

Seam: the public projection and digest functions, called directly from `tests/test_recording.py`. The snapshot tests load the repo's fixtures through plan 01's fixture adapter. The other tests build their values inside the test. Prior art: plan 01's `tests/test_review_rules.py`.

Tests, in `tests/test_recording.py`:

- `test_canonical_json_refuses_floats`: a float anywhere in a value raises `TypeError` before any text is returned.
- `test_canonical_json_ignores_key_order`: two mappings with the same keys in a different order give the same text and the same digest.
- `test_decimal_80_00_is_written_fixed_point`: `canonical_json` writes `Decimal("80.00")` as the quoted text `"80.00"` and `Decimal("80")` as `"80"`. It does not normalize.
- `test_money_is_normalized_to_two_places`: `Money` built from `Decimal("80")` and from `Decimal("80.00")` give the same money projection and the same snapshot digest.
- `test_money_with_three_places_is_refused`: a `Money` with three decimal places raises `ValueError` in the money projection.
- `test_money_digit_change_changes_digest`: one changed digit in one price changes the snapshot digest.
- `test_digest_survives_field_rename`: the transcript projection of a fixed transcript, built in the test, gives the canonical text that the test pins as a literal written from L6, and its digest equals the pinned literal digest. The projection writes literal keys, so a renamed domain field changes no digest, and a changed key string fails this test.
- `test_transcript_digest_covers_domain_transcript`: changing one earlier tool result changes the transcript digest, and so does changing only the turn number.

Proof: from the repo root, `uv run --all-extras pytest -q tests/test_recording.py::test_canonical_json_refuses_floats tests/test_recording.py::test_canonical_json_ignores_key_order tests/test_recording.py::test_decimal_80_00_is_written_fixed_point tests/test_recording.py::test_money_is_normalized_to_two_places tests/test_recording.py::test_money_with_three_places_is_refused tests/test_recording.py::test_money_digit_change_changes_digest tests/test_recording.py::test_digest_survives_field_rename tests/test_recording.py::test_transcript_digest_covers_domain_transcript` prints no failures and exits 0.

### Milestone 2 - Recording wrapper with a scripted model

Goal: `review_with_model`, run with the recording wrapper around the scripted fake model, keeps every reply in memory with its turn. On a provider failure it stops calling the inner model and reports `RecordingStopped`.

Work: first check the plan 02 names listed in Context. Stop and report if they differ. The wrapper takes the inner `AgentModel`, the `RecordingHeader` and reads the model name from the inner model. On each call it reads the booking and the turn from the transcript (L9), computes the transcript digest (L6), and delegates. A `ToolCalls`, `FinalText` or `Refusal` reply is stored as a `RecordedTurn` (booking, turn, transcript digest, reply and usage) and returned unchanged. The stored reply type is the alias `RecordedReply`, which is the union of those three types and excludes `ProviderFailed`. A mixed reply is stored as a `ToolCalls` reply that carries its text. A `ProviderFailed` reply is returned unchanged and kept as the stop. After the stop, the wrapper returns the same failure for every later call without calling the inner model. `outcome()` returns `RecordingCompleted` with `RecordedTurns` (header, model name, and turns sorted by booking and turn) or `RecordingStopped`. The file form of `RecordedTurns` comes in Milestone 3.

If plan 02 has not created the scripted fake model, this milestone creates it in `tests/`. It returns a fixed list of replies for each booking, can return a `ProviderFailed` reply on a chosen turn, and records every transcript it was shown.

Seam: `review_with_model` from `orchestration/`, called in the test with the in-memory ports of plan 01's tests, the wrapper around the scripted fake model, and a header built from the in-memory values. Prior art: the scripted-model tests of plan 02.

Tests, in `tests/test_recording.py`:

- `test_recording_keeps_every_turn`: two bookings with scripted turns. The outcome's turns hold each booking's replies in turn order, with the turn numbers that the loop gave.
- `test_recording_stops_at_first_provider_failure`: the fake returns `ProviderFailed` on turn 2 of the first booking. The outcome is `RecordingStopped` with that booking and the code. The fake was asked for no call after the failure, for any booking.
- `test_mixed_reply_is_stored_with_its_text`: a scripted reply holding tool calls and final text is stored as a `ToolCalls` reply with that text. The loop receives the same reply unchanged, and it ends the booking as `bad_final_answer` with no tool run.

Proof: from the repo root, `uv run --all-extras pytest -q tests/test_recording.py::test_recording_keeps_every_turn tests/test_recording.py::test_recording_stops_at_first_provider_failure tests/test_recording.py::test_mixed_reply_is_stored_with_its_text` prints no failures and exits 0.

### Milestone 3 - Atomic writer, file schema and the `--record` flag

Goal: `fare-reshop review --model openai --record --data <set>` writes the recording of that data set after a complete run and prints its path on stderr. A stopped run writes nothing and exits 2. `--record` with another model exits 2 before any call.

Work: `infrastructure/json_files/` gets the file models of L5 (pydantic, `extra="forbid"`, `frozen=True`), a converter from the domain recording to the file text and back (the back direction serves Milestone 4), the atomic writer of L7, and the write error. The writer creates the folder when it is missing and removes its temporary file on failure. In `composition/`: the `DataSet` value, `recording_path` (L8), `re_record_command` (L12), `compute_header` (L4), and `record_review(source, recording_path, model)`. `record_review` reads the policy and rate files from the working directory, reads the prompt from the package, computes the header, and writes `model.model_name` into the file. It maps a write error to `SetupError`, and it returns `RecordingStopped` without writing when the wrapper stopped. In `cli/`: the `--data` flag, the `--record` gate (exit 2 with `record needs --model openai` on stderr, and the fix from `re_record_command`), the path line on stderr, the stdout report, and the rendering of a stopped run (L13). The model for `--model openai` comes from plan 02's model factory, which checks the extra, the key and the model name before any call.

Seam: `record_review` from `composition/`, called with the in-memory source, the scripted fake model or the OpenAI adapter with a stub client, and a path in `tmp_path`. The CLI rendering functions are called directly. The `--record` gate test runs the installed script as a subprocess from the repo root with `--model none`, which exits before any call.

No-secrets test. The test builds the OpenAI adapter with a stub client whose responses carry a request id and a key-shaped string, both built from a sentinel value that begins `sk-test-`. It runs `record_review` into `tmp_path`. It then calls the `cli/` functions that print the report and the path, and captures stdout and stderr with `capsys`. It asserts that the sentinel is absent from the written bytes, from stdout and from stderr. It also asserts that the file's top-level keys and turn keys are exactly the ones L5 lists. The test fails if anything copies a request id or a key into the recording or the printed output.

Tests, in `tests/test_recording.py`:

- `test_recording_schema_round_trip`: a `RecordedTurns` value, including one `ToolCalls` reply whose arguments are malformed JSON text, converts to file text and back to an equal value. The text is UTF-8 with sorted keys, an indent of 2 and one final newline.
- `test_atomic_write_leaves_no_temp_file`: the writer targets a path that is a directory of the same name, so the rename fails. The writer raises the typed error, no temporary file is left in the folder, and the directory is unchanged.
- `test_recording_creates_missing_folder`: `record_review` writes into a `recordings/` folder that does not exist yet.
- `test_recording_written_after_turn_cap`: `record_review` with a scripted booking that uses all ten turns with tool calls. The file holds ten turns for that booking, the report row is `INCOMPLETE_ANALYSIS` with `turn_cap`, and the header has six digests.
- `test_failed_recording_keeps_old_file`: an old file's bytes are at the path. `record_review` with a scripted provider failure returns `RecordingStopped`. The bytes are unchanged, no temporary file is left, and the CLI rendering gives exit 2 with three lines that name the booking and the closed code.
- `test_recording_has_no_secrets`: as described above.
- `test_record_flag_needs_openai_exits_2`: the subprocess `review --model none --record` exits 2, and stderr contains `record needs --model openai`.

Proof: from the repo root, `uv run --all-extras pytest -q tests/test_recording.py::test_recording_schema_round_trip tests/test_recording.py::test_atomic_write_leaves_no_temp_file tests/test_recording.py::test_recording_creates_missing_folder tests/test_recording.py::test_recording_written_after_turn_cap tests/test_recording.py::test_failed_recording_keeps_old_file tests/test_recording.py::test_recording_has_no_secrets tests/test_recording.py::test_record_flag_needs_openai_exits_2` prints no failures and exits 0.

### Milestone 4 - Replay reader and header check

Goal: the recording file is read and validated, and a replay with a changed input raises `StaleRecording` before any model turn.

Work: the reader in `infrastructure/json_files/` reads the file as UTF-8, parses it with the file models, requires `schema_version` 1, and returns the domain recording. A missing file, a file that does not parse, and a `schema_version` other than 1 each give a typed read error with the path and the reason. `HeaderInput` and `changed_inputs` (L4) live in `orchestration/`. `replay_review(source, recording_path)` reads the file, computes the current header, and compares. A changed input raises `StaleRecording` with one `HeaderChanged` reason per input. The check runs before the loop, so no model call happens on a stale file. This milestone builds only the stale path and the read errors. The matching path runs the loop, which Milestone 5 adds. Composition maps the read errors to `SetupError`.

Seam: `replay_review` from `composition/`, and the reader and `changed_inputs` from their modules. The changed-fixture test calls `replay_review` with the in-memory source, with one fare changed, against a recording made from the original data by `record_review` with the scripted fake model in `tmp_path`. The changed-policy test runs after `monkeypatch.chdir` to a `tmp_path` copy in which one policy value is changed, against a recording made in that copy. The reader tests call the reader on copies in `tmp_path`.

Tests, in `tests/test_recording.py`:

- `test_changed_fixture_is_stale`: `replay_review` raises `StaleRecording` with `HeaderChanged` for `fares_feed`. The scripted fake was asked for no call.
- `test_stale_header_names_changed_input`: the changed policy copy gives exactly `policy` and no other input.
- `test_unknown_schema_version_is_read_error`: a file with `schema_version` 2 gives a typed read error whose reason names the version.
- `test_missing_file_is_read_error`: a path that does not exist gives a typed read error with the path.
- `test_unreadable_file_is_read_error`: a file with invalid JSON gives a typed read error with the path.

Proof: from the repo root, `uv run --all-extras pytest -q tests/test_recording.py::test_changed_fixture_is_stale tests/test_recording.py::test_stale_header_names_changed_input tests/test_recording.py::test_unknown_schema_version_is_read_error tests/test_recording.py::test_missing_file_is_read_error tests/test_recording.py::test_unreadable_file_is_read_error` prints no failures and exits 0.

### Milestone 5 - Recorded adapter and turn checks

Goal: `replay_review` runs the real review loop with `RecordedModel` as the model. Each reply comes from the file, the tools run for real, and a changed or missing turn raises `StaleRecording` that names the booking and the turn. A malformed or mixed reply replays as it was recorded.

Work: `RecordedModel` (L10) is a pure lookup over `RecordedTurns`. It exposes the file's model name as `model_name`. A missing entry and a digest mismatch raise `StaleRecording` with the `MissingTurn` or `DigestMismatch` reason. `replay_review` runs the loop with `RecordedModel`, then builds the report with `mode` set to `recorded`, and maps each trace to the recorded variant with `recorded_trace` (L11). `StaleRecording` raised inside the loop passes through it unchanged.

Seam: `replay_review` from `composition/`, after `record_review` has written a recording into a `tmp_path` folder with the scripted fake model. The changed-turn and missing-turn tests edit a copy of that recording through the file's converters, then call `replay_review` in the same folder.

Tests, in `tests/test_recording.py`:

- `test_replay_reproduces_turn_cap_booking`: a scripted run that hits the turn cap is recorded and replayed. The replayed row has the same status, incomplete reason and turn count.
- `test_replay_trace_shows_recorded_model`: the trace holds `recorded_model` with the scripted model's name and `recorded_usage` with the summed tokens. The trace has no `usage` key.
- `test_changed_turn_is_stale`: turn 2 of one booking in the copy has a different transcript digest. `replay_review` raises `StaleRecording` with a `DigestMismatch` for that booking and turn 2.
- `test_missing_turn_is_stale`: turn 2 of one booking is removed from the copy. `replay_review` raises `StaleRecording` with a `MissingTurn` for that booking and turn 2.
- `test_mixed_reply_record_and_replay_match`: a scripted mixed reply is recorded. The file's reply is `tool_calls` with non-null `text`. `replay_review` gives the same row as the recorded run, `INCOMPLETE_ANALYSIS` with `bad_final_answer`, and a trace with no tool call.
- `test_malformed_arguments_replay_matches`: a scripted reply whose argument text is malformed JSON is recorded and replayed. The replay gives the same `bad_arguments` tool error and no `StaleRecording`.
- `test_stale_recording_passes_through_the_loop`: a `StaleRecording` raised by `RecordedModel` during `review_with_model` leaves the function unchanged, and the loop does not turn it into a booking outcome.

Proof: from the repo root, `uv run --all-extras pytest -q tests/test_recording.py::test_replay_reproduces_turn_cap_booking tests/test_recording.py::test_replay_trace_shows_recorded_model tests/test_recording.py::test_changed_turn_is_stale tests/test_recording.py::test_missing_turn_is_stale tests/test_recording.py::test_mixed_reply_record_and_replay_match tests/test_recording.py::test_malformed_arguments_replay_matches tests/test_recording.py::test_stale_recording_passes_through_the_loop` prints no failures and exits 0.

### Milestone 6 - Leftover check and exit codes

Goal: a booking that finishes with recorded turns left over fails with `StaleRecording`. The CLI maps every recording error to its exit code with the three lines of L12.

Work: `replay_review` runs the leftover check of L10 after the loop. The CLI maps `StaleRecording` to exit 3 with the stale lines of L12. It maps a missing or unreadable file to exit 2 with the lines of L12. It accepts `--model recorded`. `re_record_command` and the missing-file fix produce exact strings for each data set.

Seam: `replay_review` for the leftover test, on a copy of a recording in `tmp_path` with an extra turn beyond a booking's turn count. The CLI tests run the installed script as a subprocess with the working directory set to a `tmp_path` copy of the repo's data and config. Each copy holds a recording written there by `record_review`, or has no `recordings/` folder, or has an unreadable file.

Tests, in `tests/test_recording.py`:

- `test_leftover_turn_is_stale`: the extra stored turn is reported as a `LeftoverTurn` for its booking and turn.
- `test_missing_recording_exits_2`: the subprocess `review --model recorded` in a copy with no recording exits 2. Stderr holds the three lines, and the fix line is `uv run fare-reshop review --data sample --model none`.
- `test_missing_scenario_recording_names_its_path`: the same with `--data scenarios`. The error line names `recordings/scenarios-run.json`, and the fix line names `--data scenarios`.
- `test_unreadable_recording_exits_2`: the subprocess in a copy whose recording is invalid JSON exits 2 with the three lines of the typed read error.
- `test_stale_recording_exits_3`: the subprocess in a copy whose policy file changed after recording exits 3. Stderr names `policy` and holds the exact line `fix: uv run --env-file .env.local --extra live fare-reshop review --data sample --model openai --record`.
- `test_re_record_command_per_data_set`: `re_record_command(DataSet.SAMPLE)` and `re_record_command(DataSet.SCENARIOS)` equal the exact strings of L12, with `--data sample` and `--data scenarios`.

Proof: from the repo root, `uv run --all-extras pytest -q tests/test_recording.py::test_leftover_turn_is_stale tests/test_recording.py::test_missing_recording_exits_2 tests/test_recording.py::test_missing_scenario_recording_names_its_path tests/test_recording.py::test_unreadable_recording_exits_2 tests/test_recording.py::test_stale_recording_exits_3 tests/test_recording.py::test_re_record_command_per_data_set` prints no failures and exits 0.

### Milestone 7 - Commit the sample recording

Goal: the sample recording exists as a real run, `.gitattributes` pins LF for the prompt and the recordings, and the default-suite tests about the committed sample file pass. Replay of the sample file works with no key.

Work: add `.gitattributes` (L14). Before the run, check that `.env.local` holds a key with `grep -c '^OPENAI_API_KEY=.' .env.local`, which prints 1. Never print the key. Make the one real run with `uv run --env-file .env.local --extra live fare-reshop review --data sample --model openai --record`. If the run stops, report the booking and the closed code it names, and ask the owner before any second paid run. If the run completes, inspect the file by eye: its `model` equals `OPENAI_MODEL` in `.env.local`, every turn has `input_tokens` above zero, and no string outside the fixtures appears except the reply text, the tool argument text, the tool names, the step kinds and the digests (A5). Then add three lines to the Decision Log, in these forms: `Prices used for the cost check: input <X> USD and output <Y> USD per 1M tokens.` (the two numbers copied from the "Milestone 1 result" entry of plan 02, and this line appears once in this plan), `model calls in the sample run: <N>` (N is the number of turns in the file), and the input tokens, output tokens, cost in USD at those prices, the model name and the date.

Two tests join `tests/test_recording.py`. `test_committed_recording_matches_data` loads the committed fixtures and config through the readers, reads the prompt file's bytes, builds the tool specs, and computes the header with the same function composition uses. It asserts that the file's header equals the result. When it fails, the message names the changed inputs and the re-record command, and says that a change to the prompt, the tool specs or the review rules needs the owner's re-record. `test_committed_recording_replays` runs `replay_review` on the committed sample file in the working directory with no key and no network. It asserts that no `StaleRecording` is raised, which covers the turn checks and the leftover check. `test_committed_prompt_and_recording_are_lf` reads the prompt file and the sample recording as bytes and asserts that no carriage return byte is present. Milestone 10 extends the first two to the scenario file. These tests read the committed files and never write them.

Seam: `record_review` for the one real run through the CLI, and `replay_review` and the header function for the committed-file tests. No test calls the provider, and no test writes to a committed path.

Tests, in `tests/test_recording.py`: `test_committed_recording_matches_data` (for the sample data set), `test_committed_recording_replays` (for the sample data set) and `test_committed_prompt_and_recording_are_lf`.

Proof: from the repo root, `env -u OPENAI_API_KEY uv run --all-extras pytest -q tests/test_recording.py::test_committed_recording_matches_data tests/test_recording.py::test_committed_recording_replays tests/test_recording.py::test_committed_prompt_and_recording_are_lf` prints no failures and exits 0.

### Milestone 8 - Replay becomes the default and doctor checks the recordings

Goal: `uv run fare-reshop review` with no flags replays the sample recording. `uv run fare-reshop doctor` reports, for each data set, whether the recording is present and matches the data. Neither command needs a key or a model call.

Work: the CLI's default `--model` becomes `recorded` (D23, L16). This step waits for Milestone 7, because the default must replay a committed file. Every existing test that runs the CLI without `--model` gets an explicit `--model none`, and the Surprises & Discoveries section lists each one. The doctor gains `check_recording` (Context) for each data set. Its line contains the word `recording` and the word `ok` when it passes, with the mark the other checks use. When it fails, the line names each changed input, or the read error, and gives the re-record command from `re_record_command`. The doctor exits 0 when every check passes and 2 when any fails (D31). The doctor reads no key and prints no key value. At this milestone the doctor shows one recording line, for the sample data set. Milestone 10 adds the scenario line. The `check_recording` and doctor parts may land before Milestone 7, because their test uses a temporary recording.

Seam: `check_recording` from `composition/` and the doctor from `cli/`. The changed-data test calls `check_recording` with the in-memory source, with one fare changed, against a recording made from the original data in `tmp_path`. It does not edit a fixture and does not touch the committed recording.

Tests, in `tests/test_recording.py`:

- `test_doctor_fails_when_recording_stale`: the check result is a failure whose line names the `fares_feed` input and the exact re-record command for the sample data set.

Proof: from the repo root, `uv run --all-extras pytest -q tests/test_recording.py::test_doctor_fails_when_recording_stale` prints no failures and exits 0. After Milestone 7 is committed, `env -u OPENAI_API_KEY uv run fare-reshop review | uv run python -c "import json,sys; d=json.load(sys.stdin); print(d['mode'], len(d['results']))"` prints `recorded 5`, and `uv run fare-reshop doctor | grep -cE '\[ok\].*recording'` prints `1`.

### Milestone 9 - Glossary, ADR 0004 and the re-record runbook

Goal: `GLOSSARY.md` defines `Recording` and `Stale recording`. `docs/adr/0004-recorded-replay-default.md` records the decision to replay a committed recording by default. `docs/runbooks/re-record.md` says how and when to re-record, and what it costs.

Work: check that `docs/adr/` holds the three ADRs that the earlier plans write (0001 to 0003). If one is missing, stop and report, because the number 0004 assumes them. Add the two terms under their own `### <term>` headings with the capitalized forms `Recording` and `Stale recording`, using the words of this plan's Context and Background. The ADR has exactly five level-two headings in this order: Status (Accepted), Context (why the default run needs an offline model answer, and why whole-traffic recording and a `.partial` file were rejected), Decision (recorded replay is the default, the file is committed, digests guard it, and replay runs the tools for real), Consequences (a change to the data, policy, rates, prompt, tool specs or review rules makes the file stale until the owner pays for a re-record; fixture facts reach the provider and the file, as D30 states), and Alternatives (default `none`, whole-traffic recording, raw-byte digests, a single header digest). The ADR must not link to any file under `.agents/plans/`.

The runbook has three level-two headings. "When to re-record" lists each change that makes `test_committed_recording_matches_data` or `test_committed_recording_replays` fail in `./scripts/check.sh`: any change to the bookings, offers, policy, rates, prompt or tool specs, and any change to the review rules. "Steps" gives the two commands as exact text, `uv run --env-file .env.local --extra live fare-reshop review --data sample --model openai --record` and the same with `--data scenarios`, then the check of the stderr path line, the replay of each data set with `uv run fare-reshop review` and `uv run fare-reshop review --data scenarios`, and the commit of the file by the owner. "Cost" gives the rule that one run costs under 1 USD at the prices in the Decision Log, and points to the token counts that the Decision Log records after each run. The runbook says that only the owner re-records and that the check script never does, because it makes no model call and needs no key (D33). The runbook must not link to plans.

Seam: none. The checks are file-level greps and the full gate.

Proof: the DoD lists the greps and the gate.

### Milestone 10 - Scenario recording, replay and committed checks

Goal: the scenario data set (D34) has its own committed recording, replays with no key, and is covered by the same committed-file checks and by the doctor. This is the second paid run. No other milestone changes.

Work: the owner runs `uv run --env-file .env.local --extra live fare-reshop review --data scenarios --model openai --record` once. It writes `recordings/scenarios-run.json` after a complete run and stops at the first provider failure without writing, as in Milestone 3. Inspect the file as in Milestone 7. Add the Decision Log line `model calls in the scenario run: <N>`, with the tokens, the cost at the price line of Milestone 7 and the date. Extend `test_committed_recording_matches_data` and `test_committed_recording_replays` to both data sets, one case for each pair of L8. Make the doctor's recording check cover both pairs, so the doctor prints two recording lines. The default run stays on `sample`, and `--data scenarios` replays the scenario file with no key.

Seam: `record_review` for the one real run through the CLI, and `replay_review`, the header function and the doctor's `check_recording` for the committed-file and doctor tests, as in Milestone 7. No test calls the provider, and no test writes to a committed path.

Tests, in `tests/test_recording.py`:

- `test_scenario_replay_has_six_results`: `replay_review` on the scenario pair, in the working directory, returns six rows with mode `recorded`.
- `test_doctor_fails_when_scenario_recording_stale`: the check for the scenario pair, with one scenario fare changed in memory, fails. Its line names the `fares_feed` input and the exact re-record command for `scenarios`.

Proof: from the repo root, `env -u OPENAI_API_KEY uv run --all-extras pytest -q tests/test_recording.py::test_scenario_replay_has_six_results tests/test_recording.py::test_doctor_fails_when_scenario_recording_stale` prints no failures and exits 0. The DoD lists the scenario checks.

## Surprises & Discoveries

- Observation: the repo has no code yet. It has `fixtures/`, `docs/future-work.md`, `.agents/plans/reshop-review/00-INDEX.md` and the plan folder. There is no `docs/adr/`, no `docs/runbooks/` and no `recordings/` folder yet. Every module this plan names is created by plan 01, plan 02 or this plan.
  Evidence: `ls` of the repo shows none of the three folders.
- Observation: plan 02 as it stood before its final pass had `ToolCalls` with no text, no `model_name` on `AgentModel`, the tool name `evaluate_offer` and the step type `ModelStep`. Plan 02's final pass puts the text on `ToolCalls` and the tool name `check_offer`. The `model_name` property is not in plan 02 yet.
  Evidence: `grep` of plan 02 for `model_name` finds nothing. Resolution: this plan requires `model_name` on `AgentModel`, and the report asks the owner to have plan 02 add it.
- Observation: this plan needs two things from plan 01 that its final pass does not yet name: the rejected booking references on the snapshot, and the rate reader returning the entries as a tuple.
  Evidence: plan 01 names `ReshopSource` as returning bookings, offers, capture time and data issues. Resolution: Milestone 3 stops and reports if plan 01 lacks either.
- Observation: the loop assigns call ids after the wrapper has returned the reply, so the wrapper cannot store them.
  Evidence: plan 02 P22 and L9 of this plan.
- When Milestone 8 is done, record here each existing CLI test that gained an explicit `--model none`.

## Decision Log

- Decision: the recording wrapper is the `AgentModel` passed to `review_with_model(source, rates, policy, model, prompt)` from plan 02. The header's prompt digest is `Prompt.version`.
  Rationale: the live review and the recording share one loop, and replay passes the replay adapter in the same place, so the three paths cannot drift.
  Date/Author: 2026-11-02, plan writer.

- Decision: the stored reply type is the union of `ToolCalls`, `FinalText` and `Refusal` (alias `RecordedReply`). Plan 02's `ModelReply` types are used as they are. `ModelStep` and `ModelReview` are not used. A mixed reply is stored as `ToolCalls` with its text.
  Rationale: plan 02 names the reply types, and a provider failure is never stored, so the type excludes it. Replay returns the stored reply, so the loop ends the booking the same way as the recorded run. Test: `test_mixed_reply_record_and_replay_match`.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: each call's raw argument text is stored as a JSON string and digested as sent. The file's call object is `{name, arguments}` with `arguments` a string.
  Rationale: a malformed argument has no object form, and the model's text is what the next turn's digest covers. Test: `test_malformed_arguments_replay_matches`, and the round-trip test in Milestone 3.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the file's per-turn key for the reply is `reply` (in place of `step`), with the kinds `tool_calls`, `final` and `refusal`.
  Rationale: the name matches plan 02's reply type. The file is not built yet, so the rename costs nothing.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: replay and recording use one canonical serializer, `canonical_json`. Money is normalized to two places, and a value with three places is refused, in the money projection only. `canonical_json` writes each `Decimal` as given, as a quoted fixed-point string.
  Rationale: normalization is a domain step (money has two places), so it belongs with the money projection. The serializer stays a plain writer. Tests: `test_decimal_80_00_is_written_fixed_point`, `test_money_is_normalized_to_two_places`, `test_money_with_three_places_is_refused`.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the rates projection takes the rate entries that composition reads once with plan 01's rate reader. Composition passes the same tuple to the rate adapter and to the projection. The `ExchangeRates` port keeps its shape, and the in-memory fake is unchanged.
  Rationale: the reader already holds every entry. A list method would change plan 01's port and its fake for one digest.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the header has six digests, `pnrs`, `fares_feed`, `policy`, `rates`, `prompt` and `tools`. The single snapshot digest and its wording are removed. `pnrs` covers the valid bookings and the rejected references. `fares_feed` covers the valid offers and the capture time. Data issues are not digested.
  Rationale: a stale error names the input that changed. A record that moves from valid to rejected changes which bookings reach the model, so its reference is digested. Reason text does not affect the model, so it is not digested.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the stale-recording error, and the stopped and missing messages, use the labels `error:`, `reason:` and `fix:`. The index's S3 text ("what:", "why:", and the short fix) is replaced by these lines.
  Rationale: plan 01 prints `SetupError` as these three labeled lines, so every error in the CLI reads the same way.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the fix command of every re-record message is built by `re_record_command(data_set)` and always names `--extra live` and `--data <set>`. The missing-recording fix names `--data <set> --model none`. Tests assert the exact string for each data set.
  Rationale: the owner copies one command for the data set that failed. Naming `--extra live` makes the command run from a clean checkout.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the trace of a replayed booking has the recorded variant (L11) with keys `recorded_model` and `recorded_usage`, and no `usage` key.
  Rationale: the index's S3 names both fields, and D24 names the model. The usage form follows S3. Plan 02's trace is unchanged for live modes.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the `StaleRecording` exception carries `StaleReason` values (header change, digest mismatch, missing turn, leftover turn). A stale recording is a setup failure with exit 3.
  Rationale: the CLI and the tests match on types, not on message text. The Python rules keep setup failures as exceptions, and D15 gives this one its own code.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: `AgentModel` exposes `model_name`. `record_review` takes `(source, recording_path, model)` and drops the environment parameter. The model name is read by plan 02's model factory from `OPENAI_MODEL`, with no fallback.
  Rationale: the recording needs the name once, from the model that made the calls. Only the model factory reads the environment, so the replay and the doctor read no key and no model name.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the cost check uses the prices of plan 02's "Milestone 1 result" entry, copied into this Decision Log at Milestone 7. This plan names no model and no price in its own text. The `gpt-5.4-mini` default and its prices are removed.
  Rationale: the owner's model is `OPENAI_MODEL`, with no code default (plan 02 P17). The prices must come from the model the owner runs. The index's A3 text is updated in the index change list.
  Date/Author: 2026-11-02, plan writer (round 3), owner answers.

- Decision: each committed run's call count, tokens and cost are recorded here: `model calls in the sample run: <N>` at Milestone 7 and `model calls in the scenario run: <N>` at Milestone 10. The owner attests that each run was live, with the date.
  Rationale: the DoD checks are consistency checks on the file. They cannot prove that a model made the calls, so the owner's attestation in this log is the record of that.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the trace of a replayed booking uses the recorded variant (L11). The recording-time usage and model name appear in place of the live fields.
  Rationale: see the trace decision above.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the file has `schema_version` 1 and the key names of L5. The header and the turns are sorted, and the file is UTF-8 with an indent of 2 and one final newline.
  Rationale: D9 says consumers break silently without a version. Sorting keeps the file deterministic.
  Date/Author: 2026-11-02, plan writer.

- Decision: the default switches to `recorded` only in Milestone 8, after Milestone 7 commits the sample file. The doctor's `check_recording` and its test may land earlier.
  Rationale: a default that replays a missing file breaks every default run.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the header check runs before the first turn. The leftover check runs after the review returns.
  Rationale: header problems are known before any call. Leftover turns are known only at the end.
  Date/Author: 2026-11-02, plan writer.

- Decision: the plan adds `tests/test_recording.py`. The no-exact-count rule of plan 01 is gone, so the file is a plain new test file, with no deviation to name.
  Rationale: the recording tests cover the recording, the replay and the doctor, and a separate file keeps them apart from the rules and CLI tests.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the no-key, no-network claim for replay is checked by running the committed tests with `HTTPS_PROXY` and `HTTP_PROXY` pointing at a dead port and no `OPENAI_API_KEY`.
  Rationale: a test cannot prove that no socket is opened, but a dead proxy makes any attempted request fail, and no key is set.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the no-secrets test asserts on the printing path (the `cli/` functions that print the report and the path), not only on the function's return value.
  Rationale: the printing is where a secret would reach the output.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the tests that run the CLI without `--model` get an explicit `--model none` in Milestone 8, and each one is listed in Surprises & Discoveries.
  Rationale: the default changes in Milestone 8, and the rules-only tests must keep their meaning.
  Date/Author: 2026-11-02, plan writer.

- Decision: the stopped run's stderr names the booking and the closed code, and gives one fix, the re-record command for the data set.
  Rationale: D24 allows only the closed code, and the owner needs the booking to find the cause.
  Date/Author: 2026-11-02, plan writer (round 2).

- Decision: a provider failure during a recording run is a `ProviderFailed` value. The wrapper keeps the first one, makes no further inner call, and reports `RecordingStopped`. There is no `RecordingAborted` exception.
  Rationale: D16 keeps provider failures as values, and the typed outcome keeps the stop visible to composition.
  Date/Author: 2026-11-02, plan writer (round 2).

- Decision: the recording file is written after a complete run, through the atomic writer. The path is printed on stderr, and stdout keeps only the JSON result (D9).
  Rationale: a shell pipe that reads stdout must still get valid JSON.
  Date/Author: 2026-11-02, plan writer.

- Decision: the recording path is fixed per data set and has no flag (L8).
  Rationale: one path per data set keeps the default run, the doctor and the committed files in agreement, and D15 keeps flags few.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: the live file checks are consistency checks. The DoD checks that the model field equals `OPENAI_MODEL`, that every turn has input tokens above zero, and that no string outside the fixture facts and the vocabulary appears. They do not prove that a live run made the file; the owner's attestation does (see the attestation decision above).
  Rationale: a script can show that a file is consistent with the run's settings, and it cannot show where the bytes came from.
  Date/Author: 2026-11-02, plan writer (round 3).

- Decision: if the owner's key never arrives, the plan stops at Milestone 7, builds the no-key parts first, and does not commit a fake recording.
  Rationale: a fake file in `recordings/` would make the default replay an answer no real model gave.
  Date/Author: 2026-11-02, plan writer.

- Decision: the reader and the writer use the storage format of L5, and their result is a domain value. The reader does not return plan 02 types that carry provider ids, because the file never holds them.
  Rationale: the file and the domain value must agree on the same reply types, and provider ids are not part of the reply types of plan 02.
  Date/Author: 2026-11-02, plan writer (round 3).

## Outcomes & Retrospective

Not started. Written at completion.

## Definition of done

Each item below is a behavior check or a consistency check with an exact command and expected output. Every command runs from the repo root.

- [ ] All 42 named tests exist: `uv run --all-extras pytest --collect-only -q tests/test_recording.py | grep -cE '::(test_canonical_json_refuses_floats|test_canonical_json_ignores_key_order|test_decimal_80_00_is_written_fixed_point|test_money_is_normalized_to_two_places|test_money_with_three_places_is_refused|test_money_digit_change_changes_digest|test_digest_survives_field_rename|test_transcript_digest_covers_domain_transcript|test_recording_keeps_every_turn|test_recording_stops_at_first_provider_failure|test_mixed_reply_is_stored_with_its_text|test_recording_schema_round_trip|test_atomic_write_leaves_no_temp_file|test_recording_creates_missing_folder|test_recording_written_after_turn_cap|test_failed_recording_keeps_old_file|test_recording_has_no_secrets|test_record_flag_needs_openai_exits_2|test_changed_fixture_is_stale|test_stale_header_names_changed_input|test_unknown_schema_version_is_read_error|test_missing_file_is_read_error|test_unreadable_file_is_read_error|test_replay_reproduces_turn_cap_booking|test_replay_trace_shows_recorded_model|test_changed_turn_is_stale|test_missing_turn_is_stale|test_mixed_reply_record_and_replay_match|test_malformed_arguments_replay_matches|test_stale_recording_passes_through_the_loop|test_leftover_turn_is_stale|test_missing_recording_exits_2|test_missing_scenario_recording_names_its_path|test_unreadable_recording_exits_2|test_stale_recording_exits_3|test_re_record_command_per_data_set|test_committed_recording_matches_data|test_committed_recording_replays|test_committed_prompt_and_recording_are_lf|test_doctor_fails_when_recording_stale|test_scenario_replay_has_six_results|test_doctor_fails_when_scenario_recording_stale)(\[[a-z]+\])?$'` prints `42`.
- [ ] The file's tests pass offline and without a key: `env -u OPENAI_API_KEY HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 uv run --all-extras pytest -q tests/test_recording.py; echo $?` ends with `0`.
- [ ] The checks are green: `./scripts/check.sh; echo $?` ends with `0`.
- [ ] The record gate: `uv run fare-reshop review --model none --record >/dev/null 2>&1; echo $?` prints `2`, and `uv run fare-reshop review --model none --record 2>&1 >/dev/null | grep -c "record needs --model openai"` prints `1`.
- [ ] Both committed recordings exist: `test -f recordings/review-run.json && test -f recordings/scenarios-run.json; echo $?` prints `0`.
- [ ] LF line endings: `git check-attr eol -- fare_reshop_agent/reshopping/orchestration/review_prompt.md recordings/review-run.json recordings/scenarios-run.json | grep -c "eol: lf"` prints `3`.
- [ ] No secret-shaped text in the files: `cat recordings/review-run.json recordings/scenarios-run.json | grep -ciE 'authorization|request-id|api[_-]?key|(^|[^a-z])sk-'` prints `0`.
- [ ] Model field matches the configured model, for both files (consistency check): `uv run python -c "import json; from pathlib import Path; env=dict(l.split('=',1) for l in Path('.env.local').read_text(encoding='utf-8').splitlines() if l.startswith('OPENAI_MODEL=')); print(all(json.loads(Path(p).read_text(encoding='utf-8'))['model']==env['OPENAI_MODEL'] for p in ('recordings/review-run.json','recordings/scenarios-run.json')))"` prints `True`.
- [ ] Every turn has input tokens, for both files (consistency check): `uv run python -c "import json; from pathlib import Path; print(all(t['usage']['input_tokens'] > 0 for p in ('recordings/review-run.json','recordings/scenarios-run.json') for t in json.loads(Path(p).read_text(encoding='utf-8'))['turns']))"` prints `True`.
- [ ] No string outside the fixture facts and the vocabulary (consistency check, both files): the script below prints `0`. Strings under the keys `text` and `arguments` are the model's own words and are checked by eye at Milestones 7 and 10.

  ```
  uv run python - <<'EOF'
  import json
  from pathlib import Path

  def strings(value, key=""):
      if isinstance(value, str):
          yield key, value
      elif isinstance(value, list):
          for item in value:
              yield from strings(item, key)
      elif isinstance(value, dict):
          for k, v in value.items():
              yield from strings(v, k)

  def load(name):
      return json.loads(Path(name).read_text(encoding="utf-8"))

  pairs = {
      "recordings/review-run.json": ("fixtures/pnrs.json", "fixtures/fares_feed.json"),
      "recordings/scenarios-run.json": ("fixtures/scenarios/pnrs.json", "fixtures/scenarios/fares_feed.json"),
  }
  unexpected = 0
  for rec_path, sources in pairs.items():
      recording = load(rec_path)
      facts = {s for src in sources for _, s in strings(load(src))}
      vocabulary = {"tool_calls", "final", "refusal", "get_booking", "search_offers", "check_offer", recording["model"]}
      for key, s in strings(recording):
          is_digest = len(s) == 64 and all(c in "0123456789abcdef" for c in s)
          if key in ("text", "arguments") or s in facts or s in vocabulary or is_digest:
              continue
          unexpected += 1
  print(unexpected)
  EOF
  ```

- [ ] Cost under 1 USD, for both files (consistency check against the price line of this Decision Log): `uv run python -c "import re; from decimal import Decimal; from pathlib import Path; import json; plan=Path('.agents/plans/reshop-review/03-record-and-replay-model-runs.md').read_text(encoding='utf-8'); m=re.search(r'Prices used for the cost check: input ([0-9.]+) USD and output ([0-9.]+) USD per 1M tokens\.', plan); p_in, p_out = Decimal(m[1]), Decimal(m[2]); print(all(sum(Decimal(t['usage']['input_tokens'])*p_in + Decimal(t['usage']['output_tokens'])*p_out for t in json.loads(Path(p).read_text(encoding='utf-8'))['turns'])/Decimal(1000000) < 1 for p in ('recordings/review-run.json','recordings/scenarios-run.json')))"` prints `True`.
- [ ] Call counts are recorded for both runs: `N=$(uv run python -c "import json; from pathlib import Path; print(len(json.loads(Path('recordings/review-run.json').read_text(encoding='utf-8'))['turns']))"); grep -c "model calls in the sample run: $N$" .agents/plans/reshop-review/03-record-and-replay-model-runs.md` prints `1`, and the same with `scenarios-run.json` and `model calls in the scenario run:` prints `1`.
- [ ] Offline replay of the sample data: `env -u OPENAI_API_KEY uv run fare-reshop review | uv run python -c "import json,sys; d=json.load(sys.stdin); print(d['mode'], len(d['results']))"` prints `recorded 5`.
- [ ] Offline replay of the scenario data: `env -u OPENAI_API_KEY uv run fare-reshop review --data scenarios | uv run python -c "import json,sys; d=json.load(sys.stdin); print(d['mode'], len(d['results']))"` prints `recorded 6`.
- [ ] Replay exits 0 with a dead proxy, for both data sets: `HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 env -u OPENAI_API_KEY uv run fare-reshop review > /dev/null; echo $?` prints `0`, and the same with `--data scenarios` prints `0`.
- [ ] The doctor shows both recording lines as ok and exits 0: `env -u OPENAI_API_KEY uv run fare-reshop doctor | grep -cE '\[ok\].*recording'` prints `2`, and `env -u OPENAI_API_KEY uv run fare-reshop doctor > /dev/null; echo $?` prints `0`.
- [ ] No review call in the tests lacks `--model`: `grep -rnE '"review"' tests | grep -v -- '--model'; echo $?` prints `1`.
- [ ] No model default in code: `grep -rnE 'gpt-[0-9]' fare_reshop_agent; echo $?` prints `1`.
- [ ] The runbook carries the re-record command for each data set: `grep -cF "uv run --env-file .env.local --extra live fare-reshop review --data sample --model openai --record" docs/runbooks/re-record.md` prints `1`, and the same with `--data scenarios` prints `1`.
- [ ] The runbook has its sections and its owner rule: `grep -cE '^## (When to re-record|Steps|Cost)$' docs/runbooks/re-record.md` prints `3`, and `grep -c 'only the owner' docs/runbooks/re-record.md` prints `1`.
- [ ] The glossary has the two terms: `grep -cE '^### (Recording|Stale recording)$' GLOSSARY.md` prints `2`.
- [ ] ADR 0004 has its five sections: `grep -cE '^## (Status|Context|Decision|Consequences|Alternatives)$' docs/adr/0004-recorded-replay-default.md` prints `5`.
- [ ] The earlier ADRs exist: `ls docs/adr/0001-*.md docs/adr/0002-*.md docs/adr/0003-*.md | wc -l` prints `3`.
- [ ] No plan link in durable docs: `grep -c '.agents/plans' docs/adr/0004-recorded-replay-default.md docs/runbooks/re-record.md` prints the two files with `0` each.
- [ ] The plan passes the format check: `/Users/igby/.claude/skills/exec-plan/scripts/check-plan-format .agents/plans/reshop-review/03-record-and-replay-model-runs.md; echo $?` ends with `0`.
- [ ] No leaks: `grep -niF -f .private/denylist.txt .agents/plans/reshop-review/03-record-and-replay-model-runs.md; echo $?` prints `1`, and `git grep --untracked -i -F -f .private/denylist.txt; echo $?` prints `1`.

## Revision notes

2026-11-02: First draft from the feature index (stories S3 and S4, decisions D15, D22, D23, D26 to D28 and D31, assumptions A3 and A5), written before critic round 1.

2026-11-02, second revision after critic round 1. Stored tool calls carried a `call_id`, assigned by orchestration as `call_<turn>_<n>`. The recording keyed turns by booking. The header got one digest per input. One canonical serializer owned by `orchestration/` served the tool results, the digests and the file writer. The prompt is read as bytes, with `.gitattributes` pinning LF. A default-suite test checks the committed header. A recording run stops at the first provider failure. The no-secrets test sets a sentinel key.

2026-11-02, round 2 revision after the critic round 2 review. The plan uses `review_with_model` with the recording wrapper as its model. A mixed reply is stored with its text and replayed. A provider failure stays a value. The recorded adapter is a pure lookup, and the leftover check runs in composition. Projections are explicit per digested value, and money has two places. Turn numbers are integers on the transcript. The file schema lives in `infrastructure/json_files/`.

2026-11-02, round 3 revision (final pass), with the findings of the round 3 review applied. Reply types follow plan 02's names; `ModelStep` and `ModelReview` are removed, and a mixed reply is stored as `ToolCalls` with text. Each call's raw argument text is stored and digested as sent, with a malformed-arguments round-trip test. The default suite replays each committed recording with no key and no network, and fails on any stale or leftover turn; the header test stays. Every re-record and fix command comes from `re_record_command(data_set)` and names `--extra live` and `--data <set>`. Projections are defined for pnrs, fares_feed, rates, policy, tools and transcript, and the single snapshot digest is removed. Money normalization and refusal live in the money projection, not in `canonical_json`. The rename test calls the projection and compares to a pinned literal. Proofs name tests by node id, and the DoD lists all 44 names. The OpenAI model comes from `OPENAI_MODEL` with no fallback, and the cost check reads the prices copied from plan 02's Milestone 1 result. Each run's call count is recorded in the Decision Log. The doctor count is 2 in the DoD. Tests use `uv run --all-extras`. The reply key is `reply`, the error labels are `error:`, `reason:` and `fix:`, and the trace variant is `recorded_model` with `recorded_usage`. `AgentModel.model_name` is a requirement on plan 02, and `record_review` takes the model without the environment. The no-review grep searches the working tree. The provenance checks are consistency checks, and the owner attests the live runs in the Decision Log. The plan is slimmed: the DoD keeps behavior and consistency checks, and duplicate items are removed.
