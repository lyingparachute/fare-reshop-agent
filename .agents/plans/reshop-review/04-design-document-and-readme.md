# Design document and README

Status: blocked - needs the owner's two recordings (Record and replay model runs) and the Q2 answer for the AI-usage section

This ExecPlan is a living document. Progress, Surprises & Discoveries, Decision Log and Outcomes & Retrospective are kept current as work proceeds. Repo plan rules: none. Starts after: Record and replay model runs.

The rules-only review, titled "Rules-only review", is built and on main. Its plan file is retired. The code, `GLOSSARY.md`, `docs/adr/0001-value-objects-and-deferred-review-aggregate.md` and the planning index now hold what it decided. "Agent review with a live model" and "Record and replay model runs" have not landed yet. This plan writes the docs so they describe what exists after all three land. Every claim in the docs is checked against the code at writing time. A claim the code does not support is cut, not softened.

## Progress

- [x] (2026-11-02) Owner answers applied: the demo rate is dated 2026-07-07, and the local check script `./scripts/check.sh` is named in the README and the Built section.
- [x] (2026-11-02) Round 3 revision applied: status, cost script, limits order, measure labels, DoD and README changes. See the revision notes.
- [ ] Milestone 1: the earlier plans are in the tree, the two recordings exist, the sample runs match, the cost script runs, and the recorded prices and statuses are captured.
- [ ] Milestone 2: DESIGN.md has its intro and the architecture, path, trust and money sections.
- [ ] Milestone 3: DESIGN.md has the output, scale and cost, data, and assumptions sections.
- [ ] Milestone 4: DESIGN.md has the not-built and AI-usage sections, the test claims in the evidence section, and the links section. Blocked on the owner's Q2 answer.
- [ ] Milestone 5: README.md is rewritten and the outdated lines are gone.
- [ ] Milestone 6: docs/future-work.md matches the code, has the new rows, AGENTS.md passes its checks, and the linked docs exist.
- [ ] Milestone 7: `## Evidence and limits` exists with the documented limits and the built scenario sentence. Independent of Q2.
- [ ] Content review (see its section) reports no FAIL.

Updated at every stopping point. This list, not memory, says where the work is.

## Background / why now

The project is a side project by its author. It checks booked flights against fares on sale and gives one recommendation per booking: rebook or keep, the offer, the nominal saving and why. Two docs are missing or wrong: `README.md` is a stub, and `DESIGN.md` does not exist yet.

After this plan, a reader can open `README.md` and run the tool. After the first `uv sync`, the default run needs no key and no network. The reader can then open `DESIGN.md` and judge the approach without reading the code. The reader sees where the model is trusted and where it is not, how money is checked, what the tests and the recorded run prove and do not prove, and what was left out.

Without this plan, the only record of the design is the planning index, which is a working file. The current README also states two rules that the later plans change: that the model only explains a choice, and that a schedule change rejects an offer. Both are wrong once the agent plan lands.

## User stories

1. As an engineer judging the approach, I want a design document that says where the model is trusted and where it is not, so that I can judge the design without reading all the code.

This is story S6 from the planning index. Step 2 is extended here to name the evidence and limits section.

S6 - Understand the design

As an engineer judging the approach, I want a design document that says where the model is trusted and where it is not, so that I can judge the design without reading all the code.

Walkthrough:

1. The reader opens `README.md`: what it does, how to run each mode, sample output.
2. The reader opens `DESIGN.md`: architecture, the model boundary, money safety, the output contract, scale and cost, data handling, assumptions and open questions, what was left out, the AI-usage note, the evidence and limits, and links to the other docs.
3. `GLOSSARY.md` and `docs/adr/` hold the terms and the hard-to-reverse decisions.

## Scope and non-goals

In scope: `DESIGN.md` (story S6, step 2), with the twelve `##` sections named in the milestones. The `README.md` rewrite (story S6, step 1). A consistency edit to `docs/future-work.md`, including two new rows. A read-only check of `AGENTS.md`. A check that `GLOSSARY.md`, `docs/adr/` and `docs/runbooks/re-record.md` exist and are linked (story S6, step 3). One new script, `scripts/cost.py`, with one test in `tests/test_recording.py`; this plan owns both. The rules-only review wrote `GLOSSARY.md` and `docs/adr/0001-value-objects-and-deferred-review-aggregate.md`, and this plan changes neither. The plan "Record and replay model runs" writes `docs/runbooks/re-record.md`. Later plans add their own glossary terms and ADRs. This plan does not write them.

Non-goals: no change to the product code, no fixture changes, and no edit to `AGENTS.md`. No glossary terms and no ADRs written here. No docs site, no docs generator, and no diagram other than the one Mermaid diagram in `DESIGN.md`. No tier line, because the repo has no paid tiers. No employer, client, outside process or outside schedule is named. No vendor or data source is named for the demo exchange rate. No doc claims that a result carries a model version. Vendor names (OpenAI for the model, Anthropic for Claude Code) appear only where the model or the tool is named. `DESIGN.md` holds no run commands.

## Context and orientation

The repo is `/Users/igby/Work/personal/fare-reshop-agent`. The Python package `fare_reshop_agent/` is on main with the rules-only review built. Its `fare-reshop` command has the `review` and `doctor` subcommands. `fixtures/pnrs.json` holds 5 booked trips under the key `pnrs`. Each booking has a `pnr`, `passengers`, `itinerary` and `ticket`. Prices are per passenger, and `totalPaid` covers all passengers. `fixtures/fares_feed.json` holds 6 offers under the key `offers` and a `capturedAt` of `2026-07-08T09:00:00Z`. `README.md` is the old stub. `AGENTS.md` is the rules file for agents. `docs/future-work.md` lists later items in tables with a Tier column. `.agents/plans/reshop-review/00-INDEX.md` is the planning index. It is the source for the decisions, stories and assumptions in this plan. The public docs never link to it.

Terms. The docs use the terms defined in `GLOSSARY.md`, which is on main and which later plans extend. `DESIGN.md` and `README.md` link to that file and do not define the terms again. If a term the docs need is missing from it, the implementer records the gap in Surprises & Discoveries and does not define the term in the docs. For the writer's own reference, the meanings are these. A booking is one ticketed trip with its booking reference (the `pnr` field). An offer is a fare on sale for the same route and date. A rule check gives PASS or FAIL with a reason. An eligible offer passes every rule check and meets the minimum saving. An approval flag warns on a result, such as a schedule change, without failing the offer. The nominal saving is the saving on paper, before any residual value of the old ticket. It is not a realized saving. The minimum saving is 50 USD, or the same amount converted to the booking's currency. The exchange rate comes from the `ExchangeRates` port, which is a rate source behind an interface. A recommendation is the result for one booking. A tool is a function the model may call. A transcript is the complete input of one model turn for one booking. A turn is one model step, a tool call or a final answer. The safety check re-runs the rules and the money math on the model's choice after the model answers. A recording is the file of model turns from one live run. A stale recording no longer matches the data, the policy, the rates, the prompt or the tools.

Expected results on the sample data. This is the acceptance table from the planning index. It applies to `--model none` only. The recorded default run must agree with the safety rules, which Milestone 1 checks.

| Booking | Offers | Result in `none` mode | Why |
|---|---|---|---|
| QX7T2A | OF-1001 | `REBOOK` OF-1001, saving 80.00 USD | Same flight, same conditions: 1 x (480 - 300 - 100) |
| LM9P4C | OF-2001 | `KEEP` | Fails cabin and bags; saving 2 x (350 - 320 - 75) = -90.00 USD |
| RT5K8B | OF-3001 | `REBOOK` OF-3001, saving 363.21 EUR | 2,100 USD = 1,836.79 EUR; 2,200 - 1,836.79 - 0; future fee 0 USD = 0 EUR passes; 363.21 is above 43.73 |
| ZC3N1D | OF-4001 | `KEEP` | Fails refundability; the 140.00 USD saving is shown but cannot qualify |
| HB6W9E | OF-5001, OF-5002 | `KEEP` | OF-5001 saves -90.00 USD; OF-5002 fails cabin, bags and stops and saves -40.00 USD |

Two of the five bookings (QX7T2A and RT5K8B) have an eligible offer. Only those two reach the model in model modes. Code settles the other three.

The demo exchange rate is a fixed demo rate: 1 EUR = 1.1433 USD, dated 2026-07-07, the fare snapshot's capture date. The docs say that and nothing more about its source. The minimum saving is 50.00 USD, or 43.73 EUR for a euro booking.

The cost script. `scripts/cost.py` is a small Python script this plan writes in Milestone 1. It reads the committed recording and the fixture file, and it prints the token totals and the cost. Its usage is `uv run python -I scripts/cost.py [RECORDING [FIXTURES]]`, with the defaults `recordings/review-run.json` and `fixtures/pnrs.json`, run from the repo root. It takes the two prices from the environment variables `IN_USD_PER_MTOK` and `OUT_USD_PER_MTOK`, in US dollars per 1 million tokens, read as text into `Decimal`. The prices are never written into the script. The recording holds `model` (the model name as text) and `turns`. Each turn holds `booking` and `usage` with `input_tokens` and `output_tokens`. The script sums both token counts over every turn. The cost is (input tokens x input price + output tokens x output price) / 1,000,000. The model bookings are the distinct booking references in the turns. The fixture bookings are the entries under `pnrs`. Bookings settled by code have no turns, so they add nothing. The script prints one line, with these keys in this order and with the cost keys at six decimal places: `model=<name> input_tokens=<n> output_tokens=<n> total_usd=<cost> model_bookings=<n> code_settled_bookings=<n> per_model_booking_usd=<cost> fixture_bookings=<n> per_fixture_booking_usd=<cost>`. The per-model-booking figure is the total divided by the model bookings. The per-fixture-booking figure is the total divided by the fixture bookings. The script uses only the standard library and follows `.claude/rules/python.md`.

Milestone 1 writes the prices into `/tmp/prices.env`, outside the repo, from the model price record in Surprises & Discoveries (copied from plan 02 before it was retired). Milestone 3 checks them against the provider's price page and records the check. The DoD runs the script with `. /tmp/prices.env` first.

