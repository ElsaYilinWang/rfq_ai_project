# tests/test_review_endpoints.py

"""
The three review routes in api/main.py:

    POST /rfqs/sample/items/{n}/review      start a run (pauses if it drafts)
    GET  /reviews/{trace_id}                what is saved about a run
    POST /reviews/{trace_id}/decision       approve, or reject with a note

The model is a scripted fake and every test gets its own checkpointer by
replacing the get_review_checkpointer dependency, so nothing here spends
money or touches a real file (except where a test deliberately uses a
temp-folder SQLite file to prove durability through the HTTP layer).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from agent.checkpointing import make_sqlite_checkpointer
from api.main import app, get_review_checkpointer

client = TestClient(app)


# ---------------------------------------------------------------------
# Scripted fakes (self-contained)
# ---------------------------------------------------------------------

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
    input_tokens = 100
    output_tokens = 50


class FakeResponse:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = FakeUsage()


def fake_client(responses):
    c = MagicMock()
    c.messages.create.side_effect = responses
    return c


def tool_use(block_id, name, input_):
    return FakeResponse([FakeToolUseBlock(block_id, name, input_)], "tool_use")


def search():
    return tool_use("t1", "search_suppliers_by_manufacturer", {"manufacturer": "ABB"})


def draft():
    return tool_use("t2", "draft_supplier_email", {
        "supplier_name": "Mock ABB Supplier", "supplier_email": "mock.abb.supplier@example.com",
        "material_number": "MAT-001", "item_description": "ABB circuit breaker 10A",
        "quantity": 2, "uom": "EA", "manufacturer": "ABB", "part_number": "CB-10A",
    })


def final():
    return FakeResponse([FakeTextBlock(
        '{"summary": "Found suppliers and drafted an email.", "manufacturer_identified": "ABB", '
        '"supplier_candidates_found": true, "recommended_next_step": "review draft, then send manually"}'
    )], "end_turn")


@pytest.fixture
def saver():
    s = InMemorySaver()
    app.dependency_overrides[get_review_checkpointer] = lambda: s
    yield s
    app.dependency_overrides.clear()


def start(item=1, responses=None):
    model = fake_client(responses or [search(), draft(), final()])
    with patch("agent.supplier_review.Anthropic", return_value=model):
        response = client.post(f"/rfqs/sample/items/{item}/review")
    return response, model


# ---------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------

def test_start_pauses_and_returns_what_the_reviewer_must_see(saver):
    response, model = start()
    body = response.json()

    assert response.status_code == 200
    assert body["status"] == "awaiting_approval"
    assert body["review_request"]["drafts"][0]["status"] == "draft_only_not_sent"
    assert body["trace_id"].startswith("agent_")
    # the route told the agent the RFQ quantity (item 1: 2 EA)
    first_message = model.messages.create.call_args_list[0].kwargs["messages"][0]["content"]
    assert "Required quantity: 2 EA" in first_message


def test_start_for_a_line_item_that_does_not_exist_is_a_404_and_runs_nothing(saver):
    with patch("agent.supplier_review.Anthropic", side_effect=AssertionError("agent was started")):
        response = client.post("/rfqs/sample/items/99/review")
    assert response.status_code == 404


def test_a_run_that_drafts_nothing_needs_no_review(saver):
    response, _ = start(responses=[search(), final()])
    assert response.json()["status"] == "no_review_required"

    trace_id = response.json()["trace_id"]
    decision = client.post(f"/reviews/{trace_id}/decision", json={"decision": "approve"})
    assert decision.status_code == 409


# ---------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------

def test_a_waiting_run_can_be_read_back(saver):
    started, _ = start()
    trace_id = started.json()["trace_id"]

    record = client.get(f"/reviews/{trace_id}").json()
    assert record["state"] == "pending"
    assert record["review_request"] == started.json()["review_request"]
    assert record["decision"] is None


def test_reading_an_unknown_run_is_a_404(saver):
    assert client.get("/reviews/never-started").status_code == 404


# ---------------------------------------------------------------------
# Decide
# ---------------------------------------------------------------------

def test_approve_is_recorded_and_readable_afterwards(saver):
    trace_id = start()[0].json()["trace_id"]

    response = client.post(f"/reviews/{trace_id}/decision", json={"decision": "approve"})
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["result"]["human_review_required"] is True

    record = client.get(f"/reviews/{trace_id}").json()
    assert record["state"] == "decided"
    assert record["decision"] == {"decision": "approve", "note": None}


def test_reject_with_a_note_is_recorded(saver):
    trace_id = start()[0].json()["trace_id"]

    response = client.post(
        f"/reviews/{trace_id}/decision",
        json={"decision": "reject", "note": "wrong quantity"},
    )
    assert response.json()["status"] == "rejected"
    assert response.json()["decision_note"] == "wrong quantity"


def test_reject_without_a_note_is_a_422_and_the_run_keeps_waiting(saver):
    trace_id = start()[0].json()["trace_id"]

    response = client.post(f"/reviews/{trace_id}/decision", json={"decision": "reject"})
    assert response.status_code == 422
    assert client.get(f"/reviews/{trace_id}").json()["state"] == "pending"


@pytest.mark.parametrize("body", [
    {"decision": "maybe"},
    {"decision": "approve", "approved_by": "someone"},   # unknown field
    {},
])
def test_malformed_decisions_are_a_422(saver, body):
    trace_id = start()[0].json()["trace_id"]
    assert client.post(f"/reviews/{trace_id}/decision", json=body).status_code == 422
    assert client.get(f"/reviews/{trace_id}").json()["state"] == "pending"


def test_deciding_twice_is_a_409(saver):
    trace_id = start()[0].json()["trace_id"]
    client.post(f"/reviews/{trace_id}/decision", json={"decision": "approve"})

    second = client.post(f"/reviews/{trace_id}/decision", json={"decision": "reject", "note": "changed my mind"})
    assert second.status_code == 409
    assert client.get(f"/reviews/{trace_id}").json()["decision"]["decision"] == "approve"


def test_deciding_an_unknown_run_is_a_404(saver):
    assert client.post("/reviews/never-started/decision", json={"decision": "approve"}).status_code == 404


# ---------------------------------------------------------------------
# Durability through the HTTP layer, and the default checkpointer
# ---------------------------------------------------------------------

def test_a_paused_review_survives_a_restart_through_the_api(tmp_path):
    path = str(tmp_path / "reviews.sqlite")
    first = make_sqlite_checkpointer(path)
    app.dependency_overrides[get_review_checkpointer] = lambda: first
    try:
        trace_id = start()[0].json()["trace_id"]

        first.conn.close()                                  # the "restart"
        second = make_sqlite_checkpointer(path)
        app.dependency_overrides[get_review_checkpointer] = lambda: second

        assert client.get(f"/reviews/{trace_id}").json()["state"] == "pending"
        response = client.post(f"/reviews/{trace_id}/decision", json={"decision": "approve"})
        assert response.json()["status"] == "approved"
    finally:
        app.dependency_overrides.clear()


def test_the_default_checkpointer_uses_review_db_path(tmp_path, monkeypatch):
    path = tmp_path / "somewhere" / "reviews.sqlite"
    monkeypatch.setenv("REVIEW_DB_PATH", str(path))
    get_review_checkpointer.cache_clear()
    try:
        get_review_checkpointer()
        assert path.exists()
    finally:
        get_review_checkpointer.cache_clear()
