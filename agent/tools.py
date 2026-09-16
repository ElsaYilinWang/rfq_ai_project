# agent/tools.py

"""
Tool definitions for the Phase 13 supplier-search agent.

Four tools, deliberately chosen and deliberately NOT including a fifth:

  - search_suppliers_by_manufacturer  (DB read via SupplierRepository)
  - check_stale_suppliers             (DB read via SupplierRepository)
  - analyze_item_description          (delegates to the Phase 11 analyzer)
  - draft_supplier_email              (deterministic template, no LLM call)

There is NO send_email tool, and this is deliberate, not an oversight.
The project's principle since the first roadmap doc has been "email
sending must not be automatic." A tool that exists but is gated behind
an approval flag is still a code path from the model to a real send —
the flag could be wrong, forgotten, or bypassed by a future change.
Leaving the capability out of the tool list entirely means there is no
such path: the agent cannot send email, full stop, not "is told not
to." Drafting is safe to expose because generating text has no side
effect; sending is the only genuinely risky action in this workflow
and it stays outside the agent's reach.

Why analyze_item_description is a TOOL rather than something the
orchestrating model just reasons about directly: identifying a
manufacturer from an ambiguous description is a task this project has
already built, tested, and guardrailed (Phase 11) — structured output,
an unconditional human-review override, and a measured 91-100% field
accuracy on a labelled eval set. Routing this sub-task to that
existing, verified component means the agent defers to tested judgment
for the one step that's been specifically hardened, rather than
trusting its own free-form guess. That is the same reason main.py
calls parsed_rfq_to_items_response instead of re-deriving its logic —
composition over re-implementation.

Each tool has:
  - a Pydantic model defining its arguments (also the source of the
    JSON schema Claude receives — one definition, not two to keep in
    sync)
  - a plain Python function taking validated arguments and returning
    a JSON-serializable dict
  - an entry in TOOL_REGISTRY, which agent/supplier_agent.py uses to
    dispatch a tool_use block by name

Database note: search_suppliers_by_manufacturer and
check_stale_suppliers query a small in-memory SQLite database seeded
once at import time with the same three mock suppliers used in
tests/test_supplier_repository.py — NOT the real
knowledge_base/suppliers.db used by supplier_discovery.py. This is
the same "separate, parallel demonstration layer" boundary Phase 9
established; connecting to the real database is future work.
"""

from datetime import date, timedelta
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base, Supplier
from db.repositories.supplier_repository import SupplierRepository
from llm.claude_analyzer import get_analyzer
from retrieval.semantic_search import find_semantic_matches


# ---------------------------------------------------------------------
# Seeded in-memory database, module-level so it's created once and
# reused across every tool call in the process.
#
# poolclass=StaticPool + check_same_thread=False is required here, not
# optional. A real live agent run surfaced this the hard way: FastAPI
# runs synchronous route handlers in a thread pool, and SQLAlchemy's
# DEFAULT pooling for sqlite ":memory:" (SingletonThreadPool) gives
# every NEW thread it sees its own completely separate, empty
# database — the seeded data only exists on whichever thread happened
# to run this module's import. That bug is non-deterministic: it only
# fires when the thread pool schedules a request onto a worker thread
# that's never touched this engine before, which is exactly why
# earlier manual tests worked by chance and a later one didn't.
# StaticPool shares ONE real connection across every thread instead,
# which is the standard fix for this exact situation. Verified with a
# genuine multi-threaded reproduction, not just a single-threaded
# script — see tests/test_agent_tools.py's cross-thread test.
# ---------------------------------------------------------------------

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(_engine)
_SessionLocal = sessionmaker(bind=_engine)


