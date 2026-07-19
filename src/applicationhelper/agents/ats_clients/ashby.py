"""Ashby public Job Board API client.

Verified against a live board (https://api.ashbyhq.com/posting-api/job-board/ashby):
unauthenticated, returns {"jobs": [{"title", "location", "isRemote", "workplaceType",
"descriptionPlain", "applyUrl"/"jobUrl", "publishedAt", ...}]}. The response has no
organization name field, so the caller supplies `company_name`.
"""

from __future__ import annotations

import httpx

from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType

_BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{board_name}"


async def fetch_ashby_jobs(
    board_name: str, client: httpx.AsyncClient, company_name: str | None = None
) -> list[JobPosting]:
    response = await client.get(_BASE_URL.format(board_name=board_name))
    response.raise_for_status()
    data = response.json()

    postings: list[JobPosting] = []
    for job in data.get("jobs", []):
        apply_url = job.get("applyUrl") or job.get("jobUrl")
        if not apply_url:
            continue
        postings.append(
            JobPosting(
                title=job["title"],
                company=company_name or board_name,
                location=job.get("location"),
                remote_type=_infer_remote_type(job),
                description_text=job.get("descriptionPlain") or "",
                apply_url=apply_url,
                source=ATSPlatform.ASHBY,
                posted_date=job.get("publishedAt"),
            )
        )
    return postings


def _infer_remote_type(job: dict) -> RemoteType:
    if job.get("isRemote"):
        return RemoteType.REMOTE
    workplace_type = (job.get("workplaceType") or "").lower()
    if "hybrid" in workplace_type:
        return RemoteType.HYBRID
    if "onsite" in workplace_type or "on-site" in workplace_type:
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN
