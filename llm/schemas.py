# llm/schemas.py

"""
Structured output schema for the Phase 10 ambiguous RFQ item analyzer.

This mirrors what a real LLM call would eventually need to return —
constrained to fixed fields and a fixed set of confidence levels via
Pydantic, rather than open-ended free text. This is the actual point
of "structured output": the caller can rely on the shape of the
response without needing to parse or guess at natural language.
"""

from typing import Optional, Literal

from pydantic import BaseModel


class AmbiguousItemAnalysis(BaseModel):
    possible_manufacturer: Optional[str] = None
    possible_part_number: Optional[str] = None
    confidence: Literal["low", "medium", "high"]
    reason: str
    human_review_required: bool