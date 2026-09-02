# api/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from parser.schemas import (
    RFQMetadata,
    ParsedRFQ,
    LineItem,
    SourcingIdentifier,
)

from api.converters import (
    parsed_rfq_to_api_response,
    parsed_rfq_to_items_response,
    build_mock_supplier_candidates_response,
)
from api.schemas import RFQParseResponse, RFQItemsResponse, SupplierCandidatesResponse

app = FastAPI(title="RFQ AI Review API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_sample_parsed_rfq() -> ParsedRFQ:
    """Builds the mock parsed RFQ shared by all /rfqs/sample* endpoints."""
    return ParsedRFQ(
        metadata=RFQMetadata(
            source_file_path="mock_data/sample_rfq.xlsm",
            internal_reference="INT-DEMO-001",
            rfq_number="RFQ-DEMO-001",
            client_contact="mock.client@example.com",
            date="2026-07-30",
        ),
        items=[
            LineItem(
                material_number="MAT-001",
                long_description="ABB circuit breaker 10A",
                uom="EA",
                quantity=2,
                sourcing_identifiers=[
                    SourcingIdentifier(manufacturer="ABB", part_number="CB-10A")
                ],
                flags=[],
            ),
            LineItem(
                material_number="MAT-002",
                long_description="Seal kit for heat exchanger",
                uom="EA",
                quantity=1,
                sourcing_identifiers=[],
                flags=["No manufacturer or part number extracted from description."],
            ),
        ],
        overall_flags=[]
    )


@app.get("/rfqs/sample", response_model=RFQParseResponse)
def get_sample_rfq():
    """
    Return a mock parsed RFQ response.

    This endpoint proves the API schema boundary before connecting
    the real Excel parser or file upload.
    """
    return parsed_rfq_to_api_response(
        parsed_rfq=build_sample_parsed_rfq(),
        trace_id="demo_run_001"
    )


@app.get("/rfqs/sample/items", response_model=RFQItemsResponse)
def get_sample_rfq_items():
    """
    Return line-item-level detail for the sample RFQ.
    """
    return parsed_rfq_to_items_response(build_sample_parsed_rfq())

@app.get(
    "/rfqs/sample/supplier-candidates",
    response_model=SupplierCandidatesResponse
)
def get_sample_rfq_supplier_candidates():
    """
    Return mock supplier candidates for the sample RFQ.

    Mock data only — a later phase connects this to the real SQLite
    supplier knowledge base via supplier_discovery.py, at which point
    only build_mock_supplier_candidates_response's replacement needs
    to change, not this route.
    """

    rfq_number = build_sample_parsed_rfq().metadata.rfq_number
    return build_mock_supplier_candidates_response(rfq_number)