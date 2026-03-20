from pydantic import BaseModel, Field
from typing import Optional


class TreatmentPlanCreate(BaseModel):
    patient_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    goals: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field("active", pattern=r"^(active|completed|discontinued)$")


class TreatmentPlanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    goals: Optional[str] = Field(None, max_length=2000)
    notes: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = Field(None, pattern=r"^(active|completed|discontinued)$")


class TreatmentPlanResponse(BaseModel):
    id: int
    patient_id: int
    provider_id: int
    name: str
    description: Optional[str] = None
    goals: Optional[str] = None
    notes: Optional[str] = None
    status: str
    is_active: bool
    created_at: str
    updated_at: str
