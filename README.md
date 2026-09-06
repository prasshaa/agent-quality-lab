# Agent Quality Lab

**A simulation-to-release quality system for autonomous AI agents.**

Agent Quality Lab evaluates an individual agent and compares candidate releases using layered evidence: deterministic checks, simulated-world outcomes, trajectory/safety evaluation, an LLM-judge-compatible qualitative layer, evidence confidence and risk-weighted release gates.

## What you can do

1. **Evaluate one agent** — run the full suite or one selected scenario and decide whether the agent is release-ready.
2. **Compare releases** — compare V2 against a trusted V1 baseline on the same suite and identify improvements/regressions.
3. **Test a scenario** — choose a curated case or describe your own cancellation/refund situation and run it inside the sandbox.
4. **Investigate failures** — move from release decision → failed scenario → evidence → trace → root cause → regression test.

## MVP scope

The public MVP uses synthetic ride cancellation/refund data and deterministic reference agents so it is reproducible without an API key. The architecture is agent-agnostic and can later accept an LLM-powered agent through an adapter.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

## Safety

No real customer records, payments or production APIs are used. All side effects happen in an isolated simulator with policy and transaction safeguards.
