#!/usr/bin/env python3
"""Stop hook: run pytest -q. A failing suite means the task isn't done — block the stop.

pytest exit codes: 0 = all passed, 1 = tests failed, 2 = execution interrupted / collection
error, 5 = no tests collected. Only 1 and 2 represent "the suite is red" — 5 means there's
nothing to run yet (e.g. early in Phase 0) and must not block indefinitely.
"""

import json
import subprocess
import sys
from pathlib import Path

BLOCKING_EXIT_CODES = {1, 2}


def main() -> int:
    payload = json.load(sys.stdin)
    project_dir = Path(payload.get("cwd", "."))

    if not (project_dir / "pyproject.toml").exists():
        return 0

    result = subprocess.run(
        ["uv", "run", "pytest", "-q"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )

    if result.returncode in BLOCKING_EXIT_CODES:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-40:])
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "Stop",
                        "continueConversation": True,
                        "reason": f"pytest failed (exit {result.returncode}):\n{tail}",
                    }
                }
            )
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
