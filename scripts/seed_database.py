#!/usr/bin/env python
"""
Database seed script.

Seeds the database with sample AI applications and a demo policy exception
so the system is ready to demonstrate all 5 governance scenarios.

Usage:
    uv run python scripts/seed_database.py
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


SAMPLE_APPLICATIONS = [
    {
        "name": "Customer Support Copilot",
        "description": "AI assistant for customer service agents. Handles queries, suggests responses, and escalates complex issues.",
        "owner": "Sarah Chen",
        "department": "Customer Experience",
        "model_provider": "groq",
        "model_name": "llama-3.1-8b-instant",
        "environment": "production",
        "purpose": "Assist human agents in resolving customer queries faster and more consistently.",
        "data_classification": "CONFIDENTIAL",
        "status": "ACTIVE",
    },
    {
        "name": "HR Assistant",
        "description": "Internal HR tool for answering employee policy questions and leave management.",
        "owner": "James Okafor",
        "department": "Human Resources",
        "model_provider": "ollama",
        "model_name": "llama3.2",
        "environment": "production",
        "purpose": "Answer HR policy questions and assist with leave/benefits queries.",
        "data_classification": "RESTRICTED",
        "status": "ACTIVE",
    },
    {
        "name": "Financial Advisory Bot",
        "description": "Pilot AI assistant for retail banking customers. Provides personalized savings and investment insights.",
        "owner": "Priya Nair",
        "department": "Retail Banking",
        "model_provider": "groq",
        "model_name": "llama-3.1-70b-versatile",
        "environment": "staging",
        "purpose": "Help customers understand their financial options and make informed savings decisions.",
        "data_classification": "RESTRICTED",
        "status": "ACTIVE",
    },
    {
        "name": "Developer Coding Assistant",
        "description": "Internal coding assistant integrated with the developer IDE. Suggests code completions and reviews.",
        "owner": "Alex Kim",
        "department": "Engineering",
        "model_provider": "groq",
        "model_name": "llama-3.1-8b-instant",
        "environment": "production",
        "purpose": "Improve developer productivity on internal codebases.",
        "data_classification": "INTERNAL",
        "status": "ACTIVE",
    },
]


async def main() -> None:
    import structlog
    structlog.configure(
        processors=[structlog.stdlib.add_log_level, structlog.dev.ConsoleRenderer()],
        logger_factory=structlog.PrintLoggerFactory(),
    )
    logger = structlog.get_logger()

    from backend.app.db.session import get_db
    from backend.app.models.ai_application import AIApplication
    from backend.app.models.audit import AuditEvent
    from sqlalchemy import select

    print("\n" + "=" * 60)
    print("DATABASE SEED SCRIPT")
    print("=" * 60)

    created_apps = []

    async with get_db() as db:
        for app_data in SAMPLE_APPLICATIONS:
            # Check if already exists
            result = await db.execute(
                select(AIApplication).where(AIApplication.name == app_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  ~ {app_data['name']:40s} (already exists, skipping)")
                created_apps.append(existing)
                continue

            app = AIApplication(id=uuid.uuid4(), **app_data)
            db.add(app)
            audit = AuditEvent(
                event_type="APPLICATION_REGISTERED",
                application_id=app.id,
                actor="seed_script",
                details={"name": app.name, "environment": app.environment},
                summary=f"Seeded application: {app.name}",
            )
            db.add(audit)
            created_apps.append(app)
            print(f"  [OK] {app.name:40s} ({app.environment})")

        await db.commit()

    print(f"\nTotal applications: {len(created_apps)}")
    print("\nApplication IDs (use these in demo scenarios):")
    for app in created_apps:
        print(f"  {app.name:40s}  id={app.id}")

    print("\n" + "=" * 60)
    print("Seed complete. Run the demo with:")
    print("  uv run python scripts/run_demo.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

