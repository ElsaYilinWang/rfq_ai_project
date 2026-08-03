# api/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from parser.schemas import (
    RFQMetadata,
    ParsedRFQ,
    LineItem,
    SourcingIdentifier,
)

from api.converters import parsed_rfq_to_api_response
from api.schemas import RFQParseResponse


app = FastAPI(title="RFQ AI Review API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/rfqs/sample", response_model=RFQParseResponse)
def get_sample_rfq():
    """
    Return a mock parsed RFQ response.

    This endpoint proves the API schema boundary before connecting
    the real Excel parser or file upload.
    """

    sample_parsed_rfq = ParsedRFQ(
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
                    SourcingIdentifier(
                        manufacturer="ABB",
                        part_number="CB-10A"
                    )
                ],
                flags=[],
            ),
            LineItem(
                material_number="MAT-002",
                long_description="Seal kit for heat exchanger",
                uom="EA",
                quantity=1,
                sourcing_identifiers=[],
                flags=[
                    "No manufacturer or part number extracted from description."
                ],
            ),
        ],
        overall_flags=[]
    )

    return parsed_rfq_to_api_response(
        parsed_rfq=sample_parsed_rfq,
        trace_id="demo_run_001"
    )