## Fact ownership

Each fact has one owner doc, and every other doc links to it instead of repeating it. Terms belong to `GLOSSARY.md`. Hard-to-reverse decisions belong to the records in `docs/adr/`. Run steps, commands, the doctor checks and sample output belong to `README.md`. Design reasoning, figures, assumptions and the AI-usage note belong to `DESIGN.md`. Planned and unbuilt work belongs to `docs/future-work.md`. The README keeps a short user-facing list of what counts as worth a rebooking. `DESIGN.md` links to that list and does not copy it. The cost figures come from `scripts/cost.py`, and `DESIGN.md` cites its output without a command.

## Measure labels

`DESIGN.md` tags each built measure or behavior `[built]`, and each planned item that has a row in `docs/future-work.md` `[future work]`. The tag sits at the end of the sentence or bullet, just before its full stop, for example "The check runs on each call [built]." A limit that no row covers is a plain statement with no tag. The Evidence section keeps those plain limits under its own `### Limits with no planned work` heading, so a check can tell them apart. The README describes built behavior only and uses no tags.

## Locked decisions

Carried decisions are copied from the planning index. The index is the single source of decisions, so a copy that differs from it is a defect. D34 and D35 are condensed here; the operative clauses are kept word for word, and the index holds the full text.

D19 (carried for the README and the AGENTS.md check): The model picks an eligible offer or says keep, and writes the rationale. This changes the text in `AGENTS.md` and `README.md`, which today say the model only explains; the agent plan updates `AGENTS.md` and the docs plan updates `README.md`; the docs plan only checks `AGENTS.md`. The safety check re-runs the rules and the money math for the chosen offer. A failing choice becomes `NEEDS_REVIEW` with the reason. Keep while an eligible offer exists becomes `NEEDS_REVIEW` with both the rules' view and the model's rationale. A valid choice that is not the highest saving is accepted, and `best_offer_id` names the highest one. The docs plan also fixes the README line that says a schedule change rejects an offer (D3 makes it an approval flag). (Owner)

Options that lost: Trust the model's numbers: the core failure mode. Force the highest saving: overrides the trade-offs the model was asked to weigh. Let a model keep stand as `KEEP`: a missed saving would pass unseen.

What this plan does with D19: the README states the model's role as D19 gives it, and states that a schedule change is an approval flag, not a rejection. `DESIGN.md` explains the four outcomes. This plan checks `AGENTS.md` and edits it not at all.

D26: Docs: `README.md`, `DESIGN.md` with the AI-usage note, `GLOSSARY.md`, `docs/adr/` and `docs/future-work.md`. Each plan writes its own glossary terms and ADRs in its last milestone. The docs plan writes the rest. (Owner)

Options that lost: One long README: mixes setup with design.

D27: Scope is the thin slice. Not built: a model-based prefilter, token and cost budgets, and a fixed six-tool set. `DESIGN.md` says why. (Owner)

Options that lost: Build them: too large for the time, and each was argued down in the grilling.

The docs give their own reasons for what was not built, in their own words, and do not quote the index reason.

D28: Plans are tracked in the public repo. Every tracked file, commit message and branch name passes the local leak hooks. (Owner)

Options that lost: Keep plans private: loses the record of how the work was done.

D30: Only the configured data sets are read: `sample` and `scenarios` (D34). In model modes, booking and offer facts leave the machine in tool results sent to OpenAI, and the same facts are stored in the committed recording. The fixtures hold no names or contact data (Assumption 5), so nothing is masked. `DESIGN.md` states this and lists masking as needed before real data.

Options that lost: Mask PNRs now: the data is synthetic and masking breaks the digest's link to the source.

D34 (condensed): A second configured data set, `scenarios`, in `fixtures/scenarios/pnrs.json` and `fixtures/scenarios/fares_feed.json`: the same schema as the real fixtures, made-up demo bookings and offers, a top-level `_comment` that says they are made-up demo scenarios, the same capture time (2026-07-08T09:00:00Z), departures after it and USD throughout. The CLI takes `--data sample|scenarios`, default `sample`. The value names a configured data set and never a free path; an unknown value is an argparse error with exit code 2 and the three-line error format. (Owner)

Options that lost: A free path to any file: a run could read data nobody reviewed, and the recording would not know which data it covers. One combined data file: it would change the sample oracle. Scenarios inside the real fixtures: they are the owner's sample data and never change.

D35 (condensed): `DESIGN.md` has a section "Evidence and limits" that lists the documented limits, each tagged `[future work]`, with a matching row in `docs/future-work.md` where one exists: seat contention (bookings are checked alone, so two bookings can both be told to take the last seats; scenario d shows it); naive local clock times compared with the capture time in UTC; summer and winter time changes; the fixed demo rate (dated 2026-07-07, not a live or binding quote); and the nominal saving, which is not a realized saving. (Owner)

Options that lost: Leave the limits out: a reader finds them anyway and trusts the tool less. Fix seat contention now with a shared inventory: the data has no inventory, so the seam would be hypothetical.

Locks specific to this plan:

Voice. The docs use first person singular, as the project's author. They are written in plain English for readers who use English as a second language: short sentences, common words, one idea per sentence, active voice. They have no filler, no praise, no em dash character, and straight quotes only. Headings use sentence case.

Personal project. The docs never name an employer, client, outside process, or outside schedule. The denylist scan in the Definition of done enforces this.

Sample output source. The README sample output comes from the recorded runs, not from typing. The statuses come from the recorded default run that Milestone 1 captures.

Cost source. Cost figures come from the token usage stored in the committed recording, through `scripts/cost.py`. They are never typed in by hand and never estimated. The owner dropped token and cost budgets (D18, D27), but the recording keeps usage for each turn (D22), so the usage is there to read. If the owner later drops the stored usage, the cost figure becomes a labeled estimate with its formula and assumed token counts, and this decision is revisited. The prices come from plan 02 (D21).

Demo rate. The docs say "a fixed demo rate, dated 2026-07-07". They name no vendor, data source or reference rate for it.

Model version. No doc says that a result carries a model version. The model version is future work only, listed in `docs/future-work.md`.

The docs describe the code as built. Planned behavior carries the `[future work]` tag, and the docs never describe it as present.

## Alternatives considered

One long README with the design in it was rejected by D26: setup and design are different readers' needs.

A design section inside `AGENTS.md` was rejected. `AGENTS.md` is the rules file for agents, and a human reader of the design should not have to read agent rules.

Writing the docs before the code was rejected. The docs would describe planned behavior, and every number in them would be a guess.

A hand-written sample output was rejected. A hand-made sample can drift from the tool. The sample comes from a run, and the DoD diffs it against captured output.

Copying the prices into this plan as fixed figures was rejected. The model's prices belong to the agent plan. A copy here would be a second source that can drift.

Running the cost arithmetic in a one-line command inside `DESIGN.md` was rejected. The command was untested and sat in the design doc. A tested script in `scripts/` holds the arithmetic, and the doc cites its output.

## Invariants, risks and open questions

Invariants that hold while this plan runs. This plan edits only `README.md`, `DESIGN.md`, `docs/future-work.md`, and the new `scripts/cost.py` with its test. It checks `AGENTS.md` and does not edit it (D6, D19). Every number in the docs has a source: the planning index, a run of the tool, a file in the repo, or `scripts/cost.py`, and the milestone that writes the number names the source. No two numbers in the docs contradict each other. The docs contain no planning-index identifiers such as D7 or S6, and no link into the planning folder. The cost figures match the committed recording as it stands at writing time. If the recording is re-recorded, the cost figures are measured again before the docs are final.

Risks and their mitigation. An earlier plan did not land, or landed differently. Milestone 1 checks each command. If one fails, the implementer stops, records the failure in Surprises & Discoveries, and writes no docs about a feature that does not run. A sample run changes after a fixture or policy edit. The README sample is regenerated in Milestone 5, after all code is final, and the Milestone 1 captures are rechecked then. A doc claim is not supported by the code. The claim is cut, not softened. Retry safety: every milestone writes whole files, so a repeat run replaces each file with the same content, and a failed milestone is safe to run again from its first step.

Open business questions. The docs state these as open and pick no answer. What is the recoverable value of the old ticket: cash, credit, or nothing? Today the saving is nominal only (future work: residual value of the old ticket). What schedule change is acceptable without approval? Today any time change needs approval (future work: schedule tolerance window). When would automatic action be allowed? Today nothing books automatically (future work: auto-rebook for a narrow safe class, after shadow mode).

Assumptions the docs state. The Assumptions section of `DESIGN.md` lists each of these with what changes if it is wrong, under the labels "Assumption 1" to "Assumption 6". Assumption 1: the minimum saving is 50 USD, converted to the booking's currency, which is 43.73 EUR at the demo rate. The owner confirmed it. Assumption 2: the demo rate is a fixed demo rate of 1 EUR = 1.1433 USD, dated 2026-07-07, the last rate published before the fare snapshot was captured on 2026-07-08. It is not a live quote. Assumption 3: the owner's key is in `.env.local` before the recording milestone, and one recording costs under 1 USD at the prices of the recorded model. The owner confirmed the under-1-USD figure at the earlier model's prices. Milestone 1 rechecks it at the recorded model's prices, through the cost output. Assumption 4: the repo does not assume uv. `./start.sh` finds it missing and asks before it installs it. Readers use macOS or Linux, and Windows is not tested. Assumption 5: the PNRs and fares in the fixtures are made up and hold no names or contact data. The owner confirmed it. Assumption 6: a booking's change fee is in the same currency as its ticket price, as in all five fixtures. If that is not true, the fee is converted too. The owner confirmed it.

Price source. The prices come from plan 02, which recorded them (D21) before it was retired; the model price record in Surprises & Discoveries holds the copy, and Milestone 1 copies them into `/tmp/prices.env`. Milestone 3 compares them with the current OpenAI pricing page at writing time and records the URL, the prices and the check date in the Decision Log. If the page differs, the implementer stops and asks the owner which prices to use, because the price is a cost decision that belongs to the owner. Nothing is written with the new prices until the owner answers.

