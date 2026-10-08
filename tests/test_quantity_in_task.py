# tests/test_quantity_in_task.py

"""
The agent must be told the RFQ quantity.

Found in a live review run: the task message held only the description,
material number, manufacturer and part number, so the draft email tool
(which requires a number) got a made-up 1 EA while the RFQ asked for 2.
A reviewer reading only the summary could have approved the wrong
quantity. The task message is now built in ONE place
(agent.supplier_agent.build_task_message) and used by the old loop, the
graph, and the review entry point.
"""

from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import InMemorySaver

from agent.supplier_agent import SYSTEM_PROMPT, build_task_message, run_supplier_search_agent
from agent.supplier_graph import run_supplier_search_graph
from agent.supplier_review import start_supplier_review


class FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeUsage:
    input_tokens = 100
    output_tokens = 50


class FakeResponse:
    def __init__(self):
        self.content = [FakeTextBlock(
            '{"summary": "ok", "manufacturer_identified": null, '
            '"supplier_candidates_found": false, "recommended_next_step": "escalate"}'
        )]
        self.stop_reason = "end_turn"
        self.usage = FakeUsage()


def client_that_answers_immediately():
    client = MagicMock()
    client.messages.create.side_effect = [FakeResponse()]
    return client


def first_message_sent(client):
    return client.messages.create.call_args_list[0].kwargs["messages"][0]["content"]


def test_quantity_and_unit_appear_in_the_task_message():
    task = build_task_message("ABB circuit breaker 10A", quantity=2, uom="EA")
    assert "Required quantity: 2 EA" in task


def test_unknown_quantity_is_stated_as_unknown_not_omitted():
    assert "Required quantity: unknown" in build_task_message("ABB circuit breaker 10A")


def test_quantity_without_a_unit_has_no_trailing_junk():
    assert "Required quantity: 2\n" in build_task_message("x", quantity=2)


def test_the_old_loop_sends_the_quantity_to_the_model():
    client = client_that_answers_immediately()
    with patch("agent.supplier_agent.Anthropic", return_value=client):
        run_supplier_search_agent(item_description="ABB circuit breaker 10A", quantity=2, uom="EA")
    assert "Required quantity: 2 EA" in first_message_sent(client)


def test_the_graph_sends_the_same_message_as_the_old_loop():
    old_client, new_client = client_that_answers_immediately(), client_that_answers_immediately()
    kwargs = dict(item_description="ABB circuit breaker 10A", material_number="MAT-001",
                  known_manufacturer="ABB", known_part_number="CB-10A", quantity=2, uom="EA")
    with patch("agent.supplier_agent.Anthropic", return_value=old_client):
        run_supplier_search_agent(**kwargs)
    with patch("agent.supplier_graph.Anthropic", return_value=new_client):
        run_supplier_search_graph(**kwargs)

    assert first_message_sent(old_client) == first_message_sent(new_client)
    assert "Required quantity: 2 EA" in first_message_sent(new_client)


def test_the_review_entry_point_sends_the_quantity_too():
    client = client_that_answers_immediately()
    with patch("agent.supplier_review.Anthropic", return_value=client):
        start_supplier_review(
            item_description="ABB circuit breaker 10A", quantity=2, uom="EA",
            checkpointer=InMemorySaver(),
        )
    assert "Required quantity: 2 EA" in first_message_sent(client)


def test_the_prompt_forbids_presenting_a_guessed_quantity_as_fact():
    assert "Never present a guessed quantity as fact" in SYSTEM_PROMPT
    assert "placeholder" in SYSTEM_PROMPT
