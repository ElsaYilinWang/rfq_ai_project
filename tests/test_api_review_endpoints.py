# tests/test_api_review_endpoints.py

"""
API contract tests for the RFQ AI review endpoints.

These use FastAPI's TestClient to call the app in-process (no live
uvicorn server needed) and check status codes and JSON shape for each
endpoint. This protects the contract the frontend dashboard and
eval/run_eval.py both depend on — if a converter or schema change
breaks the shape of a response, these tests catch it directly instead
of only being noticed when the frontend renders "undefined."
"""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_sample_rfq_response_shape():
    response = client.get("/rfqs/sample")
    assert response.status_code == 200

    data = response.json()
    assert "rfq_number" in data
    assert "status" in data
    assert "items_processed" in data
    assert "warnings" in data
    assert "next_action" in data
    assert "trace_id" in data


def test_sample_rfq_items_response_shape():
    response = client.get("/rfqs/sample/items")
    assert response.status_code == 200

    data = response.json()
    assert "rfq_number" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0

    first_item = data["items"][0]
    assert "material_number" in first_item
    assert "description" in first_item
    assert "quantity" in first_item
    assert "uom" in first_item


def test_sample_rfq_supplier_candidates_response_shape():
    response = client.get("/rfqs/sample/supplier-candidates")
    assert response.status_code == 200

    data = response.json()
    assert "rfq_number" in data
    assert "supplier_candidates" in data
    assert isinstance(data["supplier_candidates"], list)
    assert len(data["supplier_candidates"]) > 0

    for candidate in data["supplier_candidates"]:
        assert "supplier_name" in candidate
        assert "source" in candidate
        assert "human_review_required" in candidate
        assert "reason" in candidate