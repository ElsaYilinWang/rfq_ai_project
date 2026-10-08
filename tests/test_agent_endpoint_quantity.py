# tests/test_agent_endpoint_quantity.py

"""
GET /rfqs/sample/items/{n}/agent-search must hand the agent the RFQ
line's quantity and unit. Without them the agent is never told how many
are needed and the draft email gets a made-up number (found in a live
review run). The agent itself is mocked: this tests only that the route
passes the right values through.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from agent.schemas import AgentSupplierSearchResult
from api.main import app

client = TestClient(app)


def _result():
    return AgentSupplierSearchResult(
        item_description="x", completed=True, summary="s", recommended_next_step="n",
        iterations_used=1, total_cost_usd=0.0, total_latency_seconds=0.0,
    )


def _call(line_item):
    with patch("api.main.run_supplier_search_agent", return_value=_result()) as mocked:
        response = client.get(f"/rfqs/sample/items/{line_item}/agent-search")
    return response, mocked.call_args.kwargs


def test_item_1_passes_quantity_2_ea_to_the_agent():
    response, kwargs = _call(1)
    assert response.status_code == 200
    assert kwargs["quantity"] == 2 and kwargs["uom"] == "EA"
    assert kwargs["known_manufacturer"] == "ABB"      # nothing else changed


def test_item_2_passes_its_own_quantity_not_item_1s():
    _, kwargs = _call(2)
    assert kwargs["quantity"] == 1 and kwargs["uom"] == "EA"
    assert kwargs["known_manufacturer"] is None


def test_a_line_item_that_does_not_exist_is_still_a_404():
    with patch("api.main.run_supplier_search_agent") as mocked:
        response = client.get("/rfqs/sample/items/99/agent-search")
    assert response.status_code == 404
    mocked.assert_not_called()
