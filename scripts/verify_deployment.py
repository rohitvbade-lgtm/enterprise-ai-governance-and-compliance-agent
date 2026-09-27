"""
verify_deployment.py — Smoke-test the running API server.
Tests the two new endpoints introduced in the refactor:
  1. POST /api/v1/governance/evaluate/input
  2. POST /api/v1/governance/evaluate/output
  3. GET  /api/v1/assessments/{id}
  4. GET  /api/v1/assessments/{id}/findings
  5. GET  /api/v1/assessments/{input_id}/linked  ← the previously missing endpoint
Usage (server must be running on localhost:8000):
    uv run python scripts/verify_deployment.py
Exit code 0 if all checks pass, 1 if any check fails.
"""
from __future__ import annotations
import sys
import httpx
BASE_URL = "http://localhost:8000/api/v1"
def ok(label: str) -> None:
    print(f"  [OK]  {label}")
def fail(label: str, detail: str = "") -> None:
    print(f"  [FAIL] {label}")
    if detail:
        print(f"     {detail}")
    sys.exit(1)
def get_first_application(client: httpx.Client) -> str:
    """Return the ID of any registered application, or exit if none exist."""
    res = client.get(f"{BASE_URL}/applications")
    if res.status_code != 200 or not res.json():
        fail(
            "GET /applications",
            "No applications found. Run 'uv run python scripts/seed_database.py' first.",
        )
    app_id = res.json()[0]["id"]
    ok(f"GET /applications — found application {app_id}")
    return app_id
def smoke_test_input_audit(client: httpx.Client, app_id: str) -> str:
    """POST /evaluate/input with clean text → ALLOW. Returns the assessment_id."""
    print("\n--- Input Audit Endpoint ---")
    payload = {
        "application_id": app_id,
        "input_text": "What is the capital of France?",
    }
    res = client.post(f"{BASE_URL}/governance/evaluate/input", json=payload)
    if res.status_code != 200:
        fail("POST /governance/evaluate/input", f"HTTP {res.status_code}: {res.text}")
    data = res.json()
    if data.get("assessment_phase") != "INPUT":
        fail("assessment_phase == INPUT", f"got: {data.get('assessment_phase')}")
    if data.get("decision") not in ("ALLOW", "REVIEW", "BLOCK"):
        fail("decision is valid", f"got: {data.get('decision')}")
    assessment_id = data["assessment_id"]
    ok(f"POST /governance/evaluate/input → {data['decision']} (id={assessment_id})")
    return assessment_id
def smoke_test_output_audit(client: httpx.Client, app_id: str, input_assessment_id: str) -> str:
    """POST /evaluate/output linking to the input assessment → returns output assessment_id."""
    print("\n--- Output Audit Endpoint ---")
    payload = {
        "application_id": app_id,
        "output_text": "Paris is the capital of France. It is located in northern France.",
        "input_assessment_id": input_assessment_id,
    }
    res = client.post(f"{BASE_URL}/governance/evaluate/output", json=payload)
    if res.status_code != 200:
        fail("POST /governance/evaluate/output", f"HTTP {res.status_code}: {res.text}")
    data = res.json()
    if data.get("assessment_phase") != "OUTPUT":
        fail("assessment_phase == OUTPUT", f"got: {data.get('assessment_phase')}")
    if data.get("input_assessment_id") != input_assessment_id:
        fail("input_assessment_id is correctly linked", f"got: {data.get('input_assessment_id')}")
    output_assessment_id = data["assessment_id"]
    ok(f"POST /governance/evaluate/output → {data['decision']} (id={output_assessment_id})")
    return output_assessment_id
