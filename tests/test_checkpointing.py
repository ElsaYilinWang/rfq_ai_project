# tests/test_checkpointing.py

"""
Durability of paused reviews (agent/checkpointing.py).

A "restart" here means: drop every object, close the connection, and
build a brand-new saver from nothing but the file path. Anything that
only works because an object is still alive in memory would fail.
"""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from agent.checkpointing import make_sqlite_checkpointer
from agent.supplier_graph import build_graph
from agent.supplier_review import (
    ReviewNotPending,
    get_pending_review,
    resume_supplier_review,
    start_supplier_review,
)


# ---------------------------------------------------------------------
# Scripted fakes (self-contained: no imports from other test modules)
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
    client = MagicMock()
    client.messages.create.side_effect = responses
    return client


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


def start_run(saver, trace_id="run-1"):
    client = fake_client([search(), draft(), final()])
    with patch("agent.supplier_review.Anthropic", return_value=client):
        return start_supplier_review(
            item_description="ABB circuit breaker 10A", trace_id=trace_id,
            quantity=2, uom="EA", checkpointer=saver,
        )


def restart(saver, path):
    saver.conn.close()
    return make_sqlite_checkpointer(path)


def test_a_paused_review_survives_a_restart(tmp_path):
    path = str(tmp_path / "reviews.sqlite")
    saver = make_sqlite_checkpointer(path)
    outcome = start_run(saver)
    assert outcome.status == "awaiting_approval"

    saver = restart(saver, path)

    assert get_pending_review("run-1", checkpointer=saver) == outcome.review_request
    resumed = resume_supplier_review("run-1", "approve", checkpointer=saver)
    assert resumed.status == "approved"
    assert resumed.result == outcome.result


def test_a_recorded_decision_and_its_note_survive_a_restart(tmp_path):
    path = str(tmp_path / "reviews.sqlite")
    saver = make_sqlite_checkpointer(path)
    start_run(saver)
    resume_supplier_review("run-1", "reject", note="wrong supplier", checkpointer=saver)

    saver = restart(saver, path)

    graph = build_graph(MagicMock(), [], checkpointer=saver, with_approval=True)
    saved = graph.get_state({"configurable": {"thread_id": "run-1"}}).values
    assert saved["review"] == {"decision": "reject", "note": "wrong supplier"}


def test_deciding_twice_is_still_refused_after_a_restart(tmp_path):
    path = str(tmp_path / "reviews.sqlite")
    saver = make_sqlite_checkpointer(path)
    start_run(saver)
    resume_supplier_review("run-1", "approve", checkpointer=saver)

    saver = restart(saver, path)

    assert get_pending_review("run-1", checkpointer=saver) is None
    with pytest.raises(ReviewNotPending):
        resume_supplier_review("run-1", "approve", checkpointer=saver)


def test_one_saver_can_be_used_from_different_threads(tmp_path):
    """Started on one worker thread, decided on another, with the saver
    created on the main thread: what a server's thread pool does."""
    saver = make_sqlite_checkpointer(str(tmp_path / "reviews.sqlite"))

    with ThreadPoolExecutor(max_workers=1) as pool_a:
        outcome = pool_a.submit(start_run, saver).result()
    with ThreadPoolExecutor(max_workers=1) as pool_b:
        resumed = pool_b.submit(
            resume_supplier_review, "run-1", "approve", None, saver
        ).result()

    assert outcome.status == "awaiting_approval"
    assert resumed.status == "approved"


def test_the_connection_itself_allows_other_threads(tmp_path):
    """The one property the whole file exists for."""
    saver = make_sqlite_checkpointer(str(tmp_path / "reviews.sqlite"))
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(lambda: saver.conn.execute("select 1").fetchone()).result() == (1,)


def test_two_runs_started_at_the_same_time_do_not_interfere(tmp_path):
    saver = make_sqlite_checkpointer(str(tmp_path / "reviews.sqlite"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(start_run, saver, "run-a")
        second = pool.submit(start_run, saver, "run-b")
        outcomes = [first.result(), second.result()]

    assert {o.trace_id for o in outcomes} == {"run-a", "run-b"}
    assert all(o.status == "awaiting_approval" for o in outcomes)
    assert get_pending_review("run-a", checkpointer=saver)["trace_id"] == "run-a"
    assert get_pending_review("run-b", checkpointer=saver)["trace_id"] == "run-b"


def test_the_folder_is_created_if_missing(tmp_path):
    path = tmp_path / "does" / "not" / "exist" / "reviews.sqlite"
    make_sqlite_checkpointer(str(path))
    assert path.exists()
