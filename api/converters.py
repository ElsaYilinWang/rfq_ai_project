# api/converters.py
"""
Design note — why supplier candidates get a converter function too:

Phase 3\'s mock supplier-candidate data could have been built directly
inside the /rfqs/sample/supplier-candidates route in main.py -- that\'s
literally what the project plan for this week specifies, and it would
work fine for a demo.

Instead it lives here, following the same pattern as
parsed_rfq_to_api_response and parsed_rfq_to_items_response: main.py
stays a thin routing layer, and this file owns the actual data
transformation/decision logic.

The payoff shows up later, not now: when Phase 3/4 eventually connects
to the real SQLite supplier knowledge base (supplier_discovery.py)
instead of mock data, only the body of this function changes. The
route in main.py, and the response schema in schemas.py, stay exactly
as they are. If the mock data had been built inline in the route,
that swap would mean editing main.py and mixing routing logic with
business logic again.
"""


"""
ParsedRFQ.metadata.rfq_number
-> API rfq_number

len(ParsedRFQ.items)
-> API items_processed

LineItem.flags
-> API warnings

ParsedRFQ.overall_flags
-> API warnings

warnings exist?
-> status = validation_warning
-> next_action = review_required

no warnings?
-> status = parsed_successfully
-> next_action = supplier_discovery_ready
"""

from typing import List, Optional, Callable

from parser.schemas import ParsedRFQ
from llm.schemas import AmbiguousItemAnalysis

from api.schemas import (
    RFQParseResponse,
    ValidationWarning,
    LineItemResponse,
    RFQItemsResponse,
    SupplierCandidateResponse,
    SupplierCandidatesResponse,
)
from retrieval.semantic_search import find_semantic_matches



def parsed_rfq_to_api_response(
    parsed_rfq: ParsedRFQ,
    trace_id: str | None = None
) -> RFQParseResponse:
    warnings: List[ValidationWarning] = []

    for index, item in enumerate(parsed_rfq.items, start=1):
        for flag in item.flags:
            warnings.append(
                ValidationWarning(line_item=index, field="line_item", message=flag)
            )
        if not item.material_number:
            warnings.append(
                ValidationWarning(
                    line_item=index, field="material_number",
                    message="Missing material number; human review may be required."
                )
            )
        if not item.long_description:
            warnings.append(
                ValidationWarning(
                    line_item=index, field="long_description",
                    message="Missing long description; supplier discovery may be unreliable."
                )
            )
        if not item.sourcing_identifiers:
            warnings.append(
                ValidationWarning(
                    line_item=index, field="sourcing_identifiers",
                    message="No manufacturer or part number extracted; human review required."
                )
            )

    for flag in parsed_rfq.overall_flags:
        warnings.append(ValidationWarning(line_item=0, field="rfq", message=flag))

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


def parsed_rfq_to_items_response(
    parsed_rfq: ParsedRFQ,
    analyzer: Optional[Callable[[str], AmbiguousItemAnalysis]] = None,
    trace_id: Optional[str] = None,
) -> RFQItemsResponse:
    item_responses: List[LineItemResponse] = []

    for index, item in enumerate(parsed_rfq.items, start=1):
        primary_identifier = (
            item.sourcing_identifiers[0] if item.sourcing_identifiers else None
        )
        suggestion: Optional[AmbiguousItemAnalysis] = None
        if analyzer is not None and primary_identifier is None:
            suggestion = analyzer(item.long_description)

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
                suggestion=suggestion,
            )
        )

    return RFQItemsResponse(
        rfq_number=parsed_rfq.metadata.rfq_number,
        items=item_responses,
        trace_id=trace_id,
    )

def build_supplier_candidates_response(
    parsed_rfq: ParsedRFQ,
) -> SupplierCandidatesResponse:
    """
    Build supplier candidates for each line item of the RFQ.

    Renamed from build_mock_supplier_candidates_response — as of
    Phase 14b this is only PARTLY mock. The old version took just
    rfq_number and hardcoded exactly two candidates regardless of what
    was actually in the RFQ; it never had access to item data to
    search against at all.

    Per item:
      - A known manufacturer (from deterministic parsing) gets a
        historical match. This half is STILL mock/hardcoded — wiring
        it to the real SQLite supplier knowledge base
        (supplier_discovery.py) is separate, still-open work, not
        part of Phase 14. See the design note at the top of this file
        and the README's Future Improvements.
      - No known manufacturer means deterministic lookup has nothing
        to search on. This is where Phase 14's real semantic
        retrieval fires, searching the item's raw description against
        a small historical corpus (retrieval/corpus.py).

    If semantic retrieval finds nothing above its similarity
    threshold, NO candidate is added for that item. An empty result
    is the correct, honest outcome when nothing in the historical
    corpus is actually similar — not a bug to paper over by lowering
    the threshold or forcing a guess.
    """

    supplier_candidates: List[SupplierCandidateResponse] = []

    for item in parsed_rfq.items:
        primary_identifier = (
            item.sourcing_identifiers[0] if item.sourcing_identifiers else None
        )

        if primary_identifier is not None and primary_identifier.manufacturer:
            supplier_candidates.append(
                SupplierCandidateResponse(
                    manufacturer=primary_identifier.manufacturer,
                    supplier_name=f"Mock {primary_identifier.manufacturer} Supplier",
                    source="historical_sql_match",
                    stale=False,
                    human_review_required=False,
                    reason="Matched by manufacturer history",
                )
            )
            continue

        matches = find_semantic_matches(item.long_description, top_k=1)
        if not matches:
            # Correct abstention — nothing in the corpus is similar
            # enough to trust. No candidate for this item at all.
            continue

        top_match = matches[0]
        supplier_candidates.append(
            SupplierCandidateResponse(
                manufacturer=top_match.manufacturer,
                supplier_name=top_match.supplier_name,
                source="semantic_fallback_candidate",
                stale=None,
                human_review_required=True,
                reason=(
                    f"Semantic match (similarity={top_match.similarity_score:.2f}) "
                    f'to historical item: "{top_match.matched_description}"'
                ),
            )
        )

    return SupplierCandidatesResponse(
        rfq_number=parsed_rfq.metadata.rfq_number,
        supplier_candidates=supplier_candidates,
        next_action="review_supplier_candidates",
    )
