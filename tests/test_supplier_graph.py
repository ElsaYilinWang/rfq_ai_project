# tests/test_supplier_graph.py

"""
Phase 18a: proves agent/supplier_graph.py behaves like the old loop in
agent/supplier_agent.py.

Method: the SAME scripted model responses are fed to both
implementations (each gets its own fresh fake client), and the two
results are compared field by field -- summary, tool trace, iteration
count, cost, review flag, everything except wall-clock latency. This is
stronger than re-writing each scenario for the graph: if the old
behavior ever changes, the comparison fails instead of silently
drifting apart.

The second half tests what is NEW about the graph and has no old
equivalent: the recursion_limit backstop, plain-data state, and the
absence of any send path.

No real API calls. The Anthropic client is a scripted fake, same
approach as tests/test_supplier_agent.py (whose fakes are copied here
so this file stands alone).
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from langgraph.errors import GraphRecursionError

from agent.supplier_agent import run_supplier_search_agent
from agent.supplier_graph import (
    build_graph,
    build_initial_state,
    recursion_limit_for,
    run_supplier_search_graph,
)
from retrieval.schemas import SemanticMatch


# ---------------------------------------------------------------------
# Scripted fakes (same shapes as tests/test_supplier_agent.py)
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


class FakeOtherBlock:
    type = "some_other_block_type"


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
    client = MagicMock()
    client.messages.create.side_effect = responses
    return client


FINAL_JSON = (
    '{"summary": "Found 2 ABB suppliers.", "manufacturer_identified": "ABB", '
    '"supplier_candidates_found": true, '
    '"recommended_next_step": "draft and route for review"}'
)


def tool_use(block_id, name, input_):
    return FakeResponse([FakeToolUseBlock(block_id, name, input_)], "tool_use")


def final(text=FINAL_JSON):
    return FakeResponse([FakeTextBlock(text)], "end_turn")


FAKE_MATCH = SemanticMatch(
    matched_description="Flowserve mechanical seal kit for centrifugal pump",
    supplier_name="Mock Flowserve Supplier",
    manufacturer="Flowserve",
    similarity_score=0.57,
)


# ---------------------------------------------------------------------
# Parity machinery
# ---------------------------------------------------------------------

def run_both(make_responses, **kwargs):
    """Run the old loop and the graph on identical scripted responses."""
    old_client = fake_client(make_responses())
    new_client = fake_client(make_responses())
    with patch("agent.tools.find_semantic_matches", return_value=[FAKE_MATCH]):
        with patch("agent.supplier_agent.Anthropic", return_value=old_client):
            old = run_supplier_search_agent(**kwargs)
        with patch("agent.supplier_graph.Anthropic", return_value=new_client):
            new = run_supplier_search_graph(**kwargs)
    return old, new, old_client, new_client


def assert_same_outcome(old, new):
    """Everything must match except wall-clock latency."""
    o, n = old.model_dump(), new.model_dump()
    for d in (o, n):
        d.pop("total_latency_seconds")
        for call in d["tool_calls"]:
            call.pop("latency_seconds")
    assert o == n


def request_shape(client):
    """What was sent to the model on every call, minus the growing
    message list (compared separately)."""
    return [
        {k: v for k, v in call.kwargs.items() if k != "messages"}
        for call in client.messages.create.call_args_list
    ]


def message_shape(messages):
    """The conversation as the model saw it, normalised so old-style
    SDK-object blocks and new-style dict blocks compare equal."""
    shape = []
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            shape.append((m["role"], content))
            continue
        blocks = []
        for b in content:
            if isinstance(b, dict):
                blocks.append((b["type"], b.get("id") or b.get("tool_use_id"),
                               b.get("name"), b.get("content")))
            else:
                blocks.append((b.type, getattr(b, "id", None),
                               getattr(b, "name", None), None))
        shape.append((m["role"], tuple(blocks)))
    return shape


SCENARIOS = {
    "happy_path_analyze_then_search": (
        lambda: [
            tool_use("t1", "analyze_item_description", {"description": "ABB breaker"}),
            tool_use("t2", "search_suppliers_by_manufacturer", {"manufacturer": "ABB"}),
            final(),
        ],
        {"item_description": "ABB breaker, no part number",
         "material_number": "MAT-001", "trace_id": "parity_1"},
    ),
    "unknown_tool_then_recovery": (
        lambda: [
            tool_use("t1", "send_email_to_supplier", {"to": "x@example.com"}),
            final(),
        ],
        {"item_description": "test item", "trace_id": "parity_2"},
    ),
    "bad_tool_arguments": (
        lambda: [
            tool_use("t1", "search_suppliers_by_manufacturer", {"wrong_field": "ABB"}),
            final(),
        ],
        {"item_description": "test item", "trace_id": "parity_3"},
    ),
    "iteration_cap_reached": (
        lambda: [
            tool_use(f"t{i}", "search_suppliers_by_manufacturer", {"manufacturer": "ABB"})
            for i in range(10)
        ],
        {"item_description": "test item", "trace_id": "parity_4", "max_iterations": 3},
    ),
    "final_answer_on_last_allowed_iteration": (
        lambda: [
            tool_use("t1", "search_suppliers_by_manufacturer", {"manufacturer": "ABB"}),
            tool_use("t2", "search_suppliers_by_manufacturer", {"manufacturer": "ABB"}),
            final(),
        ],
        {"item_description": "test item", "trace_id": "parity_5", "max_iterations": 3},
    ),
    "malformed_json_final_answer": (
        lambda: [final("Sure, here you go: {not valid json")],
        {"item_description": "test item", "trace_id": "parity_6"},
    ),
    "fenced_json_final_answer": (
        lambda: [final("```json\n" + FINAL_JSON + "\n```")],
        {"item_description": "test item", "trace_id": "parity_7"},
    ),
    "no_text_block_in_final_turn": (
        lambda: [FakeResponse([FakeOtherBlock()], "end_turn")],
        {"item_description": "test item", "trace_id": "parity_8"},
    ),
    "answers_immediately_without_tools": (
        lambda: [final()],
        {"item_description": "test item", "trace_id": "parity_9"},
    ),
    "semantic_fallback_chain": (
        lambda: [
            tool_use("t1", "analyze_item_description", {"description": "Seal kit"}),
            tool_use("t2", "search_suppliers_semantically", {"description": "Seal kit"}),
            final(),
        ],
        {"item_description": "Seal kit for heat exchanger", "trace_id": "parity_10"},
    ),
}


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_graph_matches_old_agent(name):
    make_responses, kwargs = SCENARIOS[name]
    old, new, old_client, new_client = run_both(make_responses, **kwargs)

    assert_same_outcome(old, new)
    # The model must be asked the same thing, the same way, every time.
    assert request_shape(old_client) == request_shape(new_client)
    assert (
        old_client.messages.create.call_args_list[0].kwargs["messages"][0]
        == new_client.messages.create.call_args_list[0].kwargs["messages"][0]
    )


def test_graph_shows_the_model_the_same_conversation_as_the_old_agent():
    """The model's view of the conversation IS the behavior. Compare the
    final request's message trail on the multi-step happy path."""
    make_responses, kwargs = SCENARIOS["happy_path_analyze_then_search"]
    _, _, old_client, new_client = run_both(make_responses, **kwargs)

    old_last = old_client.messages.create.call_args_list[-1].kwargs["messages"]
    new_last = new_client.messages.create.call_args_list[-1].kwargs["messages"]
    assert message_shape(old_last) == message_shape(new_last)


