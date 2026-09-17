#!/usr/bin/env python3
"""PreToolUse hook for Write|Edit: block writes whose path resolves outside this repo."""

import json
import sys
from pathlib import Path


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path:
        return 0

    project_dir = Path(payload.get("cwd", ".")).resolve()
    target = Path(file_path)
    if not target.is_absolute():
        target = project_dir / target

    try:
        resolved = target.resolve()
    except OSError:
        resolved = target

    is_inside = resolved == project_dir or project_dir in resolved.parents
    if not is_inside:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            f"Refusing to write outside the project directory: {resolved}"
                        ),
                    }
                }
            )
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
