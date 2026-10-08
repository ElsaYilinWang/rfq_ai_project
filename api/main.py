# api/main.py

import os
import tempfile
import logging
import uuid
from functools import lru_cache


from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
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
    build_supplier_candidates_response,
)
from api.schemas import RFQParseResponse, RFQItemsResponse, SupplierCandidatesResponse, QuotationExtractionResponse
from quotation_intake.claude_extractor import extract_quotation_with_claude
from quotation_intake.docling_extractor import extract_raw_text

from llm.claude_analyzer import get_analyzer
from agent.supplier_agent import run_supplier_search_agent
from agent.schemas import AgentSupplierSearchResult
from agent.checkpointing import make_sqlite_checkpointer
from agent.supplier_graph import ReviewDecision
from agent.supplier_review import (
    ReviewNotPending,
    ReviewRecord,
    ReviewRunOutcome,
    get_review_record,
    resume_supplier_review,
    start_supplier_review,
)

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
    Return supplier candidates for each line item of the sample RFQ.

    Items with a known manufacturer get a (still mock) historical
    match. Items with no known manufacturer are searched via Phase
    14's real semantic retrieval against the item's raw description —
    see build_supplier_candidates_response for what happens when
    nothing scores above the similarity threshold.
    """
    return build_supplier_candidates_response(build_sample_parsed_rfq())


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
        quantity=item.quantity,
        uom=item.uom,
    )


# ---------------------------------------------------------------------
# Human review of drafted emails (Phase 18b)
#
# Approval only RECORDS a decision. Nothing here sends anything: there is
# no send step anywhere in the agent, the graph, or these routes. There is
# also no authentication yet, so anyone who can reach this API can record
# a decision -- fine for a local demo, not for exposure (see the README's
# limitations).
# ---------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_review_checkpointer():
    """
    One durable SQLite checkpointer for the whole process, created on
    first use. REVIEW_DB_PATH chooses the file. In Docker or Kubernetes
    mount storage that outlives the container at that path, or paused
    reviews disappear with it. Run ONE replica: the lock that makes the
    shared connection safe lives inside this process.

    Tests replace this dependency, so they never touch a real file.
    """
    return make_sqlite_checkpointer(os.getenv("REVIEW_DB_PATH", "data/reviews.sqlite"))


@app.post(
    "/rfqs/sample/items/{line_item}/review",
    response_model=ReviewRunOutcome,
)
def start_sample_item_review(
    line_item: int, checkpointer=Depends(get_review_checkpointer)
):
    """
    Run the agent on one line item; if it drafts an email, the run
    PAUSES for a human (status "awaiting_approval") and this response
    carries what the reviewer must see. Same cost caveat as agent-search:
    a real, paid Sonnet run.
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
    return start_supplier_review(
        item_description=item.long_description,
        material_number=item.material_number,
        known_manufacturer=(
            primary_identifier.manufacturer if primary_identifier else None
        ),
        known_part_number=(
            primary_identifier.part_number if primary_identifier else None
        ),
        quantity=item.quantity,
        uom=item.uom,
        checkpointer=checkpointer,
    )


@app.get("/reviews/{trace_id}", response_model=ReviewRecord)
def get_review(trace_id: str, checkpointer=Depends(get_review_checkpointer)):
    """What is saved about a run: waiting, decided (with the note), or not
    needing review. Works after a restart."""
    record = get_review_record(trace_id, checkpointer=checkpointer)
    if record is None:
        raise HTTPException(status_code=404, detail=f"no run with trace_id {trace_id!r}")
    return record


@app.post("/reviews/{trace_id}/decision", response_model=ReviewRunOutcome)
def decide_review(
    trace_id: str,
    decision: ReviewDecision,
    checkpointer=Depends(get_review_checkpointer),
):
    """
    Approve, or reject with a note (a rejection without a note is a 422
    and leaves the run waiting). Unknown run: 404. A run that is not
    waiting (already decided, never needed review, or incomplete): 409.
    """
    record = get_review_record(trace_id, checkpointer=checkpointer)
    if record is None:
        raise HTTPException(status_code=404, detail=f"no run with trace_id {trace_id!r}")
    if record.state != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"run {trace_id!r} is not waiting for a decision (state: {record.state})",
        )
    try:
        return resume_supplier_review(
            trace_id, decision.decision, decision.note, checkpointer=checkpointer
        )
    except ReviewNotPending as exc:
        # Two decisions racing: the loser lands here.
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/rfqs/sample/quotations", response_model=QuotationExtractionResponse)
def upload_sample_rfq_quotation(file: UploadFile = File(...)):
    """
    Accepts a supplier's quotation document, extracts it with Docling,
    then structures it into SupplierQuotation with Claude.

    A genuinely unreadable file (Docling itself can't open it) is a
    422 -- broken input, not ambiguous content. A readable document
    Claude can't confidently structure still returns 200, with flags
    set and human_review_required True -- same degrade-gracefully
    pattern as every other AI-touched endpoint in this project.
    """
    trace_id = f"quotation_{uuid.uuid4().hex[:12]}"

    suffix = os.path.splitext(file.filename or "")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    try:
        raw_text = extract_raw_text(tmp_path)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not read document: {exc}",
        )
    finally:
        os.unlink(tmp_path)

    quotation, _metrics = extract_quotation_with_claude(raw_text, trace_id=trace_id)

    return QuotationExtractionResponse(quotation=quotation, trace_id=trace_id)