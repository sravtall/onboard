"""Phase 1 exit criteria: chunk boundaries align to function/class definitions, and chunking
never executes the source it parses."""

from pathlib import Path

import pytest

from onboard_agent.chunking.chunker import chunk_repo, chunk_source, discover_python_files
from onboard_agent.chunking.models import ChunkKind

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "tiny_repo"

_DEF_KEYWORDS = ("def ", "class ", "async def ")


def _chunk_starts_at_a_definition_or_module_start(chunk) -> bool:
    first_line = chunk.code_text.splitlines()[0].strip()
    if chunk.kind == ChunkKind.MODULE:
        return True  # module preamble/whole-file chunk — no def/class boundary expected
    return first_line.startswith(_DEF_KEYWORDS) or "def " in first_line or "class " in first_line


@pytest.fixture(scope="module")
def all_chunks():
    return chunk_repo(FIXTURE_REPO)


def test_discovers_every_python_file_in_the_fixture():
    files = {p.name for p in discover_python_files(FIXTURE_REPO)}
    assert files == {
        "plain_functions.py",
        "classes_and_methods.py",
        "decorators.py",
        "async_defs.py",
        "constants_only.py",
        "canary.py",
    }


def test_every_chunk_line_range_slices_back_to_its_own_code_text(all_chunks):
    """The strongest boundary check: re-slicing the *actual file* by (start_line, end_line)
    must reproduce exactly the chunk's stored code_text."""
    by_file: dict[str, list[str]] = {}
    for chunk in all_chunks:
        if chunk.file_path not in by_file:
            source = (FIXTURE_REPO / chunk.file_path).read_text(encoding="utf-8")
            by_file[chunk.file_path] = source.splitlines()

        lines = by_file[chunk.file_path]
        sliced = "\n".join(lines[chunk.start_line - 1 : chunk.end_line])
        assert sliced == chunk.code_text, f"boundary mismatch for {chunk.chunk_id}"


def test_every_non_module_chunk_starts_at_a_def_class_or_decorator_line(all_chunks):
    for chunk in all_chunks:
        if chunk.kind == ChunkKind.MODULE:
            continue
        first_line = chunk.code_text.splitlines()[0].strip()
        starts_ok = (
            first_line.startswith("def ")
            or first_line.startswith("async def ")
            or first_line.startswith("class ")
            or first_line.startswith("@")
        )
        assert starts_ok, f"{chunk.chunk_id} starts with unexpected line: {first_line!r}"


def test_plain_functions_are_chunked_individually():
    chunks = chunk_source(
        (FIXTURE_REPO / "plain_functions.py").read_text(encoding="utf-8"), "plain_functions.py"
    )
    functions = {c.symbol: c for c in chunks if c.kind == ChunkKind.FUNCTION}
    assert set(functions) == {"add", "subtract", "_private_helper"}
    assert functions["add"].summary == "Add two numbers."


def test_class_chunk_includes_full_body_and_methods_are_chunked_with_parent(all_chunks):
    class_chunks = {c.symbol: c for c in all_chunks if c.kind == ChunkKind.CLASS}
    assert "UserStore" in class_chunks
    assert "def add_user" in class_chunks["UserStore"].code_text
    assert "def get_user" in class_chunks["UserStore"].code_text

    method_chunks = {c.symbol: c for c in all_chunks if c.kind == ChunkKind.METHOD}
    assert method_chunks["UserStore.add_user"].parent_symbol == "UserStore"
    assert method_chunks["UserStore.get_user"].parent_symbol == "UserStore"


def test_nested_class_gets_dotted_symbol_path(all_chunks):
    class_chunks = {c.symbol: c for c in all_chunks if c.kind == ChunkKind.CLASS}
    assert "UserStore.Config" in class_chunks
    assert class_chunks["UserStore.Config"].parent_symbol is None  # only METHOD sets parent


def test_decorated_function_chunk_span_includes_the_decorator(all_chunks):
    functions = {c.symbol: c for c in all_chunks if c.kind == ChunkKind.FUNCTION}
    health = functions["health_check"]
    assert health.code_text.splitlines()[0].strip() == '@route("/health")'


def test_decorated_method_is_still_classified_as_method(all_chunks):
    methods = {c.symbol: c for c in all_chunks if c.kind == ChunkKind.METHOD}
    assert "Handlers.static_helper" in methods
    assert "Handlers.name" in methods
    assert "Handlers.get_user" in methods
    assert methods["Handlers.get_user"].parent_symbol == "Handlers"


def test_async_functions_are_chunked_as_function_or_method(all_chunks):
    functions = {c.symbol: c for c in all_chunks if c.kind == ChunkKind.FUNCTION}
    methods = {c.symbol: c for c in all_chunks if c.kind == ChunkKind.METHOD}
    assert "fetch_data" in functions
    assert functions["fetch_data"].code_text.startswith("async def fetch_data")
    assert "Client.connect" in methods


def test_module_with_no_definitions_becomes_a_single_module_chunk():
    chunks = chunk_source(
        (FIXTURE_REPO / "constants_only.py").read_text(encoding="utf-8"), "constants_only.py"
    )
    assert len(chunks) == 1
    assert chunks[0].kind == ChunkKind.MODULE
    assert "MAX_RETRIES" in chunks[0].code_text


def test_module_preamble_chunk_captures_only_pre_definition_content(all_chunks):
    module_chunks = [
        c for c in all_chunks if c.file_path == "plain_functions.py" and c.kind == ChunkKind.MODULE
    ]
    assert len(module_chunks) == 1
    assert "from __future__" in module_chunks[0].code_text
    assert "def add" not in module_chunks[0].code_text


def test_chunking_never_executes_the_canary_file(tmp_path, monkeypatch):
    """The canary file writes a marker as a top-level side effect if executed/imported. Chunking
    must never trigger it — it's pure static AST parsing."""
    marker_path = tmp_path / "canary_fired.marker"
    monkeypatch.setenv("ONBOARD_AGENT_CANARY_MARKER", str(marker_path))
    monkeypatch.chdir(tmp_path)

    chunks = chunk_repo(FIXTURE_REPO)
    canary_chunks = [c for c in chunks if c.file_path == "canary.py"]

    assert canary_chunks, "canary.py should still be chunked normally"
    assert any(c.symbol == "canary_function" for c in canary_chunks)
    assert not marker_path.exists(), "chunking executed canary.py instead of just parsing it"
    assert not Path("canary_fired.marker").exists()
