"""SmartRecruiters public Postings API client.

Verified against a live board (https://api.smartrecruiters.com/v1/companies/BoschGroup/postings?country=de):
unauthenticated, documented API. `companyIdentifier` is case-sensitive and
comes from the company's careers URL (careers.smartrecruiters.com/{Identifier}).
Supports an optional `country` query param (ISO 3166-1 alpha-2, e.g. "de") for
server-side filtering, which `ATSBoardTarget.extra={"country": ...}` maps onto.

Two-phase like Workday: the list endpoint doesn't include a description, so
each posting needs a follow-up detail call
(`/v1/companies/{id}/postings/{postingId}`) which returns `jobAd.sections`
(HTML) and the canonical `postingUrl`.
"""

from __future__ import annotations

import httpx

from applicationhelper.agents.ats_clients._html import html_to_text
from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType

_LIST_URL = "https://api.smartrecruiters.com/v1/companies/{company_identifier}/postings"
_DETAIL_URL = "https://api.smartrecruiters.com/v1/companies/{company_identifier}/postings/{posting_id}"
_PAGE_SIZE = 100


async def fetch_smartrecruiters_jobs(
    company_identifier: str,
    client: httpx.AsyncClient,
    country: str | None = None,
    max_results: int = 20,
) -> list[JobPosting]:
    summaries = await _list_postings(company_identifier, client, country, max_results)

    postings: list[JobPosting] = []
    for summary in summaries:
        detail = await _fetch_detail(company_identifier, summary["id"], client)
        postings.append(_to_job_posting(detail, company_identifier))
    return postings


async def _list_postings(
    company_identifier: str, client: httpx.AsyncClient, country: str | None, max_results: int
) -> list[dict]:
    summaries: list[dict] = []
    offset = 0

    while len(summaries) < max_results:
        params: dict[str, str | int] = {"limit": _PAGE_SIZE, "offset": offset}
        if country:
            params["country"] = country

        response = await client.get(
            _LIST_URL.format(company_identifier=company_identifier), params=params
        )
        response.raise_for_status()
        data = response.json()

        content = data.get("content", [])
        if not content:
            break

        summaries.extend(content)
        offset += len(content)
        if offset >= data.get("totalFound", 0):
            break

    return summaries[:max_results]


async def _fetch_detail(company_identifier: str, posting_id: str, client: httpx.AsyncClient) -> dict:
    response = await client.get(
        _DETAIL_URL.format(company_identifier=company_identifier, posting_id=posting_id)
    )
    response.raise_for_status()
    return response.json()


def _to_job_posting(detail: dict, company_identifier: str) -> JobPosting:
    location = detail.get("location") or {}
    company = detail.get("company") or {}
    sections = (detail.get("jobAd") or {}).get("sections") or {}

    description_parts = []
    for key in ("jobDescription", "qualifications", "additionalInformation"):
        text = (sections.get(key) or {}).get("text")
        if text:
            description_parts.append(html_to_text(text))

    return JobPosting(
        title=detail["name"],
        company=company.get("name") or company_identifier,
        location=location.get("fullLocation") or location.get("city"),
        remote_type=RemoteType.REMOTE if location.get("remote") else RemoteType.UNKNOWN,
        description_text="\n\n".join(description_parts),
        apply_url=detail.get("postingUrl") or detail.get("applyUrl"),
        source=ATSPlatform.SMARTRECRUITERS,
        posted_date=detail.get("releasedDate"),
    )
