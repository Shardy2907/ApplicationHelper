"""Stage 2 demo: search real ATS boards + open web, score against the latest
saved profile.

Two things cost real money here, both on by default since this is the
production path, both with an opt-out flag for cheap local iteration:
- Scoring defaults to Claude (`ClaudeScoringAgent`, one batched call for all
  jobs). --heuristic-score switches to the free local scorer.
- Open-web search defaults ON (`OpenWebSearchAgent`, Claude web_search +
  web_fetch — web_search is billed at $10/1,000 searches on top of token
  costs, web_fetch is token-only). --no-open-web disables it, leaving only
  the free ATS board queries.
The automated test suite always uses a mocked Anthropic client and never
touches either live path.

Usage:
    # DACH-region default board list (Bosch/SmartRecruiters + Deutsche Bank/Workday) + open web + Claude scoring:
    python -m applicationhelper.dev.search_and_score --region DACH --title-keyword engineer

    # explicit boards instead of a region profile:
    python -m applicationhelper.dev.search_and_score \\
        --board smartrecruiters:BoschGroup:country=de \\
        --board "workday:db:dc=wd3,site=DBWebsite" \\
        --title-keyword engineer --top 5

    # fully free local iteration: ATS boards only, no open-web search, heuristic scoring:
    python -m applicationhelper.dev.search_and_score --region DACH --no-open-web --heuristic-score
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from applicationhelper.agents.job_search import JobSearchAgent
from applicationhelper.agents.open_web_search import OpenWebSearchAgent
from applicationhelper.agents.scoring import ClaudeScoringAgent, HeuristicScoringAgent
from applicationhelper.config import db_path
from applicationhelper.models.filters import ATSBoardTarget, SearchFilters
from applicationhelper.models.job import ATSPlatform, RemoteType
from applicationhelper.storage.db import make_engine, make_session_factory
from applicationhelper.storage.repository import (
    ApplicationRepository,
    JobRepository,
    ProfileRepository,
    ScoreRepository,
)

_PLATFORM_ALIASES = {
    "greenhouse": ATSPlatform.GREENHOUSE,
    "ashby": ATSPlatform.ASHBY,
    "smartrecruiters": ATSPlatform.SMARTRECRUITERS,
    "workday": ATSPlatform.WORKDAY,
}


def _parse_board(value: str) -> ATSBoardTarget:
    """Parses 'platform:board_token[:key=val,key=val,...]'."""
    parts = value.split(":", 2)
    if len(parts) < 2 or parts[0] not in _PLATFORM_ALIASES:
        raise argparse.ArgumentTypeError(
            f"Expected '<platform>:<board_token>[:key=val,...]', got {value!r} "
            f"(platform must be one of {sorted(_PLATFORM_ALIASES)})"
        )
    platform_name, token = parts[0], parts[1]
    extra = {}
    if len(parts) == 3:
        for pair in parts[2].split(","):
            key, _, val = pair.partition("=")
            if key and val:
                extra[key] = val
    return ATSBoardTarget(platform=_PLATFORM_ALIASES[platform_name], board_token=token, extra=extra)


async def _run(args: argparse.Namespace) -> None:
    engine = make_engine(db_path())
    session_factory = make_session_factory(engine)

    with session_factory() as session:
        profile = ProfileRepository(session).get_latest()
        if profile is None:
            raise SystemExit("No saved profile found. Run `applicationhelper.dev.parse_cv` first.")
        applied_job_ids = ApplicationRepository(session).active_job_ids_for_profile(profile.id)

    filters = SearchFilters(
        region=args.region,
        ats_boards=args.board,
        title_keywords=args.title_keyword,
        regions=args.locale_region,
        remote_types=[RemoteType(r) for r in args.remote],
        target_companies=args.target_company,
    )

    open_web_agent = None if args.no_open_web else OpenWebSearchAgent()
    jobs = await JobSearchAgent(open_web_agent=open_web_agent).search(
        filters, exclude_job_ids=applied_job_ids
    )
    print(f"Found {len(jobs)} job(s) after filtering + dedup against already-applied jobs.\n")
    if not jobs:
        return

    scorer = HeuristicScoringAgent() if args.heuristic_score else ClaudeScoringAgent()
    print(f"Scoring with {type(scorer).__name__}...\n")
    scores = await scorer.score_all(profile, jobs, filters)
    by_job_id = {s.job_id: s for s in scores}

    ranked = sorted(
        (job for job in jobs if job.id in by_job_id),
        key=lambda j: by_job_id[j.id].overall_score,
        reverse=True,
    )[: args.top]

    with session_factory() as session:
        job_repo = JobRepository(session)
        score_repo = ScoreRepository(session)
        app_repo = ApplicationRepository(session)
        for job in ranked:
            job_repo.upsert(job)
            score = by_job_id[job.id].model_copy(update={"profile_id": profile.id})
            score_repo.add(score)
            app_repo.create_or_get(job.id, profile.id)
        session.commit()

    for rank, job in enumerate(ranked, start=1):
        score = by_job_id[job.id]
        print(f"{rank}. [{score.overall_score:.0f}] {job.title} @ {job.company}")
        print(f"   {job.apply_url}")
        print(f"   {score.rationale}\n")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # real ATS listings include umlauts/en-dashes etc.

    parser = argparse.ArgumentParser(description="Search + score jobs against the saved profile.")
    parser.add_argument("--region", default=None, help="e.g. DACH — auto-fills boards if --board is omitted")
    parser.add_argument(
        "--board", type=_parse_board, action="append", default=[],
        help="platform:board_token[:key=val,...], e.g. smartrecruiters:BoschGroup:country=de "
        "or workday:db:dc=wd3,site=DBWebsite (repeatable)",
    )
    parser.add_argument("--title-keyword", action="append", default=[])
    parser.add_argument("--locale-region", action="append", default=[], help="location text filter, e.g. Berlin")
    parser.add_argument("--remote", action="append", default=[], choices=[r.value for r in RemoteType])
    parser.add_argument("--target-company", action="append", default=[])
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument(
        "--heuristic-score", action="store_true",
        help="Use the free local heuristic scorer instead of Claude (for repeated local iteration).",
    )
    parser.add_argument(
        "--no-open-web", action="store_true",
        help="Skip open-web search (Claude web_search/web_fetch, real $ cost) and use only ATS boards.",
    )
    args = parser.parse_args()

    if not args.board and not args.region:
        parser.error("either --region (e.g. DACH) or at least one --board is required")

    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
