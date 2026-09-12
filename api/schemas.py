# api/schemas.py

from llm.schemas import AmbiguousItemAnalysis
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
    # Populated only when the parser found no sourcing identifiers AND
    # an analyzer was supplied. Always null otherwise, so existing
    # clients that ignore this field keep working unchanged.
    #
    # Note: this nests llm.schemas.AmbiguousItemAnalysis directly rather
    # than defining a separate API-side copy. The dataclass-to-Pydantic
    # converter pattern used elsewhere exists because the parser's
    # internal dataclasses aren't serializable API contracts.
    # AmbiguousItemAnalysis already is one, so duplicating it would add
    # a mapping layer with nothing to map.
    suggestion: Optional[AmbiguousItemAnalysis] = None

class RFQItemsResponse(BaseModel):
    rfq_number: str
    items: List[LineItemResponse]
    # Per-request trace id: every model call made while building this
    # response logs the same id, so one grep finds them all.
    trace_id: Optional[str] = None


class SupplierCandidateResponse(BaseModel):
    manufacturer: Optional[str] = None
    supplier_name: str
    source: str
    stale: Optional[bool] = None
    human_review_required: bool
    reason: str


class SupplierCandidatesResponse(BaseModel):
    rfq_number: str
    supplier_candidates: List[SupplierCandidateResponse]
    next_action: str