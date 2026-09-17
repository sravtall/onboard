"""BM25 lexical search over chunk text — catches exact identifiers and error strings that
embeddings blur. Fused with dense search via Reciprocal Rank Fusion in indexing/hybrid.py."""

from __future__ import annotations

import bm25s

from onboard_agent.chunking.models import Chunk


def _chunk_lexical_text(chunk: Chunk) -> str:
    # file_path included for the same reason as the dense embedding text — see
    # indexing/vector_store.py and PLAN.md decision #18.
    return f"{chunk.file_path}\n{chunk.symbol}\n{chunk.summary}\n{chunk.code_text}"


class LexicalIndex:
    """One instance per ingested repo."""

    def __init__(self) -> None:
        self._retriever: bm25s.BM25 | None = None
        self._chunk_ids: list[str] = []

    def build(self, chunks: list[Chunk]) -> None:
        self._chunk_ids = [c.chunk_id for c in chunks]
        if not chunks:
            self._retriever = None
            return
        corpus_tokens = bm25s.tokenize(
            [_chunk_lexical_text(c) for c in chunks], show_progress=False
        )
        self._retriever = bm25s.BM25()
        self._retriever.index(corpus_tokens, show_progress=False)

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Return up to top_k (chunk_id, score) pairs, descending score (best first)."""
        if self._retriever is None or not self._chunk_ids:
            return []
        k = min(top_k, len(self._chunk_ids))
        query_tokens = bm25s.tokenize([query], show_progress=False)
        doc_indices, scores = self._retriever.retrieve(query_tokens, k=k, show_progress=False)
        return [
            (self._chunk_ids[idx], float(score))
            for idx, score in zip(doc_indices[0], scores[0], strict=True)
            if score > 0
        ]
