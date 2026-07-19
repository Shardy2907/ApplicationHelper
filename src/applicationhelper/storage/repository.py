from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from applicationhelper.models.application import ApplicationRecord, ApplicationStatus
from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType
from applicationhelper.models.profile import CandidateProfile, EducationEntry, WorkExperience
from applicationhelper.models.scoring import MatchScore
from applicationhelper.storage.schema import (
    ApplicationRow,
    EducationRow,
    JobRow,
    ProfileRow,
    ScoreRow,
    WorkExperienceRow,
)

# Applications in these states represent jobs the user has already engaged with
# and that a fresh search should not resurface.
_ACTIVE_APPLICATION_STATUSES = {
    ApplicationStatus.APPROVED,
    ApplicationStatus.TAILORING,
    ApplicationStatus.TAILORED,
    ApplicationStatus.DOCS_APPROVED,
    ApplicationStatus.SUBMITTING,
    ApplicationStatus.PAUSED_FOR_SUBMIT,
    ApplicationStatus.SUBMITTED,
}


class ProfileRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(self, profile: CandidateProfile) -> CandidateProfile:
        if profile.id is not None:
            row = self._session.get(ProfileRow, profile.id)
        else:
            row = None

        if row is None:
            row = ProfileRow(
                full_name=profile.full_name,
                email=profile.email,
                phone=profile.phone,
                location=profile.location,
                linkedin_url=profile.linkedin_url,
                portfolio_url=profile.portfolio_url,
                summary=profile.summary,
                skills=profile.skills,
                certifications=profile.certifications,
                achievements=profile.achievements,
                raw_cv_text=profile.raw_cv_text,
                source_cv_path=profile.source_cv_path,
                source_cover_letter_path=profile.source_cover_letter_path,
                parsed_at=profile.parsed_at,
            )
            self._session.add(row)
        else:
            row.full_name = profile.full_name
            row.email = profile.email
            row.phone = profile.phone
            row.location = profile.location
            row.linkedin_url = profile.linkedin_url
            row.portfolio_url = profile.portfolio_url
            row.summary = profile.summary
            row.skills = profile.skills
            row.certifications = profile.certifications
            row.achievements = profile.achievements
            row.raw_cv_text = profile.raw_cv_text
            row.source_cv_path = profile.source_cv_path
            row.source_cover_letter_path = profile.source_cover_letter_path
            row.parsed_at = profile.parsed_at
            row.experience.clear()
            row.education.clear()

        row.experience = [
            WorkExperienceRow(
                company=e.company,
                title=e.title,
                location=e.location,
                start_date=e.start_date,
                end_date=e.end_date,
                is_current=e.is_current,
                bullets=e.bullets,
            )
            for e in profile.experience
        ]
        row.education = [
            EducationRow(
                institution=e.institution,
                degree=e.degree,
                field_of_study=e.field_of_study,
                start_date=e.start_date,
                end_date=e.end_date,
                gpa=e.gpa,
            )
            for e in profile.education
        ]

        self._session.flush()
        return self._to_domain(row)

    def get(self, profile_id: int) -> CandidateProfile | None:
        row = self._session.get(
            ProfileRow,
            profile_id,
            options=[selectinload(ProfileRow.experience), selectinload(ProfileRow.education)],
        )
        return self._to_domain(row) if row else None

    def get_latest(self) -> CandidateProfile | None:
        stmt = (
            select(ProfileRow)
            .options(selectinload(ProfileRow.experience), selectinload(ProfileRow.education))
            .order_by(ProfileRow.parsed_at.desc())
            .limit(1)
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return self._to_domain(row) if row else None

    @staticmethod
    def _to_domain(row: ProfileRow) -> CandidateProfile:
        return CandidateProfile(
            id=row.id,
            full_name=row.full_name,
            email=row.email,
            phone=row.phone,
            location=row.location,
            linkedin_url=row.linkedin_url,
            portfolio_url=row.portfolio_url,
            summary=row.summary,
            skills=row.skills,
            experience=[
                WorkExperience(
                    company=e.company,
                    title=e.title,
                    location=e.location,
                    start_date=e.start_date,
                    end_date=e.end_date,
                    is_current=e.is_current,
                    bullets=e.bullets,
                )
                for e in row.experience
            ],
            education=[
                EducationEntry(
                    institution=e.institution,
                    degree=e.degree,
                    field_of_study=e.field_of_study,
                    start_date=e.start_date,
                    end_date=e.end_date,
                    gpa=e.gpa,
                )
                for e in row.education
            ],
            certifications=row.certifications,
            achievements=row.achievements,
            raw_cv_text=row.raw_cv_text,
            source_cv_path=row.source_cv_path,
            source_cover_letter_path=row.source_cover_letter_path,
            parsed_at=row.parsed_at,
        )


class JobRepository:
    def __init__(self, session: Session):
        self._session = session

    def upsert(self, job: JobPosting) -> JobPosting:
        row = self._session.get(JobRow, job.id)
        if row is None:
            row = JobRow(id=job.id, apply_url=job.apply_url, title=job.title, company=job.company)
            self._session.add(row)

        row.title = job.title
        row.company = job.company
        row.location = job.location
        row.remote_type = job.remote_type.value
        row.salary_min = job.salary_min
        row.salary_max = job.salary_max
        row.salary_currency = job.salary_currency
        row.description_text = job.description_text
        row.apply_url = job.apply_url
        row.source = job.source.value
        row.posted_date = job.posted_date
        row.discovered_at = job.discovered_at

        self._session.flush()
        return self._to_domain(row)

    def get(self, job_id: str) -> JobPosting | None:
        row = self._session.get(JobRow, job_id)
        return self._to_domain(row) if row else None

    @staticmethod
    def _to_domain(row: JobRow) -> JobPosting:
        return JobPosting(
            id=row.id,
            title=row.title,
            company=row.company,
            location=row.location,
            remote_type=RemoteType(row.remote_type),
            salary_min=row.salary_min,
            salary_max=row.salary_max,
            salary_currency=row.salary_currency,
            description_text=row.description_text,
            apply_url=row.apply_url,
            source=ATSPlatform(row.source),
            posted_date=row.posted_date,
            discovered_at=row.discovered_at,
        )


class ScoreRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, score: MatchScore) -> MatchScore:
        row = ScoreRow(
            job_id=score.job_id,
            profile_id=score.profile_id,
            skills_score=score.skills_score,
            title_seniority_score=score.title_seniority_score,
            location_score=score.location_score,
            company_score=score.company_score,
            overall_score=score.overall_score,
            rationale=score.rationale,
            scored_at=score.scored_at,
        )
        self._session.add(row)
        self._session.flush()
        return MatchScore.model_validate(row, from_attributes=True)

    def top_for_profile(self, profile_id: int, limit: int = 5) -> list[MatchScore]:
        stmt = (
            select(ScoreRow)
            .where(ScoreRow.profile_id == profile_id)
            .order_by(ScoreRow.overall_score.desc())
            .limit(limit)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [MatchScore.model_validate(r, from_attributes=True) for r in rows]


class ApplicationRepository:
    def __init__(self, session: Session):
        self._session = session

    def create_or_get(self, job_id: str, profile_id: int) -> ApplicationRecord:
        stmt = select(ApplicationRow).where(
            ApplicationRow.job_id == job_id, ApplicationRow.profile_id == profile_id
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            row = ApplicationRow(
                job_id=job_id, profile_id=profile_id, status=ApplicationStatus.SHORTLISTED.value
            )
            self._session.add(row)
            self._session.flush()
        return self._to_domain(row)

    def update_status(self, application_id: int, status: ApplicationStatus, **fields) -> ApplicationRecord:
        row = self._session.get(ApplicationRow, application_id)
        if row is None:
            raise ValueError(f"No application with id {application_id}")
        row.status = status.value
        for key, value in fields.items():
            setattr(row, key, value)
        self._session.flush()
        return self._to_domain(row)

    def active_job_ids_for_profile(self, profile_id: int) -> set[str]:
        """Job ids the user is already engaged with (dedup input for job search)."""
        stmt = select(ApplicationRow.job_id).where(
            ApplicationRow.profile_id == profile_id,
            ApplicationRow.status.in_([s.value for s in _ACTIVE_APPLICATION_STATUSES]),
        )
        return set(self._session.execute(stmt).scalars().all())

    @staticmethod
    def _to_domain(row: ApplicationRow) -> ApplicationRecord:
        return ApplicationRecord(
            id=row.id,
            job_id=row.job_id,
            profile_id=row.profile_id,
            status=ApplicationStatus(row.status),
            tailored_cv_path=row.tailored_cv_path,
            tailored_cover_letter_path=row.tailored_cover_letter_path,
            browser_notes=row.browser_notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
            submitted_at=row.submitted_at,
        )
