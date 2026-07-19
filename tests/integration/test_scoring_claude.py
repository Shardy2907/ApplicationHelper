from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from applicationhelper.agents.scoring import ClaudeScoringAgent
from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType
from applicationhelper.models.profile import CandidateProfile


def _job(job_id_source: str, **overrides) -> JobPosting:
    defaults = dict(
        title="Backend Engineer",
        company="Acme Corp",
        description_text="Python role.",
        apply_url=job_id_source,
        source=ATSPlatform.GREENHOUSE,
        remote_type=RemoteType.REMOTE,
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


def _fake_client_returning(input_dict: dict) -> AsyncMock:
    tool_use_block = SimpleNamespace(type="tool_use", input=input_dict)
    response = SimpleNamespace(content=[tool_use_block])
    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


async def test_score_all_maps_batched_tool_response_by_job_id():
    profile = CandidateProfile(id=7, full_name="Jane Doe")
    job1 = _job("https://boards.greenhouse.io/acme/jobs/1")
    job2 = _job("https://boards.greenhouse.io/acme/jobs/2", title="Frontend Engineer")

    client = _fake_client_returning(
        {
            "scores": [
                {
                    "job_id": job1.id,
                    "skills_score": 90,
                    "title_seniority_score": 80,
                    "location_score": 100,
                    "company_score": 70,
                    "overall_score": 85,
                    "rationale": "Strong backend match.",
                },
                {
                    "job_id": job2.id,
                    "skills_score": 30,
                    "title_seniority_score": 20,
                    "location_score": 100,
                    "company_score": 70,
                    "overall_score": 40,
                    "rationale": "Weak frontend match.",
                },
            ]
        }
    )
    agent = ClaudeScoringAgent(client=client)

    scores = await agent.score_all(profile, [job1, job2])

    by_id = {s.job_id: s for s in scores}
    assert by_id[job1.id].overall_score == 85
    assert by_id[job1.id].profile_id == 7
    assert by_id[job2.id].rationale == "Weak frontend match."


async def test_score_all_ignores_unknown_job_ids_in_response():
    profile = CandidateProfile(id=1, full_name="Jane Doe")
    job1 = _job("https://boards.greenhouse.io/acme/jobs/1")

    client = _fake_client_returning(
        {
            "scores": [
                {
                    "job_id": "some-id-not-in-request",
                    "skills_score": 50, "title_seniority_score": 50,
                    "location_score": 50, "company_score": 50, "overall_score": 50,
                    "rationale": "n/a",
                }
            ]
        }
    )
    agent = ClaudeScoringAgent(client=client)

    scores = await agent.score_all(profile, [job1])

    assert scores == []


async def test_score_all_returns_empty_without_calling_api_when_no_jobs():
    client = _fake_client_returning({"scores": []})
    agent = ClaudeScoringAgent(client=client)

    scores = await agent.score_all(CandidateProfile(id=1, full_name="Jane Doe"), [])

    assert scores == []
    client.messages.create.assert_not_called()


async def test_score_all_batches_all_jobs_into_a_single_api_call():
    profile = CandidateProfile(id=1, full_name="Jane Doe")
    jobs = [_job(f"https://boards.greenhouse.io/acme/jobs/{i}") for i in range(5)]

    client = _fake_client_returning(
        {"scores": [
            {
                "job_id": j.id, "skills_score": 50, "title_seniority_score": 50,
                "location_score": 50, "company_score": 50, "overall_score": 50, "rationale": "n/a",
            }
            for j in jobs
        ]}
    )
    agent = ClaudeScoringAgent(client=client)

    await agent.score_all(profile, jobs)

    client.messages.create.assert_awaited_once()
