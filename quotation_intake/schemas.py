# quotation_intake/schemas.py

"""
Schema for supplier quotation ingestion (Phase 17 / Docling).

This is the inbound counterpart to the outbound RFQ pipeline:
parser/schemas.py captures what the CLIENT asked for; this captures
what the SUPPLIER quoted back. Same separation-of-concerns principle
as everywhere else in this project (parser/schemas.py vs.
parser/validators.py, llm/analysis_core.py vs. llm/claude_analyzer.py,
the whole reason api/converters.py exists): this file holds the RAW
EXTRACTED FACTS from a supplier's document ONLY. It does not compare
those facts against the original RFQ line, does not decide whether a
part number "matches," and does not do unit-of-measure conversion
(e.g. SET vs. EA). That comparison logic is a deliberately separate
module, built next, so each piece stays independently testable and
debuggable -- exactly the "one module does only one job" principle
behind this split.

Field naming decisions, made explicitly rather than by default:

- `description`, not `long_description`. Supplier quotations
  overwhelmingly use "description" as their own document's header;
  `long_description` is the RFQ/client-side (SAP Ariba) term. These
  are already reconciled at the API boundary today --
  api/converters.py's parsed_rfq_to_items_response does exactly
  `description=item.long_description` when building the
  client-facing LineItemResponse. This schema echoes that same
  outward-facing name.
- `part_number`, `manufacturer`, `uom` are reused verbatim from
  parser/schemas.py's SourcingIdentifier/LineItem and
  email_distribution/schemas.py's LineItemRow -- not renamed, so a
  later comparison step can line fields up by name with no
  translation layer.
- `flags: List[str]`, not a single `reason: str` (matching
  parser/schemas.py's LineItem, not api/schemas.py's
  SupplierCandidateResponse). A single RFQ line's quotation can have
  several independent problems at once -- a UOM mismatch AND a
  missing certificate AND a part-number concern -- and a list keeps
  each one separately queryable and actionable later, rather than
  forcing them into one concatenated sentence.
- `human_review_required: bool = True`, unconditional and
  defaulted True, matching every other AI/extraction-touched schema
  in this project (AmbiguousItemAnalysis, AgentSupplierSearchResult,
  SemanticMatch, SupplierCandidateResponse). A document-extraction
  schema is exactly the kind of place this pattern must not quietly
  be dropped.

What is DELIBERATELY left as a raw, unconverted fact rather than
pre-processed here:
- quantity + uom are captured exactly as stated on the document (e.g.
  quantity=500, uom="SET"). Whether 500 SET satisfies an RFQ line
  that asked for 1000 EA requires knowing the units-per-set for this
  specific part number -- that is domain knowledge the comparison
  step must resolve, or correctly flag and escalate to a human when
  it can't, not something this schema should silently assume.

VERSION NOTE (v0, deliberately incomplete -- to be upgraded step by
step, not all at once):
Certificate handling only covers what a document can actually state
about itself: a certificate is mentioned as included or available at
a cost, or the document says none are available. Two real scenarios
are explicitly OUT OF SCOPE for this version, because they are not
facts a document-parsing step could ever produce on its own -- they
come from a follow-up PROCESS, not from reading the document once:
  (1) the document says nothing about certificates, so someone
      calls or emails the supplier afterward and gets a verbal/email
      confirmation;
  (2) the supplier doesn't know and has to ask their factory, with
      no response ever received.
Both belong to a later, separate concern -- something like a
follow-up/correspondence log -- not to this schema. Captured here so
the gap is a documented, deliberate decision, not a silent omission
discovered later.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class CertificateMention(BaseModel):
    """
    One certificate as stated in the supplier's own document -- not a
    certificate confirmed through any later phone call or email (see
    the VERSION NOTE above). status is a free string for now (v0):
    "included", "available_at_cost", "not_available", or None if the
    document mentions a certificate by name but doesn't say which.
    """
    name: str
    status: Optional[str] = None
    additional_cost: Optional[float] = None


class SupplierQuotation(BaseModel):
    # extra="forbid" matches agent/tools.py's input models: without
    # it, Pydantic silently drops any field it doesn't recognize
    # rather than rejecting it, which would mean a genuinely wrong-
    # shaped model response could pass validation as an empty-but-
    # "valid" quotation -- confirmed by testing, not theoretical.
    model_config = ConfigDict(extra="forbid")

    # Which supplier this quotation came from, and what it's in reply to.
    supplier_name: Optional[str] = None
    rfq_reference: Optional[str] = None

    # Sourcing identifiers -- raw as extracted, not yet compared
    # against the original RFQ line's part number/manufacturer.
    part_number: Optional[str] = None
    manufacturer: Optional[str] = None
    description: Optional[str] = None

    # Quantity as a raw fact. See module docstring: unit-of-measure
    # conversion (e.g. SET vs. EA) is explicitly NOT done here.
    quantity: Optional[int] = None
    uom: Optional[str] = None
    minimum_order_quantity: Optional[int] = None

    # Pricing. Unit price and total price are both captured, rather
    # than assuming one can always be derived from the other --
    # discounts, minimum-order pricing tiers, and rounding mean they
    # don't always reconcile cleanly, and that's a comparison-step
    # concern, not something to resolve silently here.
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    currency: Optional[str] = None
    discount: Optional[str] = None  # free text: discounts are often
    # conditional ("5% on orders over 100 units") rather than a bare
    # percentage, so a string preserves the real statement rather
    # than forcing a number that might misrepresent it.

    # Commercial terms.
    delivery_terms: Optional[str] = None  # e.g. "EXW Dublin", "EXW China"
    shipping_cost: Optional[float] = None
    customs_charge: Optional[float] = None
    quotation_validity: Optional[str] = None  # optional by design --
    # confirmed some suppliers state this and some don't; free text
    # since it may be a date or a duration ("valid 30 days").

    # v0 -- see VERSION NOTE above for what this deliberately does
    # not yet cover.
    certificates: List[CertificateMention] = []

    # Same pattern as every other AI/extraction-touched schema in
    # this project -- see module docstring.
    flags: List[str] = []
    human_review_required: bool = True