def _seed_mock_suppliers() -> None:
    """Same three mock/sanitized records as tests/test_supplier_repository.py."""
    session = _SessionLocal()
    session.add_all([
        Supplier(
            supplier_name="Mock ABB Supplier",
            manufacturer="ABB",
            email="mock.abb.supplier@example.com",
            country="Ireland",
            last_contact_date=date(2026, 6, 1),
        ),
        Supplier(
            supplier_name="Mock Second ABB Supplier",
            manufacturer="ABB",
            email="mock.abb.supplier2@example.com",
            country="Saudi Arabia",
            last_contact_date=date(2026, 5, 1),
        ),
        Supplier(
            supplier_name="Mock Siemens Supplier",
            manufacturer="Siemens",
            email="mock.siemens.supplier@example.com",
            country="Germany",
            last_contact_date=date(2023, 1, 1),
        ),
    ])
    session.commit()
    session.close()


_seed_mock_suppliers()


def _supplier_to_dict(supplier: Supplier) -> dict:
    return {
        "supplier_name": supplier.supplier_name,
        "manufacturer": supplier.manufacturer,
        "email": supplier.email,
        "country": supplier.country,
        "last_contact_date": supplier.last_contact_date.isoformat(),
    }


# ---------------------------------------------------------------------
# Tool 1 — search_suppliers_by_manufacturer
# ---------------------------------------------------------------------

class SearchSuppliersInput(BaseModel):
    # extra="forbid" makes Pydantic emit additionalProperties: false,
    # which Anthropic's strict:true tool-use mode requires.
    model_config = ConfigDict(extra="forbid")

    manufacturer: str = Field(
        description="Manufacturer or brand name to search for, e.g. 'ABB'."
    )


def search_suppliers_by_manufacturer(
    args: SearchSuppliersInput, trace_id: Optional[str] = None
) -> dict:
    session = _SessionLocal()
    try:
        repository = SupplierRepository(session)
        suppliers = repository.find_by_manufacturer(args.manufacturer)
        return {
            "found": len(suppliers) > 0,
            "count": len(suppliers),
            "suppliers": [_supplier_to_dict(s) for s in suppliers],
        }
    finally:
        session.close()


# ---------------------------------------------------------------------
# Tool 2 — check_stale_suppliers
# ---------------------------------------------------------------------

class CheckStaleSuppliersInput(BaseModel):
    # extra="forbid" makes Pydantic emit additionalProperties: false,
    # which Anthropic's strict:true tool-use mode requires.
    model_config = ConfigDict(extra="forbid")

    cutoff_date: Optional[str] = Field(
        default=None,
        description=(
            "ISO 8601 date (YYYY-MM-DD). Suppliers last contacted before "
            "this date are considered stale. Leave unset to use the "
            "project's standard 12-month staleness rule — do not invent "
            "or calculate a cutoff date yourself."
        ),
    )


# Approximates Module 2's "12 months since last contact" staleness
# rule as a fixed day count. Not calendar-month-exact (doesn't account
# for month lengths), which is an acceptable approximation for this
# mock layer but worth knowing if it's ever ported to the real
# knowledge base.
DEFAULT_STALENESS_WINDOW_DAYS = 365


def check_stale_suppliers(
    args: CheckStaleSuppliersInput, trace_id: Optional[str] = None
) -> dict:
    if args.cutoff_date is None:
        # The real business rule, computed in code — not left for the
        # model to reconstruct. A live run before this fix showed the
        # model picking a plausible-looking but arbitrary date with no
        # actual policy behind it.
        parsed_cutoff = date.today() - timedelta(days=DEFAULT_STALENESS_WINDOW_DAYS)
        cutoff_source = "default_12_month_rule"
    else:
        try:
            parsed_cutoff = date.fromisoformat(args.cutoff_date)
        except ValueError:
            return {
                "error": (
                    f"'{args.cutoff_date}' is not a valid ISO date "
                    "(expected YYYY-MM-DD)."
                )
            }
        cutoff_source = "provided_by_caller"

    session = _SessionLocal()
    try:
        repository = SupplierRepository(session)
        suppliers = repository.find_stale_suppliers(parsed_cutoff)
        return {
            "cutoff_date": parsed_cutoff.isoformat(),
            "cutoff_source": cutoff_source,
            "stale_count": len(suppliers),
            "stale_suppliers": [_supplier_to_dict(s) for s in suppliers],
        }
    finally:
        session.close()


