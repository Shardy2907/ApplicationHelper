from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from applicationhelper.utils.time import utcnow


class RemoteType(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class ATSPlatform(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKDAY = "workday"
    COMPANY_SITE = "company_site"
    USER_SPECIFIED = "user_specified"


class JobPosting(BaseModel):
    id: str | None = None
    title: str
    company: str
    location: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    description_text: str
    apply_url: str
    source: ATSPlatform
    posted_date: str | None = None
    discovered_at: datetime = Field(default_factory=utcnow)

    def model_post_init(self, __context) -> None:
        if not self.id:
            self.id = hashlib.sha256(self.apply_url.encode("utf-8")).hexdigest()[:16]
