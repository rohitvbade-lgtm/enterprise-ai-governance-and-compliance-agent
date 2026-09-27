"""
End-to-end test for the full two-phase INPUT → OUTPUT audit sequence.
This test exercises the complete interaction lifecycle using a real database:
  1. Run an input audit on a user prompt.
  2. Capture the returned assessment_id.
  3. Run an output audit referencing that input_assessment_id.
  4. Verify the FK relationship via the ORM assessment.input_assessment relationship.
  5. Verify the GET /{input_id}/linked endpoint returns the output assessment.
This is the critical integration test that confirms the two phases are truly
separate DB rows and that the linkage is correctly established end-to-end.
"""
from __future__ import annotations
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.app.main import app
from backend.app.db.session import get_db
from backend.app.models.ai_application import AIApplication
from backend.app.models.assessment import GovernanceAssessment, Finding
from backend.app.graph.workflow import app_workflow
# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def sample_application() -> AIApplication:
    """Return an existing AI application or create a minimal one for this test."""
    async with get_db() as db:
        result = await db.execute(
            select(AIApplication).where(AIApplication.name == "Developer Coding Assistant")
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        test_app = AIApplication(
            name="Test App — Two-Phase E2E",
            description="Created by end-to-end test suite",
            owner="Test Suite",
            department="QA",
            model_provider="groq",
            model_name="llama-3.1-8b-instant",
            environment="test",
            data_classification="INTERNAL",
            risk_level="MEDIUM",
        )
        db.add(test_app)
        await db.flush()
        return test_app
    
def make_state(
    app_id: uuid.UUID,
    phase: str,
    text: str,
    input_assessment_id: uuid.UUID | None = None,
) -> dict:
    """Build a fully initialized GovernanceState for any phase."""
    return {
        "application_id": app_id,
        "assessment_phase": phase,
        "assessment_type": "REAL_TIME",
        "text_to_evaluate": text,
        "input_assessment_id": input_assessment_id,
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

# ── Core two-phase E2E test ───────────────────────────────────────────────────
class TestTwoPhaseEndToEnd:
    """End-to-end tests covering the complete INPUT → OUTPUT audit sequence."""
    @pytest.mark.asyncio
    async def test_full_two_phase_sequence_via_workflow(self, sample_application):
        """
        Step (a): Run an input audit.
        Step (b): Capture the assessment_id from the input result.
        Step (c): Run an output audit with input_assessment_id set to the captured ID.
        Step (d): Verify the FK relationship resolves via assessment.input_assessment ORM
                  relationship — confirming the two rows are correctly linked in the DB.
        """
        app_id = sample_application.id
        # (a) Run the INPUT audit
        input_state = make_state(
            app_id=app_id,
            phase="INPUT",
            text="What is my account balance?",
        )
        input_result = await app_workflow.ainvoke(input_state)

        assert input_result.get("errors") == [] or input_result.get("errors") is None, (
            f"Input audit failed with errors: {input_result.get('errors')}"
        )
        assert input_result["decision"] in ("ALLOW", "REVIEW", "BLOCK")
        assert input_result["assessment_id"] is not None
        # (b) Capture the input assessment ID
        input_assessment_id: uuid.UUID = input_result["assessment_id"]
        # Verify the input row exists and has the correct phase
        async with get_db() as db:
            q = await db.execute(
                select(GovernanceAssessment).where(GovernanceAssessment.id == input_assessment_id)
            )
            input_assessment = q.scalar_one()
            assert input_assessment.assessment_phase == "INPUT"
            assert input_assessment.input_assessment_id is None  # INPUT rows have no parent
        # (c) Run the OUTPUT audit, linking back to the input
        output_state = make_state(
            app_id=app_id,
            phase="OUTPUT",
            text="Your current account balance is $1,250.00.",
            input_assessment_id=input_assessment_id,
        )
        output_result = await app_workflow.ainvoke(output_state)
        assert output_result.get("errors") == [] or output_result.get("errors") is None, (
            f"Output audit failed with errors: {output_result.get('errors')}"
        )
        assert output_result["decision"] in ("ALLOW", "REVIEW", "BLOCK")
        assert output_result["assessment_id"] is not None

        output_assessment_id: uuid.UUID = output_result["assessment_id"]
        # (d) Verify FK relationship via ORM — the output assessment must link to the input
        async with get_db() as db:
            q = await db.execute(
                select(GovernanceAssessment)
                .options(selectinload(GovernanceAssessment.input_assessment))
                .where(GovernanceAssessment.id == output_assessment_id)
            )
            output_assessment = q.scalar_one()
            # Phase is OUTPUT
            assert output_assessment.assessment_phase == "OUTPUT"
            # The FK column is set correctly
            assert output_assessment.input_assessment_id == input_assessment_id
            # The ORM relationship resolves to the actual input assessment row
            linked_input = output_assessment.input_assessment
            assert linked_input is not None, (
                "assessment.input_assessment ORM relationship did not resolve — "
                "the FK was not established correctly in the DB"
            )
            assert linked_input.id == input_assessment_id
            assert linked_input.assessment_phase == "INPUT"

    @pytest.mark.asyncio
    async def test_full_two_phase_sequence_via_api(self, sample_application):
        """
        Full HTTP flow exercising both endpoints and the /linked endpoint:
          POST /governance/evaluate/input  → capture assessment_id
          POST /governance/evaluate/output → with input_assessment_id
          GET  /assessments/{output_id}    → verify phase and linkage
          GET  /assessments/{input_id}/linked → verify the output appears in the trace
        """
        app_id = str(sample_application.id)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Audit the user prompt
            input_payload = {
                "application_id": app_id,
                "input_text": "Show me how to write a Python sort function.",
            }
            res_input = await client.post(
                "/api/v1/governance/evaluate/input", json=input_payload
            )
            assert res_input.status_code == 200, res_input.text
            input_data = res_input.json()
            assert input_data["assessment_phase"] == "INPUT"
            assert "assessment_id" in input_data
            input_assessment_id = input_data["assessment_id"]

            # 2. Audit the AI response, linked to the input
            output_payload = {
                "application_id": app_id,
                "output_text": (
                    "Here is a Python sort function: "
                    "sorted_list = sorted(my_list, key=lambda x: x['value'])"
                ),
                "input_assessment_id": input_assessment_id,
            }
            res_output = await client.post(
                "/api/v1/governance/evaluate/output", json=output_payload
            )
            assert res_output.status_code == 200, res_output.text
            output_data = res_output.json()
            assert output_data["assessment_phase"] == "OUTPUT"
            assert output_data["input_assessment_id"] == input_assessment_id
            output_assessment_id = output_data["assessment_id"]

            # 3. Verify the output assessment record is correct
            res_get = await client.get(f"/api/v1/assessments/{output_assessment_id}")
            assert res_get.status_code == 200
            get_data = res_get.json()
            assert get_data["assessment_phase"] == "OUTPUT"
            assert get_data["input_assessment_id"] == input_assessment_id

            # 4. Verify the /linked endpoint returns the output assessment
            res_linked = await client.get(
                f"/api/v1/assessments/{input_assessment_id}/linked"
            )
            assert res_linked.status_code == 200, res_linked.text
            linked_list = res_linked.json()
            assert isinstance(linked_list, list)
            assert len(linked_list) >= 1, (
                "GET /assessments/{input_id}/linked returned empty list — "
                "the output assessment was not linked to the input"
            )
            # All items in the linked list must be OUTPUT assessments
            for item in linked_list:
                assert item["assessment_phase"] == "OUTPUT"
                assert item["input_assessment_id"] == input_assessment_id
            # Our specific output assessment must be in the list
            linked_ids = {item["id"] for item in linked_list}
            assert output_assessment_id in linked_ids, (
                f"Expected output assessment {output_assessment_id} in linked list, "
                f"got: {linked_ids}"
            )

    @pytest.mark.asyncio
    async def test_linked_endpoint_returns_404_for_nonexistent_input(self):
        """GET /assessments/{bogus_id}/linked must return 404, not an empty list."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            bogus_id = str(uuid.uuid4())
            res = await client.get(f"/api/v1/assessments/{bogus_id}/linked")
            assert res.status_code == 404, (
                f"Expected 404 for a non-existent input assessment, got {res.status_code}"
            )

    @pytest.mark.asyncio
    async def test_output_without_link_has_null_input_assessment_id(self, sample_application):
        """
        An OUTPUT assessment submitted without an input_assessment_id
        should persist with a NULL input_assessment_id — not fail.
        """
        output_state = make_state(
            app_id=sample_application.id,
            phase="OUTPUT",
            text="The capital of France is Paris.",
            input_assessment_id=None,  # Not linked to any input
        )
        result = await app_workflow.ainvoke(output_state)
        assert result["decision"] in ("ALLOW", "REVIEW", "BLOCK")

        async with get_db() as db:
            q = await db.execute(
                select(GovernanceAssessment).where(
                    GovernanceAssessment.id == result["assessment_id"]
                )
            )
            assessment = q.scalar_one()
            assert assessment.assessment_phase == "OUTPUT"
            assert assessment.input_assessment_id is None  # Correctly NULL

    @pytest.mark.asyncio
    async def test_two_separate_db_rows_are_created(self, sample_application):
        """
        One input + one output audit must produce exactly two separate
        GovernanceAssessment rows, NOT one merged row.
        """
        app_id = sample_application.id
        # Run input
        input_result = await app_workflow.ainvoke(
            make_state(app_id, "INPUT", "Tell me about your features.")
        )
        input_id = input_result["assessment_id"]
        # Run output linked to input
        output_result = await app_workflow.ainvoke(
            make_state(
                app_id, "OUTPUT",
                "I can help you with financial analysis and reporting.",
                input_assessment_id=input_id,
            )
        )
        output_id = output_result["assessment_id"]
        # Confirm they are two different rows
        assert input_id != output_id, "Input and output share the same row — architecture is broken"

        async with get_db() as db:
            q = await db.execute(
                select(GovernanceAssessment).where(
                    GovernanceAssessment.id.in_([input_id, output_id])
                )
            )
            rows = q.scalars().all()
            assert len(rows) == 2, f"Expected 2 DB rows, found {len(rows)}"
            phases = {r.assessment_phase for r in rows}
            assert phases == {"INPUT", "OUTPUT"}, f"Unexpected phases: {phases}"