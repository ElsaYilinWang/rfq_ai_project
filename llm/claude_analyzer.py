# llm/claude_analyzer.py

"""
Real Claude-backed ambiguous RFQ item analyzer (Phase 11b).

Same signature as llm.ambiguous_item_analyzer.analyze_ambiguous_item,
so either can be passed as the `analyzer` argument to
parsed_rfq_to_items_response. That interchangeability is the point:
the rest of the workflow never knows which one it got.

Differences from the archived previous_approach/main.py this is based on:
  - Output is parsed into a Pydantic model (AmbiguousItemAnalysis)
    instead of a raw dict validated by hand. Pydantic rejects an
    invalid confidence value; the old hand-rolled validate_rfq() only
    checked types.
  - PROMPT_VERSION is logged with every call. The archived run log
    showed results for a field (power_rating) that the final prompt
    didn't request, with no way to tell which prompt produced what.
  - On any failure (network error, bad JSON, schema violation) this
    falls back to a low-confidence, review-required result rather
    than raising. A parse failure should degrade the suggestion, not
    break the RFQ review endpoint.

Guardrail, unchanged from the mock: human_review_required is forced to
True regardless of what the model returns. The model is not permitted
to mark its own output as trustworthy.
"""

import json
import logging
import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from llm.schemas import AmbiguousItemAnalysis

logger = logging.getLogger(__name__)

load_dotenv()

# Bump this whenever the prompt text below changes, so log lines can be
# traced back to the exact prompt that produced them.
PROMPT_VERSION = "v2"

MODEL = "claude-haiku-4-5-20251001"

PROMPT_TEMPLATE = """You are a procurement data extraction assistant.

An RFQ line item was received with only a free-text description. No
manufacturer or part number could be extracted by deterministic parsing.

Description:
{description}

Return a JSON object with exactly these fields:
- possible_manufacturer: the manufacturer/brand name if identifiable, otherwise null
- possible_part_number: the part or model number if identifiable, otherwise null
- confidence: exactly one of "low", "medium", or "high"
- reason: one sentence explaining the basis for your answer

Rules:
- Return valid JSON only.
- Do not include any explanation or extra text outside the JSON.
- Do not wrap the JSON in markdown code fences.
- If a field cannot be determined from the description, use null.
- Do not guess a manufacturer from the product type alone. Generic
  descriptions such as "seal kit" or "bearing" do not imply a brand.
- Model or series designations that identify a specific product line,
  such as "S7-1200" or "ACS580", count as part numbers. Do not return
  null for possible_part_number merely because the code names a product
  family rather than a single orderable SKU.
- Never invent supplier names, prices, lead times, or certificates.
- Use "high" confidence only when both a manufacturer and a part
  number appear explicitly in the description."""


def _fallback(reason: str) -> AmbiguousItemAnalysis:
    """A safe result used whenever the model call or parse fails."""
    return AmbiguousItemAnalysis(
        possible_manufacturer=None,
        possible_part_number=None,
        confidence="low",
        reason=reason,
        human_review_required=True,
    )


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
                    "content": PROMPT_TEMPLATE.format(description=description),
                }
            ],
        )
        raw_response = message.content[0].text
    except Exception as exc:
        logger.error(
            "Model call failed | prompt_version=%s error=%s", PROMPT_VERSION, exc
        )
        return _fallback("Analysis unavailable: the model call failed.")

    # The prompt forbids code fences and the archived run log showed no
    # violations, but stripping them is three lines and removes a whole
    # class of failure that LLMs are known to produce intermittently.
    cleaned_response = raw_response.strip()
    if cleaned_response.startswith("```"):
        cleaned_response = re.sub(r"^```(?:json)?\s*", "", cleaned_response)
        cleaned_response = re.sub(r"\s*```$", "", cleaned_response)

    try:
        payload = json.loads(cleaned_response)
    except json.JSONDecodeError:
        logger.error(
            "JSON parsing failed | prompt_version=%s raw_response=%s",
            PROMPT_VERSION, raw_response,
        )
        return _fallback("Analysis unavailable: the model returned invalid JSON.")

    # The model does not get to decide whether its own output is
    # trustworthy — this is set here, not read from the response.
    payload["human_review_required"] = True

    try:
        analysis = AmbiguousItemAnalysis(**payload)
    except ValidationError as exc:
        logger.error(
            "Schema validation failed | prompt_version=%s errors=%s",
            PROMPT_VERSION, exc.errors(),
        )
        return _fallback(
            "Analysis unavailable: the model response did not match the expected schema."
        )

    logger.info(
        "Analysis successful | prompt_version=%s confidence=%s manufacturer=%s",
        PROMPT_VERSION, analysis.confidence, analysis.possible_manufacturer,
    )
    return analysis


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
