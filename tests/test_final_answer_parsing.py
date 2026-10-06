# tests/test_final_answer_parsing.py

"""
Regression tests for agent/supplier_agent.py's _parse_final_answer.

A live old-vs-graph comparison run showed the model sometimes writes a
sentence or two BEFORE the JSON object despite the prompt asking for
only JSON. The old parser handled a code fence only at the very start,
so it discarded a correct answer and reported supplier_candidates_found
=False. The texts below are modeled on the two real failures.
"""

from agent.supplier_agent import _parse_final_answer

BODY = (
    '{"summary": "Found two ABB suppliers.", "manufacturer_identified": "ABB", '
    '"supplier_candidates_found": true, '
    '"recommended_next_step": "draft and route for review"}'
)


def test_prose_before_fenced_json_is_recovered():
    text = "Found two ABB suppliers, both recent.\n\n```json\n" + BODY + "\n```"
    result = _parse_final_answer(text, trace_id="t")
    assert result.manufacturer_identified == "ABB"
    assert result.supplier_candidates_found is True


def test_prose_before_bare_json_is_recovered():
    text = "The staleness result is unrelated to this item.\n\n" + BODY
    result = _parse_final_answer(text, trace_id="t")
    assert result.manufacturer_identified == "ABB"
    assert result.supplier_candidates_found is True


def test_prose_after_json_is_recovered():
    result = _parse_final_answer(BODY + "\n\nLet me know if you need anything else.")
    assert result.supplier_candidates_found is True


def test_clean_json_and_leading_fence_still_parse():
    assert _parse_final_answer(BODY).manufacturer_identified == "ABB"
    assert _parse_final_answer("```json\n" + BODY + "\n```").manufacturer_identified == "ABB"


def test_recovery_still_validates_the_schema():
    """Pulling a JSON object out of prose must not accept the wrong
    object: one missing required fields still falls back safely."""
    text = 'Here is the data: {"unrelated": "object", "count": 3}'
    result = _parse_final_answer(text)
    assert result.summary == "The agent did not return a valid final answer."
    assert result.supplier_candidates_found is False


def test_text_with_no_json_at_all_falls_back_safely():
    result = _parse_final_answer("I could not find anything useful, sorry.")
    assert result.recommended_next_step == "escalate to human sourcing"
    assert result.supplier_candidates_found is False
