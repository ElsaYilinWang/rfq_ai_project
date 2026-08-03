# api/converters.py

"""
ParsedRFQ.metadata.rfq_number
→ API rfq_number

len(ParsedRFQ.items)
→ API items_processed

LineItem.flags
→ API warnings

ParsedRFQ.overall_flags
→ API warnings

warnings exist?
→ status = validation_warning
→ next_action = review_required

no warnings?
→ status = parsed_successfully
→ next_action = supplier_discovery_ready
"""

from typing import List

from api.schemas import RFQParseResponse, ValidationWarning
from parser.schemas import ParsedRFQ


def parsed_rfq_to_api_response(
    parsed_rfq: ParsedRFQ,
    trace_id: str | None = None
) -> RFQParseResponse:
    """
    Convert the internal parser ParsedRFQ dataclass into an API-facing response.

    Internal model:
        ParsedRFQ -> metadata, items, overall_flags

    API model:
        RFQParseResponse -> rfq_number, status, items_processed,
        warnings, next_action, trace_id

    This keeps internal workflow structures separate from the external API contract.
    """

    warnings: List[ValidationWarning] = []

    # Convert item-level flags into API validation warnings
    for index, item in enumerate(parsed_rfq.items, start=1):
        for flag in item.flags:
            warnings.append(
                ValidationWarning(
                    line_item=index,
                    field="line_item",
                    message=flag
                )
            )

        # Optional: create more specific warnings from missing important fields
        if not item.material_number:
            warnings.append(
                ValidationWarning(
                    line_item=index,
                    field="material_number",
                    message="Missing material number; human review may be required."
                )
            )

        if not item.long_description:
            warnings.append(
                ValidationWarning(
                    line_item=index,
                    field="long_description",
                    message="Missing long description; supplier discovery may be unreliable."
                )
            )

        if not item.sourcing_identifiers:
            warnings.append(
                ValidationWarning(
                    line_item=index,
                    field="sourcing_identifiers",
                    message="No manufacturer or part number extracted; human review required."
                )
            )

    # Convert overall RFQ-level flags into API warnings
    for flag in parsed_rfq.overall_flags:
        warnings.append(
            ValidationWarning(
                line_item=0,
                field="rfq",
                message=flag
            )
        )

    if warnings:
        status = "validation_warning"
        next_action = "review_required"
    else:
        status = "parsed_successfully"
        next_action = "supplier_discovery_ready"

    return RFQParseResponse(
        rfq_number=parsed_rfq.metadata.rfq_number,
        status=status,
        items_processed=len(parsed_rfq.items),
        warnings=warnings,
        next_action=next_action,
        trace_id=trace_id
    )