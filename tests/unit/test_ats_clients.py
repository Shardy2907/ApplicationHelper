from __future__ import annotations

import httpx
import pytest

from applicationhelper.agents.ats_clients.ashby import fetch_ashby_jobs
from applicationhelper.agents.ats_clients.greenhouse import fetch_greenhouse_jobs
from applicationhelper.models.job import ATSPlatform, RemoteType

# Trimmed fixtures mirroring the real shapes verified against live boards
# (boards-api.greenhouse.io/v1/boards/gitlab/jobs and
# api.ashbyhq.com/posting-api/job-board/ashby) on 2026-07-19.
GREENHOUSE_RESPONSE = {
    "jobs": [
        {
            "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/8503792002",
            "id": 8503792002,
            "title": "Account Executive - Italy",
            "company_name": "GitLab",
            "location": {"name": "Remote, Italy"},
            "first_published": "2026-04-17T05:58:03-04:00",
            "content": "&lt;div&gt;&lt;p&gt;We are hiring a &quot;great&quot; AE.&lt;/p&gt;&lt;/div&gt;",
        },
        {
            "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/9999999999",
            "id": 9999999999,
            "title": "Office Manager",
            "company_name": "GitLab",
            "location": {"name": "San Francisco, CA"},
            "first_published": "2026-04-01T00:00:00-04:00",
            "content": "&lt;p&gt;On-site role.&lt;/p&gt;",
        },
    ]
}

ASHBY_RESPONSE = {
    "apiVersion": "1",
    "jobs": [
        {
            "id": "7458d4e9-da2e-47bd-98cb-adfda43d42b2",
            "title": "Engineering Manager - EU",
            "location": "Remote - European Union",
            "isRemote": True,
            "workplaceType": "Remote",
            "publishedAt": "2024-03-04T14:29:08.532+00:00",
            "jobUrl": "https://jobs.ashbyhq.com/ashby/7458d4e9-da2e-47bd-98cb-adfda43d42b2",
            "applyUrl": "https://jobs.ashbyhq.com/ashby/7458d4e9-da2e-47bd-98cb-adfda43d42b2/apply",
            "descriptionHtml": "<p>Lead the EU team.</p>",
            "descriptionPlain": "Lead the EU team.",
        },
        {
            "id": "no-apply-url-job",
            "title": "Broken listing",
            "location": "Nowhere",
            "isRemote": False,
            "workplaceType": "Onsite",
            "publishedAt": None,
            "descriptionPlain": "Should be skipped, has no apply URL.",
        },
    ]
}


def _mock_client(json_body: dict, expected_url_fragment: str) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert expected_url_fragment in str(request.url)
        return httpx.Response(200, json=json_body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_greenhouse_jobs_parses_and_strips_html():
    async with _mock_client(GREENHOUSE_RESPONSE, "boards-api.greenhouse.io/v1/boards/gitlab") as client:
        jobs = await fetch_greenhouse_jobs("gitlab", client)

    assert len(jobs) == 2
    job = jobs[0]
    assert job.title == "Account Executive - Italy"
    assert job.company == "GitLab"
    assert job.location == "Remote, Italy"
    assert job.remote_type == RemoteType.REMOTE
    assert job.source == ATSPlatform.GREENHOUSE
    assert job.apply_url == "https://job-boards.greenhouse.io/gitlab/jobs/8503792002"
    # HTML entities unescaped and tags stripped
    assert "<" not in job.description_text
    assert '"great"' in job.description_text

    assert jobs[1].remote_type == RemoteType.UNKNOWN


async def test_fetch_ashby_jobs_parses_and_skips_jobs_without_apply_url():
    async with _mock_client(ASHBY_RESPONSE, "api.ashbyhq.com/posting-api/job-board/ashby") as client:
        jobs = await fetch_ashby_jobs("ashby", client, company_name="Ashby")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Engineering Manager - EU"
    assert job.company == "Ashby"
    assert job.remote_type == RemoteType.REMOTE
    assert job.source == ATSPlatform.ASHBY
    assert job.description_text == "Lead the EU team."
    assert job.apply_url.endswith("/apply")


async def test_fetch_ashby_jobs_defaults_company_name_to_board_name():
    async with _mock_client(ASHBY_RESPONSE, "job-board/ashby") as client:
        jobs = await fetch_ashby_jobs("ashby", client)

    assert jobs[0].company == "ashby"


async def test_http_error_propagates(monkeypatch=None):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_greenhouse_jobs("does-not-exist", client)
