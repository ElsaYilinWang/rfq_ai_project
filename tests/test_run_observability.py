# tests/test_run_observability.py

"""
Can a run be followed, and does a failure make noise?

  - ONE trace_id must appear on every log line of a run, from the first
    model call through the human's decision, including across a process
    restart (the id comes back out of the saved state, not out of memory)
  - the analyzer nested inside a tool call must be handed that same id
    (the Phase 13 bug where a nested call lost its trace_id)
  - a tool that raises must be recovered from AND leave a traceback in the
    log under the run's trace_id (before this, the traceback was logged
    nowhere and only the message text reached the model)

No real API calls: the model is a scripted fake.
"""

import logging
from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import InMemorySaver

from agent.checkpointing import make_sqlite_checkpointer
from agent.supplier_agent import run_supplier_search_agent
from agent.supplier_graph import run_supplier_search_graph
from agent.supplier_review import resume_supplier_review, start_supplier_review
from agent.tools import TOOL_REGISTRY


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


def agent_lines(caplog):
    return [r for r in caplog.records if r.name.startswith("agent")]


def start_run(saver, trace_id):
    with patch("agent.supplier_review.Anthropic", return_value=fake_client([search(), draft(), final()])):
        return start_supplier_review(
            item_description="ABB circuit breaker 10A", trace_id=trace_id,
            quantity=2, uom="EA", checkpointer=saver,
        )


# ---------------------------------------------------------------------
# One trace_id, start to finish
# ---------------------------------------------------------------------

def test_every_log_line_of_a_run_carries_its_trace_id_from_start_to_decision(caplog):
    caplog.set_level(logging.INFO, logger="agent")
    saver = InMemorySaver()
    start_run(saver, "trace-xyz")
    resume_supplier_review("trace-xyz", "approve", checkpointer=saver)

    messages = [r.getMessage() for r in agent_lines(caplog)]
    assert messages, "the run logged nothing at all"
    for line in messages:
        assert "trace_id=trace-xyz" in line, f"a log line lost the trace id: {line}"
    # the whole story is there, not just one kind of line
    assert any("Agent iteration" in m for m in messages)
    assert any("Tool call" in m for m in messages)
    assert any("Human review decision" in m for m in messages)


def test_the_trace_id_survives_a_restart(tmp_path, caplog):
    path = str(tmp_path / "reviews.sqlite")
    first = make_sqlite_checkpointer(path)
    started = start_run(first, trace_id="before-restart")
    first.conn.close()

    caplog.clear()
    caplog.set_level(logging.INFO, logger="agent")
    second = make_sqlite_checkpointer(path)
    resumed = resume_supplier_review("before-restart", "approve", checkpointer=second)

    assert resumed.trace_id == started.trace_id == "before-restart"
    decision = [r.getMessage() for r in agent_lines(caplog) if "Human review decision" in r.getMessage()]
    assert len(decision) == 1 and "trace_id=before-restart" in decision[0]


def test_the_analyzer_inside_a_tool_call_is_handed_the_same_trace_id():
    responses = [
        tool_use("t1", "analyze_item_description", {"description": "Seal kit for heat exchanger"}),
        final(),
    ]
    with patch("agent.tools.get_analyzer") as get_analyzer:
        get_analyzer.return_value.return_value.model_dump.return_value = {"possible_manufacturer": None}
        with patch("agent.supplier_graph.Anthropic", return_value=fake_client(responses)):
            run_supplier_search_graph(item_description="Seal kit for heat exchanger", trace_id="nested-1")

    get_analyzer.assert_called_once_with(trace_id="nested-1")


# ---------------------------------------------------------------------
# A tool that raises
# ---------------------------------------------------------------------

def _boom(args, trace_id=None):
    raise RuntimeError("db is down")


def _run_with_failing_tool(runner, patch_target):
    client = fake_client([search(), final()])
    with patch.dict(TOOL_REGISTRY["search_suppliers_by_manufacturer"], {"function": _boom}):
        with patch(patch_target, return_value=client):
            result = runner(item_description="ABB circuit breaker 10A", trace_id="boom-1")
    return result, client


def test_a_raising_tool_is_recovered_from_by_both_loops_identically():
    old, old_client = _run_with_failing_tool(run_supplier_search_agent, "agent.supplier_agent.Anthropic")
    new, new_client = _run_with_failing_tool(run_supplier_search_graph, "agent.supplier_graph.Anthropic")

    for result in (old, new):
        assert result.completed is True                        # the run carried on
        assert result.tool_calls[0].is_error is True
        assert "db is down" in result.tool_calls[0].tool_output["error"]
        assert result.human_review_required is True
    # the model was TOLD the call failed, so it could recover
    for client in (old_client, new_client):
        last = client.messages.create.call_args_list[1].kwargs["messages"][-1]
        assert last["content"][0]["is_error"] is True

    strip = lambda r: {**r.model_dump(exclude={"total_latency_seconds"}),
                       "tool_calls": [{k: v for k, v in c.items() if k != "latency_seconds"}
                                      for c in r.model_dump()["tool_calls"]]}
    assert strip(old) == strip(new)


def test_a_raising_tool_leaves_a_traceback_in_the_log_under_the_trace_id(caplog):
    caplog.set_level(logging.INFO, logger="agent")
    _run_with_failing_tool(run_supplier_search_graph, "agent.supplier_graph.Anthropic")

    errors = [r for r in agent_lines(caplog) if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "trace_id=boom-1" in errors[0].getMessage()
    assert errors[0].exc_info is not None and errors[0].exc_info[0] is RuntimeError
