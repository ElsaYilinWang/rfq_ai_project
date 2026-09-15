# agent/schemas.py

"""
Result schemas for the Phase 13 supplier-search agent.

Two schemas, deliberately kept separate:

  - AgentFinalAnswer: the small, interpretive part the MODEL produces
    at the end of the loop (its summary and recommendation). Parsed
    and validated the same way llm/analysis_core.py validates the
    single-shot analyzer's output — Pydantic-enforced, safe fallback
    on failure.

  - AgentSupplierSearchResult: the full result returned to callers.
    Its tool_calls list is built by the PYTHON dispatcher from the
    actual tool_use blocks it executed — not from anything the model
    claims about its own actions. The model's self-report is never
    the source of truth for what tools were actually called; the
    application's own execution log is.
"""

from typing import Any, List, Optional

from pydantic import BaseModel


class AgentFinalAnswer(BaseModel):
    summary: str
    manufacturer_identified: Optional[str] = None
    supplier_candidates_found: bool
    recommended_next_step: str


class ToolCallRecord(BaseModel):
    """One step in the agent's tool-use trace, logged by the dispatcher."""
    iteration: int
    tool_name: str
    tool_input: dict
    tool_output: dict
    is_error: bool = False
    latency_seconds: float


class AgentSupplierSearchResult(BaseModel):
    material_number: Optional[str] = None
    item_description: str

    completed: bool
    summary: str
    manufacturer_identified: Optional[str] = None
    supplier_candidates_found: bool = False
    recommended_next_step: str

    tool_calls: List[ToolCallRecord] = []
    iterations_used: int

    total_cost_usd: float
    total_latency_seconds: float

    trace_id: Optional[str] = None

    # Unconditional, same pattern as AmbiguousItemAnalysis and every
    # other AI-derived result in this project. Nothing sets this to
    # False — not the model, not a "high confidence" run, not a
    # successful completion. An agent's multi-step conclusion is
    # exactly the kind of result that should never bypass a human.
    human_review_required: bool = True
