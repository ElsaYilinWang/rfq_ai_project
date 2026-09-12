# llm/claude_analyzer.py

"""
Anthropic adapter for the ambiguous RFQ item analyzer (thinned in
Phase 12a).

Everything provider-neutral — the prompt, fence-stripping, JSON
parsing, the human-review override, schema validation, fallbacks —
lives in llm/analysis_core.py. This file is only the glue that:

  1. knows the Anthropic SDK and model name exist,
  2. sends the prompt the core built,
  3. hands the raw response text back to the core for validation,
  4. degrades to the core's safe fallback if the call itself fails.

Swapping providers means writing another adapter with this same shape
against analysis_core — nothing else in the project changes.

Same signature as llm.ambiguous_item_analyzer.analyze_ambiguous_item,
so either can be passed as the `analyzer` argument to
parsed_rfq_to_items_response. That interchangeability is the point:
the rest of the workflow never knows which one it got.
"""

import logging
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from llm.analysis_core import PROMPT_VERSION, build_prompt, fallback, parse_and_validate
from llm.schemas import AmbiguousItemAnalysis

logger = logging.getLogger(__name__)

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"


def analyze_ambiguous_item_with_claude(description: str) -> AmbiguousItemAnalysis:
    logger.info(
        "Analyzing ambiguous item | prompt_version=%s model=%s input_length=%d",
        PROMPT_VERSION, MODEL, len(description),
    )

    try:
        # Client construction is inside the try: a missing or malformed
        # API key raises here, and that should degrade to a fallback
        # suggestion like any other failure, not crash the endpoint.
        client = Anthropic()
        message = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": build_prompt(description),
                }
            ],
        )
        raw_response = message.content[0].text
    except Exception as exc:
        logger.error(
            "Model call failed | prompt_version=%s error=%s", PROMPT_VERSION, exc
        )
        return fallback("Analysis unavailable: the model call failed.")

    return parse_and_validate(raw_response)


def get_analyzer():
    """
    Returns the real Claude analyzer when an API key is configured,
    otherwise the deterministic mock.

    This is what lets the same route work locally with a key, in CI
    without one, and in tests without either — no branching at the
    call site.
    """
    if os.getenv("ANTHROPIC_API_KEY"):
        return analyze_ambiguous_item_with_claude

    from llm.ambiguous_item_analyzer import analyze_ambiguous_item
    logger.info("No ANTHROPIC_API_KEY found — falling back to the mock analyzer.")
    return analyze_ambiguous_item
