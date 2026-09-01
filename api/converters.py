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

from api.schemas import (
    RFQParseResponse,
    ValidationWarning,
    LineItemResponse,
    RFQItemsResponse,
)

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


def parsed_rfq_to_items_response(parsed_rfq: ParsedRFQ) -> RFQItemsResponse:
    """
    Convert the internal parser ParsedRFQ dataclass into a line-item-level
    API response.

    Internal model:
        LineItem -> material_number, long_description, uom, quantity,
        sourcing_identifiers (List[SourcingIdentifier]), flags

    API model:
        LineItemResponse -> line_item, material_number, description,
        manufacturer, part_number, uom, quantity, flags

    Key transformation:
        An item can carry MULTIPLE sourcing_identifiers internally.
        The API flattens this to a single manufacturer/part_number pair,
        taking the first identifier as "primary." Surfacing alternates
        is a candidate for a later phase.
    """

    item_responses: List[LineItemResponse] = []

    for index, item in enumerate(parsed_rfq.items, start=1):
        primary_identifier = (
            item.sourcing_identifiers[0] if item.sourcing_identifiers else None
        )

        item_responses.append(
            LineItemResponse(
                line_item=index,
                material_number=item.material_number,
                description=item.long_description,
                manufacturer=(
                    primary_identifier.manufacturer if primary_identifier else None
                ),
                part_number=(
                    primary_identifier.part_number if primary_identifier else None
                ),
                uom=item.uom,
                quantity=item.quantity,
                flags=item.flags,
            )
        )

    return RFQItemsResponse(
        rfq_number=parsed_rfq.metadata.rfq_number,
        items=item_responses,
    )