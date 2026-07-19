"""Agent 3: grades JobPostings against a CandidateProfile.

Two implementations behind the same `score_all` shape:

- `HeuristicScoringAgent`: local keyword/title/location overlap math, zero API
  calls. Use this during development/testing so iterating on search+scoring
  doesn't cost anything.
- `ClaudeScoringAgent`: LLM-graded via a single batched forced tool-use call
  (one call scores every job at once, not one call per job) for when you want
  real judgment quality, e.g. for an actual end-to-end run.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from applicationhelper.config import anthropic_api_key
from applicationhelper.models.filters import SearchFilters
from applicationhelper.models.job import JobPosting, RemoteType
from applicationhelper.models.profile import CandidateProfile
from applicationhelper.models.scoring import MatchScore

_STOPWORDS = {
    "a", "an", "and", "at", "for", "in", "of", "on", "or", "the", "to", "with", "senior", "junior",
}
_WORD_RE = re.compile(r"[a-z0-9+.#]+")


class ScoringAgent(Protocol):
    async def score_all(
        self,
        profile: CandidateProfile,
        jobs: list[JobPosting],
        filters: SearchFilters | None = None,
    ) -> list[MatchScore]: ...


def _words(text: str | None) -> set[str]:
    if not text:
        return set()
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


class HeuristicScoringAgent:
    """Deterministic, free scorer. Good enough to exercise the pipeline during
    development; not a substitute for `ClaudeScoringAgent`'s judgment."""

    async def score_all(
        self,
        profile: CandidateProfile,
        jobs: list[JobPosting],
        filters: SearchFilters | None = None,
    ) -> list[MatchScore]:
        return [self._score_one(profile, job, filters) for job in jobs]

    def _score_one(
        self, profile: CandidateProfile, job: JobPosting, filters: SearchFilters | None
    ) -> MatchScore:
        skills_score = self._skills_score(profile, job)
        title_score = self._title_seniority_score(profile, job)
        location_score = self._location_score(profile, job, filters)
        company_score = self._company_score(job, filters)

        overall = skills_score * 0.4 + title_score * 0.25 + location_score * 0.2 + company_score * 0.15

        rationale = (
            f"Heuristic match - skills {skills_score:.0f}, title/seniority {title_score:.0f}, "
            f"location {location_score:.0f}, company {company_score:.0f}."
        )

        return MatchScore(
            job_id=job.id,
            profile_id=profile.id or 0,
            skills_score=skills_score,
            title_seniority_score=title_score,
            location_score=location_score,
            company_score=company_score,
            overall_score=round(overall, 1),
            rationale=rationale,
        )

    @staticmethod
    def _skills_score(profile: CandidateProfile, job: JobPosting) -> float:
        profile_skills = {s.lower() for s in profile.skills}
        if not profile_skills:
            return 50.0
        description_lower = job.description_text.lower()
        matched = sum(1 for skill in profile_skills if skill in description_lower)
        return round(min(100.0, (matched / len(profile_skills)) * 100), 1)

    @staticmethod
    def _title_seniority_score(profile: CandidateProfile, job: JobPosting) -> float:
        if not profile.experience:
            return 50.0
        latest = next((e for e in profile.experience if e.is_current), profile.experience[0])
        profile_words = _words(latest.title)
        job_words = _words(job.title)
        if not profile_words or not job_words:
            return 50.0
        overlap = profile_words & job_words
        union = profile_words | job_words
        return round((len(overlap) / len(union)) * 100, 1) if union else 50.0

    @staticmethod
    def _location_score(
        profile: CandidateProfile, job: JobPosting, filters: SearchFilters | None
    ) -> float:
        wants_remote = bool(filters and filters.remote_types and RemoteType.REMOTE in filters.remote_types)

        if job.remote_type == RemoteType.REMOTE:
            return 100.0
        if wants_remote and job.remote_type in (RemoteType.ONSITE, RemoteType.HYBRID):
            return 20.0

        profile_loc = _words(profile.location)
        job_loc = _words(job.location)
        if not profile_loc or not job_loc:
            return 50.0
        return 80.0 if profile_loc & job_loc else 40.0

    @staticmethod
    def _company_score(job: JobPosting, filters: SearchFilters | None) -> float:
        if not filters or not filters.target_companies:
            return 70.0
        preferred = {c.lower() for c in filters.target_companies}
        return 100.0 if job.company.lower() in preferred else 40.0


_PROMPT_PATH = Path(__file__).parent / "prompts" / "scoring_rubric.md"
_TOOL_NAME = "record_scores"
_DEFAULT_MODEL = "claude-sonnet-5"


class _ScoreItem(BaseModel):
    job_id: str
    skills_score: float = Field(ge=0, le=100)
    title_seniority_score: float = Field(ge=0, le=100)
    location_score: float = Field(ge=0, le=100)
    company_score: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    rationale: str


class _ScoreBatch(BaseModel):
    scores: list[_ScoreItem]


class ClaudeScoringAgent:
    """LLM-graded scorer. Costs one Anthropic API call per `score_all` invocation
    (all jobs batched into a single request), not one call per job."""

    def __init__(self, client: AsyncAnthropic | None = None, model: str = _DEFAULT_MODEL):
        self._client = client or AsyncAnthropic(api_key=anthropic_api_key())
        self._model = model
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def score_all(
        self,
        profile: CandidateProfile,
        jobs: list[JobPosting],
        filters: SearchFilters | None = None,
    ) -> list[MatchScore]:
        if not jobs:
            return []

        user_content = self._build_user_content(profile, jobs, filters)

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_content}],
            tools=[
                {
                    "name": _TOOL_NAME,
                    "description": "Record the match scores for every job listed.",
                    "input_schema": _ScoreBatch.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
        )

        tool_use = next(b for b in response.content if b.type == "tool_use")
        batch = _ScoreBatch.model_validate(tool_use.input)
        by_id = {item.job_id: item for item in batch.scores}

        results = []
        for job in jobs:
            item = by_id.get(job.id)
            if item is None:
                continue
            results.append(
                MatchScore(
                    job_id=job.id,
                    profile_id=profile.id or 0,
                    skills_score=item.skills_score,
                    title_seniority_score=item.title_seniority_score,
                    location_score=item.location_score,
                    company_score=item.company_score,
                    overall_score=item.overall_score,
                    rationale=item.rationale,
                )
            )
        return results

    @staticmethod
    def _build_user_content(
        profile: CandidateProfile, jobs: list[JobPosting], filters: SearchFilters | None
    ) -> str:
        lines = [
            f"CANDIDATE: {profile.full_name}",
            f"Location: {profile.location or 'unknown'}",
            f"Skills: {', '.join(profile.skills) or 'none listed'}",
            f"Summary: {profile.summary or 'none'}",
        ]
        if profile.experience:
            latest = profile.experience[0]
            lines.append(f"Most recent role: {latest.title} at {latest.company}")
        if filters:
            if filters.target_companies:
                lines.append(f"Preferred companies: {', '.join(filters.target_companies)}")
            if filters.regions:
                lines.append(f"Preferred regions: {', '.join(filters.regions)}")
            if filters.remote_types:
                lines.append(f"Preferred remote types: {', '.join(r.value for r in filters.remote_types)}")

        lines.append("\nJOBS TO SCORE:")
        for job in jobs:
            lines.append(
                f"\n- job_id: {job.id}\n  title: {job.title}\n  company: {job.company}\n"
                f"  location: {job.location or 'unknown'}\n  remote_type: {job.remote_type.value}\n"
                f"  description: {job.description_text[:1500]}"
            )
        return "\n".join(lines)
