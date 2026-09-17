"""tree-sitter Python parser setup — isolated so the version-specific construction call
(verified against tree-sitter 0.26.x / tree-sitter-python 0.25.x) lives in exactly one place."""

from __future__ import annotations

from functools import lru_cache

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser, Tree


@lru_cache(maxsize=1)
def get_parser() -> Parser:
    language = Language(tspython.language())
    return Parser(language)


def parse_source(source: str) -> Tree:
    """Parse Python source text into a tree-sitter Tree. Pure static parsing — never executes
    the source."""
    return get_parser().parse(bytes(source, "utf8"))


def node_text(node: Node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf8")


def line_range(node: Node) -> tuple[int, int]:
    """1-indexed, inclusive line range for a node."""
    return node.start_point[0] + 1, node.end_point[0] + 1
