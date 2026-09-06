from __future__ import annotations

from copy import deepcopy
from typing import Any

from agent.runtime import RefundAgent
from evaluation.engine import evaluate, release_decision


def run_scenario(scenario: dict[str, Any], agent_version: str) -> dict[str, Any]:
    agent = RefundAgent(agent_version)
    world, trace, decision = agent.run(deepcopy(scenario))
    result = evaluate(scenario, world, decision, trace)
    return {
        "scenario_id": scenario["id"],
        "name": scenario["name"],
        "risk": scenario["metadata"]["risk"],
        "category": scenario["metadata"]["category"],
        "agent_version": agent_version,
        "decision": decision.model_dump(),
        "world": world.model_dump(),
        "trace": trace.events,
        **result,
    }


def run_suite(scenarios: list[dict[str, Any]], agent_version: str) -> dict[str, Any]:
    results = [run_scenario(s, agent_version) for s in scenarios]
    release = release_decision(results, required_scenarios=len(scenarios))
    return {"agent_version": agent_version, "results": results, "release": release}


def compare_suites(v1: dict[str, Any], v2: dict[str, Any]) -> dict[str, Any]:
    by_v1 = {r["scenario_id"]: r for r in v1["results"]}
    by_v2 = {r["scenario_id"]: r for r in v2["results"]}
    changes = []
    for sid in by_v1.keys() & by_v2.keys():
        a, b = by_v1[sid], by_v2[sid]
        a_dims = {(f["dimension"], f["evaluator"]): f for f in a["findings"]}
        b_dims = {(f["dimension"], f["evaluator"]): f for f in b["findings"]}
        regressions = []
        improvements = []
        for key in a_dims.keys() & b_dims.keys():
            af, bf = a_dims[key], b_dims[key]
            if af["status"] == "PASS" and bf["status"] == "FAIL":
                regressions.append({"dimension": key[0], "evaluator": key[1], "from": af["message"], "to": bf["message"], "severity": bf["severity"]})
            elif af["status"] != "PASS" and bf["status"] == "PASS":
                improvements.append({"dimension": key[0], "evaluator": key[1]})
        quality_delta = round(b["quality_score"] - a["quality_score"], 1)
        changes.append({
            "scenario_id": sid,
            "name": a["name"],
            "v1_quality": a["quality_score"],
            "v2_quality": b["quality_score"],
            "quality_delta": quality_delta,
            "v1_p0": a["p0"],
            "v2_p0": b["p0"],
            "regressions": regressions,
            "improvements": improvements,
            "decision_changed": a["decision"]["decision"] != b["decision"]["decision"],
        })

    return {
        "v1": v1["release"],
        "v2": v2["release"],
        "quality_delta": round(v2["release"]["avg_quality"] - v1["release"]["avg_quality"], 1),
        "confidence_delta": round(v2["release"]["avg_confidence"] - v1["release"]["avg_confidence"], 1),
        "new_p0": max(0, v2["release"]["p0"] - v1["release"]["p0"]),
        "improvements": sum(len(c["improvements"]) for c in changes),
        "regressions": sum(len(c["regressions"]) for c in changes),
        "changes": sorted(changes, key=lambda x: (not bool(x["regressions"]), x["scenario_id"])),
    }
