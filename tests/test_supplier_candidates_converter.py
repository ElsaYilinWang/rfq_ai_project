# tests/test_supplier_candidates_converter.py

"""
Tests for build_supplier_candidates_response's branching logic
(Phase 14b), with find_semantic_matches MOCKED — these test the
WIRING (does the converter correctly turn a retrieval result, or the
absence of one, into the right API response), not retrieval quality
itself, which is already covered for real in
tests/test_semantic_retrieval.py.

This split matters: mocking here keeps these tests fast and
deterministic regardless of what the real embedding model happens to
return for any given description, while still proving the converter
handles both a real match AND a genuine "nothing found" correctly —
including the case this project cares most about getting right:
correct abstention must not silently disappear as "just no candidate,
who'd notice," it has to be a deliberately tested path.
"""

from unittest.mock import patch

from api.converters import build_supplier_candidates_response
from parser.schemas import LineItem, ParsedRFQ, RFQMetadata, SourcingIdentifier
from retrieval.schemas import SemanticMatch


def _make_parsed_rfq(items):
    return ParsedRFQ(
        metadata=RFQMetadata(
            source_file_path="mock.xlsm",
            internal_reference="INT-TEST",
            rfq_number="RFQ-TEST-001",
            client_contact="test@example.com",
            date="2026-01-01",
        ),
        items=items,
        overall_flags=[],
    )


def test_known_manufacturer_item_gets_historical_match_no_retrieval_call():
    """
    An item with a known manufacturer should never even reach
    semantic retrieval — deterministic lookup takes priority, and
    retrieval should not be called at all in this case.
    """
    parsed_rfq = _make_parsed_rfq([
        LineItem(
            material_number="MAT-001",
            long_description="ABB circuit breaker 10A",
            uom="EA",
            quantity=2,
            sourcing_identifiers=[
                SourcingIdentifier(manufacturer="ABB", part_number="CB-10A")
            ],
            flags=[],
        ),
    ])

    with patch("api.converters.find_semantic_matches") as mock_retrieval:
        result = build_supplier_candidates_response(parsed_rfq)
        mock_retrieval.assert_not_called()

    assert len(result.supplier_candidates) == 1
    candidate = result.supplier_candidates[0]
    assert candidate.manufacturer == "ABB"
    assert candidate.source == "historical_sql_match"
    assert candidate.human_review_required is False


def test_unknown_manufacturer_with_semantic_match_found():
    """
    No manufacturer known -> retrieval is called -> a match is found
    -> a semantic_fallback_candidate is built from the retrieval
    result, with the similarity score visible in the reason.
    """
    parsed_rfq = _make_parsed_rfq([
        LineItem(
            material_number="MAT-002",
            long_description="Seal kit for heat exchanger",
            uom="EA",
            quantity=1,
            sourcing_identifiers=[],
            flags=["No manufacturer or part number extracted from description."],
        ),
    ])

    fake_match = SemanticMatch(
        matched_description="Flowserve mechanical seal kit for centrifugal pump, standard duty",
        supplier_name="Mock Flowserve Supplier",
        manufacturer="Flowserve",
        similarity_score=0.62,
    )

    with patch(
        "api.converters.find_semantic_matches", return_value=[fake_match]
    ) as mock_retrieval:
        result = build_supplier_candidates_response(parsed_rfq)
        mock_retrieval.assert_called_once_with(
            "Seal kit for heat exchanger", top_k=1
        )

    assert len(result.supplier_candidates) == 1
    candidate = result.supplier_candidates[0]
    assert candidate.manufacturer == "Flowserve"
    assert candidate.supplier_name == "Mock Flowserve Supplier"
    assert candidate.source == "semantic_fallback_candidate"
    assert candidate.human_review_required is True
    assert "0.62" in candidate.reason


def test_unknown_manufacturer_with_no_semantic_match_produces_no_candidate():
    """
    The correct-abstention path. When retrieval finds nothing above
    threshold, NO candidate should be added for that item — an empty
    list is a valid, deliberate result here, not a bug. This is the
    single most important test in this file: it's easy to
    accidentally paper over "nothing found" with a fallback guess, and
    this test exists specifically to catch that regression.
    """
    parsed_rfq = _make_parsed_rfq([
        LineItem(
            material_number="MAT-002",
            long_description="Seal kit for heat exchanger",
            uom="EA",
            quantity=1,
            sourcing_identifiers=[],
            flags=["No manufacturer or part number extracted from description."],
        ),
    ])

    with patch("api.converters.find_semantic_matches", return_value=[]):
        result = build_supplier_candidates_response(parsed_rfq)

    assert result.supplier_candidates == []


def test_mixed_rfq_produces_one_candidate_per_resolvable_item():
    """
    A realistic multi-item RFQ: one known-manufacturer item, one
    ambiguous item that DOES find a semantic match. Exercises both
    branches together, matching the actual shape of the sample RFQ
    used elsewhere in this project.
    """
    parsed_rfq = _make_parsed_rfq([
        LineItem(
            material_number="MAT-001",
            long_description="ABB circuit breaker 10A",
            uom="EA",
            quantity=2,
            sourcing_identifiers=[
                SourcingIdentifier(manufacturer="ABB", part_number="CB-10A")
            ],
            flags=[],
        ),
        LineItem(
            material_number="MAT-002",
            long_description="Seal kit for heat exchanger",
            uom="EA",
            quantity=1,
            sourcing_identifiers=[],
            flags=["No manufacturer or part number extracted from description."],
        ),
    ])

    fake_match = SemanticMatch(
        matched_description="John Crane mechanical seal for centrifugal pump, high temperature service",
        supplier_name="Mock John Crane Supplier",
        manufacturer="John Crane",
        similarity_score=0.55,
    )

    with patch("api.converters.find_semantic_matches", return_value=[fake_match]):
        result = build_supplier_candidates_response(parsed_rfq)

    assert len(result.supplier_candidates) == 2
    sources = {c.source for c in result.supplier_candidates}
    assert sources == {"historical_sql_match", "semantic_fallback_candidate"}
