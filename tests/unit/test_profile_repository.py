from __future__ import annotations

from applicationhelper.models.profile import CandidateProfile, EducationEntry, WorkExperience
from applicationhelper.storage.repository import ProfileRepository


def _sample_profile() -> CandidateProfile:
    return CandidateProfile(
        full_name="Jane Doe",
        email="jane@example.com",
        skills=["Python", "SQL"],
        experience=[
            WorkExperience(
                company="Acme Corp",
                title="Software Engineer",
                start_date="2020-01",
                is_current=True,
                bullets=["Built things", "Fixed bugs"],
            )
        ],
        education=[EducationEntry(institution="State University", degree="B.S. Computer Science")],
        raw_cv_text="Jane Doe resume text",
    )


def test_save_and_get_round_trips_nested_data(session):
    repo = ProfileRepository(session)
    saved = repo.save(_sample_profile())
    session.commit()

    assert saved.id is not None

    fetched = repo.get(saved.id)
    assert fetched is not None
    assert fetched.full_name == "Jane Doe"
    assert fetched.skills == ["Python", "SQL"]
    assert len(fetched.experience) == 1
    assert fetched.experience[0].company == "Acme Corp"
    assert fetched.experience[0].bullets == ["Built things", "Fixed bugs"]
    assert len(fetched.education) == 1
    assert fetched.education[0].institution == "State University"


def test_get_latest_returns_most_recently_parsed(session):
    repo = ProfileRepository(session)
    first = repo.save(_sample_profile())
    second = repo.save(_sample_profile().model_copy(update={"full_name": "John Smith"}))
    session.commit()

    latest = repo.get_latest()
    assert latest is not None
    assert latest.id == second.id
    assert latest.full_name == "John Smith"
    assert first.id != second.id


def test_save_update_replaces_nested_collections(session):
    repo = ProfileRepository(session)
    saved = repo.save(_sample_profile())
    session.commit()

    updated = saved.model_copy(update={"skills": ["Go"], "experience": []})
    repo.save(updated)
    session.commit()

    fetched = repo.get(saved.id)
    assert fetched.skills == ["Go"]
    assert fetched.experience == []
