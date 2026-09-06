# Agent Quality Lab

**A simulation-to-release quality system for autonomous AI agents.**

Agent Quality Lab tests an agent in a controlled customer-support world, evaluates its trajectory and real outcomes, diagnoses failures, and recommends **SHIP / CANARY / BLOCK**.

The current prototype focuses on **ride cancellation/refund** only. It is intentionally small: one simulated world, one agent runtime, typed tools, deterministic outcome checks, an LLM-style judge for qualitative behavior, and release gates.

## Why this exists

Average response quality is not enough for an autonomous agent. An agent can produce a polished answer while taking the wrong action. The Lab separates:

- **World:** objective ground truth
- **Agent:** actor making decisions and tool calls
- **Evaluator:** observer checking behavior and outcomes

The key question is:

> **What level of autonomy has this agent earned?**

## V1 demo

The public demo works without an API key using a deterministic production-minded agent simulator. It includes two agent versions:

- **V1:** strong baseline with a subtle high-risk ambiguity weakness
- **V2:** improves average quality and efficiency but introduces a critical wrong-payment regression

The Lab should catch the regression and recommend **BLOCK** even when aggregate quality improves.

An optional LLM mode can be wired later through an environment secret. No API key is required for the core demo.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy publicly

The simplest path is:

1. Push this repository to GitHub.
2. Sign in to Streamlit Community Cloud with GitHub.
3. Create an app pointing at `streamlit_app.py`.
4. Share the resulting `*.streamlit.app` URL.

No server management is needed for the V1 prototype.

## Repository structure

```text
agent-quality-lab/
├── agent/                 # agent runtime and decision logic
├── evaluation/            # deterministic, outcome, judge and release logic
├── scenarios/             # executable scenario definitions
├── simulator/             # world state, tools and transitions
├── tests/                 # unit + integration tests
├── guides/                # product/architecture notes
├── streamlit_app.py       # public demo UI
└── requirements.txt
```

## Safety note

This project uses synthetic data only. It does not connect to Uber systems, customer records, payments, or production APIs.
