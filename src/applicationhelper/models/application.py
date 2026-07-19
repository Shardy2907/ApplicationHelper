from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from applicationhelper.utils.time import utcnow


class ApplicationStatus(str, Enum):
    SHORTLISTED = "shortlisted"
    APPROVED = "approved"
    REJECTED_BY_USER = "rejected_by_user"
    TAILORING = "tailoring"
    TAILORED = "tailored"
    DOCS_APPROVED = "docs_approved"
    SUBMITTING = "submitting"
    PAUSED_FOR_SUBMIT = "paused_for_submit"
    SUBMITTED = "submitted"
    FAILED = "failed"


class ApplicationRecord(BaseModel):
    id: int | None = None
    job_id: str
    profile_id: int
    status: ApplicationStatus = ApplicationStatus.SHORTLISTED
    tailored_cv_path: str | None = None
    tailored_cover_letter_path: str | None = None
    browser_notes: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    submitted_at: datetime | None = None
