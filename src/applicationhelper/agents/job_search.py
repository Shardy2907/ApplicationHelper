"""Agent 2: finds candidate job postings.

Pools two channels:
1. Deterministic, free ATS board APIs under the caller-supplied
   `SearchFilters.ats_boards` (or a hardcoded regional default — see
   `region_profiles.py` — if `region` is set and `ats_boards` is empty).
   Zero LLM cost.
2. An optional `OpenWebSearchAgent` (Claude web_search/web_fetch), injected
   via the constructor. **Disabled by default** — passing `open_web_agent=None`
   (the default) keeps this class's cost at zero and its behavior identical
   to before open-web search existed, which is what every existing test and
   pure-ATS workflow relies on. The production CLI path enables it explicitly
   (see `dev/search_and_score.py`); this class never constructs a real
   Anthropic client on its own.

Both channels' results are pooled, then deduped against `exclude_job_ids` and
filtered through the same `_passes_filters` — a job found via open-web search
is filtered exactly like one found via an ATS board.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from applicationhelper.agents.ats_clients.ashby import fetch_ashby_jobs
from applicationhelper.agents.ats_clients.greenhouse import fetch_greenhouse_jobs
from applicationhelper.agents.ats_clients.smartrecruiters import fetch_smartrecruiters_jobs
from applicationhelper.agents.ats_clients.workday import fetch_workday_jobs
from applicationhelper.agents.open_web_search import OpenWebSearchAgent
from applicationhelper.agents.region_profiles import resolve_region_boards, resolve_region_locations
from applicationhelper.models.filters import ATSBoardTarget, SearchFilters
from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType

logger = logging.getLogger(__name__)


class JobSearchAgent:
    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        open_web_agent: OpenWebSearchAgent | None = None,
    ):
        self._client = http_client
        self._open_web_agent = open_web_agent

    async def search(
        self, filters: SearchFilters, exclude_job_ids: set[str] | None = None
    ) -> list[JobPosting]:
        exclude_job_ids = exclude_job_ids or set()
        boards = filters.ats_boards or (resolve_region_boards(filters.region) if filters.region else [])

        # Board companies operate globally, so also default the location-text
        # filter from the region profile (unless the caller set their own),
        # or a "DACH" search would still surface e.g. a Deutsche Bank Pune listing.
        effective_regions = filters.regions or (
            resolve_region_locations(filters.region) if filters.region else []
        )
        effective_filters = (
            filters if effective_regions == filters.regions else filters.model_copy(update={"regions": effective_regions})
        )

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=20.0)
        try:
            ats_jobs, open_web_jobs = await asyncio.gather(
                self._fetch_all_boards(boards, client),
                self._fetch_open_web(effective_filters),
            )
        finally:
            if owns_client:
                await client.aclose()

        jobs = ats_jobs + open_web_jobs
        return [
            job
            for job in jobs
            if job.id not in exclude_job_ids and self._passes_filters(job, effective_filters)
        ]

    async def _fetch_open_web(self, filters: SearchFilters) -> list[JobPosting]:
        if self._open_web_agent is None:
            return []
        try:
            return await self._open_web_agent.search(filters)
        except Exception:
            logger.warning("Open-web search failed", exc_info=True)
            return []

    async def _fetch_all_boards(
        self, targets: list[ATSBoardTarget], client: httpx.AsyncClient
    ) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for target in targets:
            try:
                jobs.extend(await self._fetch_board(target, client))
            except Exception:
                logger.warning(
                    "Failed to fetch %s board '%s'", target.platform.value, target.board_token,
                    exc_info=True,
                )
        return jobs

    @staticmethod
    async def _fetch_board(target: ATSBoardTarget, client: httpx.AsyncClient) -> list[JobPosting]:
        if target.platform == ATSPlatform.GREENHOUSE:
            return await fetch_greenhouse_jobs(target.board_token, client)
        if target.platform == ATSPlatform.ASHBY:
            return await fetch_ashby_jobs(target.board_token, client, company_name=target.company_name)
        if target.platform == ATSPlatform.SMARTRECRUITERS:
            return await fetch_smartrecruiters_jobs(
                target.board_token, client, country=target.extra.get("country")
            )
        if target.platform == ATSPlatform.WORKDAY:
            missing = [k for k in ("dc", "site") if k not in target.extra]
            if missing:
                raise ValueError(f"Workday board '{target.board_token}' missing extra field(s): {missing}")
            return await fetch_workday_jobs(
                target.board_token,
                target.extra["dc"],
                target.extra["site"],
                client,
                company_name=target.company_name,
            )
        raise ValueError(f"No direct-fetch client for platform {target.platform}")

    @staticmethod
    def _passes_filters(job: JobPosting, filters: SearchFilters) -> bool:
        if filters.excluded_companies:
            excluded = {c.lower() for c in filters.excluded_companies}
            if job.company.lower() in excluded:
                return False

        if filters.title_keywords:
            title_lower = job.title.lower()
            if not any(keyword.lower() in title_lower for keyword in filters.title_keywords):
                return False

        if filters.remote_types:
            allowed = set(filters.remote_types)
            if job.remote_type != RemoteType.UNKNOWN and job.remote_type not in allowed:
                return False

        if filters.regions and job.remote_type != RemoteType.REMOTE:
            location_lower = (job.location or "").lower()
            if not any(region.lower() in location_lower for region in filters.regions):
                return False

        if filters.salary_min is not None and job.salary_max is not None:
            if job.salary_max < filters.salary_min:
                return False

        return True