Model name. The owner confirmed `gpt-6-luna` in `.env.example` (Q1, 2026-11-02). The docs still cite the name the recording stores, because the owner's `.env.local` may set another value for the recorded run.

Run order and blockers. Milestone 1 needs both recordings, which plan 03 creates. Milestone 4 needs the owner's Q2 answer. Milestones 2, 3, 5, 6 and 7 do not need Q2. Milestone 7 creates the `## Evidence and limits` heading that Milestone 4 writes into, so the run order is 1, 2, 3, 5, 6, 7, then 4.

## Milestones

### Milestone 1 - Confirm the earlier plans landed, add the cost script, and capture the sample runs

Goal: the implementer knows that the tool runs, that the sample numbers match the expected results, what the recorded default run decides, what one run costs, and which prices the cost uses. No docs are written yet.

Work: add `scripts/cost.py` as specified in Context and orientation, and its test `test_cost_line_totals_recorded_turns` in `tests/test_recording.py`. The test writes a small recording and a small fixture file into a temporary folder, runs the script as a subprocess with `-I`, and checks the exact output line. Use two bookings with turns (1000 input and 100 output tokens, then 500 and 50, for the first; 2000 and 10 for the second), three fixture bookings, and prices of 1 and 2 USD per 1 million tokens. The expected line then holds `input_tokens=3500 output_tokens=160 total_usd=0.003820 model_bookings=2 code_settled_bookings=1 per_model_booking_usd=0.001910 fixture_bookings=3 per_fixture_booking_usd=0.001273`, with the model name from the small recording. Then copy the input and output prices of the recorded model from plan 02's Decision Log entry whose title starts with "Milestone 1 result" into `/tmp/prices.env`, as two lines: `export IN_USD_PER_MTOK=<price>` and `export OUT_USD_PER_MTOK=<price>`. If that entry is missing or holds no prices, stop and report.

Then run the commands in the Definition of done that write the `/tmp` artifacts. Record each printed value that matters in Surprises & Discoveries, and the cost line in full.

Stop and report, without writing docs, if either recording file is missing (`recordings/review-run.json` and `recordings/scenarios-run.json`, both from plan 03), if plan 02 has no prices, if any recorded sample result differs from the expected statuses in the Definition of done, or if any command in the Definition of done fails. A recorded REBOOK for QX7T2A or RT5K8B with an offer other than OF-1001 or OF-3001, or a recorded KEEP that is not `rules` for LM9P4C, ZC3N1D or HB6W9E, would disagree with the safety rules. The scenario run is captured and not pinned: a recorded NEEDS_REVIEW or INCOMPLETE_ANALYSIS is reported in the Decision Log and does not stop the milestone.

Seam: the CLI, the committed recording files and `scripts/cost.py` with its test. The test runs the script in a subprocess, so it tests the boundary, not the internals.

Proof: the Definition of done items for the sample counts, the doctor, the prices, the cost script and the captured statuses.

### Milestone 2 - Write the intro, architecture, path, trust and money sections of DESIGN.md

Goal: `DESIGN.md` exists with an intro and four sections that a reader can use to judge the approach: how the code is laid out, how one booking moves through it, where the model is trusted, and how money is checked.

Work: create `DESIGN.md` at the repo root with an H1 title and a short intro. The intro says what the document covers, who it is for, what the two tags mean, and that terms and decisions are linked, not repeated. Then write the `##` sections `## Architecture`, `## Path of one booking`, `## Where the model is and is not trusted` and `## Money safety`, in that order.

The Architecture section explains the layers and the trade-offs behind the cut. Cover the layout: `domain/` with `domain/port/` for the data and rate ports, `orchestration/`, `infrastructure/<technology>/`, `composition/` and `cli/`. Cover that dependencies point inward toward the domain. Cover the data port `ReshopSource`, with one method that returns a snapshot, and the rate port `ExchangeRates`. Cover that bookings, offers, money, rates, evaluations and recommendations are immutable value objects, with no aggregate and no write repository, and that ADR 0001 describes a future review aggregate that is not built. State the trade-off for each choice in a sentence: for example, a second port per source was rejected because no second adapter exists. Link `docs/adr/0001-value-objects-and-deferred-review-aggregate.md` for these decisions. Include one Mermaid flowchart, a fenced block whose first line is three backticks followed by `mermaid`, showing the layers and the arrows between them. Keep it to the layers, not to individual classes.

The Path of one booking section walks one booking, LM9P4C, through the code. LM9P4C is a two-passenger booking from SFO to ORD in USD. Its old ticket costs 350 USD per passenger, with a change fee of 75 USD per passenger. Its one offer on the same route and date, OF-2001, costs 320 USD per passenger, is BASIC_ECONOMY, includes no checked bag, and has a change fee of 75 USD. OF-2001 also leaves at 13:10 on UA640, against 13:30 on UA642 for the booking. Name the component for each step: the source adapter loads the snapshot and translates it into domain objects, with no conversion because both sides are in USD. The rule checks run on OF-2001. The cabin rule fails, because ECONOMY ranks above BASIC_ECONOMY. The bags rule fails, because the offer includes 0 checked bags and the booking includes 1. The other rules pass: refundability, the future change fee (75 USD is not above 75 USD), stops, seats (9 seats for 2 passengers), and the exchange rate check (same currency, so no rate). The schedule change adds an approval flag, which does not fail the offer. The saving is 2 x (350 - 320 - 75) = -90.00 USD, so the offer is not eligible. Code settles the booking as `KEEP` with `decided_by` set to `rules`, and no model call happens. The evaluation keeps all seven rule results, the two failures included, each with its reason. Then one paragraph says how a booking with an eligible offer differs: it goes to the model in model modes, and the rules and the safety check apply to the model's choice.

The Where the model is and is not trusted section says what the model decides, what code decides, and what the safety check re-checks. Cover that the model sees only bookings with at least one eligible offer. Cover that the model call is one stateless turn, and that the loop, its limits and all parsing live in code. Cover the three tools, `get_booking`, `search_offers` and `evaluate_offer`, and that code binds the booking so the model never passes a booking reference. Cover the limit of at most 10 model turns per booking, the stop on a repeated call, and the `INCOMPLETE_ANALYSIS` outcome with its reasons. Cover the four outcomes of a model choice: a valid rebook; a rebook that fails the safety check, which gives `NEEDS_REVIEW` with the reason (the offer is not on the route, fails a rule, or misses the minimum); a keep while an eligible offer exists, which gives `NEEDS_REVIEW` with both views and the reason "model and rules disagree"; and a keep with no eligible offer, which code settles. Cover that the final answer's confidence is the model's own estimate, labeled uncalibrated, and null when rules decide. State plainly that the model's money figures are ignored and that the model cannot book anything. End the section with one walkthrough of scenario c of the scenario data set. WJ6T4N is a refundable one-passenger booking from SEA to SFO, with its ticket at 600 USD and a change fee of 90 USD. OF-6301 would save 210.00 USD, but it is not refundable, so it fails the `refundable` rule and is not eligible. OF-6302 is refundable at 450 USD and saves 60.00 USD, so it is the only eligible offer. A model that picks OF-6301 is caught by the safety check: the result is `NEEDS_REVIEW` with the failed refundable rule as the reason, and the model's choice stays visible. A model that picks OF-6302 is accepted. The example shows where the model's judgment counts and where code overrules it.

The Money safety section explains how a saving is computed and why it cannot drift. Cover the hard rules, each giving PASS or FAIL with a reason. Cover that a schedule change or a carrier change adds an approval flag and does not reject the offer. Cover that money is parsed from text into exact decimals and never through a float, and that a booking that fails parsing, has more than one segment, has a total that does not match passengers times price, departs before the capture time, or has no rate to convert the minimum becomes an `INVALID_DATA` result. Cover the minimum saving of 50 USD, converted through the port and rounded once. Cover the `ExchangeRates` port: the rate file holds a base, a quote, a rate and a date; the inverse direction is derived; each converted amount shows its rate, its direction and its date. Cover the nominal saving formula: passengers times (old fare per passenger minus offer fare per passenger converted to the booking's currency minus the old ticket's change fee per passenger). Cover rounding half-even to 2 places once, before the minimum check and before output, with this example: a saving of 49.996 prints as 50.00, and a check before rounding would fail it. Cover the old-versus-new change fee trap: the booking's change fee is the cost of changing the old ticket today, and the offer's change fee is the cost of changing the new fare later, and the two never swap places. Show the RT5K8B arithmetic as the worked example: the offer's 2,100 USD is 1,836.79 EUR at the demo rate, the saving is 2,200 - 1,836.79 - 0 = 363.21 EUR, and that is above the minimum of 43.73 EUR. Name the rate as "the fixed demo rate, dated 2026-07-07" on the same line.

Seam: none. These are docs.

Proof: the Definition of done items for the headings, the Mermaid block, the figures and the rate line.

### Milestone 3 - Write the output, scale and cost, data, and assumptions sections of DESIGN.md

Goal: `DESIGN.md` answers what a consumer can rely on, what breaks at scale and what one booking costs, what data leaves the machine, and which assumptions the numbers rest on.

Work: first, the price check. Check the prices in `/tmp/prices.env` against the current OpenAI pricing page for the recorded model. Record the URL, the two prices and the date of the check in a Decision Log entry whose text starts "Decision: price check". Also write `export CHECKED_ON=<date>` into `/tmp/prices.env`. If a price differs from the page, stop and ask the owner which prices to use. Nothing with new prices is written until the owner answers.

Then append these `##` sections, in this order: `## Output contract`, `## Scale, cost and observability`, `## Data handling`, and `## Assumptions and open questions`.

