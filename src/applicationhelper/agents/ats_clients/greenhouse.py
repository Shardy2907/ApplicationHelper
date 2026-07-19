"""Greenhouse public Job Board API client.

Verified against a live board (https://boards-api.greenhouse.io/v1/boards/gitlab/jobs?content=true):
unauthenticated, returns {"jobs": [{"title", "location": {"name"}, "content" (HTML-escaped HTML),
"absolute_url", "company_name", "first_published", ...}]}.
"""

from __future__ import annotations

import httpx

from applicationhelper.agents.ats_clients._html import html_to_text
from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"


async def fetch_greenhouse_jobs(board_token: str, client: httpx.AsyncClient) -> list[JobPosting]:
    response = await client.get(_BASE_URL.format(board_token=board_token), params={"content": "true"})
    response.raise_for_status()
    data = response.json()

    postings: list[JobPosting] = []
    for job in data.get("jobs", []):
        location_name = (job.get("location") or {}).get("name")
        postings.append(
            JobPosting(
                title=job["title"],
                company=job.get("company_name") or board_token,
                location=location_name,
                remote_type=_infer_remote_type(location_name),
                description_text=html_to_text(job.get("content", "")),
                apply_url=job["absolute_url"],
                source=ATSPlatform.GREENHOUSE,
                posted_date=job.get("first_published"),
            )
        )
    return postings


def _infer_remote_type(location_name: str | None) -> RemoteType:
    if location_name and "remote" in location_name.lower():
        return RemoteType.REMOTE
    return RemoteType.UNKNOWN
