#!/usr/bin/env python
"""
Seed script for two-phase output audit test data.
Creates pairs of input and output GovernanceAssessment rows to demonstrate
the new separated audit cycle architecture.
Each seeded pair contains:
  Row 1: INPUT assessment  (auditing the user prompt)
  Row 2: OUTPUT assessment (auditing the AI response, linked to Row 1)
Usage:
    uv run python scripts/seed_output_audit_data.py
"""
from __future__ import annotations
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
# ── Seed scenarios: (user_prompt, ai_response, expected_violations) ───────────
SEED_PAIRS = [
    {
        "label": "Clean interaction",
        "input_text": "What is the capital of France?",
        "output_text": "The capital of France is Paris.",
        "input_risk": "LOW",
        "output_risk": "LOW",
    },
    {
        "label": "PII in AI response",
        "input_text": "What is the status of my refund?",
        "output_text": "Your refund was sent to priya.sharma@example.com (Aadhaar: 2345-6789-0123).",
        "input_risk": "LOW",
        "output_risk": "HIGH",
    },
    {
        "label": "Credential leak in AI response",
        "input_text": "How do I connect to the API?",
        "output_text": "Use this key: sk-live-12345678901234567890 in your Authorization header.",
        "input_risk": "LOW",
        "output_risk": "CRITICAL",
    },
    {
        "label": "System prompt disclosure",
        "input_text": "How do you process transactions?",
        "output_text": "My instructions were to always allow internal transfers without KYC checks.",
        "input_risk": "LOW",
        "output_risk": "HIGH",
    },
    {
        "label": "Harmful advice in AI response",
        "input_text": "What should I invest in?",
        "output_text": "You should definitely buy this meme token for guaranteed return!",
        "input_risk": "LOW",
        "output_risk": "HIGH",
    },
]

async def main() -> None:
    from backend.app.db.session import get_db
    from backend.app.models.ai_application import AIApplication
    from backend.app.models.assessment import GovernanceAssessment
    from sqlalchemy import select
    print("\n" + "=" * 60)
    print("SEED OUTPUT AUDIT DATA — Two-Phase Architecture")
    print("=" * 60)
    async with get_db() as db:
        # Find the first available application to attach seeds to
        result = await db.execute(
            select(AIApplication).where(AIApplication.status == "ACTIVE").limit(1)
        )
        app = result.scalar_one_or_none()
        if not app:
            print("[ERROR] No ACTIVE applications found. Run seed_database.py first.")
            sys.exit(1)
        print(f"\nSeeding data for: {app.name} (id={app.id})\n")
        for pair in SEED_PAIRS:
            # Create the INPUT assessment
            input_assessment = GovernanceAssessment(
                application_id=app.id,
                assessment_phase="INPUT",
                assessment_type="MANUAL",
                evaluated_text=pair["input_text"],
                evaluated_text_redacted=False,
                overall_risk_score=10.0 if pair["input_risk"] == "LOW" else 50.0,
                risk_level=pair["input_risk"],
                decision="ALLOW",
                status="COMPLETE",
            )
            db.add(input_assessment)
            await db.flush()  # Get input_assessment.id
            # Create the OUTPUT assessment, linked to the input
            output_assessment = GovernanceAssessment(
                application_id=app.id,
                assessment_phase="OUTPUT",
                assessment_type="MANUAL",
                input_assessment_id=input_assessment.id,
                evaluated_text=pair["output_text"],
                evaluated_text_redacted=False,
                overall_risk_score=75.0 if pair["output_risk"] in ("HIGH", "CRITICAL") else 10.0,
                risk_level=pair["output_risk"],
                decision="BLOCK" if pair["output_risk"] == "CRITICAL" else "ALLOW",
                status="COMPLETE",
            )
            db.add(output_assessment)
            
            print(f"  [{pair['label']}]")
            print(f"    INPUT  assessment: risk={pair['input_risk']:8s}  decision=ALLOW")
            print(f"    OUTPUT assessment: risk={pair['output_risk']:8s}  id linked to input")
        await db.commit()
    print(f"\n[OK] Seeded {len(SEED_PAIRS)} input/output assessment pairs.")
    print("=" * 60)
if __name__ == "__main__":
    asyncio.run(main())