The Output contract section says what a consumer can rely on. It states that every result has a `status`, and names the five statuses (`REBOOK`, `KEEP`, `NEEDS_REVIEW`, `INCOMPLETE_ANALYSIS`, `INVALID_DATA`). It states that `rebook` is true only for `REBOOK`, that there is no `execution_ready` field because every result goes to a person, and that the serializer derives `status` and `rebook` from the result type, so they cannot disagree. In this build, `decided_by` is `rules` for every result. It states that adding a field is a compatible change, and that renaming or removing one needs a new schema version. It does not list every field. It points to the schema test `tests/test_cli.py::test_review_json_has_schema_version_one` for the field names and the version, and to the trimmed sample result in `README.md` for an example.

The Scale, cost and observability section answers three things. First, what breaks at a very large book of bookings, in four points, each tagged. Fare search runs once per booking, with no sharing between bookings on the same route and date (built); sharing one search is future work. The run is sequential. The app adds no retries of its own; the OpenAI SDK retries transient errors by default (built). Retries with backoff and rate limits per external source are future work. The recording is one file that holds every turn and is read whole, so it grows with the book (built). Model cost grows with the share of bookings that have an eligible offer, not with the whole book (built).

Second, what one booking costs. State the formula in words. State the two figures that `scripts/cost.py` prints: the cost per booking that reached the model, summed over its turns, and the cost per sample booking across the five fixture bookings. Give both figures, the number of each booking group, and the token totals behind them, and label them built. Say they are measured on the five sample bookings and are not a forecast. Write one sentence that gives the recorded model name, the two prices and the check date from this milestone together, so that the prices sit next to the model name and the date. Tag it built. Do not put a command in the document. Cite the script by name.

Third, what to measure. List in prose what the output already lets a reader count: counts by status and by `decided_by`, counts of incomplete reasons, turns per booking, tokens per booking, and the number of safety-check failures. Tag these built. Say in one sentence that the measures that need a dashboard or tracing backend are not built, and point to `docs/future-work.md`, tagged as future work.

The Data handling section says what leaves the machine and what is stored. Cover D30 in full: only the configured fixture files are read; in model modes, booking and offer facts go to OpenAI inside tool results; the same facts are stored in the committed recording; the fixtures hold no names or contact data, so nothing is masked (built). Say that masking is needed before real data, and name the first step: mask booking references and fare-rule attributes in the tool results, and compute the digest on the masked facts (future work, with its row). Cover that the recording holds no request ids, no headers and no keys, and that the key comes from the environment and never appears in output or in the recording (built).

The Assumptions and open questions section lists the six assumptions under the labels "Assumption 1" to "Assumption 6", each with the assumption in plain words and what changes if it is wrong. Keep these labels local to this document, and do not refer to the planning index. Then list the three open business questions, each with its future-work item linked to `docs/future-work.md`.

Seam: none.

Proof: the Definition of done items for the headings, the cost figures, the price sentence, the data terms and the assumption labels.

### Milestone 4 - Write the not-built and AI-usage sections, the test claims, and the links

Blocked on Q2. This milestone does not start until the owner confirms each AI-usage fact. Each confirmed fact is recorded in the Decision Log first. Milestone 7 runs before this milestone, so the `## Evidence and limits` heading already exists.

Goal: `DESIGN.md` is complete. It says what was left out and why, gives an honest AI-usage note, says what the tests and the recorded run prove and do not prove, and links the other docs.

Work: insert `## Not built and why` and `## AI usage` immediately above the `## Evidence and limits` heading. Append the test claims and the plain-limits subsection to the end of the Evidence section, then append `## Links` at the end of the document.

The Not built and why section covers the three things the owner cut from the first slice: a model-based prefilter before the rule checks, token and cost budgets, and a fixed six-tool set. For each, give the reason in the docs' own words. The prefilter would drop real savings before the free rule checks ran, and it would spend money on work that code does for free. The budgets moved to future work. The six-tool set was cut to three, because two of the six always return the same thing and two answer one question. Link `docs/future-work.md`.

The AI usage section is a short note in the first person singular, as the author. The facts for the owner to confirm are these. ChatGPT drove a first design discussion and a first Python prototype. Claude Code (Anthropic) ran a question-by-question design session, read reference agent code, queried two NotebookLM notebooks (one on agent design, one on domain-driven design), ran web research on tool design and aggregates, wrote these plans and implemented the code. The owner made every product decision. The AI suggestions the owner rejected or corrected are these: an LLM classifier that rejected bookings before the free rule checks (rejected, because it could drop real savings and cost money where code is free); a notebook suggestion to make the booking an aggregate root that holds the recommendation (rejected, because this project never changes bookings, so there is nothing to protect); six tools (cut to three, as above); and token and cost budgets in the first slice (dropped by the owner and kept as future work). Do not quote tool output.

The Evidence section, after the limits that Milestone 7 wrote, gets these paragraphs. The first says what the tests prove, with each sentence tagged built. Name the tests that carry each claim, grouped by claim: `test_sample_data_matches_expected_results` in `tests/test_review.py`; `test_offer_in_lower_cabin_is_rejected`, `test_minimum_is_checked_after_rounding` and `test_offer_change_fee_never_enters_nominal_saving` in `tests/test_domain_rules.py`; `test_float_trap_rejects_decimal_from_float` in `tests/test_money.py`; `test_review_json_has_schema_version_one` and `test_missing_policy_file_exits_2` in `tests/test_cli.py`; `test_turn_cap_ends_incomplete`, `test_repeated_call_ends_incomplete`, `test_bad_tool_arguments_return_hint`, `test_model_choice_failing_a_rule_needs_review`, `test_provider_error_keeps_other_bookings_running`, `test_openai_errors_map_to_provider_failed` and `test_openai_request_sets_store_off_and_no_reasoning` in `tests/test_agent_review.py`; and `test_committed_recording_matches_data`, `test_changed_fixture_is_stale`, `test_changed_turn_is_stale`, `test_missing_turn_is_stale`, `test_leftover_turn_is_stale`, `test_replay_reproduces_turn_cap_booking`, `test_recording_has_no_secrets`, `test_stale_recording_exits_3` and `test_cost_line_totals_recorded_turns` in `tests/test_recording.py`. Say that the live provider path is tested with a stub client, not the real service, and that the model loop's limits and error paths are tested with a scripted model. Say what the recorded run proves: one committed run of the real loop over the five sample bookings replays to the same results, and a change to the data, policy, rates, prompt, tools or a recorded turn is caught.

The second paragraph is for the limits the tests do not close and that a later change would close. Each gets a sentence tagged future work, only where a row exists: that the model's choice is right or its rationale is good (the eval set and the rationale-scoring rows); that the model behaves the same on another day or after another model release (the prompt and model version row). The third paragraph is the `### Limits with no planned work` subsection. It holds the plain statements, with no tag: that the results are not shown to hold for real bookings or live fares; that the cost is not shown to hold for a larger book; that the prompt is not shown to be the best one; and that a live run is not proven by the checks, because the optional manual live check is not a gate.

The Links section links relative paths: `README.md` for how to run it, `GLOSSARY.md` for terms, `docs/adr/` for the decisions that are hard to reverse, `docs/runbooks/re-record.md` for the re-record steps and their cost, and `docs/future-work.md` for what comes next.

Seam: none.

Proof: the Definition of done items for the sections, the AI-usage facts, the test names and the links.

### Milestone 5 - Rewrite README.md

Goal: `README.md` tells a reader what the tool does, how to run each mode, what the doctor checks, and what the output looks like. It uses the real commands. The outdated lines are gone.

Work: replace the file's content. Keep the title. Write a short intro of two or three sentences: what the tool does, and that it runs with no key in its default mode. Then write these `##` sections, in this order: `## What it does`, `## Quick start`, `## Modes`, `## Doctor`, `## Sample output`, `## Sample data` and `## Design`.

The What it does section gives the job in plain English and keeps the list of what counts as worth a rebooking: a cost above the old fare once the change fee for every passenger is added, a lower cabin, dropped checked baggage or refundability, an added stop, a higher change fee for the new fare than for the booking, a different currency with no rate, and too few seats. A schedule change is listed as an approval flag, not a rejection. Remove the sentence that says the model only explains a choice. Replace it with D19's role for the model: it picks an eligible offer or says keep, and writes the rationale; code computes every number and re-checks the choice.

The Quick start section opens with one prose paragraph. It says that uv is a Python package and project manager, links the official install page at https://docs.astral.sh/uv/getting-started/installation/, says that uv fetches Python 3.12 if the machine lacks it, and says that the first `uv sync` downloads the packages. Then one sentence says that `./start.sh` runs sync, the doctor and the default review, and that it asks before it installs uv or runs `uv sync`. Then one sentence says that `./scripts/check.sh` runs `ruff format --check`, `ruff check`, `mypy` and `pytest` in that order and exits non-zero on the first failure. Then the manual path as one fenced block, language `sh`, with these three commands in order: `uv sync`, `uv run fare-reshop doctor`, `uv run fare-reshop review`. Say in one sentence that these are the steps `./start.sh` runs, by hand. After the block, one sentence names the second demo command, `uv run fare-reshop review --data scenarios`, and points to the Sample output section. Then one prose paragraph says that Windows is not tested, and that a Windows reader runs the same three commands in that order from the repo folder.

The Modes section has one short paragraph per mode, each with its command. The recorded mode is the default (`uv run fare-reshop review`). It replays `recordings/review-run.json` with no key and no network. After the first `uv sync`, the default run needs no key and no network. The `--data` option picks the data set, `sample` (the default) or `scenarios`, and with it the recording it replays. It names a configured data set, never a path. The `--format` option picks `json` (the default) or `table`. The `none` mode is rules only: `uv run fare-reshop review --model none`. The `openai` mode calls the live model. Copy `.env.example` to `.env.local` with `cp .env.example .env.local`, set `OPENAI_API_KEY` in that file, run `uv sync --extra live`, then run `uv run --extra live --env-file .env.local fare-reshop review --model openai`. The `--extra live` flag keeps the `openai` package installed for that run. The `--record` flag saves a live run into the recording, and it works only with `openai`. The sample re-record command is `uv run --extra live --env-file .env.local fare-reshop review --model openai --record`, and the scenario re-record command is `uv run --extra live --env-file .env.local fare-reshop review --data scenarios --model openai --record`. Then this exact sentence: "Exit codes: 0 done, 1 internal error, 2 setup error, 3 stale recording." Say what a stale recording means in one sentence: the data, policy, rates, prompt or tools changed since the run was recorded. Point to `docs/runbooks/re-record.md` for the steps and their cost.

