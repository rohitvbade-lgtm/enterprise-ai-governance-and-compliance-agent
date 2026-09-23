"""
AI Applications CRUD endpoints.
"""
from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db_dependency
from backend.app.models.ai_application import AIApplication
from backend.app.models.audit import AuditEvent
from backend.app.schemas.application import ApplicationCreate, ApplicationResponse, ApplicationUpdate

logger = structlog.get_logger(__name__)
router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db_dependency)]


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(body: ApplicationCreate, db: DbSession) -> ApplicationResponse:
    """Register a new AI application in the governance platform."""
    app = AIApplication(**body.model_dump())
    db.add(app)

    # Audit event
    audit = AuditEvent(
        event_type="APPLICATION_REGISTERED",
        application_id=app.id,
        actor="api",
        details={"name": app.name, "environment": app.environment},
        summary=f"Registered AI application: {app.name}",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(app)
    logger.info("application_registered", app_id=str(app.id), name=app.name)
    return ApplicationResponse.model_validate(app)


@router.get("", response_model=list[ApplicationResponse])
async def list_applications(db: DbSession) -> list[ApplicationResponse]:
    """List all registered AI applications."""
    result = await db.execute(select(AIApplication).order_by(AIApplication.created_at.desc()))
    apps = result.scalars().all()
    return [ApplicationResponse.model_validate(a) for a in apps]


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(application_id: uuid.UUID, db: DbSession) -> ApplicationResponse:
    """Get a specific AI application by ID."""
    result = await db.execute(
        select(AIApplication).where(AIApplication.id == application_id)
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationResponse.model_validate(app)


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: uuid.UUID, body: ApplicationUpdate, db: DbSession
) -> ApplicationResponse:
    """Update an AI application's metadata."""
    result = await db.execute(
        select(AIApplication).where(AIApplication.id == application_id)
    )
    app = result.scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(app, field, value)

    audit = AuditEvent(
        event_type="APPLICATION_UPDATED",
        application_id=app.id,
        actor="api",
        details=body.model_dump(exclude_none=True),
        summary=f"Updated AI application: {app.name}",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(app)
    return ApplicationResponse.model_validate(app)

