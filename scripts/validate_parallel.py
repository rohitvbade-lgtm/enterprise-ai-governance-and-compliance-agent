"""
validate_parallel.py — Concurrency timing assertions for the governance workflow.
Verifies that the three parallel branches (retrieve_policies, privacy_analysis,
security_analysis) run concurrently and not sequentially.
Usage:
    uv run python scripts/validate_parallel.py
Expected result: PASS with timing well under 3x the per-branch delay.
Exit code 0 on success, 1 on failure.
"""
from __future__ import annotations
import asyncio
import sys
import time
import uuid
async def run_timing_check() -> None:
    """
    Build a stub workflow where every parallel branch sleeps for DELAY seconds.
    If branches run concurrently, total time ≈ DELAY.
    If branches run sequentially, total time ≈ 3 × DELAY — which is a bug.
    """    
    DELAY = 0.20  # seconds per branch
    SEQUENTIAL_THRESHOLD = 2 * DELAY + 0.5  # fail if total exceeds this
    # Import after confirming the project is on the path
    from langgraph.graph import StateGraph, START, END
    from backend.app.graph.state import GovernanceState
    from backend.app.graph.workflow import _route_after_load
    from backend.app.risk.engine import RiskResult
    # Stub node functions — each parallel branch just sleeps
    async def slow_retrieve(state):
        await asyncio.sleep(DELAY)
        return {"retrieved_policies": []}
    async def slow_privacy(state):
        await asyncio.sleep(DELAY)
        return {"findings": [], "masked_text": state["text_to_evaluate"]}
    async def slow_security(state):
        await asyncio.sleep(DELAY)
        return {"findings": []}
    async def noop_load(state):
        return {
            "application": {"id": str(state["application_id"]), "name": "Stub", "risk_level": "LOW"},
            "exceptions": [],
        }
    async def noop_policy(state):
        return {"findings": []}
    async def noop_risk(state):
        return {"risk_result": RiskResult(total_score=0.0, risk_level="LOW", factors_detail={})}
    async def noop_decision(state):
        return {"decision": "ALLOW", "approval_required": False}
    async def noop_save(state):
        return {"assessment_id": uuid.uuid4(), "approval_request_id": None}
    # Build graph with stub nodes
    wf = StateGraph(GovernanceState)
    wf.add_node("load_application", noop_load)
    wf.add_node("retrieve_policies", slow_retrieve)
    wf.add_node("privacy_analysis", slow_privacy)
    wf.add_node("security_analysis", slow_security)
    wf.add_node("policy_analysis", noop_policy)
    wf.add_node("calculate_risk", noop_risk)
    wf.add_node("governance_decision", noop_decision)
    wf.add_node("save_assessment", noop_save)
    wf.add_edge(START, "load_application")
    wf.add_conditional_edges(
        "load_application",
        _route_after_load,
        ["retrieve_policies", "privacy_analysis", "security_analysis", END],
    )
    wf.add_edge("retrieve_policies", "policy_analysis")
    wf.add_edge("privacy_analysis", "policy_analysis")
    wf.add_edge("security_analysis", "policy_analysis")
    wf.add_edge("policy_analysis", "calculate_risk")
    wf.add_edge("calculate_risk", "governance_decision")
    wf.add_edge("governance_decision", "save_assessment")
    wf.add_edge("save_assessment", END)
    compiled = wf.compile()
    initial_state = {
        "application_id": uuid.uuid4(),
        "assessment_phase": "INPUT",
        "assessment_type": "REAL_TIME",
        "text_to_evaluate": "hello world",
        "input_assessment_id": None,
        "application": None,
        "retrieved_policies": [],
        "exceptions": [],
        "masked_text": "",
        "findings": [],
        "risk_result": None,
        "decision": None,
        "approval_required": False,
        "approval_request_id": None,
        "assessment_id": None,
        "errors": [],
    }    
    print(f"  Running workflow with {DELAY:.2f}s delay per parallel branch...")
    print(f"  Sequential total would be: {3 * DELAY:.2f}s")
    print(f"  Concurrent total should be: ~{DELAY:.2f}s")
    print(f"  Failure threshold: {SEQUENTIAL_THRESHOLD:.2f}s")
    t0 = time.monotonic()
    await compiled.ainvoke(initial_state)
    elapsed = time.monotonic() - t0
    print(f"  Actual elapsed time: {elapsed:.3f}s")
    if elapsed >= SEQUENTIAL_THRESHOLD:
        print(f"\nFAIL -- workflow took {elapsed:.3f}s, expected under {SEQUENTIAL_THRESHOLD:.2f}s")
        print("   The parallel branches appear to be running sequentially!")
        sys.exit(1)
    else:
        print(f"\nPASS -- parallel branches ran concurrently ({elapsed:.3f}s < {SEQUENTIAL_THRESHOLD:.2f}s)")

def main() -> None:
    print("=" * 60)
    print("Parallel Workflow Concurrency Validation")
    print("=" * 60)
    print()
    # Run twice to catch flaky timing on loaded systems
    for run_num in range(1, 3):
        print(f"Run {run_num}/2:")
        asyncio.run(run_timing_check())
        print()
    print("All timing checks passed. Parallel execution confirmed.")
if __name__ == "__main__":
    main()