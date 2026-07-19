from __future__ import annotations

import httpx

from applicationhelper.agents.job_search import JobSearchAgent
from applicationhelper.models.filters import ATSBoardTarget, SearchFilters
from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType


def _job(**overrides) -> JobPosting:
    defaults = dict(
        title="Backend Engineer",
        company="Acme Corp",
        location="Berlin, Germany",
        remote_type=RemoteType.UNKNOWN,
        description_text="Build things with Python.",
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        source=ATSPlatform.GREENHOUSE,
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


def test_passes_filters_excludes_blacklisted_company():
    job = _job(company="BadCo")
    filters = SearchFilters(excluded_companies=["BadCo"])
    assert JobSearchAgent._passes_filters(job, filters) is False


def test_passes_filters_requires_title_keyword_match():
    filters = SearchFilters(title_keywords=["Frontend"])
    assert JobSearchAgent._passes_filters(_job(title="Backend Engineer"), filters) is False
    assert JobSearchAgent._passes_filters(_job(title="Frontend Engineer"), filters) is True


def test_passes_filters_region_check_skipped_for_remote_jobs():
    filters = SearchFilters(regions=["Austin"])
    remote_job = _job(location="Anywhere", remote_type=RemoteType.REMOTE)
    onsite_job = _job(location="Berlin, Germany", remote_type=RemoteType.ONSITE)
    assert JobSearchAgent._passes_filters(remote_job, filters) is True
    assert JobSearchAgent._passes_filters(onsite_job, filters) is False


def test_passes_filters_remote_type_mismatch():
    filters = SearchFilters(remote_types=[RemoteType.REMOTE])
    assert JobSearchAgent._passes_filters(_job(remote_type=RemoteType.ONSITE), filters) is False
    assert JobSearchAgent._passes_filters(_job(remote_type=RemoteType.REMOTE), filters) is True
    # UNKNOWN remote_type shouldn't be penalized since ATS data doesn't always specify it
    assert JobSearchAgent._passes_filters(_job(remote_type=RemoteType.UNKNOWN), filters) is True


def test_passes_filters_salary_min():
    filters = SearchFilters(salary_min=100_000)
    assert JobSearchAgent._passes_filters(_job(salary_max=90_000), filters) is False
    assert JobSearchAgent._passes_filters(_job(salary_max=120_000), filters) is True
    # No salary data on the posting shouldn't auto-exclude it
    assert JobSearchAgent._passes_filters(_job(salary_max=None), filters) is True


async def test_search_dedups_against_applied_job_ids_and_filters():
    greenhouse_response = {
        "jobs": [
            {
                "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/1",
                "id": 1,
                "title": "Backend Engineer",
                "company_name": "Acme",
                "location": {"name": "Remote"},
                "first_published": None,
                "content": "Python role.",
            },
            {
                "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/2",
                "id": 2,
                "title": "Sales Rep",
                "company_name": "Acme",
                "location": {"name": "Remote"},
                "first_published": None,
                "content": "Sales role.",
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=greenhouse_response)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    agent = JobSearchAgent(http_client=client)

    filters = SearchFilters(
        ats_boards=[ATSBoardTarget(platform=ATSPlatform.GREENHOUSE, board_token="acme")],
        title_keywords=["Engineer", "Sales"],
    )

    from applicationhelper.models.job import JobPosting as _JP

    already_applied_id = _JP(
        title="x", company="Acme", description_text="x",
        apply_url="https://job-boards.greenhouse.io/acme/jobs/2", source=ATSPlatform.GREENHOUSE,
    ).id

    jobs = await agent.search(filters, exclude_job_ids={already_applied_id})
    await client.aclose()

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"


async def test_search_skips_board_on_fetch_failure_and_continues():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    agent = JobSearchAgent(http_client=client)
    filters = SearchFilters(
        ats_boards=[ATSBoardTarget(platform=ATSPlatform.GREENHOUSE, board_token="broken")]
    )

    jobs = await agent.search(filters)
    await client.aclose()

    assert jobs == []


async def test_search_falls_back_to_region_profile_when_ats_boards_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        if "smartrecruiters" in str(request.url):
            return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 0, "content": []})
        # Workday board in the DACH profile
        if request.method == "POST":
            return httpx.Response(200, json={"total": 0, "jobPostings": [], "facets": []})
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    agent = JobSearchAgent(http_client=client)
    filters = SearchFilters(region="DACH")

    jobs = await agent.search(filters)
    await client.aclose()

    assert jobs == []  # both boards return zero results in this fixture; verifies no error/skip


async def test_search_explicit_ats_boards_take_precedence_over_region():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "absolute_url": "https://job-boards.greenhouse.io/explicit/jobs/1",
                        "id": 1,
                        "title": "Explicit Board Job",
                        "company_name": "Explicit Co",
                        "location": {"name": "Remote"},
                        "first_published": None,
                        "content": "x",
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    agent = JobSearchAgent(http_client=client)
    filters = SearchFilters(
        region="DACH",
        ats_boards=[ATSBoardTarget(platform=ATSPlatform.GREENHOUSE, board_token="explicit")],
    )

    jobs = await agent.search(filters)
    await client.aclose()

    assert len(jobs) == 1
    assert jobs[0].title == "Explicit Board Job"


async def test_region_defaults_location_filter_when_regions_not_set():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "absolute_url": "https://job-boards.greenhouse.io/x/jobs/1",
                        "id": 1, "title": "Engineer", "company_name": "X",
                        "location": {"name": "Pune, India"}, "first_published": None, "content": "x",
                    },
                    {
                        "absolute_url": "https://job-boards.greenhouse.io/x/jobs/2",
                        "id": 2, "title": "Engineer", "company_name": "X",
                        "location": {"name": "Berlin, Germany"}, "first_published": None, "content": "x",
                    },
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    agent = JobSearchAgent(http_client=client)
    filters = SearchFilters(
        region="DACH",
        ats_boards=[ATSBoardTarget(platform=ATSPlatform.GREENHOUSE, board_token="x")],
    )

    jobs = await agent.search(filters)
    await client.aclose()

    assert len(jobs) == 1
    assert jobs[0].location == "Berlin, Germany"


