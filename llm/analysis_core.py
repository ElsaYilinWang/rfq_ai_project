# llm/analysis_core.py

"""
Provider-neutral core of the ambiguous RFQ item analysis (Phase 12a).

Everything in this file is independent of which LLM provider is used:
the prompt, the fence-stripping, the JSON parsing, the human-review
override, the schema validation, and the safe fallback. Swapping
Anthropic for another provider means writing a new thin adapter that
calls build_prompt() and parse_and_validate() — this file does not
change.

The test for that claim is mechanical: this module must never import
`anthropic` (or any other provider SDK).

Guardrail, unchanged since the mock analyzer: human_review_required is
forced to True inside parse_and_validate, regardless of what the model
returned. The model is not permitted to mark its own output as
trustworthy.
"""

import json
import logging
import re

from pydantic import ValidationError

from llm.schemas import AmbiguousItemAnalysis

logger = logging.getLogger(__name__)

# Bump this whenever the prompt text below changes, so log lines can be
# traced back to the exact prompt that produced them.
PROMPT_VERSION = "v2"

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


def build_prompt(description: str) -> str:
    """The full prompt for one item. Provider adapters send this verbatim."""
    return PROMPT_TEMPLATE.format(description=description)


def fallback(reason: str) -> AmbiguousItemAnalysis:
    """A safe result used whenever the model call or parse fails."""
    return AmbiguousItemAnalysis(
        possible_manufacturer=None,
        possible_part_number=None,
        confidence="low",
        reason=reason,
        human_review_required=True,
    )


def parse_and_validate(raw_response: str) -> AmbiguousItemAnalysis:
    """
    Turn a raw model response string into a validated
    AmbiguousItemAnalysis, or a safe fallback if it can't be.

    Handles, in order:
      1. markdown code fences (forbidden by the prompt, but LLMs
         produce them intermittently — stripping is cheap insurance)
      2. JSON parsing
      3. the unconditional human-review override
      4. Pydantic schema validation (e.g. rejects invalid confidence)
    """

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
        return fallback("Analysis unavailable: the model returned invalid JSON.")

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
        return fallback(
            "Analysis unavailable: the model response did not match the expected schema."
        )

    logger.info(
        "Analysis validated | prompt_version=%s confidence=%s manufacturer=%s",
        PROMPT_VERSION, analysis.confidence, analysis.possible_manufacturer,
    )
    return analysis
