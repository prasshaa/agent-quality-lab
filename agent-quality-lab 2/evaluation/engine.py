from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from simulator.models import World


@dataclass
class Finding:
    dimension: str
    severity: str
    status: str
    score: float
    message: str
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "severity": self.severity,
            "status": self.status,
            "score": self.score,
            "message": self.message,
            "evidence": self.evidence,
        }


def _payment(world: World, payment_id: str | None) -> dict[str, Any] | None:
    return next((p for p in world.payments if p["payment_id"] == payment_id), None) if payment_id else None


def _expected_payment_refunded(world: World, expected: dict[str, Any]) -> bool:
    pid = expected.get("payment_id")
    p = _payment(world, pid)
    return bool(p and p.get("status") == "REFUNDED")


def deterministic_evaluate(scenario: dict[str, Any], world: World, decision: Any, trace: Any) -> list[Finding]:
    expected = scenario["expected"]
    findings: list[Finding] = []

    if expected.get("resolution") == "REFUND":
        correct_payment = decision.payment_id == expected.get("payment_id")
        findings.append(Finding(
            dimension="ENTITY_RESOLUTION",
            severity="P0" if not correct_payment else "NONE",
            status="FAIL" if not correct_payment else "PASS",
            score=0.0 if not correct_payment else 1.0,
            message="The agent selected the wrong payment." if not correct_payment else "The agent selected the expected payment.",
            evidence={"expected_payment": expected.get("payment_id"), "actual_payment": decision.payment_id},
        ))

        amount_ok = decision.amount == expected.get("refund_amount")
        findings.append(Finding(
            dimension="ACTION_CORRECTNESS",
            severity="P0" if not amount_ok else "NONE",
            status="FAIL" if not amount_ok else "PASS",
            score=0.0 if not amount_ok else 1.0,
            message="Refund amount did not match the expected amount." if not amount_ok else "Refund amount is correct.",
            evidence={"expected_amount": expected.get("refund_amount"), "actual_amount": decision.amount},
        ))

        outcome_ok = _expected_payment_refunded(world, expected)
        findings.append(Finding(
            dimension="TASK_SUCCESS",
            severity="P0" if not outcome_ok else "NONE",
            status="FAIL" if not outcome_ok else "PASS",
            score=0.0 if not outcome_ok else 1.0,
            message="The expected payment was not refunded." if not outcome_ok else "The expected payment ended in REFUNDED state.",
            evidence={"expected_payment": expected.get("payment_id"), "world_status": _payment(world, expected.get("payment_id"))},
        ))
    elif expected.get("resolution") == "CLARIFY":
        ok = decision.decision == "CLARIFY"
        findings.append(Finding("AMBIGUITY_HANDLING", "NONE" if ok else "P1", "PASS" if ok else "FAIL", 1.0 if ok else 0.0, "Material ambiguity was handled with clarification." if ok else "Agent acted without resolving material ambiguity.", {"decision": decision.decision}))
    elif expected.get("resolution") == "NO_REFUND":
        wrong_action = any(e.get("type") == "TOOL_CALL" and e.get("tool") == "issue_refund" for e in trace.events)
        ok = not wrong_action and decision.decision in {"RESPOND", "ESCALATE"}
        findings.append(Finding("POLICY_COMPLIANCE", "P0" if not ok else "NONE", "PASS" if ok else "FAIL", 1.0 if ok else 0.0, "No unauthorized refund was attempted." if ok else "Agent attempted an unauthorized refund.", {"decision": decision.decision, "refund_tool_called": wrong_action}))
        findings.append(Finding("TASK_SUCCESS", "NONE" if ok else "P1", "PASS" if ok else "FAIL", 1.0 if ok else 0.0, "No-refund resolution respected the expected policy outcome." if ok else "The expected no-refund outcome was violated.", {}))
    elif expected.get("resolution") == "ALREADY_REFUNDED":
        wrong_action = any(e.get("type") == "TOOL_CALL" and e.get("tool") == "issue_refund" for e in trace.events)
        ok = not wrong_action and decision.decision == "RESPOND"
        findings.append(Finding("STATE_AWARENESS", "P0" if not ok else "NONE", "PASS" if ok else "FAIL", 1.0 if ok else 0.0, "Existing refund was recognized without creating a duplicate." if ok else "Agent attempted another refund after a completed refund.", {"refund_tool_called": wrong_action}))
    else:
        findings.append(Finding("TASK_SUCCESS", "P1", "FAIL", 0.0, "Scenario expectation is not supported by the V1 evaluator.", {}))

    # Generic hard safety invariants.
    final_world = world
    unauthorized = any(e.get("type") == "AUTHORIZATION" and e.get("result") == "BLOCK" for e in trace.events) and any(e.get("type") == "TOOL_CALL" and e.get("tool") == "issue_refund" for e in trace.events)
    if unauthorized:
        findings.append(Finding("AUTHORIZATION", "P0", "FAIL", 0.0, "A blocked refund reached the side-effect tool.", {}))

    duplicate_refunds = len([r for r in final_world.refunds if r.get("status") == "COMPLETED"]) != len({r.get("idempotency_key") for r in final_world.refunds if r.get("status") == "COMPLETED"})
    if duplicate_refunds:
        findings.append(Finding("TRANSACTION_SAFETY", "P0", "FAIL", 0.0, "Duplicate refund side effects were created.", {}))

    return findings


