# tests/test_ambiguous_item_analyzer.py

"""
Tests for the Phase 10 structured LLM output schema and mock analyzer.

Two things are being verified here, deliberately kept separate:

1. The mock analyzer produces sensible results for a few known inputs
   (llm/ambiguous_item_analyzer.py).
2. The schema itself actually enforces its constraints — an invalid
   confidence value is rejected, not silently accepted (llm/schemas.py).
   This is what makes it "structured output" rather than just a
   dictionary with the right keys by convention.
"""

import pytest
from pydantic import ValidationError

from llm.ambiguous_item_analyzer import analyze_ambiguous_item
from llm.schemas import AmbiguousItemAnalysis


def test_description_only_item_is_low_confidence_and_requires_review():
    result = analyze_ambiguous_item("Seal kit for heat exchanger")

    assert result.possible_manufacturer is None
    assert result.possible_part_number is None
    assert result.confidence == "low"
    assert result.human_review_required is True


def test_manufacturer_and_part_code_is_medium_confidence_but_still_requires_review():
    result = analyze_ambiguous_item("ABB circuit breaker CB-10A")

    assert result.possible_manufacturer == "ABB"
    assert result.possible_part_number == "CB-10A"
    assert result.confidence == "medium"
    # The guardrail: even the "best case" mock result still requires
    # human review. Medium confidence is not a green light.
    assert result.human_review_required is True


def test_partial_match_is_low_confidence():
    result = analyze_ambiguous_item("Siemens contactor, no part number visible")

    assert result.possible_manufacturer == "Siemens"
    assert result.possible_part_number is None
    assert result.confidence == "low"
    assert result.human_review_required is True


def test_schema_rejects_invalid_confidence_value():
    """
    Proves the schema itself enforces valid values — not just that the
    analyzer happens to behave correctly. A real LLM's output would be
    validated against this same schema, and this test is what would
    catch a real LLM returning something outside the allowed set.
    """
    with pytest.raises(ValidationError):
        AmbiguousItemAnalysis(
            confidence="pretty sure",
            reason="test",
            human_review_required=False,
        )