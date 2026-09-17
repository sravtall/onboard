"""Unit test for the RRF fusion math against synthetic rank lists with a known expected merge
order — no embeddings/BM25 involved."""

from onboard_agent.indexing.hybrid import reciprocal_rank_fusion


def test_rrf_favors_a_document_ranked_well_by_both_rankers():
    dense_ranking = ["a", "b", "c"]
    lexical_ranking = ["b", "a", "d"]

    scores = reciprocal_rank_fusion([dense_ranking, lexical_ranking])

    # "a": rank 1 dense + rank 2 lexical; "b": rank 2 dense + rank 1 lexical.
    # Both combine ranks {1,2}, so with k identical across rankers they tie.
    assert scores["a"] == scores["b"]
    assert scores["a"] > scores["c"]  # "c" only appears in one ranker, at rank 3
    assert scores["a"] > scores["d"]  # "d" only appears in one ranker, at rank 3


def test_rrf_missing_from_one_ranker_contributes_zero_not_a_penalty():
    scores = reciprocal_rank_fusion([["x"], []])
    assert scores["x"] == 1 / (60 + 1)


def test_rrf_custom_k_changes_the_score_but_not_the_order():
    rankings = [["a", "b"], ["b", "a"]]
    scores_default = reciprocal_rank_fusion(rankings)
    scores_small_k = reciprocal_rank_fusion(rankings, k=1)

    assert scores_default["a"] == scores_default["b"]
    assert scores_small_k["a"] == scores_small_k["b"]
    assert scores_small_k["a"] > scores_default["a"]  # smaller k -> larger scores
