"""Workday careers-site client, using the CXS API Workday's own job-board
frontend calls (`/wday/cxs/{tenant}/{site}/jobs`). This is undocumented but
verified live and working against Workday's own board and Deutsche Bank's
(db.wd3.myworkdayjobs.com/DBWebsite — 108 real Frankfurt/Germany listings at
verification time). No API key needed.

Two-phase like SmartRecruiters: the list endpoint gives title/location/path
only. A follow-up per-job detail call
(`/wday/cxs/{tenant}/{site}{externalPath}`) returns `jobDescription` (HTML),
`country`, and the canonical `externalUrl`.

Workday doesn't return an organization name anywhere in this API, so the
caller supplies `company_name`.
"""

from __future__ import annotations

import httpx

from applicationhelper.agents.ats_clients._html import html_to_text
from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType

_LIST_URL = "https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
_DETAIL_URL = "https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}{external_path}"
_PAGE_SIZE = 20


async def fetch_workday_jobs(
    tenant: str,
    dc: str,
    site: str,
    client: httpx.AsyncClient,
    company_name: str | None = None,
    search_text: str = "",
    max_results: int = 20,
) -> list[JobPosting]:
    list_response = await client.post(
        _LIST_URL.format(tenant=tenant, dc=dc, site=site),
        json={"appliedFacets": {}, "limit": min(_PAGE_SIZE, max_results), "offset": 0, "searchText": search_text},
    )
    list_response.raise_for_status()
    summaries = list_response.json().get("jobPostings", [])[:max_results]

    postings: list[JobPosting] = []
    for summary in summaries:
        external_path = summary.get("externalPath")
        if not external_path:
            continue
        detail = await _fetch_detail(tenant, dc, site, external_path, client)
        postings.append(_to_job_posting(detail, company_name or tenant))
    return postings


async def _fetch_detail(
    tenant: str, dc: str, site: str, external_path: str, client: httpx.AsyncClient
) -> dict:
    response = await client.get(
        _DETAIL_URL.format(tenant=tenant, dc=dc, site=site, external_path=external_path)
    )
    response.raise_for_status()
    return response.json()["jobPostingInfo"]


def _to_job_posting(info: dict, company_name: str) -> JobPosting:
    country = (info.get("country") or {}).get("descriptor")
    location = info.get("location")
    full_location = ", ".join(part for part in (location, country) if part)

    return JobPosting(
        title=info["title"],
        company=company_name,
        location=full_location or None,
        remote_type=_infer_remote_type(info),
        description_text=html_to_text(info.get("jobDescription") or ""),
        apply_url=info["externalUrl"],
        source=ATSPlatform.WORKDAY,
        posted_date=info.get("startDate") or info.get("postedOn"),
    )


def _infer_remote_type(info: dict) -> RemoteType:
    remote = info.get("remote")
    if remote is True:
        return RemoteType.REMOTE
    if remote is False:
        return RemoteType.UNKNOWN
    return RemoteType.UNKNOWN
