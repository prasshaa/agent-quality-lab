from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import ToolResult, World


class ToolGateway:
    def __init__(self, world: World, failure_injections: list[dict[str, Any]] | None = None):
        self.world = world
        self.failure_injections = deepcopy(failure_injections or [])
        self.call_counts: dict[str, int] = {}

    def _maybe_fail(self, tool: str) -> ToolResult | None:
        count = self.call_counts.get(tool, 0) + 1
        self.call_counts[tool] = count
        for injection in self.failure_injections:
            if injection.get("tool") == tool and injection.get("occurrence", 1) == count:
                failure = injection.get("failure", "SERVER_ERROR")
                effect = bool(injection.get("effect_applied", False))
                return ToolResult(
                    success=False,
                    error_type=failure,
                    error_message=f"Simulated {failure.lower().replace('_', ' ')}",
                    latency_ms=1500 if failure == "TIMEOUT" else 120,
                    effect_applied=effect,
                )
        return None

    def get_customer(self, customer_id: str) -> ToolResult:
        failed = self._maybe_fail("get_customer")
        if failed:
            return failed
        customer = next((x for x in self.world.customers if x["customer_id"] == customer_id), None)
        return ToolResult(success=bool(customer), data={"customer": customer} if customer else {}, error_type=None if customer else "NOT_FOUND")

    def get_trip(self, customer_id: str, trip_id: str | None = None) -> ToolResult:
        failed = self._maybe_fail("get_trip")
        if failed:
            return failed
        trips = [x for x in self.world.trips if x["customer_id"] == customer_id]
        if trip_id:
            trips = [x for x in trips if x["trip_id"] == trip_id]
        return ToolResult(success=True, data={"trips": deepcopy(trips)})

    def get_payment(self, customer_id: str, trip_id: str) -> ToolResult:
        failed = self._maybe_fail("get_payment")
        if failed:
            return failed
        payments = [x for x in self.world.payments if x["customer_id"] == customer_id and x["trip_id"] == trip_id]
        return ToolResult(success=True, data={"payments": deepcopy(payments)})

    def get_policy(self) -> ToolResult:
        failed = self._maybe_fail("get_policy")
        if failed:
            return failed
        policy = self.world.policies[0] if self.world.policies else None
        return ToolResult(success=bool(policy), data={"policy": deepcopy(policy)} if policy else {}, error_type=None if policy else "NOT_FOUND")

    def calculate_refund(self, trip_id: str, payment_id: str, reason: str) -> ToolResult:
        failed = self._maybe_fail("calculate_refund")
        if failed:
            return failed
        trip = next((x for x in self.world.trips if x["trip_id"] == trip_id), None)
        payment = next((x for x in self.world.payments if x["payment_id"] == payment_id), None)
        policy = self.world.policies[0] if self.world.policies else None
        if not trip or not payment or not policy:
            return ToolResult(success=False, error_type="NOT_FOUND", error_message="Required record not found")
        if payment["status"] == "REFUNDED":
            return ToolResult(success=True, data={"eligible": False, "reason": "already_refunded", "amount": 0, "requires_human_review": False})
        eligible = (
            reason in policy["eligible_reasons"]
            and (trip.get("status") == "CANCELLED" or (reason == "duplicate_charge" and payment.get("kind") == "DUPLICATE"))
            and float(payment["amount"]) <= float(policy["auto_refund_max"])
        )
        return ToolResult(
            success=True,
            data={
                "eligible": eligible,
                "amount": float(payment["amount"]) if eligible else 0,
                "policy_id": policy["policy_id"],
                "requires_human_review": reason in policy["requires_human_review"],
                "reason": reason if eligible else "policy_not_met",
            },
        )

    def issue_refund(self, customer_id: str, trip_id: str, payment_id: str, amount: float, reason: str, idempotency_key: str) -> ToolResult:
        injected = self._maybe_fail("issue_refund")
        payment = next((x for x in self.world.payments if x["payment_id"] == payment_id), None)
        trip = next((x for x in self.world.trips if x["trip_id"] == trip_id), None)
        if payment is None or trip is None or payment.get("customer_id") != customer_id or payment.get("trip_id") != trip_id:
            return ToolResult(success=False, error_type="VALIDATION_ERROR", error_message="Customer, trip and payment do not match")
        if payment.get("status") == "REFUNDED":
            return ToolResult(success=True, data={"status": "ALREADY_PROCESSED", "payment_id": payment_id})
        policy = self.world.policies[0] if self.world.policies else None
        if not policy or amount > float(policy["auto_refund_max"]):
            return ToolResult(success=False, error_type="POLICY_BLOCK", error_message="Refund exceeds automatic refund policy")
        if injected and injected.error_type == "TIMEOUT" and injected.effect_applied:
            self._apply_refund(customer_id, trip_id, payment_id, amount, reason, idempotency_key)
            return injected
        if injected:
            return injected
        self._apply_refund(customer_id, trip_id, payment_id, amount, reason, idempotency_key)
        return ToolResult(success=True, data={"status": "REFUNDED", "payment_id": payment_id, "amount": amount}, effect_applied=True)

    def _apply_refund(self, customer_id: str, trip_id: str, payment_id: str, amount: float, reason: str, idempotency_key: str) -> None:
        existing = next((x for x in self.world.refunds if x.get("idempotency_key") == idempotency_key), None)
        if existing:
            return
        self.world.payments = [
            {**p, "status": "REFUNDED"} if p["payment_id"] == payment_id else p for p in self.world.payments
        ]
        self.world.refunds.append({
            "refund_id": f"ref_{len(self.world.refunds) + 1:03d}",
            "payment_id": payment_id,
            "customer_id": customer_id,
            "trip_id": trip_id,
            "amount": amount,
            "status": "COMPLETED",
            "reason": reason,
            "idempotency_key": idempotency_key,
        })

    def escalate_to_human(self, customer_id: str, reason: str) -> ToolResult:
        failed = self._maybe_fail("escalate_to_human")
        if failed:
            return failed
        case = {
            "case_id": f"case_{len(self.world.support_cases) + 1:03d}",
            "customer_id": customer_id,
            "status": "ESCALATED",
            "reason": reason,
        }
        self.world.support_cases.append(case)
        return ToolResult(success=True, data=case, effect_applied=True)
