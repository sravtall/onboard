"""AST-based (tree-sitter) chunking: splits Python source into function/class/method/module
chunks with accurate line ranges — never fixed-size text splitting."""

from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from onboard_agent.chunking.models import Chunk, ChunkKind
from onboard_agent.chunking.treesitter_parser import line_range, node_text, parse_source
from onboard_agent.ignore_patterns import IGNORED_DIR_NAMES

_DEFINITION_TYPES = {"function_definition", "class_definition", "decorated_definition"}

_MAX_SUMMARY_LEN = 160


def _unwrap(node: Node) -> tuple[Node, Node]:
    """Return (outer_span_node, inner_definition_node). For a decorated definition the outer
    span includes the decorators; the inner node is the actual function/class definition."""
    if node.type == "decorated_definition":
        inner = node.child_by_field_name("definition")
        return node, inner
    return node, node


def _iter_top_level_definitions(container: Node):
    """Yield function/class/decorated definition nodes that are *direct* children of a
    module or block node (i.e. not nested deeper, so callers control recursion depth)."""
    for child in container.children:
        if child.type in _DEFINITION_TYPES:
            yield child


def _get_name(def_node: Node, source_bytes: bytes) -> str:
    name_node = def_node.child_by_field_name("name")
    return node_text(name_node, source_bytes) if name_node is not None else "<anonymous>"


def _strip_string_literal(text: str) -> str:
    text = text.strip()
    for prefix in ('"""', "'''", '"', "'"):
        if text.startswith(prefix) and text.endswith(prefix) and len(text) >= 2 * len(prefix):
            return text[len(prefix) : len(text) - len(prefix)]
    return text


def _slice_lines(source_lines: list[str], start_line: int, end_line: int) -> str:
    """Extract lines [start_line, end_line] (1-indexed, inclusive) verbatim, preserving the
    original indentation on every line — unlike a raw node byte-range slice, whose first line
    starts at the node's start_byte and so loses its leading indentation."""
    return "\n".join(source_lines[start_line - 1 : end_line])


def _truncate(text: str) -> str:
    text = text.strip()
    if len(text) <= _MAX_SUMMARY_LEN:
        return text
    return text[: _MAX_SUMMARY_LEN - 3] + "..."


def _make_summary(def_node: Node, source_bytes: bytes) -> str:
    body = def_node.child_by_field_name("body")
    if body is not None and body.named_child_count > 0:
        first_stmt = body.named_children[0]
        if (
            first_stmt.type == "expression_statement"
            and first_stmt.named_child_count > 0
            and first_stmt.named_children[0].type == "string"
        ):
            docstring = _strip_string_literal(node_text(first_stmt.named_children[0], source_bytes))
            first_line = next((line.strip() for line in docstring.splitlines() if line.strip()), "")
            if first_line:
                return _truncate(first_line)

    signature_line = node_text(def_node, source_bytes).splitlines()[0].strip()
    return _truncate(signature_line)


def _walk(
    container: Node,
    parent_symbol: str | None,
    parent_kind: ChunkKind | None,
    source_bytes: bytes,
    source_lines: list[str],
    file_path: str,
    chunks: list[Chunk],
) -> None:
    for raw in _iter_top_level_definitions(container):
        outer, inner = _unwrap(raw)
        if inner is None:
            continue

        name = _get_name(inner, source_bytes)
        symbol = f"{parent_symbol}.{name}" if parent_symbol else name
        start_line, end_line = line_range(outer)

        if inner.type == "class_definition":
            kind = ChunkKind.CLASS
        else:
            kind = ChunkKind.METHOD if parent_kind == ChunkKind.CLASS else ChunkKind.FUNCTION

        chunks.append(
            Chunk(
                chunk_id=f"{file_path}::{symbol}",
                file_path=file_path,
                symbol=symbol,
                kind=kind,
                parent_symbol=parent_symbol if kind == ChunkKind.METHOD else None,
                start_line=start_line,
                end_line=end_line,
                code_text=_slice_lines(source_lines, start_line, end_line),
                summary=_make_summary(inner, source_bytes),
            )
        )

        body = inner.child_by_field_name("body")
        if body is not None:
            _walk(body, symbol, kind, source_bytes, source_lines, file_path, chunks)


def chunk_source(source: str, file_path: str) -> list[Chunk]:
    """Chunk a single Python file's source text. `file_path` should be relative to the repo
    root — it becomes part of every chunk's citation."""
    source_bytes = bytes(source, "utf8")
    source_lines = source.splitlines()
    tree = parse_source(source)
    root = tree.root_node

    chunks: list[Chunk] = []
    top_level_defs = list(_iter_top_level_definitions(root))

    total_lines = len(source_lines) or 1

    if top_level_defs:
        first_outer, _ = _unwrap(top_level_defs[0])
        first_def_start = line_range(first_outer)[0]
        if first_def_start > 1:
            preamble_text = _slice_lines(source_lines, 1, first_def_start - 1)
            if preamble_text.strip():
                chunks.append(
                    Chunk(
                        chunk_id=f"{file_path}::<module>",
                        file_path=file_path,
                        symbol="<module>",
                        kind=ChunkKind.MODULE,
                        start_line=1,
                        end_line=first_def_start - 1,
                        code_text=preamble_text,
                        summary=_truncate(source_lines[0]) if source_lines else "",
                    )
                )
    else:
        chunks.append(
            Chunk(
                chunk_id=f"{file_path}::<module>",
                file_path=file_path,
                symbol="<module>",
                kind=ChunkKind.MODULE,
                start_line=1,
                end_line=total_lines,
                code_text=_slice_lines(source_lines, 1, total_lines),
                summary=_truncate(source_lines[0]) if source.strip() else "(empty file)",
            )
        )

    _walk(root, None, None, source_bytes, source_lines, file_path, chunks)
    return chunks


def discover_python_files(repo_root: Path) -> list[Path]:
    """Find every .py file under repo_root, skipping vendored/build/cache directories."""
    files: list[Path] = []
    for path in repo_root.rglob("*.py"):
        if any(part in IGNORED_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def chunk_repo(repo_root: Path) -> list[Chunk]:
    """Chunk every Python file under repo_root. Pure static parsing — the repo's code is never
    imported, exec'd, or subprocess-run."""
    chunks: list[Chunk] = []
    for path in discover_python_files(repo_root):
        relative = path.relative_to(repo_root).as_posix()
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        chunks.extend(chunk_source(source, relative))
    return chunks
