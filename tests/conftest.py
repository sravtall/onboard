"""Auto-skip tests marked `requires_api_key` when ANTHROPIC_API_KEY isn't configured, per
CLAUDE.md."""

import pytest

from onboard_agent.config import has_api_key


def pytest_collection_modifyitems(config, items):
    if has_api_key():
        return
    skip_marker = pytest.mark.skip(reason="ANTHROPIC_API_KEY not set")
    for item in items:
        if "requires_api_key" in item.keywords:
            item.add_marker(skip_marker)
