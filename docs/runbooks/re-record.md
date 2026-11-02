# Re-record the model runs

A re-record costs money, so only the owner runs it. `./scripts/check.sh` never re-records: it makes no model call and needs no key.

## When to re-record

`test_committed_recording_matches_data` or `test_committed_recording_replays` fails in `./scripts/check.sh`. That happens after any change to:

- the bookings or the offers of a data set,
- the policy or the exchange rates,
- the review prompt or the tool specs,
- the tool code, including the rule checks a tool runs, when a tool result changes,
- the turn limit, when it drops below the turns of a recorded booking.

The failure message names the changed input and the command for that data set. `uv run fare-reshop doctor` shows a changed input on its recording line. A changed tool result or turn limit shows only in the replay test and in `uv run fare-reshop review`.

## Steps

1. Check that `.env.local` sets `OPENAI_API_KEY` and `OPENAI_MODEL`.
2. Record the sample data set:

   ```sh
   uv run --env-file .env.local --extra live fare-reshop review --data sample --model openai --record
   ```

3. Record the scenario data set:

   ```sh
   uv run --env-file .env.local --extra live fare-reshop review --data scenarios --model openai --record
   ```

4. Check that stderr ends with `recording written to recordings/review-run.json` or `recording written to recordings/scenarios-run.json`. A run that hits a provider failure writes nothing and names the booking and the error code. Run it again after the provider recovers. Each run costs money.
5. Replay each data set with no key:

   ```sh
   uv run fare-reshop review
   uv run fare-reshop review --data scenarios
   ```

6. Run `./scripts/check.sh`, then commit the changed files under `recordings/`.

## Cost

One run of a data set is expected to cost under 1 USD. The model makes one paid call per turn, and a booking gets at most 10 turns.

The sample run of 2026-11-02 on `gpt-5.4-mini` made 8 calls: 6,403 input tokens and 261 output tokens. At the list prices of 0.75 USD input and 4.50 USD output per 1M tokens, that is about 0.006 USD.

The scenario run of the same day made 21 calls: 17,820 input tokens and 664 output tokens, about 0.016 USD.