The Doctor section says what `uv run fare-reshop doctor` checks, and that each failed check prints a `fix:` line with the command that fixes it. The check names are the names the CLI prints. Copy them from the real output captured in the Definition of done.

The Sample output section has exactly three fenced blocks. The first holds the output of `uv run fare-reshop review --format table` for the five sample bookings, from the recorded default run. The second holds one JSON result for QX7T2A from `uv run fare-reshop review`, trimmed by removing keys so that it stays valid JSON. One sentence under it says the other fields are in `DESIGN.md`. The third holds the output of `uv run fare-reshop review --data scenarios --format table` for the six scenario bookings, with one sentence that names the judgment case each scenario shows. All three blocks are copied from real runs, not typed.

The Sample data section lists the five bookings and six offers, with the routes JFK-LAX, SFO-ORD, LHR-JFK, MIA-BOG and SEA-DEN, copied from `fixtures/pnrs.json` at writing time. State that the fixtures are made up. Then one paragraph on the scenario data set: six made-up bookings (MK3V7P, RD9Q2X, WJ6T4N, CH8L5F, FD2N8Z and YU6EG1) on the routes ORD-DEN, BOS-ATL, SEA-SFO, DFW-PHX and PDX-LAS, and seven offers. Two bookings share one flight on purpose.

The Design section links `DESIGN.md`, which covers the trust boundary, the money rules, the output contract and what was left out, and links `GLOSSARY.md` for the terms.

Remove the old `## Status` section and every status wording, including "Work in progress".

Seam: the CLI. The Proof runs the README's own commands, so a broken command shows up.

Proof: the Definition of done items for the README.

### Milestone 6 - Update future-work.md, check AGENTS.md, and check the linked docs

Goal: `docs/future-work.md` describes what is built and what is not. Built items leave the tables and are listed in a Built section. Two new rows name the limits that have no row yet. `AGENTS.md` passes its checks, and the linked docs exist.

Work: first, `docs/future-work.md`. Every row that this feature built leaves its table. These rows leave: "Exchange rates behind a port, with a stub adapter holding fixed demo rates" (Money); "Plain-code screen before any model call" (Scale and cost); "Strict structured output for the final answer, checked against a schema" (The agent); "Offline model adapter, so the default run and the tests need no key or network" (The agent); "One result shape for every tool, errors included, and bad tool arguments sent back to the model as a tool error" (The agent); "Every tool error carries a hint about what to do next" (The agent); "Record real model runs and replay them in tests" (The agent); "Every recommendation goes to a person. Nothing books automatically." (Human review); "Hexagonal layout: domain, application, ports, adapters" (Engineering); "Money and policy tests on every sample booking, including the old-vs-new change fee trap" (Engineering); and "Strict type checking and a linter in CI" (Engineering), because the local check script now runs both.

Add these rows. In the Engineering table, "A hosted pipeline that runs the check script on every push" (tier Next), with the Why "The same four checks run for each push, not only when someone runs them locally." In the Fares and itineraries table, "Seat inventory shared across bookings on one flight" (tier Later), with the Why "Two bookings on one flight can both be told to take the last seats. A seat count per flight, shared by every booking, stops that." In the Agent table, "Mask booking references and fare-rule attributes in tool results and recordings before real data arrives" (tier Later), with the Why "Tool results go to the model provider and the recording stores the same facts. Real bookings need masking first, and the digest must be computed on the masked facts."

Change the row "Policy as data" from tier Now to tier Next. Its Why text stays unchanged, because the policy version is not built. The Now tier is then empty. The row "Prompt and model version on every result" stays in its table as Next.

Add one section at the end of the file, `## Built`, with twelve bullets. Each bullet names the capability and the command or test that shows it, and names no plan. The twelve bullets:

1. The exchange-rate port with a fixed demo adapter that reads `config/exchange_rates.toml`, shown by `uv run fare-reshop review --model none --format table`.
2. A plain-code rule check before any model call. In model modes, code settles 3 of 5 sample bookings with no model call, as the `code_settled_bookings` count from `scripts/cost.py` shows.
3. Immutable value objects and the one data port, `ReshopSource`, with a fixture adapter.
4. The layered layout: `domain`, `orchestration`, `infrastructure`, `composition` and `cli`.
5. Money and rule tests on the sample and scenario bookings, including the old-versus-new change fee trap, in `tests/test_domain_rules.py`, `tests/test_money.py` and `tests/test_review.py`.
6. One result shape for tools, with a hint on every error, and bad tool arguments sent back to the model as a tool error, tested in `tests/test_agent_review.py`.
7. Strict structured output for the final answer, checked against a schema, in `tests/test_agent_review.py`.
8. The offline recorded model run: the committed recordings `recordings/review-run.json` and `recordings/scenarios-run.json`, replayed with no key by `uv run fare-reshop review`, and the stale-recording checks in `tests/test_recording.py`.
9. The prompt version in the trace of each model-mode result.
10. Strict type checking and a linter, run by `./scripts/check.sh`.
11. Every recommendation goes to a person. No code path books anything, and the result has no `execution_ready` field.
12. Policy as data, in part: the minimum saving is read from `config/policy.toml`. The hard rules and the approval rules stay in code, and results do not yet carry a policy version.

Do not write the phrase "carries a model version" in the Built section.

Second, `AGENTS.md`. This plan checks it and does not edit it. The rules-only review already made the ExchangeRates wording change (D6). The agent plan makes the D19 change to the model's role. If a check fails, the implementer records the failure in Surprises & Discoveries and stops this milestone.

Third, the linked docs. Check that `GLOSSARY.md` exists at the repo root, that `docs/adr/` holds at least one `.md` file, and that `docs/runbooks/re-record.md` exists. The rules-only review wrote the first two. The recording plan writes the runbook. If one is missing, record it in Surprises & Discoveries and stop this milestone. Do not write it here.

Seam: the files themselves.

Proof: the Definition of done items for `docs/future-work.md`, `AGENTS.md` and the linked docs.

### Milestone 7 - Documented limits in Evidence and limits

Goal: `## Evidence and limits` exists and names the limits the current build has and that a later change would close. Each such limit is one sentence, tagged `[future work]`, and matched to its row in `docs/future-work.md`. This milestone does not depend on Q2 and creates the heading that Milestone 4 writes into.

Work: append the `## Evidence and limits` section to the end of `DESIGN.md`. Write these five sentences, each ending with its tag and a full stop. The key term of each is the word the Definition of done searches for.

- Seat contention: each booking is checked alone against the seats its offer lists, so two bookings on one flight can both be told to take the last seats, as scenario d shows [future work].
- Times without a time zone: departure and arrival times are naive local clock times, compared with the capture time in UTC, so a time zone offset can misjudge a departure near the capture time [future work].
- Daylight saving time changes: near a summer or winter switch, a local time can be off by one hour, a local time may not exist or may repeat, and a schedule-change flag or trip duration can be off by an hour; no sample or scenario flight is near a switch, and the fix is timezone-aware times per airport [future work].
- The fixed demo rate, 1 EUR = 1.1433 USD, dated 2026-07-07, is the last rate published before the fare snapshot was captured on 2026-07-08; it is a fixed demo value, not a live or binding quote [future work].
- Nominal saving: every saving is nominal, the fare difference less the old ticket's change fee, and it is not a realized saving, which is not computed [future work].

Then append one sentence tagged built: the scenario tests `test_scenario_expected_results_table_matches` in `tests/test_review.py` and `test_scenario_c_model_pick_of_6301_needs_review` in `tests/test_agent_review.py` check the scenario data set's expected results and its bad-pick case [built].

Matching rows: seat contention points at the new row "Seat inventory shared across bookings on one flight" (Later). The time zone and daylight saving limits point at "Timezone-aware departure and arrival times" (Next). The fixed demo rate points at "Live exchange-rate adapter with the rate's source and timestamp in every result" (Next). The nominal saving points at "Estimated saving vs realized saving, tracked per approved rebooking" (Later). Do not add a row in this milestone, because Milestone 6 adds the one this section needs.

Seam: none.

Proof: the Definition of done items for the key terms, the tags and the future-work rows.

## Content review

This is a review step, not a Definition of done item. After Milestones 2, 3, 4 and 7 are written, the implementer starts a fresh-context reviewer subagent. The reviewer gets `DESIGN.md`, the repo, and the list of the "Cover that" sentences from Milestones 2 to 4, and none of the writer's notes. For each sentence the reviewer reports PASS or FAIL with the heading it found. The writer fixes every FAIL and asks the reviewer again for that sentence only. The milestone does not close while any FAIL stands.

## Surprises & Discoveries

Observation: `docs/future-work.md` says code settles "4 of 5" sample bookings. Evidence: the expected results table shows REBOOK for QX7T2A and RT5K8B, and KEEP for LM9P4C, ZC3N1D and HB6W9E. Only two bookings have an eligible offer, so code settles three. The row leaves its table as built in Milestone 6, and the Built bullet states "3 of 5".

Observation: `README.md` says the model only explains a choice and never produces the saving figure, and says that a schedule change rejects an offer. Both are out of date (D19, D3). Fixed in Milestone 5.

Observation: `AGENTS.md` said "an exchange rate from the data" before the rules-only review. The review changed it to name the ExchangeRates port (D6). Milestone 6 checks that wording.

Observation: plan 02 (Agent review with a live model) landed and its plan file was retired on 2026-11-02. Its "Milestone 1 result" entry recorded the prices, copied here so this plan stays self-contained. Model price record: `gpt-6-luna`, per 1M tokens, 0.10 USD input, 0.01 USD cached input, 0.50 USD output (OpenAI changelog of 2026-09-22, standard tier, prompts up to 272K tokens; SDK `openai` 3.42.1). Evidence: plan 02's Decision Log, read before retirement. Milestone 1 copies these numbers into `/tmp/prices.env`.

