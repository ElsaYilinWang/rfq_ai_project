# tests/test_claude_analyzer.py

"""
Tests for the Phase 11b Claude-backed analyzer.

No real API calls are made — the Anthropic client is patched so every
code path can be exercised without a key, without cost, and without
network flakiness in CI. What's being tested here is not the model's
answer quality (that's what eval/ is for) but the code AROUND the
model: does invalid output get rejected, does a failure degrade
safely, and is the human-review guardrail actually unconditional.
"""

from unittest.mock import MagicMock, patch

from llm.claude_analyzer import analyze_ambiguous_item_with_claude


def fake_client(response_text: str) -> MagicMock:
    """Builds a stand-in Anthropic client returning a fixed response."""
    block = MagicMock()
    block.text = response_text
    message = MagicMock()
    message.content = [block]
    client = MagicMock()
    client.messages.create.return_value = message
    return client


def test_valid_response_is_parsed():
    payload = (
        '{"possible_manufacturer": "SKF", "possible_part_number": "6205", '
        '"confidence": "medium", "reason": "Brand and code present."}'
    )
    with patch("llm.claude_analyzer.Anthropic", return_value=fake_client(payload)):
        result = analyze_ambiguous_item_with_claude("SKF-6205 bearing")

    assert result.possible_manufacturer == "SKF"
    assert result.possible_part_number == "6205"
    assert result.confidence == "medium"


def test_model_cannot_disable_human_review():
    """
    The guardrail: even if the model explicitly returns
    human_review_required=false, the application overrides it. The
    model does not get to decide whether its own output is trusted.
    """
    payload = (
        '{"possible_manufacturer": "ABB", "possible_part_number": "CB-10A", '
        '"confidence": "high", "reason": "Both present.", '
        '"human_review_required": false}'
    )
    with patch("llm.claude_analyzer.Anthropic", return_value=fake_client(payload)):
        result = analyze_ambiguous_item_with_claude("ABB CB-10A")

    assert result.human_review_required is True


def test_markdown_fenced_json_is_still_parsed():
    payload = (
        '```json\n{"possible_manufacturer": "ABB", "possible_part_number": null, '
        '"confidence": "low", "reason": "Brand named."}\n```'
    )
    with patch("llm.claude_analyzer.Anthropic", return_value=fake_client(payload)):
        result = analyze_ambiguous_item_with_claude("ABB something")

    assert result.possible_manufacturer == "ABB"


def test_malformed_json_falls_back_safely():
    with patch(
        "llm.claude_analyzer.Anthropic",
        return_value=fake_client('Sure! {"possible_manufacturer": "ABB"'),
    ):
        result = analyze_ambiguous_item_with_claude("test")

    assert result.confidence == "low"
    assert result.human_review_required is True
    assert result.possible_manufacturer is None


def test_invalid_confidence_value_falls_back_safely():
    payload = (
        '{"possible_manufacturer": null, "possible_part_number": null, '
        '"confidence": "pretty sure", "reason": "x"}'
    )
    with patch("llm.claude_analyzer.Anthropic", return_value=fake_client(payload)):
        result = analyze_ambiguous_item_with_claude("test")

    assert result.confidence == "low"
    assert result.human_review_required is True


def test_api_failure_falls_back_safely():
    """
    A network error, bad API key, or any other client failure should
    degrade the suggestion — not raise and break the RFQ endpoint.
    """
    with patch("llm.claude_analyzer.Anthropic", side_effect=Exception("boom")):
        result = analyze_ambiguous_item_with_claude("test")

    assert result.confidence == "low"
    assert result.human_review_required is True
