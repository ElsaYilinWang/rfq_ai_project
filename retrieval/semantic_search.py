# retrieval/semantic_search.py

"""
Semantic supplier retrieval — Phase 14a.

Embeds RFQ item descriptions with a local sentence-transformers model
(no API call, no cost, no network dependency once the model is
downloaded) and finds the closest historical items by cosine
similarity. This exists for exactly one situation: an item with no
manufacturer identified by the parser OR the Phase 11 analyzer, where
exact/manufacturer-based lookup has nothing to search on at all.

Deterministic-first is preserved here the same way it is everywhere
else in this project: this module is never the first thing tried, and
its own guardrail is the similarity threshold — below it, "no match"
is returned rather than the best-available-but-weak candidate. A weak
forced match is worse than an honest "nothing found."

The model is loaded lazily (on first real use, not on import) so
importing this module — or anything that imports it — doesn't pay the
model-load cost unless retrieval is actually invoked.
"""

import logging
from typing import List

from sentence_transformers import SentenceTransformer, util

from retrieval.corpus import HISTORICAL_ITEMS
from retrieval.schemas import SemanticMatch

logger = logging.getLogger("retrieval")

MODEL_NAME = "all-MiniLM-L6-v2"

# Below this cosine similarity, a match is not returned. Calibrated
# against a real diagnostic run (see tests/test_semantic_retrieval.py
# for the assertions): every true-positive top score in that run was
# >= 0.58 (the hardest case — same manufacturer, different product),
# every true-negative top score was <= 0.14. 0.5 sits with real margin
# on both sides of that observed gap, not a value copied from
# documentation or picked before anything was measured.
DEFAULT_SIMILARITY_THRESHOLD = 0.5

_model = None
_corpus_embeddings = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading sentence-transformers model | model=%s", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _get_corpus_embeddings():
    global _corpus_embeddings
    if _corpus_embeddings is None:
        model = _get_model()
        descriptions = [item.description for item in HISTORICAL_ITEMS]
        _corpus_embeddings = model.encode(descriptions, convert_to_tensor=True)
    return _corpus_embeddings


def find_semantic_matches(
    query_description: str,
    top_k: int = 3,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> List[SemanticMatch]:
    """
    Returns up to top_k historical matches for query_description, each
    with a similarity score, filtered to those at or above threshold.
    An empty list is a valid, expected result — it means nothing in
    the corpus is similar enough to trust, not that the function
    failed.
    """
    model = _get_model()
    corpus_embeddings = _get_corpus_embeddings()

    query_embedding = model.encode(query_description, convert_to_tensor=True)
    scores = util.cos_sim(query_embedding, corpus_embeddings)[0]

    scored_items = sorted(
        zip(HISTORICAL_ITEMS, scores.tolist()),
        key=lambda pair: pair[1],
        reverse=True,
    )

    matches = [
        SemanticMatch(
            matched_description=item.description,
            supplier_name=item.supplier_name,
            manufacturer=item.manufacturer,
            similarity_score=round(score, 4),
        )
        for item, score in scored_items[:top_k]
        if score >= threshold
    ]

    logger.info(
        "Semantic retrieval | query_length=%d top_score=%.4f matches_returned=%d",
        len(query_description),
        max(scores.tolist(), default=0.0),
        len(matches),
    )

    return matches
