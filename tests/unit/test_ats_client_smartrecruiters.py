from __future__ import annotations

import httpx

from applicationhelper.agents.ats_clients.smartrecruiters import fetch_smartrecruiters_jobs
from applicationhelper.models.job import ATSPlatform, RemoteType

# Trimmed fixtures mirroring the real shapes verified against
# api.smartrecruiters.com/v1/companies/BoschGroup/postings?country=de on 2026-07-19.
LIST_RESPONSE = {
    "offset": 0,
    "limit": 100,
    "totalFound": 1,
    "content": [
        {
            "id": "744000138344739",
            "name": "Key Account Manager (w/m/div.)",
            "company": {"identifier": "BoschGroup", "name": "Bosch Group"},
            "location": {"city": "Eschborn", "country": "de", "remote": False, "fullLocation": "Eschborn, DE"},
            "releasedDate": "2026-07-19T14:46:27.094Z",
        }
    ],
}

DETAIL_RESPONSE = {
    "id": "744000138344739",
    "name": "Key Account Manager (w/m/div.)",
    "company": {"identifier": "BoschGroup", "name": "Bosch Group"},
    "location": {"city": "Eschborn", "country": "de", "remote": False, "fullLocation": "Eschborn, DE"},
    "releasedDate": "2026-07-19T14:46:27.094Z",
    "postingUrl": "https://jobs.smartrecruiters.com/BoschGroup/744000138344739-key-account-manager",
    "applyUrl": "https://jobs.smartrecruiters.com/BoschGroup/744000138344739-key-account-manager?oga=true",
    "jobAd": {
        "sections": {
            "jobDescription": {"title": "Stellenbeschreibung", "text": "<p>Sie gewinnen Kunden.</p>"},
            "qualifications": {"title": "Qualifikationen", "text": "<ul><li>Studium</li></ul>"},
        }
    },
}


def _mock_client() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/postings/744000138344739" in str(request.url):
            return httpx.Response(200, json=DETAIL_RESPONSE)
        assert "country=de" in str(request.url)
        return httpx.Response(200, json=LIST_RESPONSE)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_fetch_smartrecruiters_jobs_combines_list_and_detail():
    async with _mock_client() as client:
        jobs = await fetch_smartrecruiters_jobs("BoschGroup", client, country="de")

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Key Account Manager (w/m/div.)"
    assert job.company == "Bosch Group"
    assert job.location == "Eschborn, DE"
    assert job.remote_type == RemoteType.UNKNOWN
    assert job.source == ATSPlatform.SMARTRECRUITERS
    assert job.apply_url == "https://jobs.smartrecruiters.com/BoschGroup/744000138344739-key-account-manager"
    assert "Sie gewinnen Kunden." in job.description_text
    assert "Studium" in job.description_text
    assert "<" not in job.description_text


async def test_fetch_smartrecruiters_jobs_stops_at_max_results():
    many_content = [{**LIST_RESPONSE["content"][0], "id": str(i)} for i in range(5)]
    list_response = {"offset": 0, "limit": 100, "totalFound": 5, "content": many_content}

    def handler(request: httpx.Request) -> httpx.Response:
        segments = request.url.path.strip("/").split("/")
        # /v1/companies/{id}/postings -> list, /v1/companies/{id}/postings/{postingId} -> detail
        if len(segments) == 5:
            posting_id = segments[-1]
            return httpx.Response(200, json={**DETAIL_RESPONSE, "id": posting_id})
        return httpx.Response(200, json=list_response)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        jobs = await fetch_smartrecruiters_jobs("BoschGroup", client, max_results=2)

    assert len(jobs) == 2
