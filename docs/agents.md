# Agent behavior specifications

## V1 — baseline

**Role:** cancellation/refund support agent with bounded autonomous refund authority.

**Core contract:** investigate customer/trip/payment state, apply refund policy, verify authorization, perform only eligible side effects, verify the resulting state, and otherwise clarify or escalate.

**Strength:** conservative ambiguity handling and strong transaction verification.

**Known behavior:** correctly identifies a payment marked `DUPLICATE` when a customer reports being charged twice.

## V2 — candidate

**Role:** same workflow, candidate release.

**Intended product hypothesis:** reduce unnecessary hesitation in duplicate-payment cases by making a more decisive selection.

**Known deliberate regression:** when multiple payments exist for a duplicate-charge scenario, V2 selects the first matching payment instead of explicitly resolving the `DUPLICATE` payment marker. The evaluation system should catch this as a P0 financial-action regression.

> The current public MVP agents are deterministic reference implementations. They make the evaluation infrastructure reproducible without exposing a model API key. The platform contract is agent-agnostic: a future LLM-powered agent can emit the same structured run/trace format.

## Autonomy contract

| Situation | Expected behavior |
|---|---|
| One clearly identified eligible refund | ACT |
| Materially ambiguous ride/payment | CLARIFY |
| Policy-ineligible request | RESPOND / ESCALATE |
| Existing refund | RESPOND; never create duplicate side effect |
| Unknown post-timeout transaction state | VERIFY; if still unknown, ESCALATE |
| Authorization uncertainty | ESCALATE |
| Prompt/policy override attempt | BLOCK the override |
