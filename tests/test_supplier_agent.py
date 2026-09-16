# tests/test_supplier_agent.py

"""
Tests for the Phase 13b agent loop (agent/supplier_agent.py).

No real API calls — the Anthropic client is patched with a scripted
sequence of responses, same approach as test_claude_analyzer.py. What
matters here is the LOOP MECHANICS, not model quality: does it
dispatch tool calls correctly, recover from a bad tool call instead of
crashing, stop at the iteration cap instead of running forever, and
always produce a valid result with human_review_required=True no
matter which path it took.
"""

from unittest.mock import MagicMock, patch

from agent.supplier_agent import dispatch_tool, run_supplier_search_agent
from retrieval.schemas import SemanticMatch


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
    """A MagicMock Anthropic client that returns each response in
    sequence, one per call to messages.create."""
    client = MagicMock()
    client.messages.create.side_effect = responses
    return client


# ---------------------------------------------------------------------
# dispatch_tool — direct tests, no loop involved
# ---------------------------------------------------------------------

def test_dispatch_tool_unknown_name_returns_error_not_exception():
    result, is_error = dispatch_tool("this_tool_does_not_exist", {})
    assert is_error is True
    assert "Unknown tool" in result["error"]


def test_dispatch_tool_bad_arguments_returns_error_not_exception():
    result, is_error = dispatch_tool(
        "search_suppliers_by_manufacturer", {"wrong_field": "ABB"}
    )
    assert is_error is True
    assert "error" in result


def test_dispatch_tool_valid_call_succeeds():
    result, is_error = dispatch_tool(
        "search_suppliers_by_manufacturer", {"manufacturer": "ABB"}
    )
    assert is_error is False
    assert result["found"] is True


# ---------------------------------------------------------------------
# run_supplier_search_agent — full loop, mocked model responses
# ---------------------------------------------------------------------

def test_agent_happy_path_two_tool_calls_then_final_answer():
    """
    Simulates: analyze the description -> search using the identified
    manufacturer -> final answer. Proves the loop correctly chains
    multiple tool calls and produces a valid structured result.
    """
    responses = [
        FakeResponse(
            content=[FakeToolUseBlock("t1", "analyze_item_description",
                                       {"description": "ABB breaker, no part number"})],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[FakeToolUseBlock("t2", "search_suppliers_by_manufacturer",
                                       {"manufacturer": "ABB"})],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[FakeTextBlock(
                '{"summary": "Found 2 ABB suppliers.", '
                '"manufacturer_identified": "ABB", '
                '"supplier_candidates_found": true, '
                '"recommended_next_step": "draft and route for review"}'
            )],
            stop_reason="end_turn",
        ),
    ]

    with patch("agent.supplier_agent.Anthropic", return_value=fake_client(responses)):
        result = run_supplier_search_agent(
            item_description="ABB breaker, no part number",
            material_number="MAT-001",
            trace_id="test_trace_001",
        )

    assert result.completed is True
    assert result.iterations_used == 3
    assert len(result.tool_calls) == 2
    assert result.tool_calls[0].tool_name == "analyze_item_description"
    assert result.tool_calls[1].tool_name == "search_suppliers_by_manufacturer"
    assert result.manufacturer_identified == "ABB"
    assert result.supplier_candidates_found is True
    assert result.trace_id == "test_trace_001"
    assert result.human_review_required is True
    # 3 calls x (100 in * $2/M + 50 out * $10/M) = 3 x 0.00070
    assert result.total_cost_usd > 0


def test_agent_recovers_from_unknown_tool_call():
    """
    If the model requests a tool that doesn't exist, the loop must
    log an error tool_result and continue — not crash — giving the
    model a chance to recover on its next turn.
    """
    responses = [
        FakeResponse(
            content=[FakeToolUseBlock("t1", "send_email_to_supplier",
                                       {"to": "test@example.com"})],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[FakeTextBlock(
                '{"summary": "No send tool is available; unable to proceed.", '
                '"manufacturer_identified": null, '
                '"supplier_candidates_found": false, '
                '"recommended_next_step": "escalate to human sourcing"}'
            )],
            stop_reason="end_turn",
        ),
    ]

    with patch("agent.supplier_agent.Anthropic", return_value=fake_client(responses)):
        result = run_supplier_search_agent(
            item_description="test item", trace_id="test_trace_002"
        )

    assert result.completed is True
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].is_error is True
    assert result.human_review_required is True


