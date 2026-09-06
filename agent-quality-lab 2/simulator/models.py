from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None
    latency_ms: int = 80
    effect_applied: bool = False


class World(BaseModel):
    customers: list[dict[str, Any]] = Field(default_factory=list)
    trips: list[dict[str, Any]] = Field(default_factory=list)
    payments: list[dict[str, Any]] = Field(default_factory=list)
    refunds: list[dict[str, Any]] = Field(default_factory=list)
    policies: list[dict[str, Any]] = Field(default_factory=list)
    support_cases: list[dict[str, Any]] = Field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self.model_dump())


class AgentDecision(BaseModel):
    decision: Literal["ACT", "CLARIFY", "ESCALATE", "RESPOND"]
    intent: str
    trip_id: str | None = None
    payment_id: str | None = None
    amount: float | None = None
    reason: str | None = None
    confidence: float = 0.0
    ambiguity: Literal["NONE", "MATERIAL", "HIGH"] = "NONE"
    message: str
