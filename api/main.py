# api/main.py
import logging
import uuid
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

from llm.claude_analyzer import get_analyzer

# All llm.* loggers write one structured line per model call to
# llm_calls.log (in addition to the console). This is the greppable
# record that lets a trace_id shown in the dashboard be followed to
# the exact model call, its tokens, cost, latency, and outcome.
_llm_logger = logging.getLogger("llm")
_llm_logger.setLevel(logging.INFO)
if not _llm_logger.handlers:
    _handler = logging.FileHandler("llm_calls.log")
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    _llm_logger.addHandler(_handler)

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

    Items where the parser found no manufacturer or part number are
    passed to the analyzer, which attaches a `suggestion` for the
    reviewer. get_analyzer() returns the real Claude-backed analyzer
    when ANTHROPIC_API_KEY is configured and the deterministic mock
    otherwise, so this route works with or without a key.
    """
    trace_id = f"items_{uuid.uuid4().hex[:12]}"
    return parsed_rfq_to_items_response(
        build_sample_parsed_rfq(),
        analyzer=get_analyzer(trace_id=trace_id),
        trace_id=trace_id,
    )

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