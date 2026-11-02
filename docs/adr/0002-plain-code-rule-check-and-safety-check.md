# 2. Plain-code rule check before the model, safety check after it

## Status

Accepted

## Context

The live model mode adds an OpenAI model to the review. A model call costs money and time. A model can also write wrong numbers or pick an offer that breaks a rule. The rule checks and the money math are plain code, and they already decide every booking in the rules-only review. For most bookings, the rules settle the result alone: no offer is eligible, so the answer is keep, or the data is invalid. Only a booking with at least one eligible offer has a real choice to make. That choice can trade a saving against things code does not weigh, such as a schedule change. The model's role is to make that trade-off and explain it.

## Decision

Plain code runs the rule checks first, for every booking. The model sees only bookings with at least one eligible offer. The model picks one eligible offer or says keep, and writes the rationale and a confidence. The confidence is the model's own estimate, labeled "model estimate, not calibrated".

A safety check in plain code runs after the model's final answer. For a rebook, it checks that the offer is on this booking's route and date. Then it re-runs the rule checks and the nominal saving for that offer. The model's reply has no amount fields, so the code never reads a model figure. A failing choice becomes `NEEDS_REVIEW`, with the reason from the check. A valid choice that is not the highest saving stands as `REBOOK`, and `best_offer_id` names the highest one.

A model keep while an eligible offer exists becomes `NEEDS_REVIEW`, never `KEEP`. The rules found a saving that the model turned down. No code can tell whether that trade-off was right, so a person decides.

## Consequences

Bookings that the rules settle cost no model call. Each booking that reaches the model costs one extra plain-code evaluation of one offer after the model answers. That cost is small next to a model call, and it needs no network.

A reader can trust every amount in the output, because plain code computed it. Text from the model sits after the label "Model text:", so a reader can tell it from the code's facts. A `REBOOK` from the model passed the same rules and money math as a `REBOOK` from the rules. A reader sees more `NEEDS_REVIEW` rows than with a model that may keep freely. Each such row shows the rules' view and the model's rationale side by side.

The model cannot change a result that the rules settled. It can only choose among offers the rules already accepted, or send the booking to a person.

## Alternatives

A model prefilter first. It lost because it drops real savings before the free checks run.

The model on every booking. It lost because it pays for calls that code can settle, and the model could change a rules result.

Code decides and the model only writes text. It lost because it leaves no agent to show.

Trusting the model's numbers. It lost because wrong figures from the model are the core failure mode.

Forcing the highest saving. It lost because it overrides the trade-offs the model is there to weigh.

Letting a model keep stand as `KEEP`. It lost because a missed saving would pass unseen.
