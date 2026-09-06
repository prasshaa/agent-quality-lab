from scenarios.library import scenarios
from agent.runtime import RefundAgent
from evaluation.engine import evaluate, release_decision


def get(sid):
    return next(s for s in scenarios() if s["id"] == sid)


def test_happy_path_refunds_correct_payment():
    s = get("refund_001")
    world, trace, decision = RefundAgent("v1").run(s)
    result = evaluate(s, world, decision, trace)
    assert decision.decision == "ACT"
    assert decision.payment_id == "pay_101"
    assert result["p0"] == 0


def test_ambiguous_case_clarifies():
    s = get("refund_003")
    world, trace, decision = RefundAgent("v1").run(s)
    result = evaluate(s, world, decision, trace)
    assert decision.decision == "CLARIFY"
    assert result["p0"] == 0


def test_timeout_after_side_effect_is_verified_without_duplicate():
    s = get("refund_005")
    world, trace, decision = RefundAgent("v1").run(s)
    assert decision.decision == "ACT"
    assert next(p for p in world.payments if p["payment_id"] == "pay_105")["status"] == "REFUNDED"
    assert len(world.refunds) == 1


def test_v2_wrong_payment_is_p0():
    s = get("refund_010")
    world, trace, decision = RefundAgent("v2").run(s)
    result = evaluate(s, world, decision, trace)
    assert decision.payment_id == "pay_110a"
    assert result["p0"] >= 1


def test_release_blocks_v2_on_p0():
    from evaluation.runner import run_suite
    ss = scenarios()
    v2 = run_suite(ss, "v2")
    assert v2["release"]["status"] == "BLOCK"
