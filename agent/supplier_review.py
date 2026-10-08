# agent/supplier_review.py

"""
Phase 18b: run the supplier agent with a human approval pause.

Two entry points, because a run can now end "waiting for you":

    start_supplier_review(...)   run the agent; if it produced a draft,
                                 pause for approval and say so
    resume_supplier_review(...)  a human approves, or rejects with a note

plus get_pending_review(...), so a reviewer who comes back later can
fetch what is waiting without having kept the start response.

SENDING IS NOT HERE. Approval only records the decision. Nothing in this
module or the graph can send an email; the human still sends from
Outlook. And `human_review_required` on the result stays True even
after approval: the approval is a separate, recorded fact
(ReviewRunOutcome.status), and nothing is allowed to flip that flag.

Identity: thread_id == trace_id == the run's id. One id finds the run in
the logs, the checkpoint, and the reviewer's resume call.

Guards, each proven by tests/test_supplier_review.py:
  - resume cannot spend money: it is given a model client that raises
    if anything tries to call it, so the guarantee is structural
  - an invalid decision (reject with no note) is refused BEFORE the run
    is touched, and the run stays pending
  - resuming a run that is not waiting (already decided, or unknown)
    raises ReviewNotPending instead of re-running anything
  - starting with a trace_id that already has a checkpoint is refused:
    LangGraph would otherwise APPEND the new run's messages onto the old
    thread's state

The checkpointer defaults to LangGraph's in-memory one: paused runs are
lost on process restart. A durable (SQLite) checkpointer is the next
step and is injected through the `checkpointer` parameter.
"""

import uuid
from typing import Literal, Optional

from anthropic import Anthropic
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from agent.schemas import AgentSupplierSearchResult
from agent.supplier_agent import MAX_ITERATIONS
from agent.supplier_graph import (
    ReviewDecision,
    build_graph,
    build_initial_state,
    recursion_limit_for,
)
from agent.tools import build_anthropic_tool_definitions

default_checkpointer = InMemorySaver()

# Resuming runs a single step (the approval node). An explicit, tiny
# limit, never the framework's ~10,000 default.
RESUME_RECURSION_LIMIT = 10


class ReviewNotPending(ValueError):
    """The run is not waiting for a decision (already decided, or unknown)."""


class ReviewRunOutcome(BaseModel):
    status: Literal["awaiting_approval", "approved", "rejected", "no_review_required"]
    trace_id: str
    result: AgentSupplierSearchResult
    review_request: Optional[dict] = None   # what the reviewer must see (awaiting only)
    decision_note: Optional[str] = None


class _NoModelOnResume:
    """Stands in for the Anthropic client while resuming. Resuming only
    runs the approval node; if anything ever tries to call the model, it
    fails loudly instead of quietly spending money."""

    class _Messages:
        def create(self, *args, **kwargs):
            raise RuntimeError("the model must never be called while resuming a review")

    messages = _Messages()


def _thread(trace_id: str) -> dict:
    return {"configurable": {"thread_id": trace_id}}


def _outcome_from(final_state: dict, trace_id: str) -> ReviewRunOutcome:
    result = AgentSupplierSearchResult(**final_state["result"])
    interrupts = final_state.get("__interrupt__")
    if interrupts:
        return ReviewRunOutcome(
            status="awaiting_approval", trace_id=trace_id, result=result,
            review_request=interrupts[0].value,
        )
    review = final_state.get("review")
    if review:
        return ReviewRunOutcome(
            status="approved" if review["decision"] == "approve" else "rejected",
            trace_id=trace_id, result=result, decision_note=review["note"],
        )
    return ReviewRunOutcome(status="no_review_required", trace_id=trace_id, result=result)


def start_supplier_review(
    item_description: str,
    material_number: Optional[str] = None,
    known_manufacturer: Optional[str] = None,
    known_part_number: Optional[str] = None,
    trace_id: Optional[str] = None,
    max_iterations: int = MAX_ITERATIONS,
    checkpointer=None,
    quantity: Optional[int] = None,
    uom: Optional[str] = None,
) -> ReviewRunOutcome:
    trace_id = trace_id or f"agent_{uuid.uuid4().hex[:12]}"
    graph = build_graph(
        Anthropic(), build_anthropic_tool_definitions(),
        checkpointer=checkpointer or default_checkpointer, with_approval=True,
    )
    if graph.get_state(_thread(trace_id)).values:
        raise ValueError(
            f"trace_id {trace_id!r} already has a saved run; "
            "starting again would merge the new run into the old one"
        )

    final_state = graph.invoke(
        build_initial_state(
            item_description, material_number, known_manufacturer,
            known_part_number, trace_id, max_iterations, quantity, uom,
        ),
        {**_thread(trace_id), "recursion_limit": recursion_limit_for(max_iterations)},
    )
    return _outcome_from(final_state, trace_id)


def get_pending_review(trace_id: str, checkpointer=None) -> Optional[dict]:
    """The review request of a run that is waiting, else None."""
    graph = build_graph(
        _NoModelOnResume(), [], checkpointer=checkpointer or default_checkpointer,
        with_approval=True,
    )
    snapshot = graph.get_state(_thread(trace_id))
    if snapshot.next != ("human_approval",):
        return None
    return snapshot.tasks[0].interrupts[0].value


def resume_supplier_review(
    trace_id: str,
    decision: str,
    note: Optional[str] = None,
    checkpointer=None,
) -> ReviewRunOutcome:
    # Validate first: a bad answer must leave the run exactly as it was.
    answer = ReviewDecision(decision=decision, note=note)

    graph = build_graph(
        _NoModelOnResume(), [], checkpointer=checkpointer or default_checkpointer,
        with_approval=True,
    )
    if graph.get_state(_thread(trace_id)).next != ("human_approval",):
        raise ReviewNotPending(
            f"run {trace_id!r} is not waiting for a decision "
            "(unknown, already decided, or it never needed review)"
        )

    final_state = graph.invoke(
        Command(resume=answer.model_dump()),
        {**_thread(trace_id), "recursion_limit": RESUME_RECURSION_LIMIT},
    )
    return _outcome_from(final_state, trace_id)