# ---------------------------------------------------------------------
# Tool 3 — analyze_item_description
# ---------------------------------------------------------------------

class AnalyzeItemDescriptionInput(BaseModel):
    # extra="forbid" makes Pydantic emit additionalProperties: false,
    # which Anthropic's strict:true tool-use mode requires.
    model_config = ConfigDict(extra="forbid")

    description: str = Field(
        description="The raw RFQ line item description to analyze."
    )


def analyze_item_description(
    args: AnalyzeItemDescriptionInput, trace_id: Optional[str] = None
) -> dict:
    # Passing trace_id through here is the point of this parameter
    # existing at all: without it, this nested call to the Phase 11
    # analyzer would log under trace_id=None, breaking the "one grep
    # finds every call made while answering one request" property
    # Phase 12c built. get_analyzer(trace_id=...) binds it via
    # functools.partial when the real analyzer is used; the mock
    # ignores it (nothing to trace on a regex).
    analyzer = get_analyzer(trace_id=trace_id)
    analysis = analyzer(args.description)
    return analysis.model_dump()


# ---------------------------------------------------------------------
# Tool 4 — draft_supplier_email
# ---------------------------------------------------------------------

class DraftSupplierEmailInput(BaseModel):
    # extra="forbid" makes Pydantic emit additionalProperties: false,
    # which Anthropic's strict:true tool-use mode requires.
    model_config = ConfigDict(extra="forbid")

    supplier_name: str = Field(description="Name of the supplier to draft to.")
    supplier_email: str = Field(description="Supplier's email address.")
    material_number: str = Field(description="Internal material number.")
    item_description: str = Field(description="RFQ line item description.")
    quantity: int = Field(description="Quantity required.")
    uom: str = Field(description="Unit of measure, e.g. 'EA'.")
    manufacturer: Optional[str] = Field(
        default=None, description="Manufacturer, if known."
    )
    part_number: Optional[str] = Field(
        default=None, description="Part number, if known."
    )


def draft_supplier_email(
    args: DraftSupplierEmailInput, trace_id: Optional[str] = None
) -> dict:
    """
    Deterministic template fill — NOT an LLM call. Consistent with
    Module 3's existing design ("uses fixed templates and structured
    data"). The agent gathers the structured facts via other tools;
    this tool only formats them. There is no free-text generation step
    here that could invent a detail.
    """

    # Was all-or-nothing (both fields or neither) — fixed after a live
    # run showed a known manufacturer with no part number got dropped
    # from the email entirely, discarding real information the agent
    # had actually gathered.
    known_parts = [p for p in (args.manufacturer, args.part_number) if p]
    identification = (
        " ".join(known_parts) if known_parts else "manufacturer/part number to be confirmed"
    )

    subject = f"RFQ — {args.material_number} — {args.quantity}x {args.uom}"

    body = (
        f"Dear {args.supplier_name} team,\n\n"
        f"We are requesting a quote for the following item:\n\n"
        f"  Material Number: {args.material_number}\n"
        f"  Description: {args.item_description}\n"
        f"  Identification: {identification}\n"
        f"  Quantity: {args.quantity} {args.uom}\n\n"
        f"Please confirm pricing, lead time, and any applicable "
        f"certificates.\n\n"
        f"Kind regards"
    )

    return {
        "to": args.supplier_email,
        "subject": subject,
        "body": body,
        # Explicit and unconditional, same pattern as
        # AmbiguousItemAnalysis.human_review_required — this is a
        # draft, not a queued send. Nothing in this tool or the agent
        # loop can change this value.
        "status": "draft_only_not_sent",
    }


# ---------------------------------------------------------------------
# Tool 5 — search_suppliers_semantically (Phase 14c)
# ---------------------------------------------------------------------

class SearchSuppliersSemanticInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(
        description=(
            "The RFQ item's raw description, to search for similar "
            "historical items by meaning rather than exact wording."
        )
    )


