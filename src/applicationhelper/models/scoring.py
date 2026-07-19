from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from applicationhelper.utils.time import utcnow


class MatchScore(BaseModel):
    job_id: str
    profile_id: int
    skills_score: float = Field(ge=0, le=100)
    title_seniority_score: float = Field(ge=0, le=100)
    location_score: float = Field(ge=0, le=100)
    company_score: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    rationale: str
    scored_at: datetime = Field(default_factory=utcnow)
