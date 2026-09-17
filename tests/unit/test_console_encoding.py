"""Regression test for a real bug found via a live smoke test: a Unicode character in a model
answer (e.g. an arrow, '↔') crashed the CLI on Windows, whose console defaults to a legacy
codepage that can't encode it. cli/_console_encoding reconfigures stdout/stderr to UTF-8 on
import."""

import importlib
import io
import sys


def test_importing_console_encoding_reconfigures_stdout_to_utf8(monkeypatch):
    fake_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    fake_stderr = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    import onboard_agent.cli._console_encoding as console_encoding

    importlib.reload(console_encoding)

    assert sys.stdout.encoding.lower().replace("-", "") == "utf8"
    assert sys.stderr.encoding.lower().replace("-", "") == "utf8"

    # The actual failure mode: printing a non-cp1252-encodable character used to raise
    # UnicodeEncodeError before the reconfigure.
    sys.stdout.write("2 ↔ 3 = 6\n")
    sys.stdout.flush()
