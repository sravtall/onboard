"""Local embeddings via sentence-transformers — no external API/key required. Model name is
configurable via ONBOARD_AGENT_EMBED_MODEL (see PLAN.md decision #5)."""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _model_name() -> str:
    return os.environ.get("ONBOARD_AGENT_EMBED_MODEL", DEFAULT_EMBED_MODEL)


@lru_cache(maxsize=1)
def _get_model():
    # Imported lazily: sentence-transformers/torch are heavy, and most unit tests never touch
    # this module.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(_model_name())


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a batch of texts. Returns an (N, D) float32 array, L2-normalized so that L2
    distance and cosine similarity rank identically."""
    if not texts:
        return np.zeros((0, embedding_dimension()), dtype=np.float32)
    vectors = _get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vectors, dtype=np.float32)


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0].tolist()


def embedding_dimension() -> int:
    return _get_model().get_sentence_embedding_dimension()
