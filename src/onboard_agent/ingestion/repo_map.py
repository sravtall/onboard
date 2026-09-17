"""Repo-level signals: README, dependencies, directory tree, entry points. An onboarding tool
needs the map, not just the pieces — this is what gets rendered into the agent's cached
system-prompt block."""

from __future__ import annotations

import re
from pathlib import Path

from onboard_agent.chunking.models import RepoMap
from onboard_agent.ignore_patterns import IGNORED_DIR_NAMES

_README_NAMES = ["README.md", "README.rst", "README.txt", "README"]
_ENTRY_POINT_CANDIDATES = ["main.py", "app.py", "manage.py", "cli.py", "__main__.py"]
_README_EXCERPT_CHARS = 4000
_MAX_TREE_DEPTH = 3
_MAX_TREE_ENTRIES = 400


def _read_readme(repo_root: Path) -> str | None:
    for name in _README_NAMES:
        candidate = repo_root / name
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8", errors="replace")
            return text[:_README_EXCERPT_CHARS]
    return None


def _parse_dependencies(repo_root: Path) -> list[str]:
    deps: list[str] = []

    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        in_deps = False
        for line in text.splitlines():
            stripped = line.strip()
            if re.match(r"^dependencies\s*=\s*\[", stripped):
                in_deps = True
                continue
            if in_deps:
                if stripped.startswith("]"):
                    in_deps = False
                    continue
                match = re.match(r'^"([^"]+)"', stripped)
                if match:
                    deps.append(match.group(1))

    requirements = repo_root / "requirements.txt"
    if requirements.is_file():
        for line in requirements.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                deps.append(stripped)

    return deps


def _find_entry_points(repo_root: Path) -> list[str]:
    found: list[str] = []
    for candidate in _ENTRY_POINT_CANDIDATES:
        matches = [
            p
            for p in repo_root.rglob(candidate)
            if not any(part in IGNORED_DIR_NAMES for part in p.parts)
        ]
        found.extend(str(p.relative_to(repo_root).as_posix()) for p in matches)

    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        found.extend(re.findall(r"^\[project\.scripts\][^\[]*", text, re.MULTILINE))

    return sorted(set(found))


def _build_directory_tree(repo_root: Path) -> str:
    lines: list[str] = []
    entry_count = 0

    def walk(directory: Path, prefix: str, depth: int) -> None:
        nonlocal entry_count
        if depth > _MAX_TREE_DEPTH or entry_count >= _MAX_TREE_ENTRIES:
            return
        try:
            entries = sorted(
                (e for e in directory.iterdir() if e.name not in IGNORED_DIR_NAMES),
                key=lambda e: (e.is_file(), e.name.lower()),
            )
        except OSError:
            return
        for entry in entries:
            if entry_count >= _MAX_TREE_ENTRIES:
                lines.append(f"{prefix}... (truncated)")
                return
            marker = "/" if entry.is_dir() else ""
            lines.append(f"{prefix}{entry.name}{marker}")
            entry_count += 1
            if entry.is_dir():
                walk(entry, prefix + "  ", depth + 1)

    walk(repo_root, "", 0)
    return "\n".join(lines)


def build_repo_map(repo_root: Path, repo_url: str, commit_sha: str) -> RepoMap:
    return RepoMap(
        repo_url=repo_url,
        commit_sha=commit_sha,
        readme_excerpt=_read_readme(repo_root),
        dependencies=_parse_dependencies(repo_root),
        directory_tree=_build_directory_tree(repo_root),
        entry_points=_find_entry_points(repo_root),
    )
