# tests/test_quotation_endpoint.py

"""
Tests for POST /rfqs/sample/quotations. Both extract_raw_text
(Docling) and extract_quotation_with_claude are mocked -- this file
tests the ROUTE's own logic (temp-file handling, the 422-vs-200
distinction, response shape), not Docling or Claude quality, which
are already covered for real elsewhere (the manual diagnostic runs,
quotation_intake's own design). Same split as
test_supplier_candidates_converter.py mocking find_semantic_matches.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from llm.schemas import CallMetrics
from quotation_intake.schemas import SupplierQuotation

client = TestClient(app)


def _dummy_upload():
    return {"file": ("quote.pdf", b"fake pdf bytes", "application/pdf")}


def test_quotation_upload_success():
    fake_quotation = SupplierQuotation(
        supplier_name="Mock Flowserve Supplier",
        part_number="FLS-MSK-200",
        manufacturer="Flowserve",
    )
    fake_metrics = CallMetrics(
        model="claude-haiku-4-5-20251001",
        prompt_version="v0",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.0003,
        latency_seconds=1.2,
        outcome="success",
    )

    with patch("api.main.extract_raw_text", return_value="fake raw text"):
        with patch(
            "api.main.extract_quotation_with_claude",
            return_value=(fake_quotation, fake_metrics),
        ):
            response = client.post("/rfqs/sample/quotations", files=_dummy_upload())

    assert response.status_code == 200
    data = response.json()
    assert data["quotation"]["supplier_name"] == "Mock Flowserve Supplier"
    assert data["quotation"]["part_number"] == "FLS-MSK-200"
    assert data["trace_id"].startswith("quotation_")


def test_quotation_upload_unreadable_file_returns_422_not_500():
    """
    Docling itself failing to open the file is broken input, not
    ambiguous content -- a real 422, never a crash.
    """
    with patch(
        "api.main.extract_raw_text",
        side_effect=RuntimeError("corrupt PDF structure"),
    ):
        response = client.post("/rfqs/sample/quotations", files=_dummy_upload())

    assert response.status_code == 422
    assert "corrupt PDF structure" in response.json()["detail"]


def test_quotation_upload_ambiguous_content_still_returns_200():
    """
    A readable document Claude can't confidently structure is NOT a
    422 -- the fallback quotation (already built by
    extract_quotation_with_claude internally) passes through as a
    normal 200, flagged and human_review_required, same
    degrade-gracefully pattern as every other AI-touched endpoint.
    """
    degraded_quotation = SupplierQuotation(
        flags=["Automated extraction failed: could not parse model response as JSON"],
        human_review_required=True,
    )
    fake_metrics = CallMetrics(
        model="claude-haiku-4-5-20251001",
        prompt_version="v0",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.0003,
        latency_seconds=1.2,
        outcome="invalid_json",
    )

    with patch("api.main.extract_raw_text", return_value="garbled text"):
        with patch(
            "api.main.extract_quotation_with_claude",
            return_value=(degraded_quotation, fake_metrics),
        ):
            response = client.post("/rfqs/sample/quotations", files=_dummy_upload())

    assert response.status_code == 200
    data = response.json()
    assert data["quotation"]["human_review_required"] is True
    assert len(data["quotation"]["flags"]) == 1
