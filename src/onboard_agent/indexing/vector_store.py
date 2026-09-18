"""LanceDB-backed dense vector store. Bring-your-own-vectors: embeddings are computed by
indexing/embeddings.py, this module only stores and searches them.

LanceDB chosen over pgvector/Chroma: embedded (no separate server process, unlike a Postgres
dependency), disk-backed via Apache Arrow/Lance so it scales past RAM (unlike Chroma's
memory-first default) — appropriate for a local CLI tool. See docs/PLAN.md decision #4.
"""

from __future__ import annotations

from pathlib import Path

import lancedb

from onboard_agent.chunking.models import Chunk
from onboard_agent.indexing.embeddings import embed_query, embed_texts

_TABLE_NAME = "chunks"


def _chunk_embedding_text(chunk: Chunk) -> str:
    # file_path is included so a query naming or implying a specific module (e.g. "conftest",
    # "cli.py") has something to match against even when that filename never appears in the
    # chunk's own body — see docs/PLAN.md decision #18.
    return f"{chunk.file_path}\n{chunk.symbol}\n{chunk.summary}\n{chunk.code_text}"


class VectorStore:
    """One instance per ingested repo. `db_path` should be a per-repo cache directory."""

    def __init__(self, db_path: Path) -> None:
        self._db = lancedb.connect(str(db_path))
        self._table = None

    def build(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        vectors = embed_texts([_chunk_embedding_text(c) for c in chunks])
        data = [
            {"chunk_id": chunk.chunk_id, "vector": vector.tolist()}
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self._table = self._db.create_table(_TABLE_NAME, data=data, mode="overwrite")

    def load(self) -> bool:
        """Open a previously-built table. Returns False if none exists yet."""
        if _TABLE_NAME not in self._db.table_names():
            return False
        self._table = self._db.open_table(_TABLE_NAME)
        return True

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Return up to top_k (chunk_id, distance) pairs, ascending distance (best first)."""
        if self._table is None:
            return []
        query_vector = embed_query(query)
        results = self._table.search(query_vector).limit(top_k).to_list()
        return [(row["chunk_id"], float(row["_distance"])) for row in results]
