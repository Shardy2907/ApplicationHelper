"""Agent 1: parses an uploaded CV (+ optional cover letter) into a CandidateProfile.

Uses a forced tool-use call against the Anthropic Messages API so the model's
output is validated against a JSON schema rather than free-form text. PDFs are
sent as native `document` content blocks (Claude reads them directly);
`.docx` files are text-extracted first since there is no native docx block type.
"""

from __future__ import annotations

import base64
from pathlib import Path

from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field

from applicationhelper.config import anthropic_api_key
from applicationhelper.models.profile import CandidateProfile, EducationEntry, WorkExperience
from applicationhelper.utils.files import extract_docx_text, extract_pdf_text

_PROMPT_PATH = Path(__file__).parent / "prompts" / "parser_system.md"
_TOOL_NAME = "extract_candidate_profile"
_DEFAULT_MODEL = "claude-sonnet-5"


class _ExtractedProfile(BaseModel):
    """Shape the LLM must fill in. Deliberately excludes DB/provenance fields
    (id, parsed_at, source paths) which are set by the caller, not the model."""

    full_name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[WorkExperience] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)


class DocumentParserAgent:
    def __init__(self, client: AsyncAnthropic | None = None, model: str = _DEFAULT_MODEL):
        self._client = client or AsyncAnthropic(api_key=anthropic_api_key())
        self._model = model
        self._system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def parse(
        self, cv_path: Path, cover_letter_path: Path | None = None
    ) -> CandidateProfile:
        content_blocks, raw_text_parts = self._build_content_blocks(cv_path, cover_letter_path)

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=self._system_prompt,
            messages=[{"role": "user", "content": content_blocks}],
            tools=[
                {
                    "name": _TOOL_NAME,
                    "description": "Record the structured candidate profile extracted from the documents.",
                    "input_schema": _ExtractedProfile.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
        )

        tool_use = next(b for b in response.content if b.type == "tool_use")
        extracted = _ExtractedProfile.model_validate(tool_use.input)

        return CandidateProfile(
            **extracted.model_dump(),
            raw_cv_text="\n\n".join(raw_text_parts),
            source_cv_path=str(cv_path),
            source_cover_letter_path=str(cover_letter_path) if cover_letter_path else None,
        )

    @staticmethod
    def _build_content_blocks(
        cv_path: Path, cover_letter_path: Path | None
    ) -> tuple[list[dict], list[str]]:
        blocks: list[dict] = []
        raw_text_parts: list[str] = []

        for label, path in (("CV/resume", cv_path), ("Cover letter", cover_letter_path)):
            if path is None:
                continue
            suffix = path.suffix.lower()
            if suffix == ".pdf":
                data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
                blocks.append({"type": "text", "text": f"--- {label} (PDF follows) ---"})
                blocks.append(
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": data},
                    }
                )
                raw_text_parts.append(extract_pdf_text(path))
            elif suffix == ".docx":
                text = extract_docx_text(path)
                blocks.append({"type": "text", "text": f"--- {label} ---\n{text}"})
                raw_text_parts.append(text)
            else:
                text = path.read_text(encoding="utf-8", errors="ignore")
                blocks.append({"type": "text", "text": f"--- {label} ---\n{text}"})
                raw_text_parts.append(text)

        return blocks, raw_text_parts
