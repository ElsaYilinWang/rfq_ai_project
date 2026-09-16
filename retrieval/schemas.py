# retrieval/schemas.py

"""
Schemas for the Phase 14 semantic supplier retrieval layer.

Two models, matching the same split used everywhere else in this
project: one for the data being searched over (HistoricalItem), one
for a search result (SemanticMatch).
"""

from typing import Optional

from pydantic import BaseModel


class HistoricalItem(BaseModel):
    """One row of the mock historical corpus being searched over."""
    description: str
    supplier_name: str
    manufacturer: Optional[str] = None


class SemanticMatch(BaseModel):
    """
    One retrieval result: a historical item plus how well it matched
    the query, expressed as cosine similarity (0.0-1.0).
    """
    matched_description: str
    supplier_name: str
    manufacturer: Optional[str] = None
    similarity_score: float

    # Unconditional, same pattern as every other AI-derived result in
    # this project. A high similarity score is evidence, not
    # certainty — nothing here is trusted enough to skip a human.
    human_review_required: bool = True