# ---------------------------------------------------------------------
# What is new in the graph: the cap, the backstop, plain-data state
# ---------------------------------------------------------------------

@pytest.mark.parametrize("cap", [1, 2, 6, 40])
def test_cap_ends_with_reviewable_result_and_never_trips_the_framework_limit(cap):
    """The worst legitimate path is 2*cap + 1 steps. The recursion_limit
    backstop must sit above it for every cap, or the framework would
    kill a valid capped run and throw the result away."""
    responses = [
        tool_use(f"t{i}", "search_suppliers_by_manufacturer", {"manufacturer": "ABB"})
        for i in range(cap + 5)
    ]
    with patch("agent.supplier_graph.Anthropic", return_value=fake_client(responses)):
        result = run_supplier_search_graph(
            item_description="test item", max_iterations=cap
        )

    assert result.completed is False
    assert len(result.tool_calls) == cap
    assert result.iterations_used == cap
    assert result.human_review_required is True
    assert recursion_limit_for(cap) > 2 * cap + 1


def test_recursion_limit_backstop_stops_a_broken_cap_instead_of_running_on():
    """If the cap logic itself is ever broken, the explicit
    recursion_limit must stop the run after a handful of steps -- not
    after the framework default of roughly 10,000. It fails LOUDLY
    (an exception), and the scripted client proves it stopped early."""
    responses = [
        tool_use(f"t{i}", "search_suppliers_by_manufacturer", {"manufacturer": "ABB"})
        for i in range(100)
    ]
    client = fake_client(responses)
    with patch("agent.supplier_graph.route_after_tool", lambda state: "call_model"):
        with patch("agent.supplier_graph.Anthropic", return_value=client):
            with pytest.raises(GraphRecursionError):
                run_supplier_search_graph(item_description="test item", max_iterations=3)

    # limit = 2*3 + 5 = 11 steps -> at most 6 model calls, never 100.
    assert client.messages.create.call_count <= recursion_limit_for(3)


def test_state_is_plain_data_a_checkpointer_could_serialize():
    """Phase 18b will checkpoint this state. SDK objects would not
    serialize; dicts do. Run the graph directly and dump everything."""
    responses = [
        tool_use("t1", "search_suppliers_by_manufacturer", {"manufacturer": "ABB"}),
        final(),
    ]
    graph = build_graph(fake_client(responses), tools=[])
    final_state = graph.invoke(
        build_initial_state("ABB breaker", "MAT-001", None, None, "state_test", 6),
        {"recursion_limit": recursion_limit_for(6)},
    )

    json.dumps(final_state)  # raises if anything in state is not plain data
    assert final_state["result"]["completed"] is True


def test_graph_has_no_node_that_could_send_email():
    """Graph-level twin of test_registry_has_no_send_email_tool: the
    only nodes are the four that exist, and none of them sends."""
    graph = build_graph(fake_client([]), tools=[])
    nodes = set(graph.get_graph().nodes) - {"__start__", "__end__"}
    assert nodes == {"call_model", "run_tool", "finalize", "capped"}


def test_tool_use_stop_reason_without_a_tool_use_block_fails_loudly():
    """The one deliberate difference from the old loop: instead of a bare
    StopIteration, an explicit RuntimeError that says what happened."""
    responses = [FakeResponse([FakeTextBlock("no tool here")], "tool_use")]
    with patch("agent.supplier_graph.Anthropic", return_value=fake_client(responses)):
        with pytest.raises(RuntimeError, match="no tool_use block"):
            run_supplier_search_graph(item_description="test item")