def smoke_test_get_assessment(client: httpx.Client, assessment_id: str, expected_phase: str) -> None:
    """GET /assessments/{id} → verify phase is correct."""
    res = client.get(f"{BASE_URL}/assessments/{assessment_id}")
    if res.status_code != 200:
        fail(f"GET /assessments/{assessment_id}", f"HTTP {res.status_code}: {res.text}")
    data = res.json()
    if data.get("assessment_phase") != expected_phase:
        fail(
            f"assessment_phase == {expected_phase}",
            f"got: {data.get('assessment_phase')}",
        )
    ok(f"GET /assessments/{assessment_id} → phase={expected_phase}")
def smoke_test_get_findings(client: httpx.Client, assessment_id: str) -> None:
    """GET /assessments/{id}/findings → verify it returns a list."""
    res = client.get(f"{BASE_URL}/assessments/{assessment_id}/findings")
    if res.status_code != 200:
        fail(f"GET /assessments/{assessment_id}/findings", f"HTTP {res.status_code}: {res.text}")
    findings = res.json()
    if not isinstance(findings, list):
        fail("findings is a list", f"got: {type(findings)}")
    ok(f"GET /assessments/{assessment_id}/findings → {len(findings)} finding(s)")
def smoke_test_linked_endpoint(client: httpx.Client, input_assessment_id: str) -> None:
    """GET /assessments/{input_id}/linked → verify the output assessment appears."""
    print("\n--- Linked Assessments Endpoint (new) ---")
    res = client.get(f"{BASE_URL}/assessments/{input_assessment_id}/linked")
    if res.status_code != 200:
        fail(
            f"GET /assessments/{input_assessment_id}/linked",
            f"HTTP {res.status_code}: {res.text}",
        )
    linked = res.json()
    if not isinstance(linked, list):
        fail("linked is a list", f"got: {type(linked)}")
    if len(linked) == 0:
        fail("linked endpoint returns at least one OUTPUT assessment", "list is empty")
    for item in linked:
        if item.get("assessment_phase") != "OUTPUT":
            fail(
                "all linked assessments have phase==OUTPUT",
                f"found phase: {item.get('assessment_phase')}",
            )
    ok(f"GET /assessments/{input_assessment_id}/linked → {len(linked)} linked output assessment(s)")
def smoke_test_phase_filter(client: httpx.Client) -> None:
    """GET /assessments?phase=INPUT and ?phase=OUTPUT — verify filtering works."""
    print("\n--- Phase Filter ---")
    for phase in ("INPUT", "OUTPUT"):
        res = client.get(f"{BASE_URL}/assessments", params={"phase": phase})
        if res.status_code != 200:
            fail(f"GET /assessments?phase={phase}", f"HTTP {res.status_code}: {res.text}")
        items = res.json()
        for item in items:
            if item.get("assessment_phase") != phase:
                fail(
                    f"all results have phase={phase}",
                    f"found: {item.get('assessment_phase')}",
                )
        ok(f"GET /assessments?phase={phase} → {len(items)} result(s), all correct phase")
def main() -> None:
    print("=" * 60)
    print("Deployment Smoke Test")
    print(f"Target: {BASE_URL}")
    print("=" * 60)
    # Increase timeout for LLM-backed endpoints
    client = httpx.Client(timeout=120.0)
    try:
        app_id = get_first_application(client)
        print("\n--- GET /assessments endpoint ---")
        smoke_test_phase_filter(client)
        input_id = smoke_test_input_audit(client, app_id)
        print("\n--- GET assessment after input audit ---")
        smoke_test_get_assessment(client, input_id, expected_phase="INPUT")
        smoke_test_get_findings(client, input_id)
        output_id = smoke_test_output_audit(client, app_id, input_assessment_id=input_id)
        print("\n--- GET assessment after output audit ---")
        smoke_test_get_assessment(client, output_id, expected_phase="OUTPUT")
        smoke_test_get_findings(client, output_id)
        smoke_test_linked_endpoint(client, input_id)
    finally:
        client.close()
    print()
    print("=" * 60)
    print("[OK] All deployment smoke tests passed.")
    print("=" * 60)
if __name__ == "__main__":
    main()