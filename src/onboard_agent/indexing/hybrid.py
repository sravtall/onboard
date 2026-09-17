"""Hybrid retrieval: dense (LanceDB) + lexical (BM25) fused via Reciprocal Rank Fusion, then a
cheap algorithmic rerank. See PLAN.md decisions #6-7 for why RRF and why no cross-encoder.

Retrieval is "wide" (top-N per ranker, fused) then narrowed by rerank to the final top-K handed
to a caller (the agent's search_codebase tool, or an eval).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from onboard_agent.chunking.models import Chunk, ChunkKind
from onboard_agent.indexing.lexical import LexicalIndex
from onboard_agent.indexing.vector_store import VectorStore

RRF_K = 60
DEFAULT_WIDE_K = 30
DEFAULT_FINAL_K = 8

_IDENTIFIER_BONUS = 0.05
_MODULE_PENALTY = 0.02
_SETUP_QUERY_WORDS = {
    "import",
    "imports",
    "setup",
    "module",
    "structure",
    "config",
    "configuration",
}

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class RetrievalResult:
    chunk: Chunk
    score: float


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """score(chunk) = sum over rankers of 1/(k + rank). A chunk missing from a ranker simply
    contributes 0 from that term rather than an infinite-rank penalty."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores


def _query_tokens(query: str) -> set[str]:
    return {tok.lower() for tok in _WORD_RE.findall(query)}


def _rerank(
    candidate_ids: list[str],
    fused_scores: dict[str, float],
    chunks_by_id: dict[str, Chunk],
    query: str,
) -> list[RetrievalResult]:
    """Cheap, deterministic rerank over the fused candidate set — no cross-encoder / LLM call,
    so retrieval stays testable without an API key (PLAN.md decision #7)."""
    q_tokens = _query_tokens(query)
    setup_query = bool(q_tokens & _SETUP_QUERY_WORDS)

    scored: list[RetrievalResult] = []
    for chunk_id in candidate_ids:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        score = fused_scores[chunk_id]

        symbol_tokens = _query_tokens(chunk.symbol.replace(".", " "))
        if symbol_tokens & q_tokens:
            score += _IDENTIFIER_BONUS

        if chunk.kind == ChunkKind.MODULE and not setup_query:
            score -= _MODULE_PENALTY

        scored.append(RetrievalResult(chunk=chunk, score=score))

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored


class HybridRetriever:
    """One instance per ingested repo. Owns the dense + lexical indexes and the chunk registry
    they're built from — the single place `search_codebase` (tools/search_codebase.py) delegates
    to."""

    def __init__(self, vector_store: VectorStore, lexical_index: LexicalIndex) -> None:
        self._vector_store = vector_store
        self._lexical_index = lexical_index
        self._chunks_by_id: dict[str, Chunk] = {}

    def build(self, chunks: list[Chunk]) -> None:
        self._chunks_by_id = {c.chunk_id: c for c in chunks}
        self._vector_store.build(chunks)
        self._lexical_index.build(chunks)

    def search(
        self,
        query: str,
        final_k: int = DEFAULT_FINAL_K,
        wide_k: int = DEFAULT_WIDE_K,
    ) -> list[RetrievalResult]:
        dense_ranking = [chunk_id for chunk_id, _ in self._vector_store.search(query, wide_k)]
        lexical_ranking = [chunk_id for chunk_id, _ in self._lexical_index.search(query, wide_k)]

        fused_scores = reciprocal_rank_fusion([dense_ranking, lexical_ranking])
        if not fused_scores:
            return []

        candidate_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)
        candidate_ids = candidate_ids[:wide_k]

        reranked = _rerank(candidate_ids, fused_scores, self._chunks_by_id, query)
        return reranked[:final_k]
