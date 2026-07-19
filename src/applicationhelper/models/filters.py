from __future__ import annotations

from pydantic import BaseModel, Field

from applicationhelper.models.job import RemoteType


class SearchFilters(BaseModel):
    regions: list[str] = Field(default_factory=list)
    target_companies: list[str] = Field(default_factory=list)
    title_keywords: list[str] = Field(default_factory=list)
    remote_types: list[RemoteType] = Field(default_factory=list)
    salary_min: float | None = None
    salary_currency: str | None = None
    excluded_companies: list[str] = Field(default_factory=list)
    user_specified_sites: list[str] = Field(default_factory=list)
