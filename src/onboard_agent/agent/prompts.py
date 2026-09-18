"""System prompt construction: a static instructions block plus a per-repo "repo map" block
that's cache_control-marked so it's reused across every question asked against the same repo in
a session (docs/PLAN.md decision #10)."""

from __future__ import annotations

from onboard_agent.chunking.models import RepoMap

STATIC_INSTRUCTIONS = """\
You are OnboardAgent, a read-only assistant that helps a new engineer understand an unfamiliar \
Python codebase. You have three tools: search_codebase (hybrid semantic + keyword search over \
the repo), read_file (read an exact line range), and list_structure (list a directory's files \
and their top-level symbols).

Rules:
- Every factual claim about the codebase must be backed by a citation to code you actually \
retrieved this session, in the form `path/to/file.py:START-END`. Never cite a file or line \
range you have not seen via a tool call.
- search_codebase only indexes Python source files — it cannot surface config/tooling files \
like pyproject.toml, setup.cfg, tox.ini, or CI YAML, even though those are exactly where "how \
is testing/linting/packaging configured" questions are usually answered. For questions about \
project setup, test tooling, build configuration, or CI, call list_structure on the repo root \
(and relevant subdirectories) to see what config files exist, then read_file them directly — \
don't rely on search_codebase alone for these.
- If your first search doesn't surface everything you need — for example you find a request \
handler but not the middleware or config it depends on — issue another search_codebase call \
with a refined query, or read_file to pull in the surrounding context, before answering.
- If, after searching, you cannot find the answer in this codebase, say so explicitly rather \
than guessing or answering from general knowledge. An honest "I couldn't find this in the repo" \
is always better than a plausible-sounding fabrication.
- You cannot write, edit, or execute code. You only read and explain.
- Keep answers focused on what was asked. Cite the specific files/lines that support each claim \
directly in your prose (not as an unexplained list at the end).\
"""


def build_repo_map_block(repo_map: RepoMap) -> str:
    lines = [
        f"# Repository map: {repo_map.repo_url} @ {repo_map.commit_sha[:12]}",
        "",
        "## Directory tree",
        repo_map.directory_tree or "(empty)",
        "",
        "## Dependencies",
        ", ".join(repo_map.dependencies) if repo_map.dependencies else "(none detected)",
        "",
        "## Entry points",
        "\n".join(repo_map.entry_points) if repo_map.entry_points else "(none detected)",
    ]
    if repo_map.readme_excerpt:
        lines += ["", "## README excerpt", repo_map.readme_excerpt]
    return "\n".join(lines)


def build_system_blocks(repo_map: RepoMap) -> list[dict]:
    """Two blocks: static instructions (small, effectively free to re-send) and the repo map
    (large, marked ephemeral so it's cached across every question in a session)."""
    return [
        {"type": "text", "text": STATIC_INSTRUCTIONS},
        {
            "type": "text",
            "text": build_repo_map_block(repo_map),
            "cache_control": {"type": "ephemeral"},
        },
    ]
