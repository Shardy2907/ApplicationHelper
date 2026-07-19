from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from applicationhelper.utils.time import utcnow


class WorkExperience(BaseModel):
    company: str
    title: str
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    bullets: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    gpa: str | None = None


class CandidateProfile(BaseModel):
    id: int | None = None
    full_name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[WorkExperience] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    raw_cv_text: str | None = None
    source_cv_path: str | None = None
    source_cover_letter_path: str | None = None
    parsed_at: datetime = Field(default_factory=utcnow)
