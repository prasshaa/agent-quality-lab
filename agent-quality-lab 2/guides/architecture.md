# Architecture — Agent Quality Lab V1

```text
Scenario
   ↓
Run Manager
   ↓
Simulated World ←→ Typed Tools ←→ Agent
   ↓
Trajectory
   ↓
Evaluators
   ├─ Deterministic
   ├─ Outcome
   └─ Qualitative Judge
   ↓
Risk Gates
   ↓
SHIP / CANARY / BLOCK
```

## Boundaries

**World = truth.** The simulator owns customers, trips, payments, refunds and policies.

**Agent = actor.** The agent interprets the user, retrieves context, decides whether to resolve/clarify/escalate, and proposes tool actions.

**Evaluator = observer.** Evaluators inspect the trajectory and final world state. They never alter the world.

## Engineering choices

- Python + Pydantic for simple typed contracts.
- Streamlit for the public V1 UI because it can deploy directly from GitHub.
- In-memory world state for runs; no external database required.
- No multi-agent framework in V1.
- No real production API calls or customer data.
- Critical authorization and financial correctness are deterministic, not delegated to the LLM.

## Public-hosting shape

GitHub is the source repository. Streamlit Community Cloud runs the Python app. This avoids requiring a separate frontend/backend deployment for the interview prototype.
