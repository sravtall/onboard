"""read_file: read a line range (or a whole small file) from the cloned repo. Path-confined to
the repo root — never touches anything outside it."""

from __future__ import annotations

from onboard_agent.ingestion.pipeline import RepoContext
from onboard_agent.tools.path_safety import PathEscapesRepoError, resolve_within_repo
from onboard_agent.tools.schemas import ReadFileInput, ReadFileOutput, ToolError

_MAX_LINES = 500


def read_file(input: ReadFileInput, ctx: RepoContext) -> ReadFileOutput | ToolError:
    try:
        target = resolve_within_repo(ctx.repo_root, input.path)
    except PathEscapesRepoError as exc:
        return ToolError(error=str(exc))

    if not target.is_file():
        return ToolError(error=f"Not a file: {input.path}")

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return ToolError(error=f"Could not read {input.path}: {exc}")

    lines = text.splitlines()
    start = input.start_line or 1
    end = input.end_line or len(lines)
    start = max(1, start)
    end = min(len(lines), end)
    if end - start + 1 > _MAX_LINES:
        end = start + _MAX_LINES - 1

    if start > len(lines):
        return ToolError(error=f"start_line {start} is beyond end of file ({len(lines)} lines)")

    content = "\n".join(lines[start - 1 : end])
    return ReadFileOutput(path=input.path, start_line=start, end_line=end, content=content)
