"""Agent 2c: discovers job postings from the open web via Claude's native
`web_search` + `web_fetch` server tools, for coverage beyond the fixed ATS
board list.

Real, non-trivial cost: `web_search` is billed by Anthropic at $10 per 1,000
searches, on top of ordinary token costs; `web_fetch` has no extra per-call
fee but each fetched page adds meaningfully to token usage (~2,500 tokens for
an average page). See https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
and .../web-fetch-tool. `max_searches`/`max_fetches` bound this per call.

Deliberately NOT LinkedIn-specific: this agent does open, general web search.
It doesn't target or scrape LinkedIn — if a LinkedIn job URL organically
shows up in search results the way it would in any web search, that's fine,
but there is no dedicated LinkedIn integration here (see project notes on
why a LinkedIn scraper was intentionally not built).

Mechanically: `web_search`/`web_fetch` are server tools — Anthropic executes
them and injects results back into the same turn. Mixing them with a forced
custom tool_choice would prevent Claude from calling them, so this agent uses
tool_choice="auto" and relies on the system prompt to get a final
`record_job_postings` call. Never invoked by the test suite with a real
client — tests inject a mocked AsyncAnthropic client, same pattern as
`DocumentParserAgent`/`ClaudeScoringAgent`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from applicationhelper.config import anthropic_api_key
from applicationhelper.models.filters import SearchFilters
from applicationhelper.models.job import ATSPlatform, JobPosting, RemoteType

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "open_web_search_system.md"
_TOOL_NAME = "record_job_postings"
_DEFAULT_MODEL = "claude-sonnet-5"


class _OpenWebPosting(BaseModel):
    title: str
    company: str
    location: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    description_text: str
    apply_url: str
    posted_date: str | None = None


class _PostingBatch(BaseModel):
    postings: list[_OpenWebPosting] = Field(default_factory=list)


class OpenWebSearchAgent:
    def __init__(
        self,
        client: AsyncAnthropic | None = None,
        model: str = _DEFAULT_MODEL,
        max_searches: int = 3,
        max_fetches: int = 5,
        max_pause_turns: int = 5,
    ):
        self._client = client or AsyncAnthropic(api_key=anthropic_api_key())
        self._model = model
        self._max_searches = max_searches
        self._max_fetches = max_fetches
        self._max_pause_turns = max_pause_turns
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def search(self, filters: SearchFilters, max_results: int = 10) -> list[JobPosting]:
        tools = [
            {"type": "web_search_20250305", "name": "web_search", "max_uses": self._max_searches},
            {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": self._max_fetches},
            {
                "name": _TOOL_NAME,
                "description": "Record the confirmed real job postings found.",
                "input_schema": _PostingBatch.model_json_schema(),
            },
        ]
        messages: list[dict] = [{"role": "user", "content": self._build_query(filters, max_results)}]

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=self._system_prompt,
            messages=messages,
            tools=tools,
            tool_choice={"type": "auto"},
        )

        iterations = 0
        while response.stop_reason == "pause_turn" and iterations < self._max_pause_turns:
            messages.append({"role": "assistant", "content": response.content})
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=self._system_prompt,
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"},
            )
            iterations += 1

        tool_use = next(
            (b for b in response.content if getattr(b, "type", None) == "tool_use" and b.name == _TOOL_NAME),
            None,
        )
        if tool_use is None:
            logger.warning(
                "OpenWebSearchAgent finished without calling %s (stop_reason=%s)",
                _TOOL_NAME, response.stop_reason,
            )
            return []

        batch = _PostingBatch.model_validate(tool_use.input)
        return [self._to_job_posting(item) for item in batch.postings[:max_results]]

    @staticmethod
    def _build_query(filters: SearchFilters, max_results: int) -> str:
        lines = [f"Find up to {max_results} real, currently-open job postings matching:"]
        if filters.title_keywords:
            lines.append(f"- Title/role keywords: {', '.join(filters.title_keywords)}")
        if filters.regions:
            lines.append(f"- Location/region: {', '.join(filters.regions)}")
        if filters.remote_types:
            lines.append(f"- Remote preference: {', '.join(r.value for r in filters.remote_types)}")
        if filters.target_companies:
            lines.append(f"- Preferred companies: {', '.join(filters.target_companies)}")
        if filters.excluded_companies:
            lines.append(f"- Exclude companies: {', '.join(filters.excluded_companies)}")
        if filters.user_specified_sites:
            lines.append(f"- Prioritize these sites: {', '.join(filters.user_specified_sites)}")
        if len(lines) == 1:
            lines.append("- (no specific filters given — use your judgment on what's broadly useful)")
        return "\n".join(lines)

    @staticmethod
    def _to_job_posting(item: _OpenWebPosting) -> JobPosting:
        return JobPosting(
            title=item.title,
            company=item.company,
            location=item.location,
            remote_type=item.remote_type,
            description_text=item.description_text,
            apply_url=item.apply_url,
            source=ATSPlatform.OPEN_WEB,
            posted_date=item.posted_date,
        )
