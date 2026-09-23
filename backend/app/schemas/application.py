"""
Pydantic schemas for AIApplication API request/response.
Separate from ORM models — schemas are the API contract.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    owner: str = Field(..., min_length=1, max_length=255)
    department: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    purpose: Optional[str] = None
    data_classification: str = Field(
        default="INTERNAL",
        pattern="^(PUBLIC|INTERNAL|CONFIDENTIAL|RESTRICTED)$",
    )


class ApplicationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    owner: Optional[str] = None
    department: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    environment: Optional[str] = None
    purpose: Optional[str] = None
    data_classification: Optional[str] = None
    status: Optional[str] = None


class ApplicationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: Optional[str]
    owner: str
    department: Optional[str]
    model_provider: Optional[str]
    model_name: Optional[str]
    environment: str
    purpose: Optional[str]
    data_classification: str
    status: str
    risk_level: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_assessment_at: Optional[datetime]

