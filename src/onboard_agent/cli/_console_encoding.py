"""Reconfigure stdout/stderr to UTF-8 on import. Model answers can include arbitrary Unicode
(arrows, smart quotes, non-Latin identifiers); Windows terminals default to a legacy codepage
(e.g. cp1252) that can't encode it, crashing the CLI mid-answer. A no-op where stdout is already
UTF-8 or doesn't support reconfigure (e.g. captured by a test runner)."""

import sys

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
