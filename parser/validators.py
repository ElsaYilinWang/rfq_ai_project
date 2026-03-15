"""
RFQ Validator
==============
Validates parsed RFQ data and generates flags.
Hard errors raise exceptions immediately.
Item-level flags are appended to the item's flag list.
"""

from .schemas import LineItem, SourcingIdentifier
from typing import List


# ---------------------------------------------------------------
# Hard error validation — runs before parsing line items
# ---------------------------------------------------------------

def validate_hard_errors(rfq_number: str, items_count: int) -> None:
    """
    Validates RFQ-level hard errors.
    Raises ValueError immediately if any condition is met.
    """
    if not rfq_number or rfq_number.strip() == "":
        raise ValueError("Hard error: RFQ number is missing from cell A1")

    if items_count == 0:
        raise ValueError("Hard error: No line items found in SPREADSHEET sheet")


# ---------------------------------------------------------------
# Item-level flag validation — runs after parsing all items
# ---------------------------------------------------------------

def validate_sourcing_identifiers(item: LineItem) -> List[str]:
    """
    Validates sourcing identifiers for a single line item.
    Returns a list of flags. Empty list means no issues found.
    """
    flags = []

    # Check if PN/MODEL/MFR was entirely blank
    if not item.sourcing_identifiers:
        flags.append("missing_sourcing_identifier")
        return flags

    # Check each sourcing identifier entry
    for identifier in item.sourcing_identifiers:
        if not identifier.part_number or identifier.part_number.strip() == "":
            flags.append("missing_part_number")
        if not identifier.manufacturer or identifier.manufacturer.strip() == "":
            flags.append("missing_manufacturer")

    return flags


# ---------------------------------------------------------------
# RFQ-level overall flags — runs after all items are validated
# ---------------------------------------------------------------

def generate_overall_flags(items: List[LineItem]) -> List[str]:
    """
    Generates RFQ-level overall flags based on item-level flags.
    Returns a list of overall flags.
    """
    overall_flags = []

    flagged_items = [
        item.material_number
        for item in items
        if item.flags
    ]

    if flagged_items:
        overall_flags.append(
            f"items_need_review: {', '.join(flagged_items)}"
        )

    return overall_flags