def test_agent_stops_at_iteration_cap_instead_of_running_forever():
    """
    If the model keeps calling tools indefinitely (or a bug causes
    it to), the loop MUST stop at max_iterations rather than run
    forever. This is a safety property, not an edge case to shrug off.
    """
    # More tool_use responses than max_iterations allows.
    responses = [
        FakeResponse(
            content=[FakeToolUseBlock(f"t{i}", "search_suppliers_by_manufacturer",
                                       {"manufacturer": "ABB"})],
            stop_reason="tool_use",
        )
        for i in range(10)
    ]

    with patch("agent.supplier_agent.Anthropic", return_value=fake_client(responses)):
        result = run_supplier_search_agent(
            item_description="test item",
            trace_id="test_trace_003",
            max_iterations=3,
        )

    assert result.completed is False
    assert result.iterations_used == 3
    assert len(result.tool_calls) == 3
    assert result.human_review_required is True
    assert "escalate" in result.recommended_next_step.lower()


def test_agent_final_answer_malformed_json_falls_back_safely():
    """Mirrors test_claude_analyzer.py's malformed-JSON test, applied
    to the agent's final-answer parsing instead of the single-shot
    analyzer's."""
    responses = [
        FakeResponse(
            content=[FakeTextBlock("Sure, here you go: {not valid json")],
            stop_reason="end_turn",
        ),
    ]

    with patch("agent.supplier_agent.Anthropic", return_value=fake_client(responses)):
        result = run_supplier_search_agent(
            item_description="test item", trace_id="test_trace_004"
        )

    assert result.completed is True
    assert result.human_review_required is True
    assert result.recommended_next_step == "escalate to human sourcing"


def test_agent_never_calls_send_email_because_it_does_not_exist_as_a_tool():
    """
    Belt-and-suspenders check at the loop level (test_agent_tools.py
    already checks the registry directly): even if the model tries to
    call a send-email-shaped tool name, dispatch_tool cannot succeed,
    because no such tool is registered.
    """
    for forbidden_name in ("send_email", "send_supplier_email", "send"):
        result, is_error = dispatch_tool(forbidden_name, {"to": "x@example.com"})
        assert is_error is True


def test_agent_falls_back_to_semantic_search_when_manufacturer_search_empty():
    """
    Phase 14c: the full three-tool chain — analyze finds no
    manufacturer -> semantic search is tried as the fallback -> finds
    a match -> final answer. This proves the new tool is reachable
    through the ACTUAL dispatch mechanism inside the loop, not just
    callable in isolation (that part is already covered in
    test_agent_tools.py).
    """
    responses = [
        FakeResponse(
            content=[FakeToolUseBlock(
                "t1", "analyze_item_description",
                {"description": "Seal kit for heat exchanger"},
            )],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[FakeToolUseBlock(
                "t2", "search_suppliers_semantically",
                {"description": "Seal kit for heat exchanger"},
            )],
            stop_reason="tool_use",
        ),
        FakeResponse(
            content=[FakeTextBlock(
                '{"summary": "No manufacturer identified, but a semantic '
                'match was found with a modest similarity score.", '
                '"manufacturer_identified": null, '
                '"supplier_candidates_found": true, '
                '"recommended_next_step": "review semantic match with caution"}'
            )],
            stop_reason="end_turn",
        ),
    ]

    fake_match = SemanticMatch(
        matched_description="Flowserve mechanical seal kit for centrifugal pump, standard duty",
        supplier_name="Mock Flowserve Supplier",
        manufacturer="Flowserve",
        similarity_score=0.57,
    )

    with patch("agent.supplier_agent.Anthropic", return_value=fake_client(responses)):
        with patch("agent.tools.find_semantic_matches", return_value=[fake_match]):
            result = run_supplier_search_agent(
                item_description="Seal kit for heat exchanger",
                trace_id="test_trace_005",
            )

    assert result.completed is True
    assert len(result.tool_calls) == 2
    assert result.tool_calls[0].tool_name == "analyze_item_description"
    assert result.tool_calls[1].tool_name == "search_suppliers_semantically"
    assert result.tool_calls[1].is_error is False
    assert result.supplier_candidates_found is True
    assert result.manufacturer_identified is None
    assert result.human_review_required is True