def search_suppliers_semantically(
    args: SearchSuppliersSemanticInput, trace_id: Optional[str] = None
) -> dict:
    """
    Fallback search by description similarity (Phase 14a/14b), for
    when manufacturer-based search has nothing to work with. Returns
    a similarity score with every match as evidence — a low score is
    weak evidence, not a confident finding, and the caller (the model,
    via the system prompt) is told to treat it that way.
    """
    matches = find_semantic_matches(args.description, top_k=3)
    return {
        "found": len(matches) > 0,
        "count": len(matches),
        "matches": [
            {
                "supplier_name": m.supplier_name,
                "manufacturer": m.manufacturer,
                "similarity_score": m.similarity_score,
                "matched_historical_description": m.matched_description,
            }
            for m in matches
        ],
    }


# ---------------------------------------------------------------------
# Registry — maps tool name to its input schema, Python function, and
# the Anthropic-facing tool definition (derived from the Pydantic
# schema, not hand-duplicated).
# ---------------------------------------------------------------------

TOOL_REGISTRY = {
    "search_suppliers_by_manufacturer": {
        "input_model": SearchSuppliersInput,
        "function": search_suppliers_by_manufacturer,
        "description": (
            "Search the supplier knowledge base for suppliers matching a "
            "given manufacturer name. Read-only."
        ),
    },
    "check_stale_suppliers": {
        "input_model": CheckStaleSuppliersInput,
        "function": check_stale_suppliers,
        "description": (
            "Check which suppliers have not been contacted since a "
            "cutoff date. Read-only. Omit cutoff_date to use the "
            "project's standard 12-month staleness rule — do not "
            "calculate or invent a cutoff date yourself."
        ),
    },
    "analyze_item_description": {
        "input_model": AnalyzeItemDescriptionInput,
        "function": analyze_item_description,
        "description": (
            "Analyze an ambiguous RFQ item description to suggest a "
            "possible manufacturer and part number, with a confidence "
            "level and reasoning. Use this when a description has no "
            "clear manufacturer or part number and you need a suggestion "
            "before searching for suppliers. This always requires human "
            "review regardless of confidence."
        ),
    },
    "draft_supplier_email": {
        "input_model": DraftSupplierEmailInput,
        "function": draft_supplier_email,
        "description": (
            "Draft a supplier outreach email using a fixed template. "
            "This ONLY produces draft text — it never sends anything. "
            "There is no tool available to send email; drafts always "
            "require a human to review and send manually."
        ),
    },
    "search_suppliers_semantically": {
        "input_model": SearchSuppliersSemanticInput,
        "function": search_suppliers_semantically,
        "description": (
            "Search historical RFQ items by DESCRIPTION SIMILARITY "
            "rather than manufacturer name. Use this ONLY as a "
            "fallback — after search_suppliers_by_manufacturer has "
            "either found nothing or had no manufacturer to search "
            "with. Deterministic manufacturer matching is more "
            "reliable and should always be tried first when possible. "
            "Every result includes a similarity score: treat a low "
            "score as weak evidence, never as equivalent to a "
            "manufacturer-based match."
        ),
    },
}


def build_anthropic_tool_definitions() -> List[dict]:
    """
    Builds the `tools` list for the Messages API from TOOL_REGISTRY,
    deriving each input_schema from its Pydantic model rather than
    maintaining a second, hand-written copy of the schema.

    strict: true asks the API to guarantee that Claude's tool_use
    arguments match the schema exactly — no missing/malformed fields
    to defensively handle on our side.
    """
    definitions = []
    for name, entry in TOOL_REGISTRY.items():
        schema = entry["input_model"].model_json_schema()
        # Anthropic's schema format doesn't want Pydantic's own
        # "title" key cluttering the top level.
        schema.pop("title", None)
        definitions.append({
            "name": name,
            "description": entry["description"],
            "input_schema": schema,
            "strict": True,
        })
    return definitions
