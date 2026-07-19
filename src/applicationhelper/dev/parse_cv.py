"""Stage 1 demo: parse a real CV (+ optional cover letter) and persist it.

Usage:
    python -m applicationhelper.dev.parse_cv path/to/cv.pdf [path/to/cover_letter.pdf]

Requires ANTHROPIC_API_KEY (or a keyring entry) to be set.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from applicationhelper.agents.document_parser import DocumentParserAgent
from applicationhelper.config import db_path
from applicationhelper.storage.db import make_engine, make_session_factory
from applicationhelper.storage.repository import ProfileRepository


async def _run(cv_path: Path, cover_letter_path: Path | None) -> None:
    agent = DocumentParserAgent()
    profile = await agent.parse(cv_path, cover_letter_path)

    engine = make_engine(db_path())
    session_factory = make_session_factory(engine)
    with session_factory() as session:
        repo = ProfileRepository(session)
        saved = repo.save(profile)
        session.commit()

    print(json.dumps(saved.model_dump(mode="json"), indent=2))
    print(f"\nSaved profile id={saved.id} to {db_path()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse a CV into a structured profile.")
    parser.add_argument("cv_path", type=Path)
    parser.add_argument("cover_letter_path", type=Path, nargs="?", default=None)
    args = parser.parse_args()

    asyncio.run(_run(args.cv_path, args.cover_letter_path))


if __name__ == "__main__":
    main()
