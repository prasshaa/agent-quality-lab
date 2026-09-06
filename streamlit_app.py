from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from evaluation.runner import compare_suites, run_scenario, run_suite
from scenarios.library import scenarios

st.set_page_config(
    page_title="Agent Quality Lab",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCENARIOS = scenarios()
SCENARIO_BY_ID = {s["id"]: s for s in SCENARIOS}


def badge(status: str) -> str:
    return {
        "SHIP": "🟢 SHIP",
        "CANARY": "🟡 CANARY",
        "BLOCK": "🔴 BLOCK",
        "PASS": "🟢 PASS",
        "FAIL": "🔴 FAIL",
        "WARN": "🟡 WARN",
    }.get(status, status)


def severity_label(severity: str) -> str:
    return {"P0": "🔴 Critical", "P1": "🟠 Significant", "P2": "🟡 Minor", "NONE": "✓ Passed"}.get(severity, severity)


def render_finding(f: dict, compact: bool = False) -> None:
    severity = f.get("severity", "NONE")
    if severity == "NONE":
        st.markdown(f"**✓ {f['dimension'].replace('_', ' ').title()}** — {f['message']}")
    else:
        st.markdown(f"**{severity_label(severity)} · {f['dimension'].replace('_', ' ').title()}**")
        st.write(f["message"])
    if f.get("evidence") and not compact:
        with st.expander("Show evidence"):
            st.json(f["evidence"])


def result_card(result: dict, title: str | None = None) -> None:
    if title:
        st.markdown(f"### {title}")

    status = result.get("release_status") or ("BLOCK" if result.get("p0", 0) else "PASS")
    if status == "BLOCK":
        st.error(f"{badge(status)}")
    elif status == "CANARY":
        st.warning(f"{badge(status)}")
    else:
        st.success(f"{badge(status)}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Quality", f"{result['quality_score']:.1f}%")
    c2.metric("Critical failures", result["p0"])
    c3.metric("Significant failures", result["p1"])
    c4.metric("Agent action", result["decision"]["decision"])


def render_trace(trace: list[dict]) -> None:
    for i, event in enumerate(trace, start=1):
        event_type = event.get("type", "EVENT")
        tool = event.get("tool")
        label = f"{i:02d} · {event_type}" + (f" · {tool}" if tool else "")
        with st.expander(label, expanded=False):
            st.json(event)


def render_world_summary(world: dict) -> None:
    payments = world.get("payments", [])
    trips = world.get("trips", [])
    refunds = world.get("refunds", [])
    st.markdown("**What changed in the simulated world?**")
    cols = st.columns(3)
    cols[0].metric("Rides", len(trips))
    cols[1].metric("Payments", len(payments))
    cols[2].metric("Refunds completed", len([r for r in refunds if r.get("status") == "COMPLETED"]))

    payment_rows = [
        {
            "Payment": p.get("payment_id"),
            "Ride": p.get("trip_id"),
            "Amount": f"₹{float(p.get('amount', 0)):.0f}",
            "Final status": p.get("status"),
            "Type": p.get("kind", "—").replace("_", " ").title(),
        }
        for p in payments
    ]
    if payment_rows:
        st.dataframe(payment_rows, use_container_width=True, hide_index=True)


def render_scenario_context(scenario: dict) -> None:
    st.markdown("#### What is being tested?")
    st.write(scenario["description"])
    st.info(f"**Customer says:** “{scenario['user_messages'][-1]}”")

    meta = scenario["metadata"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Risk", meta["risk"])
    m2.metric("Ambiguity", meta["ambiguity"])
    m3.metric("Test type", meta["category"].replace("_", " ").title())


def render_run_result(result: dict) -> None:
    status = "BLOCK" if result["p0"] else "PASS"
    result["release_status"] = status
    result_card(result)

    st.markdown("#### What happened?")
    st.write(result["decision"]["message"])

    with st.expander("See why the Lab reached this result", expanded=True):
        failures = [f for f in result["findings"] if f["severity"] != "NONE"]
        passes = [f for f in result["findings"] if f["severity"] == "NONE"]
        if failures:
            for finding in failures:
                render_finding(finding)
        else:
            st.success("All required checks passed for this scenario.")
        if passes:
            with st.expander(f"{len(passes)} checks passed"):
                for finding in passes:
                    render_finding(finding, compact=True)

    with st.expander("See the simulated world"):
        render_world_summary(result["world"])

    st.markdown("#### Follow the evidence")
    st.caption("The trace is the step-by-step evidence behind the result. It shows what the agent asked the system to do and what actually happened.")
    render_trace(result["trace"])

    st.download_button(
        "Download this run as JSON",
        data=json.dumps(result, indent=2),
        file_name=f"{result['scenario_id']}-{result['agent_version']}.json",
        mime="application/json",
    )


# -----------------------------
# Header / navigation
# -----------------------------
st.title("🧪 Agent Quality Lab")
st.caption("Test whether a ride-booking AI agent has earned the right to act autonomously.")

with st.sidebar:
    st.markdown("## Agent Quality Lab")
    st.caption("A simulation-to-release quality system for AI agents in ride-booking applications.")
    st.divider()
    st.markdown("**The journey**")
    st.markdown("1. **Understand** what the Lab tests\n2. **Run** an agent against realistic scenarios\n3. **Inspect** what actually happened\n4. **Compare** a candidate with its baseline\n5. **Decide** Ship, Canary, or Block")
    st.divider()
    st.markdown("**Release outcomes**")
    st.markdown("🟢 **SHIP** — evidence supports release\n\n🟡 **CANARY** — controlled exposure recommended\n\n🔴 **BLOCK** — a critical issue must be fixed")

# Keep navigation intentionally user-facing rather than architecture-facing.
overview_tab, run_tab, compare_tab = st.tabs(["🏠 Overview", "▶ Run & Investigate", "📊 Release Comparison"])

with overview_tab:
    st.markdown("# What is Agent Quality Lab?")
    st.markdown(
        """
        **Agent Quality Lab is a testing and release-readiness system for AI agents.**

        Instead of asking only *“Did the AI give a good answer?”*, the Lab puts an agent inside a **realistic simulated ride-booking environment** and asks a more important question:

        > **Can we trust this agent to take the right action, safely, when it is given autonomy?**

        The Lab creates realistic customer situations, lets the agent investigate and act through tools, checks the **actual simulated outcome**, and then recommends whether a new agent version should **Ship, Canary, or Block**.
        """
    )

    st.markdown("## Why this exists")
    st.write(
        "AI agents can produce convincing responses while making a serious mistake behind the scenes. "
        "For example, an agent might tell a customer that a duplicate charge was refunded while actually refunding the legitimate payment. "
        "A quality system therefore needs to evaluate the agent's behavior and outcome—not just its final words."
    )

    st.markdown("## How the Lab works")
    steps = [
        ("1", "Scenario", "Give the agent a realistic customer situation with a known ground truth."),
        ("2", "Simulated world", "The agent operates on synthetic customers, rides, payments and refund policies—not real Uber data."),
        ("3", "Agent run", "The agent investigates, uses tools, makes a decision and takes an action when authorized."),
        ("4", "Evaluation", "The Lab checks objective correctness, actual world outcome and customer-facing quality."),
        ("5", "Evidence", "Every important step is recorded so a PM or engineer can understand what happened."),
        ("6", "Release decision", "The Lab recommends Ship, Canary or Block based on risk and evaluation results."),
    ]
    cols = st.columns(3)
    for i, (num, title, description) in enumerate(steps):
        with cols[i % 3]:
            st.markdown(f"### {num}. {title}")
            st.write(description)

    st.markdown("## What do V1 and V2 mean?")
    st.markdown(
        """
        **V1 = baseline agent.** This is the existing version we trust as our comparison point.

        **V2 = candidate agent.** This is the newer version we are considering releasing. It may improve average quality or efficiency, but it can also introduce a regression.

        The Lab compares **the agents across the same evaluation suite**. It is not simply comparing two answers to one scenario. You can then drill into a specific scenario to understand *why* the versions differ.
        """
    )

    st.markdown("## What do the evaluation terms mean?")
    definitions = [
        ("Scenario", "One realistic situation used to test the agent."),
        ("Suite", "A collection of scenarios used to evaluate an agent version as a release."),
        ("Trajectory / Trace", "The observable sequence of messages, tool calls, checks, actions and outcomes during one run."),
        ("Ground truth", "What is objectively true in the simulated world and what outcome the scenario requires."),
        ("Deterministic evaluation", "Checks objective facts such as the correct payment, amount, policy and final state."),
        ("LLM judge", "A qualitative evaluator for things that are harder to verify deterministically, such as clarity and customer experience."),
        ("P0", "Critical failure. A release-blocking safety, financial, authorization or outcome error."),
        ("P1", "Significant reliability or quality issue that may require controlled exposure."),
        ("P2", "Minor quality issue, such as wording or unnecessary steps."),
    ]
    st.dataframe(
        [{"Term": term, "Meaning": meaning} for term, meaning in definitions],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("## What is the key idea?")
    st.success(
        "**LLM-as-a-judge is only one evaluator inside the Lab.** The Lab combines the agent's observable behavior, "
        "the actual simulated outcome, deterministic safety checks and qualitative evaluation to decide whether the agent has earned more autonomy."
    )

    st.markdown("## Start here")
    st.info("👉 Go to **Run & Investigate** to run one scenario and see the entire story—from customer request to agent action to evaluation result.")

    with st.expander("What is intentionally simulated?"):
        st.write(
            "This prototype uses synthetic ride-booking data. It is inspired by the kinds of agent-quality problems relevant to ride-booking applications, "
            "but it does not use Uber's internal systems, APIs, customer data or proprietary architecture."
        )

with run_tab:
    st.markdown("# Run & Investigate")
    st.write("Run one scenario when you want to understand an agent's behavior in detail. V1 and V2 each get a **fresh copy of the same simulated world**, so their runs are independent and directly comparable.")

    selected = st.selectbox(
        "Choose a scenario",
        [s["id"] for s in SCENARIOS],
        format_func=lambda x: f"{x} — {SCENARIO_BY_ID[x]['name']}",
    )
    scenario = SCENARIO_BY_ID[selected]
    render_scenario_context(scenario)

    st.markdown("## Choose what you want to investigate")
    mode = st.radio(
        "",
        ["Compare V1 and V2 on this scenario", "Run one agent version"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if mode == "Run one agent version":
        version = st.radio("Agent version", ["v1", "v2"], horizontal=True)
        if st.button("▶ Run scenario", type="primary", use_container_width=True):
            progress = st.progress(0, text="Preparing the simulated world…")
            progress.progress(25, text="Running the agent and its tools…")
            with st.spinner("The agent is investigating the scenario…"):
                result = run_scenario(scenario, version)
            progress.progress(75, text="Checking the agent's behavior and outcome…")
            result["release_status"] = "BLOCK" if result["p0"] else "PASS"
            progress.progress(100, text="Evaluation complete")
            st.session_state["last_run"] = result
            st.session_state["last_run_scenario"] = selected
            st.session_state["last_run_version"] = version
            st.session_state["investigation_v1"] = result if version == "v1" else st.session_state.get("investigation_v1")
            st.session_state["investigation_v2"] = result if version == "v2" else st.session_state.get("investigation_v2")

        result = st.session_state.get("last_run")
        if result:
            st.divider()
            render_run_result(result)
    else:
        st.caption("This answers: **Did V1 and V2 behave differently on this exact scenario?**")
        if st.button("▶ Run V1 and V2", type="primary", use_container_width=True):
            progress = st.progress(0, text="Creating two identical simulated worlds…")
            with st.spinner("Running V1…"):
                v1_result = run_scenario(scenario, "v1")
            progress.progress(50, text="V1 complete · running V2…")
            with st.spinner("Running V2…"):
                v2_result = run_scenario(scenario, "v2")
            progress.progress(100, text="Both versions evaluated")
            st.session_state["investigation_v1"] = v1_result
            st.session_state["investigation_v2"] = v2_result
            st.session_state["last_run"] = v2_result
            st.session_state["last_run_scenario"] = selected

        v1_result = st.session_state.get("investigation_v1")
        v2_result = st.session_state.get("investigation_v2")
        if v1_result and v2_result and v1_result["scenario_id"] == selected and v2_result["scenario_id"] == selected:
            st.divider()
            st.markdown("## Same scenario, two agent versions")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### V1 — baseline")
                result_card(v1_result)
            with c2:
                st.markdown("### V2 — candidate")
                result_card(v2_result)

            if v1_result["decision"] == v2_result["decision"] and v1_result["p0"] == v2_result["p0"] and v1_result["quality_score"] == v2_result["quality_score"]:
                st.info("**No measurable difference on this scenario.** That is expected: V1 and V2 are not supposed to behave differently on every test. The release comparison checks the full suite to find meaningful regressions and improvements.")
            else:
                st.warning("**There is a measurable difference on this scenario.** Open the evidence below to see where their behavior diverged.")

            comparison_rows = []
            for label, a, b in [
                ("Quality", v1_result["quality_score"], v2_result["quality_score"]),
                ("Critical failures (P0)", v1_result["p0"], v2_result["p0"]),
                ("Significant failures (P1)", v1_result["p1"], v2_result["p1"]),
            ]:
                comparison_rows.append({"Measure": label, "V1": a, "V2": b, "Change": round(b - a, 1) if isinstance(a, float) else b - a})
            st.dataframe(comparison_rows, use_container_width=True, hide_index=True)

            with st.expander("Inspect V1 evidence"):
                render_run_result(v1_result)
            with st.expander("Inspect V2 evidence"):
                render_run_result(v2_result)

with compare_tab:
    st.markdown("# Release Comparison")
    st.write(
        "This is the **release-level view**. It compares the baseline agent (V1) and candidate agent (V2) across the same cancellation/refund evaluation suite. "
        "The goal is to answer: **Did V2 improve enough—and remain safe enough—to release?**"
    )

    st.info("💡 **This compares the agents across the full suite, not just one scenario.** After the run, you can open any changed scenario and inspect its evidence.")

    if st.button("▶ Run release evaluation: V1 vs V2", type="primary", use_container_width=True):
        progress = st.progress(0, text="Running V1 baseline across the evaluation suite…")
        with st.spinner("Evaluating V1 across all scenarios…"):
            v1 = run_suite(SCENARIOS, "v1")
        progress.progress(50, text="V1 complete · running V2 candidate…")
        with st.spinner("Evaluating V2 across all scenarios…"):
            v2 = run_suite(SCENARIOS, "v2")
        progress.progress(90, text="Comparing releases and checking gates…")
        comparison = compare_suites(v1, v2)
        progress.progress(100, text="Release evaluation complete")
        st.session_state["comparison"] = comparison
        st.session_state["v1_suite"] = v1
        st.session_state["v2_suite"] = v2

    comparison = st.session_state.get("comparison")
    if comparison:
        v1_release = comparison["v1"]
        v2_release = comparison["v2"]

        st.markdown("## Release recommendation for V2")
        if v2_release["status"] == "BLOCK":
            st.error(f"# {badge(v2_release['status'])}\n\n{v2_release['rationale']}")
        elif v2_release["status"] == "CANARY":
            st.warning(f"# {badge(v2_release['status'])}\n\n{v2_release['rationale']}")
        else:
            st.success(f"# {badge(v2_release['status'])}\n\n{v2_release['rationale']}")

        st.markdown("## What changed from V1 to V2?")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Quality", f"{v2_release['avg_quality']:.1f}%", delta=f"{comparison['quality_delta']:+.1f} pts")
        c2.metric("P0 failures", v2_release["p0"], delta=f"{comparison['p0_delta']:+d}", delta_color="inverse")
        c3.metric("P1 failures", v2_release["p1"], delta=f"{comparison['p1_delta']:+d}", delta_color="inverse")
        c4.metric("Scenarios", f"{v2_release['scenarios_executed']}/{v2_release['scenarios_executed']}")

        st.markdown("## Why did the Lab make this recommendation?")
        if comparison["regressions"]:
            st.error(f"The Lab found **{len(comparison['regressions'])} scenario(s) where V2 regressed or introduced a critical failure.**")
            st.dataframe(comparison["regressions"], use_container_width=True, hide_index=True)
        else:
            st.success("No meaningful scenario-level regressions were detected.")

        st.markdown("## Investigate a specific scenario")
        v2_results = {r["scenario_id"]: r for r in st.session_state["v2_suite"]["results"]}
        v1_results = {r["scenario_id"]: r for r in st.session_state["v1_suite"]["results"]}
        selected_compare = st.selectbox(
            "Choose a scenario to drill into",
            [s["id"] for s in SCENARIOS],
            format_func=lambda x: f"{x} — {SCENARIO_BY_ID[x]['name']}",
            key="comparison_scenario",
        )
        a = v1_results[selected_compare]
        b = v2_results[selected_compare]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### V1")
            result_card(a)
        with c2:
            st.markdown("### V2")
            result_card(b)

        if a["p0"] or b["p0"] or a["quality_score"] != b["quality_score"]:
            st.markdown("#### Evidence")
            e1, e2 = st.columns(2)
            with e1:
                st.caption("V1 trajectory")
                render_trace(a["trace"])
            with e2:
                st.caption("V2 trajectory")
                render_trace(b["trace"])
        else:
            st.info("The two versions behaved the same on this scenario. Try a scenario highlighted in the regression table to see the Lab's strongest finding.")

        st.download_button(
            "Download release comparison JSON",
            data=json.dumps(comparison, indent=2),
            file_name="v1-v2-release-comparison.json",
            mime="application/json",
        )

st.caption("Prototype uses synthetic data and a deterministic demo judge; no production ride-booking or customer data is used.")
