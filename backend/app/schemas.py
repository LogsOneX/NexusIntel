from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Mode = Literal["standard", "active", "aggressive"]


class InvestigationCreate(BaseModel):
    target: str = Field(..., min_length=2, max_length=512)
    mode: Mode = "standard"


class ManualEntityCreate(BaseModel):
    type: str = Field(..., min_length=2, max_length=80)
    value: str = Field(..., min_length=1, max_length=1024)
    label: str | None = None
    confidence: int = Field(default=70, ge=0, le=100)
    properties: dict[str, Any] = Field(default_factory=dict)
    source_entity_id: str | None = None
    relationship_type: str = "manual_link"


class ExpandRequest(BaseModel):
    entity_id: str
    mode: Mode | None = None


class LegacyNexusRequest(BaseModel):
    target: str | None = Field(default=None, max_length=512)
    mode: Mode | None = None


class InvestigationOut(BaseModel):
    id: str
    target: str
    target_type: str
    mode: str
    status: str
    summary: dict[str, Any]
    error: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class EntityOut(BaseModel):
    id: str
    type: str
    value: str
    label: str
    confidence: int
    source: str
    properties: dict[str, Any]

    model_config = {"from_attributes": True}


class RelationshipOut(BaseModel):
    id: str
    source: str
    target: str
    type: str
    label: str
    confidence: int
    properties: dict[str, Any]


class EventOut(BaseModel):
    id: str
    level: str
    message: str
    module: str | None
    payload: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
