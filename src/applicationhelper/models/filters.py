from __future__ import annotations

from pydantic import BaseModel, Field

from applicationhelper.models.job import ATSPlatform, RemoteType


class ATSBoardTarget(BaseModel):
    """A specific company's job board to query directly (deterministic, no LLM).

    Different platforms address a board differently:
    - Greenhouse: `board_token` is the board slug (e.g. "gitlab").
    - Ashby: `board_token` is the job-board name (e.g. "ashby").
    - SmartRecruiters: `board_token` is the companyIdentifier (e.g. "BoschGroup").
    - Workday: `board_token` is the tenant subdomain (e.g. "db"); `extra` must
      also carry `dc` (data-center subdomain, e.g. "wd3") and `site`
      (the site slug, e.g. "DBWebsite").

    `company_name` is required for platforms whose API doesn't return an
    organization name in-band (Ashby, Workday); ignored otherwise.
    `extra` carries platform-specific parameters (e.g. Workday's `dc`/`site`,
    SmartRecruiters' `country`).
    """

    platform: ATSPlatform
    board_token: str
    company_name: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


class SearchFilters(BaseModel):
    region: str | None = None  # e.g. "DACH" — auto-fills ats_boards from a hardcoded profile if set and ats_boards is empty
    ats_boards: list[ATSBoardTarget] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    target_companies: list[str] = Field(default_factory=list)
    title_keywords: list[str] = Field(default_factory=list)
    remote_types: list[RemoteType] = Field(default_factory=list)
    salary_min: float | None = None
    salary_currency: str | None = None
    excluded_companies: list[str] = Field(default_factory=list)
    user_specified_sites: list[str] = Field(default_factory=list)
