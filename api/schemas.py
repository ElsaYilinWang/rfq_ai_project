# api/schemas.py

# api/schemas.py

from pydantic import BaseModel
from typing import List, Optional


class ValidationWarning(BaseModel):
    line_item: int
    field: str
    message: str


class RFQParseResponse(BaseModel):
    rfq_number: str
    status: str
    items_processed: int
    warnings: List[ValidationWarning]
    next_action: str
    trace_id: Optional[str] = None


class LineItemResponse(BaseModel):
    line_item: int
    material_number: str
    description: str
    manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    uom: str
    quantity: int
    flags: List[str] = []


class RFQItemsResponse(BaseModel):
    rfq_number: str
    items: List[LineItemResponse]