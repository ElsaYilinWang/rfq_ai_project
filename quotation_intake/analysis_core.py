# quotation_intake/analysis_core.py

"""
Provider-neutral core for structuring a supplier quotation's raw
extracted text into SupplierQuotation. Same split as
llm/analysis_core.py vs. llm/claude_analyzer.py: this file has no
Anthropic import at all, so the prompt and parsing logic stay
testable and swappable independent of which model actually calls it.

parse_and_validate returns (SupplierQuotation, outcome) rather than
just the quotation, so the caller (claude_extractor.py) can build an
accurate llm.schemas.CallMetrics.outcome -- "invalid_json" vs.
"schema_invalid" are genuinely different failure modes worth telling
apart in evaluation/reporting, matching the four-value outcome
convention llm/schemas.py's CallMetrics already established
(success | call_failed | invalid_json | schema_invalid). This module
still never imports CallMetrics itself -- it stays provider-neutral
and has no idea metrics even exist, same separation as
llm/analysis_core.py.
"""

import json
import logging
import re
from typing import Tuple

from pydantic import ValidationError

from quotation_intake.schemas import SupplierQuotation

logger = logging.getLogger("quotation_intake")

PROMPT_VERSION = "v0"

_SCHEMA_FIELDS = """
- supplier_name: who the quotation is from
- rfq_reference: what RFQ/request this is replying to, if stated
- part_number: the quoted part/article number
- manufacturer: the quoted item's manufacturer/brand
- description: the quoted item's description
- quantity: the quoted quantity, as a plain number, exactly as stated
- uom: the unit of measure exactly as stated (e.g. "EA", "SET") -- do NOT convert between units
- minimum_order_quantity: minimum order quantity, if stated
- unit_price: price per unit, as a plain number (no currency symbol)
- total_price: total price, as a plain number (no currency symbol)
- currency: the currency code or symbol used (e.g. "USD", "EUR")
- discount: any discount mentioned, as free text, exactly as stated (do not compute a value)
- delivery_terms: delivery/incoterms, e.g. "EXW Dublin"
- shipping_cost: shipping cost, as a plain number, if stated separately
- customs_charge: customs charge, as a plain number, if stated separately
- quotation_validity: how long the quote is valid, if stated, as free text
- certificates: a list of objects, each with:
    - name: the certificate's name, exactly as stated
    - status: "included", "available_at_cost", "not_available", or null if unclear
    - additional_cost: a plain number if a cost is specifically stated for this certificate, else null
"""


def build_prompt(raw_text: str) -> str:
    return (
        "You are extracting structured data from a supplier's quotation document. "
        "Extract ONLY the following fields, exactly as stated in the text below. "
        "Never guess, compute, or infer a value that is not actually stated. "
        "Leave any field null if the document does not state it.\n\n"
        f"Fields to extract:\n{_SCHEMA_FIELDS}\n\n"
        "Respond with ONLY a single JSON object matching these fields -- no "
        "preamble, no markdown code fences, no explanation.\n\n"
        "Document text:\n"
        "---\n"
        f"{raw_text}\n"
        "---"
    )


def fallback(reason: str) -> SupplierQuotation:
    """
    Same unconditional-safety pattern as llm/analysis_core.py's
    fallback(): a failure to extract or parse NEVER raises up to the
    caller. Returns a schema-valid SupplierQuotation with every field
    null, a flag explaining what happened, and human_review_required
    True (already the schema's default -- set explicitly here so this
    function's intent is visible without reading the schema too).
    """
    return SupplierQuotation(
        flags=[f"Automated extraction failed: {reason}"],
        human_review_required=True,
    )


def parse_and_validate(raw_response: str) -> Tuple[SupplierQuotation, str]:
    """
    Fence-stripping / parse / validate / fallback -- same shape as
    llm/analysis_core.py's parse_and_validate, applied to
    SupplierQuotation instead of AmbiguousItemAnalysis.

    Returns (quotation, outcome), where outcome is one of
    "success" | "invalid_json" | "schema_invalid" -- the same
    granularity llm.schemas.CallMetrics.outcome documents. (The
    fourth documented value, "call_failed", covers the API call
    itself failing before any response exists to parse -- that's
    claude_extractor.py's concern, not this function's.)
    """
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(
            "Quotation JSON parsing failed | prompt_version=%s error=%s raw_response=%r",
            PROMPT_VERSION, exc, raw_response,
        )
        return fallback("could not parse model response as JSON"), "invalid_json"

    try:
        quotation = SupplierQuotation(**payload)
    except ValidationError as exc:
        logger.error(
            "Quotation schema validation failed | prompt_version=%s error=%s payload=%r",
            PROMPT_VERSION, exc, payload,
        )
        return fallback("model response did not match the expected schema"), "schema_invalid"

    logger.info(
        "Quotation extracted | prompt_version=%s supplier=%s part_number=%s",
        PROMPT_VERSION, quotation.supplier_name, quotation.part_number,
    )
    return quotation, "success"
