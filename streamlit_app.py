from __future__ import annotations

import json
import re
import time
from datetime import datetime

import streamlit as st

from evaluation.runner import compare_suites, run_scenario, run_suite
from scenarios.library import get_scenario, scenarios

st.set_page_config(page_title="Agent Quality Lab", page_icon="🧪", layout="wide", initial_sidebar_state="expanded")

SCENARIOS = scenarios()
SCENARIO_BY_ID = {s["id"]: s for s in SCENARIOS}


def badge(status: str) -> str:
    return {"SHIP": "🟢 SHIP", "CANARY": "🟡 CANARY", "BLOCK": "🔴 BLOCK", "PASS": "🟢 PASS", "FAIL": "🔴 FAIL", "WARN": "🟡 WARN"}.get(status, status)


def severity_label(severity: str) -> str:
    return {"P0": "🔴 P0 — Critical", "P1": "🟠 P1 — Significant", "P2": "🟡 P2 — Minor", "NONE": "✓ Passed"}.get(severity, severity)


def status_icon(status: str) -> str:
    return {"PASS": "✓", "FAIL": "✕", "WARN": "!"}.get(status, "•")


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem;}
        .hero {padding: 1.4rem 1.6rem; border: 1px solid rgba(128,128,128,.25); border-radius: 18px; background: linear-gradient(135deg, rgba(120,120,120,.06), rgba(120,120,120,.015));}
        .eyebrow {font-size:.78rem; letter-spacing:.12em; text-transform:uppercase; opacity:.65; font-weight:700;}
        .hero h1 {font-size:2.4rem; margin:.35rem 0 .6rem 0;}
        .hero p {font-size:1.08rem; line-height:1.55; max-width:900px;}
        .mini {border:1px solid rgba(128,128,128,.22); border-radius:14px; padding:1rem; height:100%;}
        .mini b {font-size:1.15rem;}
        .step {border:1px solid rgba(128,128,128,.18); border-radius:12px; padding:.8rem 1rem; margin-bottom:.5rem;}
        .step-current {border-width:2px;}
        .result-title {font-size:1.3rem; font-weight:700;}
        .muted {opacity:.7;}
        .small {font-size:.88rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_finding(f: dict, compact: bool = False) -> None:
    if f["severity"] == "NONE":
        st.markdown(f"**{status_icon(f['status'])} {f['dimension'].replace('_', ' ').title()}** · {f['message']}")
    else:
        st.markdown(f"**{severity_label(f['severity'])} · {f['dimension'].replace('_', ' ').title()}**")
        st.write(f["message"])
    if f.get("evidence") and not compact:
        with st.expander("Evidence"):
            st.json(f["evidence"])


def render_evaluation_summary(result: dict) -> None:
    status = "BLOCK" if result["p0"] else "CANARY" if result["p1"] else "PASS"
    st.markdown(f"### {badge(status)}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Quality", f"{result['quality_score']:.1f}%")
    c2.metric("P0", result["p0"])
    c3.metric("P1", result["p1"])
    c4.metric("Evidence", result["confidence"]["level"])
    c5.metric("Agent decision", result["decision"]["decision"])


def render_progress(stage: str, scenario_idx: int, total: int) -> None:
    stages = ["SETUP", "SIMULATE", "EXECUTE", "EVALUATE", "SAFETY", "DIAGNOSE", "RELEASE"]
    idx = stages.index(stage)
    pct = (idx + 1) / len(stages)
    st.progress(pct, text=f"Stage {idx+1} of {len(stages)} · {stage.title()} · scenario {scenario_idx}/{total}")
    cols = st.columns(len(stages))
    for i, name in enumerate(stages):
        state = "✓" if i < idx else "●" if i == idx else "○"
        cols[i].markdown(f"**{state} {name.title()}**")


def run_with_progress(selected_scenarios: list[dict], agent_version: str) -> dict:
    progress = st.empty()
    status_box = st.empty()
    results = []
    total = len(selected_scenarios)

    render_progress("SETUP", 0, total)
    status_box.info(f"Preparing {total} isolated scenario world(s) for **{agent_version.upper()}**…")
    time.sleep(0.25)
    render_progress("SIMULATE", 0, total)
    status_box.info("Creating fresh synthetic worlds so each run starts from the same ground truth…")
    time.sleep(0.25)

    for i, scenario in enumerate(selected_scenarios, 1):
        render_progress("EXECUTE", i, total)
        status_box.info(f"Running **{scenario['name']}**")
        time.sleep(0.12)
        raw = run_scenario(scenario, agent_version)
        results.append(raw)
        render_progress("EVALUATE", i, total)
        status_box.info(f"Running deterministic, outcome, trajectory and qualitative evaluators for scenario {i}/{total}…")
        time.sleep(0.12)
        if raw["p0"]:
            render_progress("SAFETY", i, total)
            status_box.warning(f"⚠ {raw['p0']} critical failure(s) found in **{scenario['name']}**. Continuing evaluation so the final decision includes complete evidence.")
        else:
            render_progress("SAFETY", i, total)
            status_box.success(f"Safety gates passed for **{scenario['name']}**.")
        time.sleep(0.1)
        render_progress("DIAGNOSE", i, total)
        time.sleep(0.08)

    render_progress("RELEASE", total, total)
    release = __import__("evaluation.engine", fromlist=["release_decision"]).release_decision(results, required_scenarios=total)
    status_box.empty()
    progress.empty()
    return {"agent_version": agent_version, "results": results, "release": release}


def render_trace(trace: list[dict]) -> None:
    labels = {
        "USER_MESSAGE": "Customer request",
        "TOOL_CALL": "Tool requested",
        "TOOL_RESULT": "Tool result",
        "STATE_UPDATE": "Selection / state",
        "POLICY_CHECK": "Policy gate",
        "AUTHORIZATION": "Authorization gate",
        "VERIFICATION": "Outcome verification",
        "DECISION": "Agent decision",
    }
    for i, event in enumerate(trace, 1):
        label = labels.get(event.get("type"), event.get("type", "Event"))
        detail = event.get("tool") or event.get("reason") or event.get("decision") or ""
        with st.expander(f"{i:02d} · {label}" + (f" · {detail}" if detail else "")):
            if event.get("type") == "TOOL_CALL":
                st.write(f"**Tool:** `{event.get('tool')}`")
                st.json(event.get("input", {}))
            elif event.get("type") == "TOOL_RESULT":
                st.write(f"**Result:** {'Success' if event.get('success') else 'Failure'}")
                st.json({k: v for k, v in event.items() if k not in {"type", "tool"}})
            else:
                st.json({k: v for k, v in event.items() if k != "type"})


def render_run_detail(result: dict) -> None:
    render_evaluation_summary(result)
    st.info(f"**Why this result?** {next((f['message'] for f in result['findings'] if f['severity'] in {'P0','P1'}), 'All hard gates passed.')} ")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Expected")
        st.write(result["scenario_id"])
        expected = SCENARIO_BY_ID.get(result["scenario_id"], {}).get("expected", {})
        st.json(expected)
    with right:
        st.markdown("#### Actual")
        d = result["decision"]
        st.write(f"Decision: **{d['decision']}**")
        st.write(result["decision"]["message"])
        st.json({k: d.get(k) for k in ["intent", "trip_id", "payment_id", "amount", "confidence", "ambiguity"]})

    st.markdown("#### Why did the Lab reach this result?")
    failures = [f for f in result["findings"] if f["severity"] != "NONE"]
    passes = [f for f in result["findings"] if f["severity"] == "NONE"]
    for f in failures:
        render_finding(f)
    if not failures:
        st.success("All hard correctness and safety checks passed.")
    with st.expander(f"Show {len(passes)} passing checks"):
        for f in passes:
            render_finding(f, compact=True)

    st.markdown("#### Evidence: execution timeline")
    st.caption("This is the observable evidence behind the decision. Raw JSON is available inside each step for engineering review.")
    render_trace(result["trace"])


def build_custom_scenario(message: str, expected_mode: str) -> tuple[dict | None, str]:
    text = message.strip()
    if not text:
        return None, "Enter a customer request first."
    lower = text.lower()
    supported = any(term in lower for term in ["ride", "trip", "charged", "charge", "refund", "cancel", "payment", "airport"])
    if not supported:
        return None, "This MVP is scoped to cancellation/refund workflows involving rides, payments or refunds."

    amount_match = re.search(r"(?:₹|rs\.?|inr|\$)\s*(\d+(?:\.\d+)?)", lower)
    amount = float(amount_match.group(1)) if amount_match else 350.0
    duplicate = "twice" in lower or "duplicate" in lower or "double charged" in lower
    already = "already refunded" in lower or "refund was processed" in lower
    ambiguous = any(term in lower for term in ["yesterday", "last ride", "my ride"]) and "which" in lower

    if expected_mode == "Auto-detect":
        resolution = "ALREADY_REFUNDED" if already else "CLARIFY" if ambiguous else "REFUND"
    else:
        resolution = {"Refund": "REFUND", "Clarify": "CLARIFY", "No refund": "NO_REFUND", "Already refunded": "ALREADY_REFUNDED"}[expected_mode]

    trip_status = "CANCELLED" if "cancel" in lower else "COMPLETED"
    payment_kind = "DUPLICATE" if duplicate else "LEGITIMATE"
    scenario_id = f"custom_{abs(hash(text)) % 100000:05d}"
    expected = {"resolution": resolution}
    if resolution == "REFUND":
        expected.update({"trip_id": "trip_custom", "payment_id": "pay_custom_b" if duplicate else "pay_custom", "refund_amount": amount})
    elif resolution == "ALREADY_REFUNDED":
        expected.update({"trip_id": "trip_custom", "payment_id": "pay_custom", "refund_amount": amount})
    scenario = {
        "id": scenario_id,
        "name": "Custom evaluator scenario",
        "description": "Evaluator-authored cancellation/refund situation created from natural language input.",
        "user_messages": [text],
        "world": {
            "customers": [{"customer_id": "cust_custom", "name": "Test Customer"}],
            "trips": [{"trip_id": "trip_custom", "customer_id": "cust_custom", "status": trip_status, "fare": amount}],
            "payments": [{"payment_id": "pay_custom", "customer_id": "cust_custom", "trip_id": "trip_custom", "amount": amount, "status": "REFUNDED" if already else "CHARGED", "kind": "LEGITIMATE"}],
            "refunds": ([{"refund_id": "ref_existing", "payment_id": "pay_custom", "customer_id": "cust_custom", "trip_id": "trip_custom", "amount": amount, "status": "COMPLETED", "reason": "prior_refund", "idempotency_key": "existing"}] if already else []),
            "policies": [{"policy_id": "policy_custom", "auto_refund_max": 1000.0, "eligible_reasons": ["charged_after_cancellation", "duplicate_charge"], "requires_human_review": ["fraud"]}],
            "support_cases": [],
        },
        "expected": expected,
        "metadata": {"risk": "HIGH" if duplicate or "refund" in lower else "MEDIUM", "ambiguity": "HIGH" if ambiguous else "NONE", "category": "CUSTOM", "coverage": "CUSTOM"},
    }
    if duplicate and resolution == "REFUND":
        scenario["world"]["payments"] = [
            {"payment_id": "pay_custom_a", "customer_id": "cust_custom", "trip_id": "trip_custom", "amount": amount, "status": "CHARGED", "kind": "LEGITIMATE"},
            {"payment_id": "pay_custom_b", "customer_id": "cust_custom", "trip_id": "trip_custom", "amount": amount, "status": "CHARGED", "kind": "DUPLICATE"},
        ]
    if resolution == "CLARIFY":
        scenario["world"]["trips"] = [
            {"trip_id": "trip_custom_a", "customer_id": "cust_custom", "status": trip_status, "fare": amount, "pickup": "Home", "destination": "Office"},
            {"trip_id": "trip_custom_b", "customer_id": "cust_custom", "status": trip_status, "fare": amount, "pickup": "Airport", "destination": "Home"},
        ]
    return scenario, ""


inject_css()
st.title("🧪 Agent Quality Lab")
st.caption("A simulation-to-release quality system for autonomous AI agents — built around evidence, safety and release decisions.")

with st.sidebar:
    st.markdown("### The mental model")
    st.markdown("**Evaluate → Understand → Fix → Re-test → Release**")
    st.divider()
    st.markdown("**MVP domain**")
    st.caption("Ride cancellation & refunds · synthetic data only")
    st.markdown("**Agent versions**")
    st.caption("V1 trusted baseline · V2 candidate")
    st.markdown("**Core release rule**")
    st.caption("A P0 safety or financial-action failure blocks release, regardless of average quality.")

overview_tab, eval_tab, compare_tab, scenarios_tab, docs_tab = st.tabs([
    "Overview", "Evaluate an Agent", "Compare Releases", "Scenarios & Try It", "Agent & Eval Docs"
])

with overview_tab:
    st.markdown('<div class="hero"><div class="eyebrow">Simulation → evaluation → release</div><h1>Can this AI agent be trusted to act?</h1><p>Agent Quality Lab puts an agent inside a controlled, realistic cancellation/refund world, checks what it did and what actually happened, explains failures from observable evidence, and recommends whether the agent should Ship, Canary or Block.</p></div>', unsafe_allow_html=True)
    st.write("")
    cols = st.columns(4)
    cards = [
        ("1", "Evaluate one agent", "Run a full suite or one scenario and judge absolute quality and safety."),
        ("2", "Compare releases", "Run V1 and V2 under the same conditions to expose improvements and regressions."),
        ("3", "Test your own case", "Choose a curated scenario or type a cancellation/refund situation in natural language."),
        ("4", "Learn from failures", "Trace the evidence, find the root cause, and turn the failure into a regression test."),
    ]
    for c, (n, title, body) in zip(cols, cards):
        with c:
            st.markdown(f'<div class="mini"><b>{n}. {title}</b><p>{body}</p></div>', unsafe_allow_html=True)

    st.markdown("## What is actually being evaluated?")
    st.write("The final response is only one part. The Lab evaluates the agent's decision, tool use, policy adherence, side effects, recovery behavior, customer-facing response and—most importantly—the actual simulated outcome.")
    st.dataframe([
        {"Layer": "Deterministic", "What it answers": "Did the agent select the right entity, amount, policy outcome and allowed action?"},
        {"Layer": "Outcome / state", "What it answers": "Did the simulated world end in the required state?"},
        {"Layer": "Trajectory / safety", "What it answers": "Did the agent follow safe gates and recover correctly?"},
        {"Layer": "LLM judge", "What it answers": "Was the response clear, useful and contextually appropriate?"},
        {"Layer": "Evidence confidence", "What it answers": "How strong is the evidence behind the evaluation?"},
    ], use_container_width=True, hide_index=True)

    st.markdown("## The MVP story")
    st.write("V1 is the trusted baseline. V2 is the candidate release. Both operate against the same synthetic scenario suite. The current deliberate V2 regression is a wrong-payment selection in the duplicate-charge case; the Lab should catch it as a P0 and block release.")
    st.info("The demo agents are deterministic reference implementations so this public MVP is reproducible without exposing a model API key. The evaluation contract is designed so a future real LLM-powered agent can plug in without redesigning the evaluators.")

    st.markdown("## What the PM sees at the end")
    st.markdown("**Decision → Why → What changed → Which scenario broke → Evidence → Recommended fix**")

with eval_tab:
    st.markdown("## Evaluate an agent")
    st.write("Evaluate **one agent on its own**. Comparison is a separate workflow. Start with the suite or select exactly one scenario.")
    c1, c2 = st.columns([1, 1])
    with c1:
        agent_version = st.selectbox("Agent", ["v1", "v2"], format_func=lambda x: "V1 · trusted baseline" if x == "v1" else "V2 · candidate")
    with c2:
        scope = st.radio("Evaluation scope", ["Full suite (10 scenarios)", "One scenario"], horizontal=True)
    if scope == "One scenario":
        chosen = st.selectbox("Scenario", [s["id"] + " · " + s["name"] for s in SCENARIOS])
        selected = [SCENARIO_BY_ID[chosen.split(" · ", 1)[0]]]
    else:
        selected = SCENARIOS
    st.divider()
    st.markdown("### Scenario source")
    source = st.radio("Choose the input to evaluate", ["Use selected curated scenario(s)", "Write my own scenario"], horizontal=True)
    custom = None
    if source == "Write my own scenario":
        msg = st.text_area("Customer situation", placeholder="Example: I was charged twice for my cancelled ride yesterday. Please refund the duplicate charge.", height=110)
        expected_mode = st.selectbox("Expected behavior", ["Auto-detect", "Refund", "Clarify", "No refund", "Already refunded"])
        if st.button("Create test scenario", type="secondary"):
            custom, err = build_custom_scenario(msg, expected_mode)
            if custom:
                st.session_state["custom_eval_scenario"] = custom
                st.success("Custom scenario created inside the supported cancellation/refund sandbox. Review it below, then run the evaluation.")
            else:
                st.error(err)
        custom = st.session_state.get("custom_eval_scenario")
        if custom:
            selected = [custom]
            st.info(f"**Input:** {custom['user_messages'][0]}  ·  **Expected:** {custom['expected']}")
    if st.button("Run evaluation", type="primary", use_container_width=True):
        if not selected:
            st.error("Select at least one scenario.")
        else:
            run = run_with_progress(selected, agent_version)
            st.session_state["last_eval"] = run
    if st.session_state.get("last_eval"):
        run = st.session_state["last_eval"]
        rel = run["release"]
        st.divider()
        st.markdown("## Evaluation result")
        st.markdown(f"### {badge(rel['status'])} · autonomy evidence: **{rel['autonomy_level']}**")
        st.write(rel["rationale"])
        a, b, c, d, e = st.columns(5)
        a.metric("Avg quality", f"{rel['avg_quality']:.1f}%")
        b.metric("P0 failures", rel["p0"])
        c.metric("P1 failures", rel["p1"])
        d.metric("Evidence confidence", f"{rel['avg_confidence']:.0f}%")
        e.metric("Scenarios", rel["scenarios_executed"])
        st.markdown("### Scenario summary")
        rows = []
        for r in run["results"]:
            rows.append({"Scenario": r["name"], "Risk": r["risk"], "Result": "BLOCK" if r["p0"] else "PASS" if r["p1"] == 0 else "WARN", "Quality": f"{r['quality_score']:.1f}%", "P0": r["p0"], "P1": r["p1"], "Evidence": r["confidence"]["level"]})
        st.dataframe(rows, use_container_width=True, hide_index=True)
        failed = [r for r in run["results"] if r["p0"] or r["p1"]]
        if failed:
            st.markdown("### Where it broke")
            for r in failed:
                with st.expander(f"{badge('BLOCK' if r['p0'] else 'CANARY')} · {r['name']}"):
                    render_run_detail(r)

with compare_tab:
    st.markdown("## Compare releases")
    st.write("This workflow evaluates **V1 and V2 on the same suite**. Use it to answer: *Did the candidate improve, and what did it break?*")
    suite = SCENARIOS
    st.info("Baseline: **V1 trusted**  ·  Candidate: **V2**  ·  Suite: **Cancellation & Refund · 10 scenarios**")
    if st.button("Run V1 vs V2 comparison", type="primary", use_container_width=True):
        with st.status("Running the same suite against both agent versions…", expanded=True) as status:
            v1 = run_with_progress(suite, "v1")
            v2 = run_with_progress(suite, "v2")
            comp = compare_suites(v1, v2)
            st.session_state["compare"] = comp
            status.update(label="Comparison complete", state="complete")
    comp = st.session_state.get("compare")
    if comp:
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Quality delta", f"{comp['quality_delta']:+.1f} pts")
        c2.metric("Confidence delta", f"{comp['confidence_delta']:+.1f} pts")
        c3.metric("New P0s", comp["new_p0"])
        c4.metric("Regressions", comp["regressions"])
        left, right = st.columns(2)
        with left:
            st.markdown(f"### V1 · {badge(comp['v1']['status'])}")
            st.write(comp["v1"]["rationale"])
            st.metric("Quality", f"{comp['v1']['avg_quality']:.1f}%")
        with right:
            st.markdown(f"### V2 · {badge(comp['v2']['status'])}")
            st.write(comp["v2"]["rationale"])
            st.metric("Quality", f"{comp['v2']['avg_quality']:.1f}%")
        st.markdown("### What changed across the suite?")
        rows = []
        for c in comp["changes"]:
            rows.append({"Scenario": c["name"], "Quality Δ": f"{c['quality_delta']:+.1f}", "V1 P0": c["v1_p0"], "V2 P0": c["v2_p0"], "Improved checks": len(c["improvements"]), "Regressions": len(c["regressions"])})
        st.dataframe(rows, use_container_width=True, hide_index=True)
        regressions = [c for c in comp["changes"] if c["regressions"]]
        if regressions:
            st.markdown("### Candidate regressions")
            for c in regressions:
                with st.expander(f"🚨 {c['name']}"):
                    for reg in c["regressions"]:
                        st.markdown(f"**{reg['severity']} · {reg['dimension']}** — {reg['to']}")
                    st.caption("The comparison tells you which scenario regressed; open the scenario in the Evaluate tab for the evidence timeline.")

with scenarios_tab:
    st.markdown("## Scenarios & Try It")
    st.write("Every evaluation starts from a scenario: a customer request + a synthetic world + expected outcome + risk. Pick an existing case, or type a new case from the supported domain.")
    names = [f"{s['id']} · {s['name']}" for s in SCENARIOS]
    selected_name = st.selectbox("Curated scenario", names)
    s = SCENARIO_BY_ID[selected_name.split(" · ", 1)[0]]
    st.markdown(f"### {s['name']}")
    st.write(s["description"])
    st.info(f"**Customer says:** “{s['user_messages'][-1]}”")
    m1, m2, m3 = st.columns(3)
    m1.metric("Risk", s["metadata"]["risk"])
    m2.metric("Ambiguity", s["metadata"]["ambiguity"])
    m3.metric("Category", s["metadata"]["category"].replace("_", " ").title())
    st.markdown("**Expected outcome:**")
    st.json(s["expected"])
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run V1 on this scenario", use_container_width=True):
            st.session_state["scenario_result_v1"] = run_scenario(s, "v1")
    with c2:
        if st.button("Run V2 on this scenario", use_container_width=True):
            st.session_state["scenario_result_v2"] = run_scenario(s, "v2")
    if st.session_state.get("scenario_result_v1") or st.session_state.get("scenario_result_v2"):
        st.divider()
        st.markdown("### Same scenario, different agent versions")
        cols = st.columns(2)
        for col, version in zip(cols, ["v1", "v2"]):
            with col:
                result = st.session_state.get(f"scenario_result_{version}")
                if result:
                    st.markdown(f"#### {version.upper()}")
                    render_run_detail(result)

with docs_tab:
    st.markdown("## Agent & evaluation docs")
    st.write("The MVP is intentionally transparent: each agent has a behavior specification, and the evaluation system is documented as a layered quality framework.")
    tab1, tab2, tab3 = st.tabs(["Agent specs", "Evaluation methodology", "Architecture & vision"])
    with tab1:
        st.markdown("### V1 — trusted baseline")
        st.write("Conservative refund agent with explicit policy/authorization checks, state verification and safe recovery.")
        st.markdown("### V2 — candidate")
        st.write("Candidate variant whose deliberate duplicate-payment selection regression demonstrates why release evaluation must look beyond average quality.")
        st.markdown("### Autonomy contract")
        st.dataframe([
            {"Situation": "Clearly eligible refund", "Behavior": "ACT"},
            {"Situation": "Material ambiguity", "Behavior": "CLARIFY"},
            {"Situation": "Policy uncertainty", "Behavior": "ESCALATE"},
            {"Situation": "Existing refund", "Behavior": "RESPOND; no duplicate side effect"},
            {"Situation": "Unknown transaction state", "Behavior": "VERIFY; escalate if still unknown"},
        ], use_container_width=True, hide_index=True)
    with tab2:
        st.markdown("### Layered evaluation")
        st.write("Deterministic + outcome + trajectory/safety + LLM-judge-compatible qualitative evaluation + evidence confidence + risk gates.")
        st.markdown("### Release principle")
        st.error("A P0 safety or financial-action violation blocks release even when aggregate quality is high.")
    with tab3:
        st.markdown("### Product vision")
        st.write("The future production flow is: connect a real agent → run the versioned suite → compare against a trusted baseline → diagnose regressions → add failures to the regression suite → promote autonomy only when evidence supports it.")
        st.markdown("### Architecture")
        st.code("Scenario / Custom Input → Simulator → Agent Adapter → Trace → Deterministic + Outcome + Trajectory + LLM Judge → Evidence Confidence + Risk Gates → Release Decision → Failure → Regression Test", language="text")

st.caption(f"Synthetic demo · {datetime.now().strftime('%d %b %Y %H:%M')} · No production/customer data · Public MVP")
