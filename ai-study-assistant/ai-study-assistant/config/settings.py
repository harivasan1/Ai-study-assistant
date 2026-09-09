"""
config/settings.py
-------------------
WHAT:
    Single source of truth for application configuration. Every other
    module imports values from here instead of calling os.getenv()
    directly, so there is exactly one place that knows how
    configuration is loaded.

WHY:
    Hard-coding API keys or magic numbers (chunk size, top-k, etc.)
    inside business logic makes the code fragile and insecure. Keeping
    configuration in one module makes the app safe to opensource: the
    repo can be public while the ".env" file (which is git-ignored)
    stays private.

HOW:
    python-dotenv reads a local ".env" file (if present) and loads its
    key=value pairs into the process environment. On Render, the
    ".env" file will not exist — instead, Render injects environment
    variables directly, which os.getenv() picks up the same way.

INPUT:
    Environment variables (from ".env" locally, or the hosting platform).

OUTPUT:
    Typed, validated Python constants that the rest of the app imports.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load variables from a local .env file if one exists. This is a no-op
# in production environments (like Render) that inject env vars directly.
load_dotenv()


def _get_int(name: str, default: int) -> int:
    """Read an integer environment variable safely, falling back to default."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        # Never crash the whole app because of a malformed env var.
        return default


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    embedding_model: str
    chat_model: str


def load_settings() -> Settings:
    """
    Build a validated Settings object from environment variables.

    Raises:
        RuntimeError: if OPENAI_API_KEY is missing. The app must fail
        loudly and early rather than silently making broken API calls.
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Create a '.env' file (see "
            "'.env.example') or set the environment variable in your "
            "hosting platform's dashboard."
        )

    return Settings(
        openai_api_key=api_key,
        chunk_size=_get_int("CHUNK_SIZE", 800),
        chunk_overlap=_get_int("CHUNK_OVERLAP", 120),
        top_k=_get_int("TOP_K", 4),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        chat_model=os.getenv("CHAT_MODEL", "gpt-4o-mini").strip(),
    )


# NOTE: We intentionally do NOT instantiate `Settings` at import time here.
# app.py calls load_settings() itself, inside a try/except, so a missing
# key produces a friendly Streamlit error instead of crashing on import.
