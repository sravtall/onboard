#!/usr/bin/env python3
"""PostToolUse hook for Write|Edit: run ruff format + ruff check --fix on the touched file."""

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path or not file_path.endswith(".py"):
        return 0

    path = Path(file_path)
    if not path.exists():
        return 0

    project_dir = Path(payload.get("cwd", "."))
    subprocess.run(
        ["uv", "run", "ruff", "format", str(path)],
        cwd=project_dir,
        capture_output=True,
    )
    subprocess.run(
        ["uv", "run", "ruff", "check", "--fix", str(path)],
        cwd=project_dir,
        capture_output=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
