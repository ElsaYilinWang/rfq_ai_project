# tests/test_supplier_review.py

"""
Phase 18b tests: the human approval pause (agent/supplier_review.py and
the human_approval node in agent/supplier_graph.py).

No real API calls: the Anthropic client is a scripted fake, as in the
other agent tests. The real tool registry is used, so a "draft" here is
the real draft_supplier_email tool's real output.

Every test injects its own InMemorySaver. The module-level default
checkpointer is shared across a process, so tests must never use it.

Resume tests deliberately do NOT patch Anthropic: resuming has to work
with no model client at all, which is the structural guarantee that a
resume can never spend money.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from agent.supplier_graph import build_graph
from agent.supplier_review import (
    ReviewNotPending,
    get_pending_review,
    resume_supplier_review,
    start_supplier_review,
)
from retrieval.schemas import SemanticMatch


# ---------------------------------------------------------------------
# Scripted fakes
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


FINAL_JSON = (
    '{"summary": "Found 2 ABB suppliers and drafted an email.", '
    '"manufacturer_identified": "ABB", "supplier_candidates_found": true, '
    '"recommended_next_step": "review draft, then send manually"}'
)


def final():
    return FakeResponse([FakeTextBlock(FINAL_JSON)], "end_turn")


DRAFT_ARGS = {
    "supplier_name": "Mock ABB Supplier",
    "supplier_email": "mock.abb.supplier@example.com",
    "material_number": "MAT-001",
    "item_description": "ABB circuit breaker 10A",
    "quantity": 1,
    "uom": "EA",
    "manufacturer": "ABB",
    "part_number": "CB-10A",
}


def search():
    return tool_use("t1", "search_suppliers_by_manufacturer", {"manufacturer": "ABB"})


def draft():
    return tool_use("t2", "draft_supplier_email", DRAFT_ARGS)


def start(responses, trace_id="run-1", **kwargs):
    """Start a review run; returns (outcome, checkpointer, client)."""
    checkpointer = InMemorySaver()
    client = fake_client(responses)
    with patch("agent.supplier_review.Anthropic", return_value=client):
        outcome = start_supplier_review(
            item_description="ABB circuit breaker 10A", material_number="MAT-001",
            trace_id=trace_id, checkpointer=checkpointer, **kwargs,
        )
    return outcome, checkpointer, client


def paused_run(trace_id="run-1"):
    return start([search(), draft(), final()], trace_id=trace_id)


# ---------------------------------------------------------------------
# The pause
# ---------------------------------------------------------------------

def test_run_with_a_draft_pauses_and_shows_the_reviewer_the_draft():
    outcome, _, _ = paused_run()

    assert outcome.status == "awaiting_approval"
    assert outcome.result.completed is True
    request = outcome.review_request
    assert request["trace_id"] == "run-1"
    assert len(request["drafts"]) == 1
    assert request["drafts"][0]["to"] == "mock.abb.supplier@example.com"
    assert request["drafts"][0]["status"] == "draft_only_not_sent"
    assert request["summary"] == outcome.result.summary
    json.dumps(request)  # a reviewer UI needs it as plain JSON


def test_weak_semantic_matches_are_shown_to_the_reviewer():
    fake_match = SemanticMatch(
        matched_description="Flowserve mechanical seal kit", supplier_name="Mock Flowserve Supplier",
        manufacturer="Flowserve", similarity_score=0.57,
    )
    responses = [
        tool_use("t1", "search_suppliers_semantically", {"description": "Seal kit"}),
        draft(),
        final(),
    ]
    with patch("agent.tools.find_semantic_matches", return_value=[fake_match]):
        outcome, _, _ = start(responses)

    assert outcome.status == "awaiting_approval"
    assert outcome.review_request["semantic_matches"][0]["similarity_score"] == 0.57


def test_run_without_a_draft_does_not_pause():
    outcome, checkpointer, _ = start([search(), final()])

    assert outcome.status == "no_review_required"
    assert outcome.review_request is None
    assert get_pending_review("run-1", checkpointer=checkpointer) is None


def test_a_failed_draft_call_does_not_count_as_a_draft():
    bad_draft = tool_use("t2", "draft_supplier_email", {"supplier_name": "only this"})
    outcome, _, _ = start([search(), bad_draft, final()])

    assert outcome.status == "no_review_required"


def test_a_capped_run_never_pauses_even_if_it_drafted_something():
    responses = [draft() for _ in range(6)]
    outcome, checkpointer, _ = start(responses, max_iterations=2)

    assert outcome.status == "no_review_required"
    assert outcome.result.completed is False
    assert get_pending_review("run-1", checkpointer=checkpointer) is None


def test_trace_id_is_generated_when_missing_and_is_the_resume_handle():
    checkpointer = InMemorySaver()
    with patch("agent.supplier_review.Anthropic", return_value=fake_client([search(), draft(), final()])):
        outcome = start_supplier_review(
            item_description="ABB circuit breaker 10A", checkpointer=checkpointer
        )

    assert outcome.trace_id.startswith("agent_")
    resumed = resume_supplier_review(outcome.trace_id, "approve", checkpointer=checkpointer)
    assert resumed.status == "approved"


# ---------------------------------------------------------------------
# Resuming: approve and reject
# ---------------------------------------------------------------------

def test_approve_records_the_decision_without_any_model_client():
    outcome, checkpointer, client = paused_run()
    calls_before = client.messages.create.call_count

    # No Anthropic patch here: resume must not need (or build) a client.
    with patch("agent.supplier_review.Anthropic", side_effect=AssertionError("resume built a client")):
        resumed = resume_supplier_review("run-1", "approve", checkpointer=checkpointer)

    assert resumed.status == "approved"
    assert client.messages.create.call_count == calls_before


def test_approval_does_not_change_the_agents_result_or_clear_the_review_flag():
    outcome, checkpointer, _ = paused_run()
    resumed = resume_supplier_review("run-1", "approve", checkpointer=checkpointer)

    assert resumed.result == outcome.result
    assert resumed.result.human_review_required is True


def test_reject_with_a_note_is_recorded():
    _, checkpointer, _ = paused_run()
    resumed = resume_supplier_review(
        "run-1", "reject", note="  wrong supplier for this material  ", checkpointer=checkpointer
    )

    assert resumed.status == "rejected"
    assert resumed.decision_note == "wrong supplier for this material"


@pytest.mark.parametrize("note", [None, "", "   "])
def test_reject_without_a_real_note_is_refused_and_the_run_stays_pending(note):
    _, checkpointer, _ = paused_run()

    with pytest.raises(ValidationError):
        resume_supplier_review("run-1", "reject", note=note, checkpointer=checkpointer)

    # untouched: still waiting, and a valid answer still works
    assert get_pending_review("run-1", checkpointer=checkpointer) is not None
    assert resume_supplier_review("run-1", "approve", checkpointer=checkpointer).status == "approved"


def test_an_unknown_decision_word_is_refused():
    _, checkpointer, _ = paused_run()
    with pytest.raises(ValidationError):
        resume_supplier_review("run-1", "maybe", checkpointer=checkpointer)


def test_deciding_twice_raises_instead_of_rerunning_anything():
    _, checkpointer, client = paused_run()
    resume_supplier_review("run-1", "approve", checkpointer=checkpointer)
    calls_before = client.messages.create.call_count

    with pytest.raises(ReviewNotPending):
        resume_supplier_review("run-1", "approve", checkpointer=checkpointer)
    assert client.messages.create.call_count == calls_before


def test_resuming_an_unknown_run_raises():
    with pytest.raises(ReviewNotPending):
        resume_supplier_review("never-started", "approve", checkpointer=InMemorySaver())


def test_resuming_a_run_that_needed_no_review_raises():
    _, checkpointer, _ = start([search(), final()])
    with pytest.raises(ReviewNotPending):
        resume_supplier_review("run-1", "approve", checkpointer=checkpointer)


# ---------------------------------------------------------------------
# Coming back later, and run identity
# ---------------------------------------------------------------------

def test_a_reviewer_can_fetch_the_pending_request_later():
    outcome, checkpointer, _ = paused_run()

    assert get_pending_review("run-1", checkpointer=checkpointer) == outcome.review_request
    resume_supplier_review("run-1", "approve", checkpointer=checkpointer)
    assert get_pending_review("run-1", checkpointer=checkpointer) is None
    assert get_pending_review("never-started", checkpointer=checkpointer) is None


def test_reusing_a_trace_id_is_refused_and_the_first_run_is_unharmed():
    _, checkpointer, _ = paused_run()

    with patch("agent.supplier_review.Anthropic", return_value=fake_client([final()])):
        with pytest.raises(ValueError, match="already has a saved run"):
            start_supplier_review(
                item_description="another item", trace_id="run-1", checkpointer=checkpointer
            )

    assert get_pending_review("run-1", checkpointer=checkpointer) is not None


def test_the_decision_is_logged_with_the_trace_id(caplog):
    _, checkpointer, _ = paused_run(trace_id="audit-me")
    with caplog.at_level(logging.INFO, logger="agent"):
        resume_supplier_review("audit-me", "reject", note="not this supplier", checkpointer=checkpointer)

    line = next(r.getMessage() for r in caplog.records if "Human review decision" in r.getMessage())
    assert "trace_id=audit-me" in line and "decision=reject" in line


# ---------------------------------------------------------------------
# No way to send
# ---------------------------------------------------------------------

def test_the_review_graph_still_has_no_node_that_could_send_email():
    graph = build_graph(fake_client([]), tools=[], with_approval=True)
    nodes = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    assert nodes == {"call_model", "run_tool", "finalize", "capped", "human_approval"}
