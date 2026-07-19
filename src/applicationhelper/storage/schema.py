from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from applicationhelper.utils.time import utcnow


class Base(DeclarativeBase):
    pass


class ProfileRow(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    email: Mapped[str | None]
    phone: Mapped[str | None]
    location: Mapped[str | None]
    linkedin_url: Mapped[str | None]
    portfolio_url: Mapped[str | None]
    summary: Mapped[str | None]
    skills: Mapped[list] = mapped_column(JSON, default=list)
    certifications: Mapped[list] = mapped_column(JSON, default=list)
    achievements: Mapped[list] = mapped_column(JSON, default=list)
    raw_cv_text: Mapped[str | None]
    source_cv_path: Mapped[str | None]
    source_cover_letter_path: Mapped[str | None]
    parsed_at: Mapped[datetime] = mapped_column(default=utcnow)

    experience: Mapped[list["WorkExperienceRow"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    education: Mapped[list["EducationRow"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class WorkExperienceRow(Base):
    __tablename__ = "work_experience"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    company: Mapped[str]
    title: Mapped[str]
    location: Mapped[str | None]
    start_date: Mapped[str | None]
    end_date: Mapped[str | None]
    is_current: Mapped[bool] = mapped_column(default=False)
    bullets: Mapped[list] = mapped_column(JSON, default=list)

    profile: Mapped[ProfileRow] = relationship(back_populates="experience")


class EducationRow(Base):
    __tablename__ = "education"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    institution: Mapped[str]
    degree: Mapped[str | None]
    field_of_study: Mapped[str | None]
    start_date: Mapped[str | None]
    end_date: Mapped[str | None]
    gpa: Mapped[str | None]

    profile: Mapped[ProfileRow] = relationship(back_populates="education")


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    company: Mapped[str]
    location: Mapped[str | None]
    remote_type: Mapped[str]
    salary_min: Mapped[float | None]
    salary_max: Mapped[float | None]
    salary_currency: Mapped[str | None]
    description_text: Mapped[str]
    apply_url: Mapped[str] = mapped_column(unique=True)
    source: Mapped[str]
    posted_date: Mapped[str | None]
    discovered_at: Mapped[datetime] = mapped_column(default=utcnow)


class SearchRunRow(Base):
    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_at: Mapped[datetime] = mapped_column(default=utcnow)
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_count: Mapped[int] = mapped_column(default=0)


class ScoreRow(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    skills_score: Mapped[float]
    title_seniority_score: Mapped[float]
    location_score: Mapped[float]
    company_score: Mapped[float]
    overall_score: Mapped[float]
    rationale: Mapped[str]
    scored_at: Mapped[datetime] = mapped_column(default=utcnow)


class ApplicationRow(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("job_id", "profile_id", name="uq_application_job_profile"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    status: Mapped[str]
    tailored_cv_path: Mapped[str | None]
    tailored_cover_letter_path: Mapped[str | None]
    browser_notes: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)
    submitted_at: Mapped[datetime | None]


class SettingRow(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
