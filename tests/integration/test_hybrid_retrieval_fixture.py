"""Phase 2 exit criteria: hybrid retrieval returns relevant chunks with accurate citations on
the fixture repo — proven via both an exact-identifier query (BM25's strength) and a paraphrased
natural-language query (dense embeddings' strength), showing both signals actually contribute."""

from pathlib import Path

import pytest

from onboard_agent.chunking.chunker import chunk_repo
from onboard_agent.indexing.hybrid import HybridRetriever
from onboard_agent.indexing.lexical import LexicalIndex
from onboard_agent.indexing.vector_store import VectorStore

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "tiny_repo"


@pytest.fixture(scope="module")
def retriever(tmp_path_factory):
    chunks = chunk_repo(FIXTURE_REPO)
    db_path = tmp_path_factory.mktemp("lancedb")
    hybrid = HybridRetriever(VectorStore(db_path), LexicalIndex())
    hybrid.build(chunks)
    return hybrid


def _top_symbols(results, n=5):
    return [r.chunk.symbol for r in results[:n]]


def test_exact_identifier_query_surfaces_the_named_function(retriever):
    results = retriever.search("add_user", final_k=5)
    assert "UserStore.add_user" in _top_symbols(results)
    top = results[0]
    assert top.chunk.citation().startswith("classes_and_methods.py:")


def test_paraphrased_query_surfaces_the_same_function_via_dense_similarity(retriever):
    results = retriever.search("how do I register a brand new user account", final_k=5)
    assert "UserStore.add_user" in _top_symbols(results)


def test_results_carry_accurate_file_and_line_citations(retriever):
    results = retriever.search("async fetch data from a url", final_k=3)
    assert results
    for result in results:
        citation = result.chunk.citation()
        assert citation.startswith(result.chunk.file_path + ":")
        assert f"{result.chunk.start_line}-{result.chunk.end_line}" in citation


def test_setup_style_query_does_not_penalize_module_chunks(retriever):
    results = retriever.search("module imports and configuration constants", final_k=5)
    kinds = [r.chunk.kind.value for r in results]
    assert "module" in kinds
