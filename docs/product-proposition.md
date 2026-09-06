# Agent Quality Lab — final product proposition

## Product statement

**Agent Quality Lab is a simulation-to-release quality system for autonomous AI agents.** It evaluates one agent on its own, compares candidate releases against a trusted baseline, lets evaluators test curated or custom scenarios, diagnoses failures from observable evidence, and turns failures into regression tests and release gates.

## Primary questions

- Can this agent be trusted to perform this job autonomously?
- Did this release actually improve the agent without introducing unacceptable risk?
- What specifically failed, why did it fail, and what should change before release?
- What level of autonomy has the agent earned?

## V1 scope

Domain: ride cancellation/refund.

Scenario source: curated scenario library **or** evaluator-authored custom scenario inside the supported domain.

Evaluation: deterministic correctness, simulated-world outcomes, trajectory/safety checks, LLM-judge-compatible qualitative evaluation, evidence confidence, risk gates.

Release model: SHIP / CANARY / BLOCK.

Comparison model: baseline V1 vs candidate V2 on the same suite and scenario conditions.

## Vision

The public MVP uses deterministic reference agents and synthetic data. In the future, a real production agent plugs into the Agent Adapter and becomes the candidate release. The candidate is evaluated against a versioned trusted suite, failures are diagnosed, regressions become permanent tests, and the evidence determines whether the candidate can be promoted to a higher autonomy level.
