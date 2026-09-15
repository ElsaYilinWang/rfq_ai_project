# tests/test_agent_endpoint.py

"""
Tests for the Phase 13c API route that exposes the agent loop
(GET /rfqs/sample/items/{line_item}/agent-search).

Same mocked-Anthropic approach as test_supplier_agent.py — these tests
must never make a real, paid API call. What's being checked here is
the ROUTE WIRING: does line_item lookup work, does an out-of-range
item return 404 before any model call is attempted, and does a
successful agent run actually serialize through FastAPI's
response_model validation (a real failure mode distinct from anything
test_supplier_agent.py already covers, since that file never goes
through FastAPI's response serialization layer at all).
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, block_id, name, input_):
        self.id = block_id
        self.name = name
        self.input = input_


class FakeUsage:
    def __init__(self, input_tokens=100, output_tokens=50):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeResponse:
    def __init__(self, content, stop_reason, usage=None):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage or FakeUsage()


def fake_client(responses):
    c = MagicMock()
    c.messages.create.side_effect = responses
    return c


def test_agent_search_endpoint_returns_valid_result_for_known_item():
    """
    Line item 1 in the sample RFQ has a known manufacturer (ABB)
    already. One search call plus a final answer is enough to reach
    a valid, schema-conformant response.
    """
    responses = [
        FakeResponse(
            content=[FakeToolUseBlock(
                "t1", "search_suppliers_by_manufacturer", {"manufacturer": "ABB"}
            )],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[FakeTextBlock(
                '{"summary": "Found ABB suppliers.", '
                '"manufacturer_identified": "ABB", '
                '"supplier_candidates_found": true, '
                '"recommended_next_step": "draft and route for review"}'
            )],
            stop_reason="end_turn",
        ),
    ]

    with patch("agent.supplier_agent.Anthropic", return_value=fake_client(responses)):
        response = client.get("/rfqs/sample/items/1/agent-search")

    assert response.status_code == 200
    data = response.json()
    assert data["manufacturer_identified"] == "ABB"
    assert data["human_review_required"] is True
    assert data["trace_id"] is not None
    assert data["trace_id"].startswith("agent_")
    assert data["completed"] is True


def test_agent_search_endpoint_404_for_out_of_range_item():
    """
    No mocking here — line_item 99 must be rejected before the route
    ever attempts to build a task or call the model at all.
    """
    response = client.get("/rfqs/sample/items/99/agent-search")
    assert response.status_code == 404


def test_agent_search_endpoint_404_for_zero_is_out_of_range():
    """
    line_item is 1-indexed; 0 must also 404, not be silently treated
    as item 1 or crash on a negative-index lookup.
    """
    response = client.get("/rfqs/sample/items/0/agent-search")
    assert response.status_code == 404