Observation: an earlier draft of plan 02 changed `.env.example` to `gpt-5.4-mini`. Its round-2 revision no longer edits the file, and the owner confirmed `gpt-6-luna` (Q1). Evidence: `.env.example` line 3 reads `OPENAI_MODEL=gpt-6-luna`.

Observation: the built output puts an `exchange_rates` list on each result (`fare_reshop_agent/reshopping/cli/json_output.py`). The docs do not list result fields, so the output contract cannot drift from it. The schema test is the reference.

## Decision Log

Decision: the docs carry only the decisions the index marks for this plan, plus D19's README change and its AGENTS.md check. Rationale: this plan's scope is the docs, and each other decision is owned by the plan that builds it. Date/Author: 2026-11-02, plan author.

Decision: D27 is copied from the index word for word, including "too large for the time" and "argued down in the grilling". The docs give their own reasons, in their own words. Rationale: the index is the one source. Date/Author: 2026-11-02, plan author.

Decision: the cost per booking is computed from the usage stored in the committed recording, by `scripts/cost.py`, and no cost figure is typed by hand or estimated. Rationale: the index drops token and cost budgets (D18, D27), but it keeps per-turn usage in the recording (D22) and in the trace (D24). The owner should confirm that the stored usage stays. If the owner drops it, the figure becomes a labeled estimate. Date/Author: 2026-11-02, plan author. Round 3 changed the carrier from a one-line command in the document to the script.

Decision: the cost is reported two ways, labeled. The first is the cost per booking that reached the model, summed over its turns. The second is the cost per sample booking across the five fixture bookings, since code settles some bookings for free. Date/Author: 2026-11-02, plan author.

Decision: the walkthrough in the Path section uses LM9P4C, which settles by code, not QX7T2A. Rationale: LM9P4C shows two failed rules and a settled-by-code path with no model call, which a reader needs first. Date/Author: 2026-11-02, plan author.

Decision: the docs tag each built measure as `[built]`, and each planned item that has a future-work row as `[future work]`, with the tag before the full stop. A limit with no row is a plain statement. Rationale: a reader must tell what the code does from what it will do. A tag for an item with no planned work would claim a plan that does not exist. Date/Author: 2026-11-02, plan author; round 3.

Decision: `DESIGN.md` has twelve `##` sections, and the Evidence section holds the limits and the test claims. Rationale: a reader who judges the approach needs to know what the tests and the recorded run prove, and what they do not. Date/Author: 2026-11-02, plan author.

Decision: each fact has one owner doc, and the others link to it. Rationale: a fact written in two places drifts. Date/Author: 2026-11-02, plan author.

Decision: the docs name no vendor or data source for the demo exchange rate, and say only that it is a fixed demo rate dated 2026-07-07. Rationale: the owner's instruction. Date/Author: 2026-11-02, plan author.

Decision: no doc claims that a result carries a model version. The item stays in `docs/future-work.md`. Rationale: the model version is not built, so the claim would be false. Date/Author: 2026-11-02, plan author.

Decision: exit codes are 0 done, 1 internal error, 2 setup error, 3 stale recording, which is index D15 as written. Date/Author: 2026-11-02, plan author.

Decision: this plan checks `AGENTS.md` and does not edit it. Rationale: the index gives each `AGENTS.md` edit one owner (D6, D19). Date/Author: 2026-11-02, plan author.

Decision: the Built section of `docs/future-work.md` lists built items by capability and command, not by plan title or deleted rows. Rationale: a reader who asks "was this planned" finds the answer in the table, and the Built section says what works now. Date/Author: 2026-11-02, plan author; round 3.

Decision: the README sample output comes from the recorded default run, with its statuses captured in Milestone 1 and pinned in the Definition of done. The expected results table applies to `--model none` only. Milestone 1 stops and reports if the recording disagrees with the safety rules. Date/Author: 2026-11-02, plan author.

Decision: every Definition of done command that takes a value from a variable tests that the value is not empty first, so that an empty pattern cannot match every line. Date/Author: 2026-11-02, plan author.

Decision: every Python command runs through `uv run python -I`, so that the working directory stays out of the import path. Date/Author: 2026-11-02, plan author.

Decision: the AI-usage facts are pending owner confirmation (index Q2). Milestone 4 is blocked on Q2. Each confirmed fact goes into this log before the section is written. Date/Author: 2026-11-02, plan author.

Decision: the model and its prices follow index D21 and Q1. The docs cite the model name the recording stores and the prices plan 02 recorded. Date/Author: 2026-11-02, plan author.

Decision: the Definition of done has no word-count floors. A section passes when its named facts are present. Date/Author: 2026-11-02, plan author; round 3.

Decision: the DESIGN.md Mermaid check requires a first line that starts with `flowchart` or `graph`, and at least three arrows. Date/Author: 2026-11-02, plan author; round 3.

Decision: the start script check answers `n` to every prompt. It never answers `y`, so no install or sync runs during the check. Date/Author: 2026-11-02, plan author; round 3.

Decision: the `## Evidence and limits` heading is created by Milestone 7 and extended by Milestone 4, so Milestone 7 runs first. Milestone 7 does not wait for Q2. Rationale: the limits do not depend on the AI-usage answer. Date/Author: 2026-11-02, plan author; round 3.

Decision: the blocked status. The plan status is "blocked - needs the owner's two recordings (Record and replay model runs) and the Q2 answer for the AI-usage section". This replaces the round 2 status "ready - rests on Q1 and Q2". Q1 is answered. Rationale: the two recordings are not in the tree yet and Q2 is open. Date/Author: 2026-11-02, plan author; round 3.

Decision: seat contention and masking get future-work rows, so their limits carry the `[future work]` tag. This reverses the round 2 decision that seat contention had no row. Rationale: the owner's round 3 finding asks for the rows, and the rule is that a tag needs a row. Date/Author: 2026-11-02, plan author; round 3.

Decision: the outcome check on `scripts/cost.py` is a single test in `tests/test_recording.py`, not a new test module. Rationale: the rules-only review built one test module per seam (`tests/test_domain_rules.py`, `tests/test_money.py`, `tests/test_review.py`). The cost script is its own seam, so its one test goes in `tests/test_recording.py`, the module for the recording seam. Date/Author: 2026-11-02, plan author; round 3.

Decision: the price check records the URL, the two prices and the check date in the Decision Log, and the date also goes into `/tmp/prices.env` for the DESIGN check. Rationale: the Decision Log is the record, and `/tmp` is working state. Date/Author: 2026-11-02, plan author; round 3.

Decision: the SDK retry claim is checked against the installed client's default retry count. Rationale: the claim is about a third-party library, and its default is the only thing the docs can state. Date/Author: 2026-11-02, plan author; round 3.

Decision: the statuses in the recorded run are captured as lines of `<pnr> <status> <decided_by> <offer_id>`, with JSON null shown as `-`, sorted by pnr. Rationale: a fixed line format lets a diff compare runs exactly. Date/Author: 2026-11-02, plan author; round 3.

Decision: realign the plan's claims about the rules-only review to the code on main (commit a245d0b). Its plan file is deleted, so each claim now points at the code, `GLOSSARY.md`, the ADR or the planning index. The package layout, the seven rule checks, the `none` results and savings, the table columns, the JSON keys, the exit codes 0, 1 and 2, the doctor checks, the scenario data set, the test names and the future-work and AGENTS.md wording were checked against the repo. The `Status` line did not change. Rationale: the docs must describe the code that exists, and a deleted plan file is not a source. Date/Author: 2026-11-02, plan author.

## Outcomes & Retrospective

Filled at completion.

## Definition of done

Each command below regenerates its `/tmp` artifact first with `rm -f`, so a stale file cannot pass. The status line format is `<pnr> <status> <decided_by> <offer_id>`, with JSON null shown as `-`. The shell is zsh or bash, because the checks use process substitution.

Sample results, doctor and cost:

- [ ] The none-mode counts match: `uv run fare-reshop review --model none --format json | grep -c '"status": "REBOOK"'` prints `2`, and the same command with `"status": "KEEP"` prints `3`.
- [ ] Doctor exits 0 and its check names are captured, and every name appears in the README Doctor section: `rm -f /tmp/doctor.txt /tmp/doctor-names.txt && uv run fare-reshop doctor > /tmp/doctor.txt; echo $?` prints `0`; then `grep -E '^\[(ok|FAIL)\]' /tmp/doctor.txt | sed -E 's/^\[(ok|FAIL)\] +//; s/[:(].*$//; s/ +$//' > /tmp/doctor-names.txt && test -s /tmp/doctor-names.txt && while IFS= read -r n; do test -n "$n" && awk '/^## Doctor/{s=1;next} /^## /{s=0} s' README.md | grep -qF -- "$n" || echo "missing $n"; done < /tmp/doctor-names.txt; echo checked` prints `checked` and nothing before it.
- [ ] The prices came from plan 02 and are two export lines: `test -s /tmp/prices.env && grep -cE '^export (IN|OUT)_USD_PER_MTOK=[0-9]+(\.[0-9]+)?$' /tmp/prices.env` prints `2`; then `IN=$(sed -n 's/^export IN_USD_PER_MTOK=//p' /tmp/prices.env); OUT=$(sed -n 's/^export OUT_USD_PER_MTOK=//p' /tmp/prices.env); test -n "$IN" && test -n "$OUT" && grep -F -- "$IN" .agents/plans/reshop-review/04-design-document-and-readme.md | grep -cF -- "$OUT"` prints at least `1`.
- [ ] The cost script test passes, and the script's output has the expected counts and a total under 1 USD: `rm -f /tmp/cost.txt && . /tmp/prices.env && uv run pytest -q tests/test_recording.py -k cost_line && uv run python -I scripts/cost.py > /tmp/cost.txt && grep -c 'model_bookings=2 code_settled_bookings=3 ' /tmp/cost.txt`, which prints `1`; then `v=$(grep -o 'total_usd=[0-9.]*' /tmp/cost.txt | cut -d= -f2); test -n "$v" && awk -v t="$v" 'BEGIN{exit !(t+0 > 0 && t+0 < 1)}' && echo under-one` prints `under-one`.
- [ ] The sample statuses match the safety rules exactly: `rm -f /tmp/recorded.json /tmp/recorded-statuses.txt && uv run fare-reshop review > /tmp/recorded.json && uv run python -I -c "import json, sys; d = json.load(open(sys.argv[1], encoding='utf-8')); [print(r['pnr'], r['status'], r['decided_by'] or '-', r['offer_id'] or '-') for r in sorted(d['results'], key=lambda r: r['pnr'])]" /tmp/recorded.json > /tmp/recorded-statuses.txt && diff /tmp/recorded-statuses.txt <(printf '%s\n' 'HB6W9E KEEP rules -' 'LM9P4C KEEP rules -' 'QX7T2A REBOOK model OF-1001' 'RT5K8B REBOOK model OF-3001' 'ZC3N1D KEEP rules -') && echo same` prints `same`.
- [ ] The scenario statuses are captured and each line has a valid status: `rm -f /tmp/recorded-scenarios.json /tmp/recorded-statuses-scenarios.txt && uv run fare-reshop review --data scenarios > /tmp/recorded-scenarios.json && uv run python -I -c "import json, sys; d = json.load(open(sys.argv[1], encoding='utf-8')); [print(r['pnr'], r['status'], r['decided_by'] or '-', r['offer_id'] or '-') for r in sorted(d['results'], key=lambda r: r['pnr'])]" /tmp/recorded-scenarios.json > /tmp/recorded-statuses-scenarios.txt && grep -cE '^[A-Z0-9]{6} (REBOOK|KEEP|NEEDS_REVIEW|INCOMPLETE_ANALYSIS|INVALID_DATA) ' /tmp/recorded-statuses-scenarios.txt` prints `6`.

