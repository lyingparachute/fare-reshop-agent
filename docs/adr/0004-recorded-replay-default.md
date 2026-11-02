---
status: accepted
date: 2026-11-02
---

# ADR 0004: The default run replays a recorded model run

## Context

Anyone who clones the repo should see what the model decided, with no API key, no network and no cost. A live run needs a key every time. The rules-only mode needs nothing, but it hides the model completely.

## Decision

The default mode replays a committed recording of one real model run per data set. I make each recording with one paid live run and commit the file.

Replay is not a cache of final results. The real loop, the real tools and the real safety check run every time. Only the model's replies come from the file.

The file holds a fingerprint (SHA-256) of each input: bookings, fares, policy, rates, prompt and tool definitions. Each recorded turn also holds a fingerprint of the transcript the model saw. If anything differs on replay, the run stops with exit code 3 and names what changed. It never replays an answer to a question that is no longer being asked.

## Consequences

- The default run shows real model replies and needs nothing beyond `uv sync`.
- Any change to the data, policy, rates, prompt, tools or rule results makes the recording stale. The stale error tells the reader to run `--model none`, which needs no key. A new recording needs a key and a paid run, as described in [the re-record runbook](../runbooks/re-record.md).
- `./scripts/check.sh` includes a test that the committed recordings match the committed data, so a stale recording cannot be committed by accident.
- During a recording, booking and fare facts go to the provider, and the recording stores the model's text. The fixtures hold no personal data. Real data would need masking first.
- The recording stores no API key, request id or provider response id.
- Revisit if the inputs change so often that re-recording costs more than giving every run a key.

## Alternatives rejected

| Alternative | Why not |
| --- | --- |
| Default to the rules-only mode | The default run would show no model decision at all. |
| Fall back to rules-only when the recording is stale | The output would silently change meaning. A reader must know the model is not in the run. |
| Record the raw HTTP traffic | It stores headers and provider ids, and ties replay to one SDK version. |
| Fingerprint the raw bytes of each data file | Reformatting a file would make the recording stale with no change in meaning. |
| One fingerprint for all inputs together | The stale error could not say which input changed. |
