from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from applicationhelper.agents.document_parser import DocumentParserAgent

FIXTURE_CV = Path(__file__).parent.parent / "fixtures" / "sample_cv.txt"

_EXTRACTED_INPUT = {
    "full_name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+1-555-0100",
    "location": "Austin, TX",
    "summary": "Backend engineer with 5 years of experience building distributed systems.",
    "skills": ["Python", "SQL", "AWS", "Docker"],
    "experience": [
        {
            "company": "Acme Corp",
            "title": "Senior Software Engineer",
            "start_date": "2021-03",
            "end_date": None,
            "is_current": True,
            "bullets": [
                "Led migration of the billing service to Python 3.13",
                "Mentored two junior engineers",
            ],
        },
        {
            "company": "Globex Inc",
            "title": "Software Engineer",
            "start_date": "2018-06",
            "end_date": "2021-02",
            "is_current": False,
            "bullets": ["Built the internal analytics pipeline"],
        },
    ],
    "education": [
        {
            "institution": "State University",
            "degree": "B.S. Computer Science",
            "start_date": "2014-08",
            "end_date": "2018-05",
        }
    ],
    "certifications": [],
    "achievements": [],
}


def _fake_client_returning(input_dict: dict) -> AsyncMock:
    tool_use_block = SimpleNamespace(type="tool_use", input=input_dict)
    response = SimpleNamespace(content=[tool_use_block])

    client = AsyncMock()
    client.messages.create = AsyncMock(return_value=response)
    return client


async def test_parse_maps_tool_use_output_into_candidate_profile():
    client = _fake_client_returning(_EXTRACTED_INPUT)
    agent = DocumentParserAgent(client=client)

    profile = await agent.parse(FIXTURE_CV)

    assert profile.full_name == "Jane Doe"
    assert profile.email == "jane@example.com"
    assert profile.skills == ["Python", "SQL", "AWS", "Docker"]
    assert len(profile.experience) == 2
    assert profile.experience[0].company == "Acme Corp"
    assert profile.experience[0].is_current is True
    assert profile.education[0].institution == "State University"
    assert profile.source_cv_path == str(FIXTURE_CV)
    assert profile.source_cover_letter_path is None
    assert "Jane Doe" in profile.raw_cv_text


async def test_parse_forces_tool_choice_and_sends_cv_text():
    client = _fake_client_returning(_EXTRACTED_INPUT)
    agent = DocumentParserAgent(client=client)

    await agent.parse(FIXTURE_CV)

    _, kwargs = client.messages.create.call_args
    assert kwargs["tool_choice"] == {"type": "tool", "name": "extract_candidate_profile"}
    assert kwargs["tools"][0]["name"] == "extract_candidate_profile"
    sent_text = kwargs["messages"][0]["content"][0]["text"]
    assert "Jane Doe" in sent_text
