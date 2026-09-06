from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulator.models import AgentDecision, World
from simulator.world import ToolGateway


@dataclass
class Trajectory:
    events: list[dict[str, Any]] = field(default_factory=list)

    def add(self, event_type: str, **data: Any) -> None:
        self.events.append({"type": event_type, **data})


class RefundAgent:
    """Production-minded demo agent.

    This intentionally uses deterministic structured reasoning so the public demo
    can run without exposing an LLM API key. The interface is designed so an LLM
    adapter can replace the decision layer later without changing the simulator
    or evaluators.
    """

    def __init__(self, version: str = "v1"):
        if version not in {"v1", "v2"}:
            raise ValueError("Supported versions: v1, v2")
        self.version = version

    def run(self, scenario: dict[str, Any]) -> tuple[World, Trajectory, AgentDecision]:
        world = World(**scenario["world"])
        tools = ToolGateway(world, scenario.get("failure_injections", []))
        trace = Trajectory()
        customer_id = world.customers[0]["customer_id"]
        user_text = scenario["user_messages"][-1]
        trace.add("USER_MESSAGE", text=user_text)

        is_duplicate = "twice" in user_text.lower() or "duplicate" in user_text.lower()
        wants_refund = "refund" in user_text.lower() or "charged" in user_text.lower()
        injection = "ignore all" in user_text.lower() or "authorized" in user_text.lower() and "completed ride" in user_text.lower()

        # Retrieve the customer and trips first.
        result = tools.get_customer(customer_id)
        trace.add("TOOL_CALL", tool="get_customer", input={"customer_id": customer_id})
        trace.add("TOOL_RESULT", tool="get_customer", success=result.success, data=result.data, error=result.error_type)
        if not result.success:
            return world, trace, AgentDecision(decision="ESCALATE", intent="REFUND", confidence=0.3, message="I need a human to help verify your account.")

        trips_result = tools.get_trip(customer_id)
        trace.add("TOOL_CALL", tool="get_trip", input={"customer_id": customer_id})
        trace.add("TOOL_RESULT", tool="get_trip", success=trips_result.success, data=trips_result.data, error=trips_result.error_type)
        trips = trips_result.data.get("trips", [])

        if injection:
            trace.add("POLICY_CHECK", result="BLOCK", reason="Customer instruction cannot override policy")
            return world, trace, AgentDecision(
                decision="RESPOND", intent="REFUND", confidence=0.98, message="I can’t override the refund policy. I can help with a refund when the trip meets the policy criteria."
            )

        # Ambiguous cases: V1 asks; V2 is intentionally over-aggressive only for
        # the high-risk duplicate-payment pattern used to demonstrate a regression.
        if len(trips) != 1 and not is_duplicate:
            trace.add("DECISION", decision="CLARIFY", ambiguity="MATERIAL")
            return world, trace, AgentDecision(
                decision="CLARIFY", intent="REFUND", ambiguity="MATERIAL", confidence=0.97,
                message="I found multiple rides that could match. Which ride would you like me to refund?"
            )

        if not wants_refund:
            return world, trace, AgentDecision(decision="RESPOND", intent="OTHER", confidence=0.9, message="I can help with ride charges and refunds.")

        trip = self._select_trip(world, trips, user_text, is_duplicate)
        if trip is None:
            trace.add("DECISION", decision="CLARIFY", ambiguity="MATERIAL")
            return world, trace, AgentDecision(decision="CLARIFY", intent="REFUND", ambiguity="MATERIAL", confidence=0.9, message="Which specific ride should I work on?")

        trip_id = trip["trip_id"]
        trace.add("STATE_UPDATE", selected_trip=trip_id)

        payments_result = tools.get_payment(customer_id, trip_id)
        trace.add("TOOL_CALL", tool="get_payment", input={"customer_id": customer_id, "trip_id": trip_id})
        trace.add("TOOL_RESULT", tool="get_payment", success=payments_result.success, data=payments_result.data, error=payments_result.error_type)
        payments = payments_result.data.get("payments", [])
        if not payments:
            trace.add("DECISION", decision="ESCALATE", reason="No payment found")
            return world, trace, AgentDecision(decision="ESCALATE", intent="REFUND", trip_id=trip_id, confidence=0.65, message="I couldn’t verify the payment for that ride, so I’m escalating this for review.")

        # Duplicate-charge case: V1 correctly identifies the duplicate marker;
        # V2 intentionally regresses by selecting the first matching payment.
        if is_duplicate and len(payments) > 1:
            if self.version == "v1":
                duplicate = next((p for p in payments if p.get("kind") == "DUPLICATE"), payments[-1])
            else:
                duplicate = payments[0]
            payment = duplicate
            reason = "duplicate_charge"
        else:
            payment = payments[0]
            reason = "charged_after_cancellation"

        payment_id = payment["payment_id"]

        policy_result = tools.get_policy()
        trace.add("TOOL_CALL", tool="get_policy", input={})
        trace.add("TOOL_RESULT", tool="get_policy", success=policy_result.success, data=policy_result.data, error=policy_result.error_type)
        policy = policy_result.data.get("policy", {})

        # Prompt injection / policy bypass is handled before this point. This is
        # a deterministic gate even though the agent proposes the action.
        eligible = (
            reason in policy.get("eligible_reasons", [])
            and (trip.get("status") == "CANCELLED" or (reason == "duplicate_charge" and payment.get("kind") == "DUPLICATE"))
            and float(payment["amount"]) <= float(policy.get("auto_refund_max", 0))
        )
        trace.add("POLICY_CHECK", result="PASS" if eligible else "BLOCK", payment_id=payment_id, reason=reason)
        if payment.get("status") == "REFUNDED":
            trace.add("DECISION", decision="RESPOND", reason="ALREADY_REFUNDED")
            return world, trace, AgentDecision(decision="RESPOND", intent="REFUND", trip_id=trip_id, payment_id=payment_id, confidence=0.99, message="That payment has already been refunded. I won’t create another refund.")
        if not eligible:
            trace.add("DECISION", decision="RESPOND", reason="POLICY_NOT_MET")
            return world, trace, AgentDecision(decision="RESPOND", intent="REFUND", trip_id=trip_id, payment_id=payment_id, confidence=0.97, message="I checked the refund policy, and this charge isn’t eligible for an automatic refund.")

        calc = tools.calculate_refund(trip_id, payment_id, reason)
        trace.add("TOOL_CALL", tool="calculate_refund", input={"trip_id": trip_id, "payment_id": payment_id, "reason": reason})
        trace.add("TOOL_RESULT", tool="calculate_refund", success=calc.success, data=calc.data, error=calc.error_type)
        if not calc.success or not calc.data.get("eligible"):
            return world, trace, AgentDecision(decision="ESCALATE", intent="REFUND", trip_id=trip_id, payment_id=payment_id, confidence=0.7, message="I couldn’t safely verify the refund, so I’m escalating this case.")

        amount = float(calc.data["amount"])
        authorized = self._authorization(world, customer_id, trip_id, payment_id, amount)
        trace.add("AUTHORIZATION", result="PASS" if authorized else "BLOCK", customer_id=customer_id, trip_id=trip_id, payment_id=payment_id, amount=amount)
        if not authorized:
            return world, trace, AgentDecision(decision="ESCALATE", intent="REFUND", trip_id=trip_id, payment_id=payment_id, amount=amount, confidence=0.75, message="I couldn’t safely authorize that refund, so I’m escalating it for review.")

        refund_result = tools.issue_refund(
            customer_id=customer_id,
            trip_id=trip_id,
            payment_id=payment_id,
            amount=amount,
            reason=reason,
            idempotency_key=f"{customer_id}:{payment_id}:{scenario['id']}",
        )
        trace.add("TOOL_CALL", tool="issue_refund", input={"customer_id": customer_id, "trip_id": trip_id, "payment_id": payment_id, "amount": amount})
        trace.add("TOOL_RESULT", tool="issue_refund", success=refund_result.success, data=refund_result.data, error=refund_result.error_type, effect_applied=refund_result.effect_applied)

        # A timeout is ambiguous. Verify state before claiming success or retrying.
        payment_after = next(p for p in world.payments if p["payment_id"] == payment_id)
        trace.add("VERIFICATION", payment_id=payment_id, status=payment_after["status"])
        if payment_after["status"] == "REFUNDED":
            return world, trace, AgentDecision(
                decision="ACT", intent="REFUND", trip_id=trip_id, payment_id=payment_id, amount=amount, confidence=0.99,
                message=f"Your refund of ₹{amount:.0f} has been processed for the verified payment."
            )

        # Only retry once when the state proves the first attempt did not happen.
        retry = tools.issue_refund(
            customer_id=customer_id,
            trip_id=trip_id,
            payment_id=payment_id,
            amount=amount,
            reason=reason,
            idempotency_key=f"{customer_id}:{payment_id}:{scenario['id']}",
        )
        trace.add("TOOL_CALL", tool="issue_refund", input={"retry": True, "payment_id": payment_id})
        trace.add("TOOL_RESULT", tool="issue_refund", success=retry.success, data=retry.data, error=retry.error_type, effect_applied=retry.effect_applied)
        payment_final = next(p for p in world.payments if p["payment_id"] == payment_id)
        trace.add("VERIFICATION", payment_id=payment_id, status=payment_final["status"])
        if payment_final["status"] == "REFUNDED":
            return world, trace, AgentDecision(
                decision="ACT", intent="REFUND", trip_id=trip_id, payment_id=payment_id, amount=amount, confidence=0.98,
                message=f"Your refund of ₹{amount:.0f} has been processed."
            )
        return world, trace, AgentDecision(decision="ESCALATE", intent="REFUND", trip_id=trip_id, payment_id=payment_id, confidence=0.7, message="I couldn’t verify the refund, so I’m escalating this case rather than guessing.")

    def _select_trip(self, world: World, trips: list[dict[str, Any]], text: str, is_duplicate: bool) -> dict[str, Any] | None:
        if len(trips) == 1:
            return trips[0]
        lower = text.lower()
        candidates = trips
        if "airport" in lower:
            candidates = [t for t in trips if "airport" in str(t.get("destination", "")).lower() or "airport" in str(t.get("pickup", "")).lower()]
        # V2's regression only applies to the duplicate-payment ambiguity; for
        # other ambiguities it still asks for clarification.
        return candidates[0] if is_duplicate and len(candidates) >= 1 else None

    @staticmethod
    def _authorization(world: World, customer_id: str, trip_id: str, payment_id: str, amount: float) -> bool:
        payment = next((p for p in world.payments if p["payment_id"] == payment_id), None)
        trip = next((t for t in world.trips if t["trip_id"] == trip_id), None)
        policy = world.policies[0] if world.policies else None
        return bool(
            payment
            and trip
            and policy
            and payment.get("customer_id") == customer_id
            and payment.get("trip_id") == trip_id
            and trip.get("customer_id") == customer_id
            and payment.get("status") != "REFUNDED"
            and amount <= float(policy.get("auto_refund_max", 0))
        )
