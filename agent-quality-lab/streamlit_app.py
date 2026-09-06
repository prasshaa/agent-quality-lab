from __future__ import annotations

import json
import streamlit as st

from evaluation.runner import compare_suites, run_scenario, run_suite
from scenarios.library import scenarios

st.set_page_config(page_title="Agent Quality Lab", page_icon="🧪", layout="wide")

SCENARIOS = scenarios()
SCENARIO_BY_ID = {s["id"]: s for s in SCENARIOS}


def badge(status: str) -> str:
    return {"SHIP": "🟢 SHIP", "CANARY": "🟡 CANARY", "BLOCK": "🔴 BLOCK", "PASS": "🟢 PASS", "FAIL": "🔴 FAIL", "WARN": "🟡 WARN"}.get(status, status)


def render_finding(f: dict):
    sev = f["severity"]
    st.markdown(f"**{badge(sev) if sev != 'NONE' else 'PASS'} · {f['dimension']}**")
    st.write(f["message"])
    if f.get("evidence"):
        with st.expander("Evidence"):
            st.json(f["evidence"])


st.title("🧪 Agent Quality Lab")
st.caption("Simulation-to-release quality system for autonomous AI agents · synthetic ride cancellation/refund environment")

with st.sidebar:
    st.subheader("Prototype")
    st.info("Public-demo mode is fully self-contained. No API key or production data required.")
    st.markdown("**Core loop**")
    st.code("Scenario → World → Agent → Tools → Trace → Evaluate → Release", language="text")
    st.markdown("**Release outcomes**\n\n🟢 SHIP · 🟡 CANARY · 🔴 BLOCK")


home, run_tab, compare_tab, trace_tab = st.tabs(["Overview", "Run a scenario", "Compare V1 vs V2", "Inspect a trace"])

with home:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Golden scenarios", len(SCENARIOS))
    with c2:
        st.metric("Evaluators", "3")
    with c3:
        st.metric("Release gates", "P0 / coverage / quality")

    st.markdown("### What the Lab tests")
    st.write("It does not score only the final response. It checks entity resolution, policy adherence, tool use, state transitions, financial outcomes, recovery and customer experience.")

    st.markdown("### Why LLM-as-a-judge is not enough")
    st.warning("A response can look perfect while the wrong payment is refunded. The simulator owns ground truth; deterministic evaluators can therefore catch critical failures that a semantic judge might miss.")

    st.markdown("### Current golden suite")
    st.dataframe([
        {"ID": s["id"], "Scenario": s["name"], "Risk": s["metadata"]["risk"], "Category": s["metadata"]["category"]}
        for s in SCENARIOS
    ], use_container_width=True, hide_index=True)

with run_tab:
    st.subheader("Run one scenario")
    selected = st.selectbox("Scenario", [s["id"] for s in SCENARIOS], format_func=lambda x: f"{x} — {SCENARIO_BY_ID[x]['name']}")
    version = st.radio("Agent version", ["v1", "v2"], horizontal=True)
    s = SCENARIO_BY_ID[selected]
    st.caption(s["description"])
    st.code(s["user_messages"][-1])

    if st.button("Run evaluation", type="primary", use_container_width=True):
        result = run_scenario(s, version)
        st.session_state["last_run"] = result

    result = st.session_state.get("last_run")
    if result:
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Quality", f"{result['quality_score']:.1f}%")
        m2.metric("P0", result["p0"])
        m3.metric("P1", result["p1"])
        m4.metric("Agent decision", result["decision"]["decision"])

        st.markdown("### Decision")
        st.success(result["decision"]["message"])

        st.markdown("### Findings")
        for f in result["findings"]:
            render_finding(f)

        with st.expander("Final simulated world"):
            st.json(result["world"])

with compare_tab:
    st.subheader("Release comparison")
    st.write("The demonstration intentionally contains one realistic regression: V2 is more decisive on duplicate-charge cases and can select the wrong payment.")
    if st.button("Run V1 vs V2 comparison", type="primary", use_container_width=True):
        v1 = run_suite(SCENARIOS, "v1")
        v2 = run_suite(SCENARIOS, "v2")
        comparison = compare_suites(v1, v2)
        st.session_state["comparison"] = comparison
        st.session_state["v1_suite"] = v1
        st.session_state["v2_suite"] = v2

    comparison = st.session_state.get("comparison")
    if comparison:
        v1, v2 = comparison["v1"], comparison["v2"]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### V1 baseline")
            st.metric("Average quality", f"{v1['avg_quality']:.1f}%")
            st.metric("Critical failures", v1["p0"])
            st.success(badge(v1["status"]))
        with c2:
            st.markdown("#### V2 candidate")
            st.metric("Average quality", f"{v2['avg_quality']:.1f}%", delta=f"{comparison['quality_delta']:+.1f} pts")
            st.metric("Critical failures", v2["p0"], delta=f"{comparison['p0_delta']:+d}", delta_color="inverse")
            if v2["status"] == "BLOCK":
                st.error(badge(v2["status"]))
            else:
                st.warning(badge(v2["status"]))

        st.markdown("### Release recommendation")
        st.error(f"🔴 {v2['status']} — {v2['rationale']}") if v2["status"] == "BLOCK" else st.warning(f"🟡 {v2['status']} — {v2['rationale']}")

        st.markdown("### Regression findings")
        if comparison["regressions"]:
            st.dataframe(comparison["regressions"], use_container_width=True, hide_index=True)
        else:
            st.success("No regressions detected.")

        v2_results = st.session_state["v2_suite"]["results"]
        critical = [r for r in v2_results if r["p0"]]
        if critical:
            st.markdown("### Critical evidence")
            for r in critical:
                with st.expander(f"{r['scenario_id']} — {r['name']}"):
                    st.json({"decision": r["decision"], "findings": r["findings"]})

with trace_tab:
    st.subheader("Trajectory inspector")
    run = st.session_state.get("last_run")
    if not run:
        st.info("Run a scenario first. The trace will appear here.")
    else:
        st.caption(f"{run['scenario_id']} · {run['agent_version']}")
        for i, event in enumerate(run["trace"], start=1):
            label = event.get("type", "EVENT")
            with st.expander(f"{i:02d} · {label}", expanded=False):
                st.json(event)

        st.markdown("### Downloadable run evidence")
        st.download_button("Download run JSON", data=json.dumps(run, indent=2), file_name=f"{run['scenario_id']}-{run['agent_version']}.json", mime="application/json")
