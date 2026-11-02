# 3. Stateless model turn seam

## Status

Accepted

## Context

The live model mode runs a loop for each booking: call the model, run the tools it asks for, and call it again, until it gives a final answer or a limit ends the booking. The loop must work the same with the OpenAI model, a scripted fake in tests, and a recorded run that replays offline. The provider can keep conversation state on its side and link each reply to the last one by an id. Provider state would tie the loop to one provider, and a replay could not reproduce it. Provider errors such as a timeout or a rate limit are normal outcomes for one booking, not bugs.

## Decision

The model seam is one call: `AgentModel.next_step(transcript) -> ModelReply`. Each call is one turn. Every adapter also exposes `model_name`.

The seam is stateless. The transcript holds everything the model needs, and each turn sends the whole transcript with `store` off. The loop builds a longer transcript after each turn.

A `ModelReply` is one of four frozen types:

- `ToolCalls`: the calls, each with its name and raw argument text, an optional text, and the turn's token usage.
- `FinalText`: the text and the usage.
- `Refusal`: the refusal text and the usage.
- `ProviderFailed`: one code from a closed set (`connection`, `timeout`, `rate_limit`, `server_error`).

A provider failure is a typed reply, not an exception. The loop assigns call ids (`call_<turn>_<n>`) once. Adapters only translate them to and from provider ids. The loop, the turn cap, the repeat rule and all parsing of the model's output live in `orchestration/`.

## Consequences

An adapter is thin. It translates one transcript into one request and one response into one reply. The OpenAI adapter and the scripted fake share one loop, and a replay adapter will join them. The loop's rules hold for every adapter and are tested once, offline.

Each turn resends the whole transcript, so input tokens grow with each turn. The cap of 10 turns per booking bounds that cost.

The loop must match all four reply types, and the type checker enforces that. A timeout or a rate limit ends one booking as `INCOMPLETE_ANALYSIS` with `provider_error`, and the run goes on. A reader sees the closed error code in the trace, never provider text.

## Alternatives

A whole-run seam, where the adapter runs the full review. It lost because it copies the loop into every adapter.

A stateful session that chains replies on the provider side. It lost because it leaks provider response chaining into the seam, and a replay could not reproduce it.

A raised exception for provider failures. It lost because a typed outcome would then look like a bug.
