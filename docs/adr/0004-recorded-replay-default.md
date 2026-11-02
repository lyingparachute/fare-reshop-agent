# 4. Recorded replay is the default run

## Status

Accepted

## Context

The default run must show what a real model decided for each booking, with no key, no network and no cost to the person who runs it. A live call needs a key every time, and the `none` mode (rules only) hides the model completely.

Related: [ADR 0003](0003-stateless-model-turn-seam.md).

## Decision

**The default mode replays a committed recording of one real run per data set.** The owner makes each recording with one paid run, and the file is committed to the repo.

Digests guard the file, one for each input of the run and one for each turn's transcript. The data, policy, rate and tool digests cover a projection of the domain value, so renaming a field or reformatting a data file does not stale a recording. The prompt digest covers the prompt file's bytes, and the repo keeps that file at LF. Replay refuses a stale recording (see the glossary).

Replay runs the real review loop and the tools for real. Only the model's replies come from the file. The safety check still re-reads the booking and the offer and recomputes the saving.

A recording is written atomically, and only after a run with no provider failure.

## Consequences

- Anyone can run the default review offline and see real model replies, with the same rules and safety check as a live run.
- A change to the bookings, offers, policy, rates, prompt or tool specs stales the recording, and so does a rule change that alters a tool result. The default run and the check script then fail until the owner pays for a re-record.
- Booking and offer facts reach the model provider during a recording, and the same facts are stored in the committed file. The fixtures hold no names or contact data, so nothing is masked. Real data would need masking first.
- The file stores the replies, the token usage, the model name and the digests. It stores no key, no request id and no provider response id.
- Revisit if the inputs change so often that re-recording costs more than a key for every run.

## Alternatives

| Option | Outcome |
| --- | --- |
| Default to the `none` mode | Rejected because the default run would show no model decision. |
| Record whole HTTP traffic | Rejected because it stores headers and provider ids and ties replay to one SDK. |
| Keep a `.partial` file for an interrupted run | Rejected because it is a second write path that no reader uses. |
| Digest the raw bytes of the data files | Rejected because a reformatted file would stale the recording with no change in meaning. |
| One digest for the whole header | Rejected because a stale error could not name the input that changed. |
