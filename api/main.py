# api/main.py

import logging
import uuid

from fastapi import FastAPI, HTTPException
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
from agent.supplier_agent import run_supplier_search_agent
from agent.schemas import AgentSupplierSearchResult

# Both the single-shot analyzer ("llm") and the Phase 13 agent loop
# ("agent") write one structured line per call to the SAME
# llm_calls.log file (in addition to the console). This is what makes
# a trace_id greppable end to end: an agent run's own iteration/tool
# lines AND any nested analyzer call it triggers (analyze_item_description
# calls the Phase 11 analyzer internally) all land in one file, in
# call order, under the same trace_id.
_llm_calls_handler = logging.FileHandler("llm_calls.log")
_llm_calls_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
)
for _logger_name in ("llm", "agent"):
    _logger = logging.getLogger(_logger_name)
    _logger.setLevel(logging.INFO)
    if not _logger.handlers:
        _logger.addHandler(_llm_calls_handler)

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
    """
    rfq_number = build_sample_parsed_rfq().metadata.rfq_number
    return build_mock_supplier_candidates_response(rfq_number)


@app.get(
    "/rfqs/sample/items/{line_item}/agent-search",
    response_model=AgentSupplierSearchResult,
)
def get_sample_rfq_item_agent_search(line_item: int):
    """
    Run the Phase 13 multi-step agent to find supplier candidates for
    one line item of the sample RFQ.

    line_item is 1-indexed, matching /rfqs/sample/items' numbering.

    IMPORTANT: unlike every other endpoint in this API, this one makes
    REAL, PAID Sonnet 5 API calls — typically 2-4 calls per request,
    a few cents total, several seconds of latency. It is not free or
    instant like the mock endpoints, and there is no rate limiting
    here; this is a portfolio/demo endpoint, not a production one.
    """
    parsed_rfq = build_sample_parsed_rfq()

    if line_item < 1 or line_item > len(parsed_rfq.items):
        raise HTTPException(
            status_code=404,
            detail=(
                f"line_item {line_item} does not exist; the sample RFQ "
                f"has {len(parsed_rfq.items)} items."
            ),
        )

    item = parsed_rfq.items[line_item - 1]
    primary_identifier = (
        item.sourcing_identifiers[0] if item.sourcing_identifiers else None
    )

    trace_id = f"agent_{uuid.uuid4().hex[:12]}"

    return run_supplier_search_agent(
        item_description=item.long_description,
        material_number=item.material_number,
        known_manufacturer=(
            primary_identifier.manufacturer if primary_identifier else None
        ),
        known_part_number=(
            primary_identifier.part_number if primary_identifier else None
        ),
        trace_id=trace_id,
    )
