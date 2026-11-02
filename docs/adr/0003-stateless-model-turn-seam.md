---
status: accepted
date: 2026-11-02
---

# ADR 0003: The model is called one stateless turn at a time

## Context

For each booking the model works in a loop. It asks for a tool, gets the result, and asks again until it answers. The same loop has to work with three kinds of model: the live OpenAI model, a scripted fake in the tests, and a replay of a recorded run.

The OpenAI API can keep the conversation on its side and chain each reply to the previous one by an id. That state lives with the provider, so a test fake or a replay cannot reproduce it.

## Decision

The model interface is one call: `next_step(transcript) -> reply`. The transcript holds everything the model has seen for this booking, and every turn sends all of it, with provider storage off.

A reply is one of four types: tool calls, a final answer, a refusal, or a provider failure. A provider failure, such as a timeout or a rate limit, is a normal reply with a fixed error code, not an exception.

The loop, the 10-turn cap, the rule against repeating the same call, and the parsing of the model's answer all live in one place, outside the adapters.

## Consequences

- An adapter only translates a transcript into a request, and a response into a reply.
- The loop's limits and failure paths are tested once, offline, with the fake.
- Input tokens grow with each turn, because each turn resends the whole transcript. The turn cap bounds that. Prompt caching would cut the cost of the repeated part.
- A timeout or a rate limit ends one booking as `INCOMPLETE_ANALYSIS`, and the run goes on with the next booking. The trace shows the error code, never the provider's message.
- Revisit if a model needs its reasoning sent back to it between turns. That state would then have to go into the transcript.

## Alternatives rejected

| Alternative | Why not |
| --- | --- |
| The adapter runs the whole review | Each adapter would carry its own copy of the loop and its limits. |
| Chain replies on the provider side by id | Replay and tests could not reproduce the provider's state. |
| Raise an exception on a provider failure | A timeout is an expected outcome for one booking, not a bug that should stop the run. |
