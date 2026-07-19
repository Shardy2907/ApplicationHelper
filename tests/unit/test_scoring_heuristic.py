from __future__ import annotations

from applicationhelper.agents.scoring import HeuristicScoringAgent
from applicationhelper.models.filters import SearchFilters
from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType
from applicationhelper.models.profile import CandidateProfile, WorkExperience


def _profile(**overrides) -> CandidateProfile:
    defaults = dict(
        id=1,
        full_name="Jane Doe",
        location="Berlin, Germany",
        skills=["Python", "SQL", "Docker"],
        experience=[
            WorkExperience(company="Acme", title="Backend Engineer", is_current=True)
        ],
    )
    defaults.update(overrides)
    return CandidateProfile(**defaults)


def _job(**overrides) -> JobPosting:
    defaults = dict(
        title="Backend Engineer",
        company="Acme Corp",
        location="Berlin, Germany",
        remote_type=RemoteType.UNKNOWN,
        description_text="We need someone skilled in Python, SQL, and Docker.",
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        source=ATSPlatform.GREENHOUSE,
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


async def test_high_skill_overlap_scores_higher_than_low_overlap():
    agent = HeuristicScoringAgent()
    profile = _profile()

    good_job = _job(description_text="Python, SQL, Docker expert wanted.")
    bad_job = _job(description_text="We need a Java Spring developer.")

    [good_score] = await agent.score_all(profile, [good_job])
    [bad_score] = await agent.score_all(profile, [bad_job])

    assert good_score.skills_score > bad_score.skills_score
    assert good_score.overall_score > bad_score.overall_score


async def test_remote_job_gets_perfect_location_score():
    agent = HeuristicScoringAgent()
    profile = _profile(location="Nowhere near this job")
    remote_job = _job(location="Anywhere", remote_type=RemoteType.REMOTE)

    [score] = await agent.score_all(profile, [remote_job])

    assert score.location_score == 100.0


async def test_onsite_job_penalized_when_filters_want_remote():
    agent = HeuristicScoringAgent()
    profile = _profile()
    onsite_job = _job(remote_type=RemoteType.ONSITE)
    filters = SearchFilters(remote_types=[RemoteType.REMOTE])

    [score] = await agent.score_all(profile, [onsite_job], filters)

    assert score.location_score < 50.0


async def test_preferred_company_scores_higher_than_unlisted_company():
    agent = HeuristicScoringAgent()
    profile = _profile()
    filters = SearchFilters(target_companies=["Acme Corp"])

    preferred_job = _job(company="Acme Corp")
    other_job = _job(company="Some Other Co")

    [preferred_score] = await agent.score_all(profile, [preferred_job], filters)
    [other_score] = await agent.score_all(profile, [other_job], filters)

    assert preferred_score.company_score > other_score.company_score


async def test_scores_are_within_bounds_and_reference_job_and_profile_ids():
    agent = HeuristicScoringAgent()
    profile = _profile(id=42)
    job = _job()

    [score] = await agent.score_all(profile, [job])

    assert score.job_id == job.id
    assert score.profile_id == 42
    assert 0 <= score.overall_score <= 100
