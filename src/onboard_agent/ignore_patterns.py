"""Directory names skipped when walking a cloned repo — vendored/build/cache noise that
should never be chunked, indexed, or shown in the directory tree."""

IGNORED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    ".egg-info",
}
