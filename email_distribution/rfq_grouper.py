import json
from pathlib import Path
from typing import List, Optional
from email_distribution.schemas import MFRGroup, LineItemRow


def load_parsed_rfq(rfq_number: str, base_dir: Optional[Path] = None) -> dict:
    if base_dir is None:
        base_dir = Path(__file__).parent.parent / "output"
    path = base_dir / f"parsed_{rfq_number}.json"
    with open(path, "r") as f:
        return json.load(f)


def group_by_manufacturer(parsed_rfq: dict) -> List[MFRGroup]:
    """Group line items by manufacturer, returning a list of MFRGroup objects."""
    groups = {}  # key: manufacturer name, value: list of LineItemRow

    for item in parsed_rfq["items"]:
        for identifier in item["sourcing_identifiers"]:
            manufacturer = identifier.get("manufacturer")
            if not manufacturer:
                continue  # skip if no manufacturer found

            # convert raw dict to LineItemRow object
            line_item_row = LineItemRow(
                material_number=item["material_number"],
                long_description=item["long_description"],
                uom=item["uom"],
                quantity=item["quantity"],
                part_number=identifier.get("part_number")
            )

            # add to correct group
            if manufacturer not in groups:
                groups[manufacturer] = []
            groups[manufacturer].append(line_item_row)

    return [MFRGroup(manufacturer=k, line_items=v) for k, v in groups.items()]