DESIGN.md is a real document and its facts hold:

- [ ] The headings are exactly the twelve `##` sections, in order: `diff <(grep '^## ' DESIGN.md) <(printf '%s\n' '## Architecture' '## Path of one booking' '## Where the model is and is not trusted' '## Money safety' '## Output contract' '## Scale, cost and observability' '## Data handling' '## Assumptions and open questions' '## Not built and why' '## AI usage' '## Evidence and limits' '## Links') && echo ok` prints `ok`.
- [ ] The Mermaid block is one flowchart or graph with at least three arrows: `awk 'index($0,"```mermaid")==1{f=1;next} index($0,"```")==1{f=0} f' DESIGN.md > /tmp/mermaid.txt && test "$(grep -c 'mermaid$' DESIGN.md)" -eq 1 && head -n 1 /tmp/mermaid.txt | grep -cE '^(flowchart|graph)( |$)' && test "$(grep -c -- '-->' /tmp/mermaid.txt)" -ge 3 && echo arrows` prints `1`, then `arrows`.
- [ ] The figures and the rate line are present: `for n in 1,836.79 363.21 1.1433 43.73 49.996 -90.00 UA640 UA642 WJ6T4N OF-6301 OF-6302; do grep -qF -- "$n" DESIGN.md || echo "missing $n"; done; grep -F 'fixed demo rate' DESIGN.md | grep -cF '2026-07-07'` prints nothing, then a count of at least `1`.
- [ ] DESIGN.md holds no run commands, and the statuses exist in the code: `grep -cE '(uv (run|sync)|fare-reshop|pytest)' DESIGN.md` prints `0`; `for s in REBOOK KEEP NEEDS_REVIEW INCOMPLETE_ANALYSIS INVALID_DATA; do grep -rqF -- "$s" fare_reshop_agent || echo "missing $s"; done; grep -rq execution_ready fare_reshop_agent && echo present || echo absent` prints nothing, then `absent`.
- [ ] The Output contract points to the schema test and the README sample: `grep -qF 'tests/test_cli.py::test_review_json_has_schema_version_one' DESIGN.md && grep -qF 'README.md' DESIGN.md && echo ok` prints `ok`.
- [ ] The cost figures from the script and the price sentence are in DESIGN.md: `. /tmp/prices.env; rm -f /tmp/cost.txt && uv run python -I scripts/cost.py > /tmp/cost.txt; v1=$(grep -o 'per_model_booking_usd=[0-9.]*' /tmp/cost.txt | cut -d= -f2); v2=$(grep -o 'per_fixture_booking_usd=[0-9.]*' /tmp/cost.txt | cut -d= -f2); test -n "$v1" && test -n "$v2" && grep -qF -- "$v1" DESIGN.md && grep -qF -- "$v2" DESIGN.md && echo figures` prints `figures`; then `mdl=$(uv run python -I -c "import json, sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['model'])" recordings/review-run.json); test -n "$mdl" && test -n "$IN_USD_PER_MTOK" && test -n "$OUT_USD_PER_MTOK" && test -n "$CHECKED_ON" && grep -F -- "$mdl" DESIGN.md | grep -F -- "$IN_USD_PER_MTOK" | grep -F -- "$OUT_USD_PER_MTOK" | grep -cF -- "$CHECKED_ON"` prints at least `1`.
- [ ] The assumption labels, the data terms, and the AI-usage facts are present: `for a in 1 2 3 4 5 6; do grep -qF -- "Assumption $a" DESIGN.md || echo "missing Assumption $a"; done; grep -qF OpenAI DESIGN.md && grep -qi mask DESIGN.md && grep -qi 'request ids' DESIGN.md && echo data` prints `data`; `for t in ChatGPT NotebookLM 'Claude Code' 'aggregate root' classifier budgets; do grep -qF -- "$t" DESIGN.md || echo "missing $t"; done` prints nothing.
- [ ] The Evidence test names are collected by pytest, and at least 25 are cited: `rm -f /tmp/collect.txt /tmp/evidence-tests.txt && uv run pytest --collect-only -q > /tmp/collect.txt && awk '/^## Evidence and limits/{s=1;next} /^## /{s=0} s' DESIGN.md | grep -oE 'test_[a-z0-9_]+' | grep -vxE 'test_(cli|recording|agent_review|review|domain_rules|money)' | sort -u > /tmp/evidence-tests.txt && test "$(grep -c . /tmp/evidence-tests.txt)" -ge 25 && while IFS= read -r t; do grep -qE "::${t}(\[.*\])?$" /tmp/collect.txt || echo "not collected $t"; done < /tmp/evidence-tests.txt; echo checked` prints `checked` and nothing before it.
- [ ] Every sentence in the tagged part of Evidence ends with its tag, and the plain-limits part has no tag: `rm -f /tmp/evidence.txt /tmp/evidence-tagged.txt /tmp/evidence-plain.txt && awk '/^## Evidence and limits/{s=1;next} /^## /{s=0} s' DESIGN.md > /tmp/evidence.txt && awk '/^### Limits with no planned work/{p=1;next} /^#/{p=0} !p' /tmp/evidence.txt > /tmp/evidence-tagged.txt && awk '/^### Limits with no planned work/{p=1;next} /^#/{p=0} p' /tmp/evidence.txt > /tmp/evidence-plain.txt && uv run python -I -c "import re, sys; t = open(sys.argv[1], encoding='utf-8').read(); lines = [re.sub(r'^[-*] ', '', l.strip()) for l in t.splitlines() if l.strip() and not l.startswith('#')]; sents = [s for l in lines for s in re.split(r'(?<=[.!?])\s+', l) if s]; bad = [s for s in sents if not re.search(r'\[(built|future work)\]\.$', s)]; print('sentences', len(sents), 'untagged', len(bad))" /tmp/evidence-tagged.txt` prints `untagged 0` after a sentence count of at least `10`; and `test -s /tmp/evidence-plain.txt && grep -c '\[' /tmp/evidence-plain.txt` prints `0`.
- [ ] The five limit rows and the two new rows exist once each in future-work, with the new rows in the right tiers: `for r in 'Timezone-aware departure and arrival times' 'Live exchange-rate adapter with the rate' 'Estimated saving vs realized saving' 'Seat inventory shared across bookings' 'Mask booking references and fare-rule attributes'; do test "$(grep -cF -- "$r" docs/future-work.md)" -eq 1 || echo "row count is not 1: $r"; done; grep 'Seat inventory shared across bookings' docs/future-work.md | grep -c '| Later |'` prints nothing, then `1`.

README.md is a real document, and its samples match real runs:

