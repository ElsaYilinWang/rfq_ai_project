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