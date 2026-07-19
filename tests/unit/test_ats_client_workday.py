from __future__ import annotations

import httpx

from applicationhelper.agents.ats_clients.workday import fetch_workday_jobs
from applicationhelper.models.job import ATSPlatform, RemoteType

# Trimmed fixtures mirroring the real shapes verified against
# db.wd3.myworkdayjobs.com (Deutsche Bank's Workday board) on 2026-07-19.
LIST_RESPONSE = {
    "total": 1,
    "jobPostings": [
        {
            "title": "Tax Specialist (d/m/w)",
            "externalPath": "/job/Frankfurt-Taunusanlage-12/Tax-Specialist_R0442040",
            "locationsText": "Frankfurt Taunusanlage 12",
            "postedOn": "Posted 2 Days Ago",
        }
    ],
    "facets": [],
}

DETAIL_RESPONSE = {
    "jobPostingInfo": {
        "title": "Tax Specialist (d/m/w)",
        "jobDescription": "<p>Steuerrecht Aufgaben.</p>",
        "location": "Frankfurt Taunusanlage 12",
        "country": {"descriptor": "Germany", "id": "abc123"},
        "postedOn": "Posted 2 Days Ago",
        "startDate": "2026-07-17",
        "externalUrl": "https://db.wd3.myworkdayjobs.com/DBWebsite/job/Frankfurt-Taunusanlage-12/Tax-Specialist_R0442040",
        "remote": None,
    }
}


def _mock_client() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert request.url.path == "/wday/cxs/db/DBWebsite/jobs"
            return httpx.Response(200, json=LIST_RESPONSE)
        assert request.url.path == "/wday/cxs/db/DBWebsite/job/Frankfurt-Taunusanlage-12/Tax-Specialist_R0442040"
        return httpx.Response(200, json=DETAIL_RESPONSE)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_workday_jobs_combines_list_and_detail():
    async with _mock_client() as client:
        jobs = await fetch_workday_jobs("db", "wd3", "DBWebsite", client, company_name="Deutsche Bank")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Tax Specialist (d/m/w)"
    assert job.company == "Deutsche Bank"
    assert "Germany" in job.location
    assert "Frankfurt" in job.location
    assert job.remote_type == RemoteType.UNKNOWN
    assert job.source == ATSPlatform.WORKDAY
    assert job.apply_url == DETAIL_RESPONSE["jobPostingInfo"]["externalUrl"]
    assert job.description_text == "Steuerrecht Aufgaben."


async def test_fetch_workday_jobs_defaults_company_name_to_tenant():
    async with _mock_client() as client:
        jobs = await fetch_workday_jobs("db", "wd3", "DBWebsite", client)

    assert jobs[0].company == "db"


async def test_fetch_workday_jobs_skips_postings_without_external_path():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"total": 1, "jobPostings": [{"title": "No path"}]})
        raise AssertionError("Should not fetch detail for a posting without externalPath")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        jobs = await fetch_workday_jobs("db", "wd3", "DBWebsite", client)

    assert jobs == []
