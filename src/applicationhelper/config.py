"""Application-wide settings and paths."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "applicationhelper"


def data_dir() -> Path:
    """Directory for the SQLite DB and generated documents (created if missing)."""
    base = os.environ.get("APPDATA") or str(Path.home() / ".local" / "share")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "applicationhelper.sqlite3"


def generated_docs_dir() -> Path:
    path = data_dir() / "generated_docs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def anthropic_api_key() -> str:
    """Resolve the Anthropic API key, preferring the OS keyring over env vars.

    Stage 4/5 will wire a settings UI backed by `keyring`; for now this falls
    back to the ANTHROPIC_API_KEY env var so CLI/dev scripts work standalone.
    """
    try:
        import keyring

        key = keyring.get_password(APP_NAME, "anthropic_api_key")
        if key:
            return key
    except Exception:
        pass

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY or store one in "
            "the OS keyring under service 'applicationhelper' / username "
            "'anthropic_api_key'."
        )
    return key
