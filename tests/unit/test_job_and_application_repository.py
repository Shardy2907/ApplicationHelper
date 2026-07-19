from __future__ import annotations

from applicationhelper.models.application import ApplicationStatus
from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType
from applicationhelper.models.profile import CandidateProfile
from applicationhelper.storage.repository import (
    ApplicationRepository,
    JobRepository,
    ProfileRepository,
)


def _sample_job(apply_url: str = "https://boards.greenhouse.io/acme/jobs/123") -> JobPosting:
    return JobPosting(
        title="Backend Engineer",
        company="Acme Corp",
        location="Remote",
        remote_type=RemoteType.REMOTE,
        description_text="Build backend services.",
        apply_url=apply_url,
        source=ATSPlatform.GREENHOUSE,
    )


def test_job_id_is_derived_from_apply_url_and_stable():
    job_a = _sample_job()
    job_b = _sample_job()
    assert job_a.id == job_b.id


def test_job_upsert_dedups_on_id(session):
    repo = JobRepository(session)
    job = _sample_job()

    first = repo.upsert(job)
    updated = job.model_copy(update={"title": "Senior Backend Engineer"})
    second = repo.upsert(updated)
    session.commit()

    assert first.id == second.id
    fetched = repo.get(job.id)
    assert fetched.title == "Senior Backend Engineer"


def test_active_job_ids_excludes_shortlisted_and_rejected(session):
    profile = ProfileRepository(session).save(CandidateProfile(full_name="Jane Doe"))
    job_repo = JobRepository(session)
    app_repo = ApplicationRepository(session)

    job1 = job_repo.upsert(_sample_job("https://boards.greenhouse.io/acme/jobs/1"))
    job2 = job_repo.upsert(_sample_job("https://boards.greenhouse.io/acme/jobs/2"))
    job3 = job_repo.upsert(_sample_job("https://boards.greenhouse.io/acme/jobs/3"))
    session.commit()

    shortlisted_only = app_repo.create_or_get(job1.id, profile.id)

    approved = app_repo.create_or_get(job2.id, profile.id)
    app_repo.update_status(approved.id, ApplicationStatus.APPROVED)

    rejected = app_repo.create_or_get(job3.id, profile.id)
    app_repo.update_status(rejected.id, ApplicationStatus.REJECTED_BY_USER)
    session.commit()

    active = app_repo.active_job_ids_for_profile(profile.id)

    assert job2.id in active
    assert job1.id not in active
    assert job3.id not in active
    assert shortlisted_only.status == ApplicationStatus.SHORTLISTED
