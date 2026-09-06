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
    return {
        "v1": v1["release"],
        "v2": v2["release"],
        "quality_delta": round(v2["release"]["avg_quality"] - v1["release"]["avg_quality"], 1),
        "p0_delta": v2["release"]["p0"] - v1["release"]["p0"],
        "p1_delta": v2["release"]["p1"] - v1["release"]["p1"],
        "regressions": [
            {
                "scenario_id": b["scenario_id"],
                "name": b["name"],
                "v1_p0": a["p0"],
                "v2_p0": b["p0"],
                "v1_quality": a["quality_score"],
                "v2_quality": b["quality_score"],
            }
            for a, b in zip(v1["results"], v2["results"])
            if b["p0"] > a["p0"] or b["quality_score"] < a["quality_score"] - 5
        ],
    }
