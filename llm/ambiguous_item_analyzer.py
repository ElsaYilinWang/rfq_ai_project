# llm/ambiguous_item_analyzer.py

"""
Mock-based ambiguous RFQ item analyzer, v0.

This is NOT a real LLM call. It's a small rule-based stand-in that
returns the same *shape* of response a real LLM call would eventually
need to produce (see llm/schemas.py), so the rest of the workflow
(validation, routing to human review) can be built and tested before
any real API integration exists.

Guardrail: human_review_required is ALWAYS True in this module.
Nothing here has been validated against a real supplier catalog or
knowledge base, so nothing it produces should ever be trusted enough
to skip human review — regardless of stated confidence. A real LLM
integration later must preserve this: confidence is a hint about how
worth-checking a suggestion is, never a substitute for review.
"""

import re

from llm.schemas import AmbiguousItemAnalysis

# A tiny mock "known manufacturers" list, standing in for a real
# supplier/manufacturer catalog. Matching against a real catalog (or
# embeddings) is future work — this is intentionally simple.
KNOWN_MANUFACTURERS = ["ABB", "Siemens", "Schneider Electric", "Honeywell", "Emerson"]

# Loose heuristic for a "part-number-shaped" token, e.g. "CB-10A".
# Not a real parts-catalog lookup — just a shape check.
PART_NUMBER_PATTERN = re.compile(r"\b[A-Z]{1,5}-?\d{2,6}[A-Z]?\b")


def analyze_ambiguous_item(description: str) -> AmbiguousItemAnalysis:
    possible_manufacturer = next(
        (m for m in KNOWN_MANUFACTURERS if m.lower() in description.lower()),
        None,
    )

    match = PART_NUMBER_PATTERN.search(description)
    possible_part_number = match.group(0) if match else None

    if possible_manufacturer and possible_part_number:
        confidence = "medium"
        reason = (
            f"The description contains {possible_manufacturer} and a "
            f"part-like code, but supplier review is still recommended."
        )
    elif possible_manufacturer or possible_part_number:
        confidence = "low"
        reason = (
            "The description contains a partial match (manufacturer or "
            "part-like code, but not both), so this suggestion is weak."
        )
    else:
        confidence = "low"
        reason = "The description does not contain a clear manufacturer or part number."

    return AmbiguousItemAnalysis(
        possible_manufacturer=possible_manufacturer,
        possible_part_number=possible_part_number,
        confidence=confidence,
        reason=reason,
        # Always True in this mock version — see module docstring.
        human_review_required=True,
    )