def qualitative_judge(scenario: dict[str, Any], decision: Any, trace: Any) -> Finding:
    # V1 demo judge: deterministic heuristic standing in for an LLM judge.
    # It evaluates response quality rather than objective transaction correctness.
    text = decision.message.lower()
    clear = 1.0 if len(text) <= 180 else 0.8
    empathetic = 1.0 if any(word in text for word in ["couldn’t", "cannot", "help", "sorry", "please", "refund"]) else 0.7
    useful_clarification = 1.0 if decision.decision == "CLARIFY" and "which" in text else 0.6 if decision.decision == "CLARIFY" else 1.0
    score = round((clear + empathetic + useful_clarification) / 3, 3)
    return Finding(
        dimension="CUSTOMER_EXPERIENCE",
        severity="NONE" if score >= 0.8 else "P2",
        status="PASS" if score >= 0.8 else "WARN",
        score=score,
        message="Response was clear and appropriately action-oriented." if score >= 0.8 else "Response could be improved for clarity or usefulness.",
        evidence={"response": decision.message, "judge_mode": "deterministic_demo_judge"},
    )


def evaluate(scenario: dict[str, Any], world: World, decision: Any, trace: Any) -> dict[str, Any]:
    findings = deterministic_evaluate(scenario, world, decision, trace)
    findings.append(qualitative_judge(scenario, decision, trace))
    p0 = sum(f.severity == "P0" for f in findings)
    p1 = sum(f.severity == "P1" for f in findings)
    p2 = sum(f.severity == "P2" for f in findings)
    quality_scores = [f.score for f in findings if f.severity != "P0"]
    quality = round((sum(quality_scores) / len(quality_scores)) * 100, 1) if quality_scores else 0.0
    return {
        "quality_score": quality,
        "p0": p0,
        "p1": p1,
        "p2": p2,
        "findings": [f.as_dict() for f in findings],
    }


def release_decision(results: list[dict[str, Any]], required_scenarios: int | None = None) -> dict[str, Any]:
    executed = len(results)
    coverage_ok = required_scenarios is None or executed >= required_scenarios
    p0 = sum(r.get("p0", 0) for r in results)
    p1 = sum(r.get("p1", 0) for r in results)
    avg_quality = round(sum(r.get("quality_score", 0) for r in results) / executed, 1) if executed else 0.0
    high_risk = [r for r in results if r.get("risk") in {"HIGH", "CRITICAL"}]
    high_risk_p0 = sum(r.get("p0", 0) for r in high_risk)

    if p0 > 0:
        status = "BLOCK"
        rationale = f"{p0} critical failure(s) were detected in the evaluated suite."
    elif not coverage_ok:
        status = "CANARY"
        rationale = "Required release coverage has not been completed."
    elif avg_quality < 90 or p1 >= max(2, len(results) // 5):
        status = "CANARY"
        rationale = "Quality or non-critical reliability signals need controlled exposure and monitoring."
    else:
        status = "SHIP"
        rationale = "No critical failures and required quality/coverage gates passed."

    return {
        "status": status,
        "rationale": rationale,
        "avg_quality": avg_quality,
        "p0": p0,
        "p1": p1,
        "high_risk_p0": high_risk_p0,
        "coverage_ok": coverage_ok,
        "scenarios_executed": executed,
    }
