# Evaluation methodology

Agent Quality Lab uses layered evidence. No single metric is the source of truth.

1. **Deterministic evaluators** check objective facts: entity selection, amounts, policy outcomes, tool gating, duplicate side effects, verified state.
2. **Outcome/state evaluators** check whether the simulated world ended in the required state.
3. **Trajectory evaluators** inspect the observable tool/verification path and failure recovery.
4. **LLM-judge layer** evaluates softer qualities such as clarity and usefulness. The public demo uses a rules-based proxy with an explicit upgrade path to a real judge provider; the product treats the judge as one sensor rather than ground truth.
5. **Risk gates** classify failures as P0/P1/P2. P0 safety or financial-action failures block release regardless of average quality.
6. **Evidence confidence** measures strength of the evaluation evidence from ground-truth availability, evaluator agreement, trace completeness and scenario provenance. It is distinct from the agent's own confidence score.
7. **Release decision** maps the evidence into SHIP / CANARY / BLOCK and an autonomy level.

## Key principle

A fluent response cannot override an objective safety failure. If the agent says it issued a refund but the expected transaction was not refunded, the outcome evaluator wins.
