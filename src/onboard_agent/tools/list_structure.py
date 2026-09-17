"""list_structure: immediate-children directory listing with per-file top-level symbols,
derived from the chunk index rather than re-parsing files."""

from __future__ import annotations

from onboard_agent.chunking.models import ChunkKind
from onboard_agent.ignore_patterns import IGNORED_DIR_NAMES
from onboard_agent.ingestion.pipeline import RepoContext
from onboard_agent.tools.path_safety import PathEscapesRepoError, resolve_within_repo
from onboard_agent.tools.schemas import (
    ListStructureInput,
    ListStructureOutput,
    StructureEntry,
    ToolError,
)


def list_structure(input: ListStructureInput, ctx: RepoContext) -> ListStructureOutput | ToolError:
    try:
        target_dir = resolve_within_repo(ctx.repo_root, input.path)
    except PathEscapesRepoError as exc:
        return ToolError(error=str(exc))

    if not target_dir.is_dir():
        return ToolError(error=f"Not a directory: {input.path}")

    symbols_by_file: dict[str, list[str]] = {}
    for chunk in ctx.chunks:
        if chunk.kind == ChunkKind.MODULE:
            continue
        symbols_by_file.setdefault(chunk.file_path, []).append(chunk.symbol)

    entries: list[StructureEntry] = []
    for child in sorted(target_dir.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if child.name in IGNORED_DIR_NAMES:
            continue

        relative = child.relative_to(ctx.repo_root).as_posix()
        if child.is_dir():
            entries.append(StructureEntry(path=relative + "/", is_directory=True, symbols=[]))
        else:
            entries.append(
                StructureEntry(
                    path=relative,
                    is_directory=False,
                    symbols=symbols_by_file.get(relative, []),
                )
            )

    return ListStructureOutput(path=input.path, entries=entries)
