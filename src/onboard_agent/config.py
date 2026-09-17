"""Environment-driven configuration. Loads .env once at import time (python-dotenv) so every
entry point (CLI, MCP server, tests) sees the same settings without repeating the load call."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "claude-opus-5"


def anthropic_api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY")


def agent_model() -> str:
    return os.environ.get("ONBOARD_AGENT_MODEL", DEFAULT_MODEL)


def has_api_key() -> bool:
    key = anthropic_api_key()
    return bool(key and key.strip())
