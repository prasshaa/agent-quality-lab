# Architecture

```text
Scenario Library / Custom Scenario
              |
        Scenario Runner
              |
        Isolated Simulator
              |
          Agent Adapter
              |
     Observable Agent Trace
              |
     +--------+---------+----------------+
     |                  |                |
Deterministic       Trajectory       LLM Judge
Evaluators          Evaluators        (pluggable)
     |                  |                |
     +------------------+----------------+
                        |
                Risk + Evidence
                   Aggregator
                        |
               Release Gate Engine
                        |
             SHIP / CANARY / BLOCK
                        |
               Failure Diagnosis
                        |
             Regression Scenario
```

## Adapter contract

A future model-powered agent should only need to produce:

- structured decision
- observable tool calls/results
- verification events
- final world outcome

The evaluation engine should not depend on a particular model vendor.

## Safety philosophy

- Sandbox all side effects.
- Separate read tools from side-effecting tools.
- Gate financial actions with deterministic authorization/policy checks.
- Use idempotency keys for transactional actions.
- Verify state after ambiguous failures/timeouts.
- Fail closed when material state is unknown.
- Never let customer text override evaluator or policy rules.
