# tests/test_agent_tools.py

"""
Tests for the Phase 13 agent tool functions (agent/tools.py).

These test the tools in isolation, with no Anthropic call involved —
the same "no real API calls, no cost, no network flakiness" approach
used for llm/ambiguous_item_analyzer.py's tests. What's being checked
here is that each tool behaves correctly given valid arguments, and
fails SAFELY (a structured result, not a crash) given bad ones — since
a tool that raises would break the whole agent loop mid-run.
"""

from agent.tools import (
    AnalyzeItemDescriptionInput,
    CheckStaleSuppliersInput,
    DraftSupplierEmailInput,
    SearchSuppliersInput,
    TOOL_REGISTRY,
    analyze_item_description,
    build_anthropic_tool_definitions,
    check_stale_suppliers,
    draft_supplier_email,
    search_suppliers_by_manufacturer,
)


def test_search_suppliers_finds_known_manufacturer():
    result = search_suppliers_by_manufacturer(
        SearchSuppliersInput(manufacturer="ABB")
    )
    assert result["found"] is True
    assert result["count"] == 2
    assert all(s["manufacturer"] == "ABB" for s in result["suppliers"])


def test_search_suppliers_unknown_manufacturer_returns_empty_not_error():
    result = search_suppliers_by_manufacturer(
        SearchSuppliersInput(manufacturer="Nonexistent Corp")
    )
    assert result["found"] is False
    assert result["count"] == 0
    assert result["suppliers"] == []


def test_check_stale_suppliers_finds_the_one_old_record():
    result = check_stale_suppliers(
        CheckStaleSuppliersInput(cutoff_date="2025-01-01")
    )
    assert result["stale_count"] == 1
    assert result["stale_suppliers"][0]["supplier_name"] == "Mock Siemens Supplier"
    assert result["cutoff_source"] == "provided_by_caller"


def test_check_stale_suppliers_default_uses_real_12_month_rule_not_a_guess():
    """
    Regression test for a real issue found in a live agent run: with
    no default, the model invented a plausible-looking but arbitrary
    cutoff date with no actual policy behind it. cutoff_date is now
    optional, and omitting it must apply the project's real 12-month
    staleness rule (computed in code) rather than leaving the model to
    reconstruct a business rule it was never given.
    """
    result = check_stale_suppliers(CheckStaleSuppliersInput())
    assert result["cutoff_source"] == "default_12_month_rule"
    # The old Siemens record (2023) must still be caught by the
    # computed default, same as an explicit cutoff would catch it.
    assert result["stale_count"] == 1
    assert result["stale_suppliers"][0]["supplier_name"] == "Mock Siemens Supplier"


def test_check_stale_suppliers_malformed_date_fails_safely():
    """
    A tool that raises on bad input would break the agent loop mid-run.
    It must return a structured error the model can see and react to.
    """
    result = check_stale_suppliers(
        CheckStaleSuppliersInput(cutoff_date="not-a-date")
    )
    assert "error" in result


def test_analyze_item_description_returns_valid_analysis_shape():
    result = analyze_item_description(
        AnalyzeItemDescriptionInput(description="Seal kit for heat exchanger")
    )
    assert result["confidence"] in ("low", "medium", "high")
    assert result["human_review_required"] is True


def test_draft_supplier_email_never_indicates_sent():
    """
    The single most important assertion in this test file: no matter
    what arguments are passed, this tool's own output must say the
    email was only drafted, never sent.
    """
    result = draft_supplier_email(
        DraftSupplierEmailInput(
            supplier_name="Mock ABB Supplier",
            supplier_email="mock.abb.supplier@example.com",
            material_number="MAT-001",
            item_description="ABB circuit breaker 10A",
            quantity=2,
            uom="EA",
            manufacturer="ABB",
            part_number="CB-10A",
        )
    )
    assert result["status"] == "draft_only_not_sent"
    assert "ABB CB-10A" in result["body"]


def test_draft_supplier_email_handles_missing_identification():
    """Drafting must work even when nothing is known yet — that's the
    exact situation an ambiguous item is in before analysis."""
    result = draft_supplier_email(
        DraftSupplierEmailInput(
            supplier_name="Unknown Supplier",
            supplier_email="unknown@example.com",
            material_number="MAT-002",
            item_description="Seal kit for heat exchanger",
            quantity=1,
            uom="EA",
        )
    )
    assert result["status"] == "draft_only_not_sent"
    assert "to be confirmed" in result["body"]


def test_draft_supplier_email_uses_partial_identification_when_available():
    """
    Regression test for a real bug found in a live agent run: a known
    manufacturer with no known part number was being discarded
    entirely (showing "to be confirmed" instead of "ABB"), because the
    original logic only used the identification fields if BOTH were
    present. A manufacturer the agent actually identified must appear
    in the draft even when the part number is still unknown.
    """
    result = draft_supplier_email(
        DraftSupplierEmailInput(
            supplier_name="Mock ABB Supplier",
            supplier_email="mock.abb.supplier@example.com",
            material_number="MAT-001",
            item_description="ABB circuit breaker 10A",
            quantity=1,
            uom="EA",
            manufacturer="ABB",
            # part_number deliberately omitted
        )
    )
    identification_line = next(
        line for line in result["body"].splitlines() if "Identification" in line
    )
    assert "ABB" in identification_line
    assert "to be confirmed" not in identification_line


def test_registry_has_no_send_email_tool():
    """
    The core safety property of this phase, checked mechanically
    rather than left as a comment someone could miss: there is no tool
    in the registry whose name suggests it can send anything.
    """
    tool_names = set(TOOL_REGISTRY.keys())
    forbidden = {"send_email", "send_supplier_email", "send"}
    assert tool_names.isdisjoint(forbidden)
    assert "draft_supplier_email" in tool_names


def test_anthropic_tool_definitions_are_well_formed():
    definitions = build_anthropic_tool_definitions()
    assert len(definitions) == len(TOOL_REGISTRY)
    for tool_def in definitions:
        assert "name" in tool_def
        assert "description" in tool_def
        assert tool_def["strict"] is True
        assert tool_def["input_schema"]["type"] == "object"
        assert "title" not in tool_def["input_schema"]
