from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from applicationhelper.agents.open_web_search import OpenWebSearchAgent
from applicationhelper.models.filters import SearchFilters
from applicationhelper.models.job import ATSPlatform, RemoteType

_POSTINGS_INPUT = {
    "postings": [
        {
            "title": "Backend Engineer",
            "company": "Acme Corp",
            "location": "Berlin, Germany",
            "remote_type": "hybrid",
            "description_text": "Real role fetched from Acme's careers page.",
            "apply_url": "https://acme.example/careers/backend-engineer",
            "posted_date": "2026-07-01",
        }
    ]
}


def _tool_use_response(input_dict: dict, stop_reason: str = "end_turn"):
    tool_use_block = SimpleNamespace(type="tool_use", name="record_job_postings", input=input_dict)
    return SimpleNamespace(content=[tool_use_block], stop_reason=stop_reason)


def _client_with_responses(*responses) -> AsyncMock:
    client = AsyncMock()
    client.messages.create = AsyncMock(side_effect=list(responses))
    return client


async def test_search_maps_final_tool_use_into_job_postings():
    client = _client_with_responses(_tool_use_response(_POSTINGS_INPUT))
    agent = OpenWebSearchAgent(client=client)

    jobs = await agent.search(SearchFilters(title_keywords=["backend"]))

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Backend Engineer"
    assert job.company == "Acme Corp"
    assert job.remote_type == RemoteType.HYBRID
    assert job.source == ATSPlatform.OPEN_WEB
    assert job.apply_url == "https://acme.example/careers/backend-engineer"
    client.messages.create.assert_awaited_once()


async def test_search_does_not_force_tool_choice():
    client = _client_with_responses(_tool_use_response(_POSTINGS_INPUT))
    agent = OpenWebSearchAgent(client=client)

    await agent.search(SearchFilters())

    _, kwargs = client.messages.create.call_args
    assert kwargs["tool_choice"] == {"type": "auto"}
    tool_types = {t.get("type") for t in kwargs["tools"] if "type" in t}
    assert "web_search_20250305" in tool_types
    assert "web_fetch_20250910" in tool_types
    tool_names = {t["name"] for t in kwargs["tools"]}
    assert "record_job_postings" in tool_names


async def test_search_continues_through_pause_turn():
    paused = SimpleNamespace(
        content=[SimpleNamespace(type="server_tool_use", name="web_search", input={"query": "x"})],
        stop_reason="pause_turn",
    )
    final = _tool_use_response(_POSTINGS_INPUT)
    client = _client_with_responses(paused, final)
    agent = OpenWebSearchAgent(client=client)

    jobs = await agent.search(SearchFilters())

    assert len(jobs) == 1
    assert client.messages.create.await_count == 2
    # second call's message list should include the paused assistant turn appended
    _, second_kwargs = client.messages.create.await_args_list[1]
    assert second_kwargs["messages"][-1]["role"] == "assistant"
    assert second_kwargs["messages"][-1]["content"] == paused.content


async def test_search_gives_up_after_max_pause_turns():
    paused = SimpleNamespace(content=[], stop_reason="pause_turn")
    client = _client_with_responses(paused, paused, paused)
    agent = OpenWebSearchAgent(client=client, max_pause_turns=2)

    jobs = await agent.search(SearchFilters())

    assert jobs == []
    assert client.messages.create.await_count == 3  # initial + 2 continuations


async def test_search_returns_empty_list_when_model_never_calls_the_tool():
    text_only_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Nothing found.")], stop_reason="end_turn"
    )
    client = _client_with_responses(text_only_response)
    agent = OpenWebSearchAgent(client=client)

    jobs = await agent.search(SearchFilters())

    assert jobs == []


async def test_search_truncates_to_max_results():
    many = {
        "postings": [
            {**_POSTINGS_INPUT["postings"][0], "apply_url": f"https://acme.example/careers/job-{i}"}
            for i in range(5)
        ]
    }
    client = _client_with_responses(_tool_use_response(many))
    agent = OpenWebSearchAgent(client=client)

    jobs = await agent.search(SearchFilters(), max_results=2)

    assert len(jobs) == 2