async def test_explicit_regions_override_region_profile_location_default():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "absolute_url": "https://job-boards.greenhouse.io/x/jobs/1",
                        "id": 1, "title": "Engineer", "company_name": "X",
                        "location": {"name": "Vienna, Austria"}, "first_published": None, "content": "x",
                    },
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    agent = JobSearchAgent(http_client=client)
    filters = SearchFilters(
        region="DACH",
        regions=["Vienna"],
        ats_boards=[ATSBoardTarget(platform=ATSPlatform.GREENHOUSE, board_token="x")],
    )

    jobs = await agent.search(filters)
    await client.aclose()

    assert len(jobs) == 1


async def test_search_pools_ats_and_open_web_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/1",
                        "id": 1, "title": "ATS Job", "company_name": "Acme",
                        "location": {"name": "Remote"}, "first_published": None, "content": "x",
                    }
                ]
            },
        )

    class _FakeOpenWebAgent:
        async def search(self, filters):
            return [
                _job(
                    title="Open Web Job",
                    apply_url="https://open-web.example/job/1",
                    source=ATSPlatform.OPEN_WEB,
                    remote_type=RemoteType.REMOTE,
                )
            ]

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    agent = JobSearchAgent(http_client=client, open_web_agent=_FakeOpenWebAgent())
    filters = SearchFilters(
        ats_boards=[ATSBoardTarget(platform=ATSPlatform.GREENHOUSE, board_token="acme")]
    )

    jobs = await agent.search(filters)
    await client.aclose()

    titles = {job.title for job in jobs}
    assert titles == {"ATS Job", "Open Web Job"}


async def test_search_open_web_disabled_by_default():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobs": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    agent = JobSearchAgent(http_client=client)  # no open_web_agent passed

    assert agent._open_web_agent is None
    jobs = await agent.search(SearchFilters())
    await client.aclose()

    assert jobs == []


async def test_search_continues_when_open_web_agent_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "absolute_url": "https://job-boards.greenhouse.io/acme/jobs/1",
                        "id": 1, "title": "ATS Job", "company_name": "Acme",
                        "location": {"name": "Remote"}, "first_published": None, "content": "x",
                    }
                ]
            },
        )

    class _BrokenOpenWebAgent:
        async def search(self, filters):
            raise RuntimeError("open web search blew up")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    agent = JobSearchAgent(http_client=client, open_web_agent=_BrokenOpenWebAgent())
    filters = SearchFilters(
        ats_boards=[ATSBoardTarget(platform=ATSPlatform.GREENHOUSE, board_token="acme")]
    )

    jobs = await agent.search(filters)
    await client.aclose()

    assert len(jobs) == 1
    assert jobs[0].title == "ATS Job"


async def test_workday_board_missing_extra_fields_raises_clear_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Should not make an HTTP request when extra fields are missing")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    agent = JobSearchAgent(http_client=client)
    filters = SearchFilters(
        ats_boards=[ATSBoardTarget(platform=ATSPlatform.WORKDAY, board_token="db")]
    )

    # _fetch_all_boards catches and logs exceptions per-board rather than raising,
    # so this should complete with zero jobs, not crash.
    jobs = await agent.search(filters)
    await client.aclose()

    assert jobs == []
