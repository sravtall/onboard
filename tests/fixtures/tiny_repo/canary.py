"""Canary file: writes a marker file as a top-level side effect the instant this module is
imported or executed. Chunking must NEVER trigger this — it proves chunking is pure static AST
parsing, never execution, of untrusted repo code."""

import os

_MARKER_PATH = os.environ.get("ONBOARD_AGENT_CANARY_MARKER", "canary_fired.marker")

with open(_MARKER_PATH, "w", encoding="utf-8") as _f:
    _f.write("canary fired: this file was executed, not just parsed")


def canary_function():
    """A normal-looking function alongside the top-level side effect."""
    return "canary"