- [ ] The headings are exactly the seven `##` sections: `diff <(grep '^## ' README.md) <(printf '%s\n' '## What it does' '## Quick start' '## Modes' '## Doctor' '## Sample output' '## Sample data' '## Design') && echo ok` prints `ok`.
- [ ] The quick start block holds exactly the three manual commands and exits 0: `rm -f /tmp/quick-start.sh && awk '/^## Quick start/{f=1;next} /^## /{f=0} f' README.md | awk '/^```sh/{c=1;next} /^```/{c=0} c' > /tmp/quick-start.sh && test "$(grep -c . /tmp/quick-start.sh)" -eq 3 && grep -cxE 'uv sync|uv run fare-reshop doctor|uv run fare-reshop review' /tmp/quick-start.sh && sh -e /tmp/quick-start.sh > /dev/null 2>&1; echo $?` prints `3`, then `0`.
- [ ] The start script stops at its install or sync question when every answer is no, and it never answers yes: `rm -f /tmp/start.txt && printf 'n\n' | ./start.sh > /tmp/start.txt 2>&1; echo $?` prints `1`; then `grep -cE 'Install uv now\? \[y/N\]|Run uv sync now\? \[y/N\]' /tmp/start.txt` prints at least `1`.
- [ ] The three samples match real runs: `rm -f /tmp/review-table.txt /tmp/readme-table.txt && uv run fare-reshop review --format table > /tmp/review-table.txt && awk '/^## Sample output/{s=1;next} /^## /{s=0} s && /^```/{b++; next} s && b==1' README.md > /tmp/readme-table.txt && diff /tmp/review-table.txt /tmp/readme-table.txt && echo same-table` prints `same-table`; `rm -f /tmp/review-json.txt /tmp/readme-json.txt && uv run fare-reshop review > /tmp/review-json.txt && awk '/^## Sample output/{s=1;next} /^## /{s=0} s && /^```/{b++; next} s && b==3' README.md > /tmp/readme-json.txt && uv run python -I -c "import json, sys; s = json.load(open(sys.argv[1], encoding='utf-8')); r = json.load(open(sys.argv[2], encoding='utf-8'))['results']; m = [x for x in r if x['pnr'] == s['pnr']]; print(s['pnr'] == 'QX7T2A' and len(m) == 1 and all(m[0][k] == v for k, v in s.items()))" /tmp/readme-json.txt /tmp/review-json.txt` prints `True`; and `rm -f /tmp/scen-table.txt /tmp/readme-scen.txt && uv run fare-reshop review --data scenarios --format table > /tmp/scen-table.txt && awk '/^## Sample output/{s=1;next} /^## /{s=0} s && /^```/{b++; next} s && b==5' README.md > /tmp/readme-scen.txt && diff /tmp/scen-table.txt /tmp/readme-scen.txt && echo same-scen` prints `same-scen`, and `awk '/^## Sample output/{s=1;next} /^## /{s=0} s && /^```/' README.md | grep -c .` prints `6`.
- [ ] The table block agrees with the captured statuses: `while read -r p st d o; do grep -wF -- "$p" /tmp/readme-table.txt | grep -qwF -- "$st" || echo "mismatch $p"; done < /tmp/recorded-statuses.txt; echo checked` prints `checked` and nothing before it. (Run after the table check above.)
- [ ] The Sample data section names the five sample routes and the three scenario routes: `awk '/^## Sample data/{s=1;next} /^## /{s=0} s' README.md > /tmp/sample-data.txt && for r in JFK-LAX SFO-ORD LHR-JFK MIA-BOG SEA-DEN ORD-DEN BOS-ATL SEA-SFO DFW-PHX PDX-LAS; do grep -qF -- "$r" /tmp/sample-data.txt || echo "missing $r"; done; echo checked` prints `checked` and nothing before it.
- [ ] The stale lines are gone, and the Modes and Exit code text is present: `grep -cF 'The model only explains a choice and never produces the saving figure.' README.md; grep -cF 'changes the schedule or adds a stop' README.md; grep -cF 'Work in progress.' README.md; grep -c '^## Status' README.md` prints `0` four times; `grep -cF 'Exit codes: 0 done, 1 internal error, 2 setup error, 3 stale recording.' README.md` prints `1`; and `for t in '--model none' '--model openai' '--data scenarios' '--format table' '--record' 'uv sync --extra live' 'docs/runbooks/re-record.md' 'DESIGN.md' 'GLOSSARY.md' './scripts/check.sh'; do grep -qF -- "$t" README.md || echo "missing $t"; done; echo checked` prints `checked` and nothing before it.
- [ ] The local gate passes: `./scripts/check.sh > /tmp/check.txt 2>&1; echo $?` prints `0`.

docs/future-work.md, AGENTS.md and the linked docs match the code:

- [ ] The future-work structure is right: `grep -c '| Now |' docs/future-work.md` prints `0`; `grep -c '^## Built' docs/future-work.md` prints `1`; `awk '/^## Built/{s=1;next} /^## /{s=0} s && /^- /' docs/future-work.md | wc -l` prints `12`; `grep 'Policy as data' docs/future-work.md | grep -c '| Next |'` prints `1`; `grep 'hosted pipeline' docs/future-work.md | grep -c '| Next |'` prints `1`; `grep -c '4 of 5' docs/future-work.md` prints `0`; `grep -c '3 of 5' docs/future-work.md` prints at least `1`; and `awk '/^## Built/{s=1;next} /^## /{s=0} s' docs/future-work.md | grep -cE 'Rules-only review|Agent review with a live model|Record and replay model runs|carries a model version'` prints `0`.
- [ ] No built row text remains in a table: `for p in 'Exchange rates behind a port' 'Plain-code screen before any model call' 'Strict structured output for the final answer' 'Offline model adapter, so the default run' 'One result shape for every tool' 'Every tool error carries a hint' 'Record real model runs and replay them in tests' 'Every recommendation goes to a person' 'Hexagonal layout: domain, application, ports, adapters' 'Money and policy tests on every sample booking' 'Strict type checking and a linter in CI'; do grep '^|' docs/future-work.md | grep -qF -- "$p" && echo "still in table: $p"; done; echo checked` prints `checked` and nothing before it.
- [ ] AGENTS.md has the ExchangeRates wording and the model's choice, and the linked docs exist: `grep -c 'from the data' AGENTS.md` prints `0`; `grep -c 'ExchangeRates port' AGENTS.md` prints at least `1`; `grep -c 'may choose which read-only tools to call and write the short rationale' AGENTS.md` prints `0`; `grep -ci 'eligible offer' AGENTS.md` prints at least `1`; and `test -f GLOSSARY.md && ls docs/adr/*.md > /dev/null && test -f docs/runbooks/re-record.md && echo links` prints `links`.
- [ ] The model version claim and the planning identifiers are absent from the docs: `grep -ci 'carries a model version' DESIGN.md README.md` prints `0` for each file; `grep -cE '(^|[^A-Za-z0-9])(D[0-9]{1,2}|S[0-9]|A[0-9]|Q[0-9])([^A-Za-z0-9]|$)' DESIGN.md README.md` prints `0` for each file; and `grep -c '.agents/plans' DESIGN.md README.md docs/future-work.md` prints `0` for each file.

Voice, leaks and the plan's own format:

- [ ] The denylist is not empty and matches nothing: `test -s .private/denylist.txt && test "$(grep -c '^$' .private/denylist.txt)" -eq 0 && grep -niF -f .private/denylist.txt DESIGN.md README.md docs/future-work.md AGENTS.md scripts/cost.py .agents/plans/reshop-review/04-design-document-and-readme.md; echo $?` prints `1`.
- [ ] No em dash, no curly quotes, and first person singular: `grep -l "$(printf '\342\200\224')" DESIGN.md README.md docs/future-work.md scripts/cost.py .agents/plans/reshop-review/04-design-document-and-readme.md; echo $?` prints `1`; `LC_ALL=C grep -c -e "$(printf '\342\200\234')" -e "$(printf '\342\200\235')" -e "$(printf '\342\200\230')" -e "$(printf '\342\200\231')" DESIGN.md README.md` prints `DESIGN.md:0` and `README.md:0`; and `grep -cwE '[Ww]e|[Oo]ur|[Uu]s' DESIGN.md README.md` prints `DESIGN.md:0` and `README.md:0`.
- [ ] The plan passes the format check: `/Users/igby/.claude/skills/exec-plan/scripts/check-plan-format .agents/plans/reshop-review/04-design-document-and-readme.md` reports it passes with no failing items.
- [ ] The SDK default retry count matches the claim: `uv run --extra live python -I -c "from openai import OpenAI; print(OpenAI(api_key='placeholder').max_retries)"` prints `2`.
- [ ] The price check is in the Decision Log with its URL, prices and date: `. /tmp/prices.env && grep -E '^(- )?Decision: price check' .agents/plans/reshop-review/04-design-document-and-readme.md | grep -F -- "$IN_USD_PER_MTOK" | grep -F -- "$OUT_USD_PER_MTOK" | grep -F -- "$CHECKED_ON" | grep -c 'https://'` prints at least `1`.

## Revision notes

2026-11-02: first draft, written from the planning index (S6, D19, D26, D27, D28, D30) and the repo state at writing time.

2026-11-02: critic round 1 fixes. The walkthrough now uses LM9P4C. D27 is copied from the index again. The AGENTS.md edit is removed from this plan, and the plan only checks it. Exit codes list 0, 1, 2, 3. The demo rate names no source. The model version claim is removed and kept in future work only. The DoD checks now compare real output with the docs and count sections and words. Measure labels, the Evidence and limits section, and the fact ownership rule are added. The cost figure comes from the stored recording usage.

2026-11-02, round 2: the critic round 2 findings are applied. The README sample comes from the recorded default run. Every DoD command with a variable is guarded against an empty pattern. Every Python one-liner uses `uv run python -I -c`. Future work adds the Policy as data bullet, moves every built row out of its table, and states "3 of 5". The AI-usage facts wait for Q2.

2026-11-02, owner answers: Q1 confirmed, `.env.example` keeps `gpt-6-luna`, and the owner's `.env.local` sets the local value. The demo rate is dated 2026-07-07, the fare snapshot's capture date. The README and the Built section name `./scripts/check.sh`, and the hosted pipeline is a new Next row. The README gains the scenario table as its second demo, DESIGN.md walks scenario c, and Milestone 7 adds the documented limits (D35).

2026-11-02, round 3: the status is blocked on the two owner recordings and Q2. Milestone 7 creates the Evidence heading and runs before Milestone 4, which appends to it. The /tmp artifacts have exact commands with a fixed line format, and each one is regenerated in its DoD step. The cost arithmetic moved from a command in DESIGN.md into `scripts/cost.py`, with one test. Measure labels follow the future-work rows: a tag needs a row, and limits with no planned work are plain statements under their own heading. Seat contention and masking get future-work rows. The output contract points to the schema test and the README sample. The SDK retry claim, the quick start paragraph, the Built section wording, the start script check and the price check record are changed as the findings asked. The fresh-context content review is a stated review step outside the DoD. The DoD drops the word-count floors, uses a Mermaid check on the first line and the arrow count, and has one heading check per file.

2026-11-02, realignment: the rules-only review is built on main, and its plan file is gone. The Status, Context and Scope sections now name the built package, `GLOSSARY.md` and the ADR as existing files. The Path, Output contract and Built sections match the built rule checks, `decided_by` value and check script. The What it does list gains the change-fee rule. The future-work check and the DoD test filter name the built test modules. The Decision Log gains one entry for this change. Plans 02 and 03 are not built, and their items are unchanged.

2026-11-02, plan 02 retired. Its model prices are copied into Surprises & Discoveries as the model price record, and the price check in the DoD greps this plan instead of the retired file.
