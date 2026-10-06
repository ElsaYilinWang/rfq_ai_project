# agent/supplier_graph.py

"""
Phase 18a: the Phase 13 agent loop, rebuilt as a LangGraph graph.

This is a REFACTOR, not a feature: same prompt, same model, same five
tools, same dispatcher, same cap, same result schema. The only thing
that changes is who runs the loop. The old implementation
(agent/supplier_agent.py) stays in place as the reference; nothing
imports this module yet, and tests/test_supplier_graph.py proves the
two behave identically on the same scripted model responses.

How the old for-loop maps onto the graph:

    for iteration in range(...)      ->  `iteration` in state, plus the
                                         edge run_tool -> call_model
    client.messages.create + cost    ->  node call_model
    if stop_reason != "tool_use"     ->  router route_after_model
    dispatch_tool + record + append  ->  node run_tool
    (loop ran out of iterations)     ->  router route_after_tool -> capped
    final-answer parse + result      ->  node finalize
    code after the for-loop          ->  node capped

        START -> call_model -+-> run_tool -+-> call_model   (loop)
                             |             +-> capped -> END
                             +-> finalize -> END

THE CAP. recursion_limit is not the cap. The cap is `max_iterations`
in state, enforced by route_after_tool, so hitting it ends the run
with a valid, reviewable completed=False result -- exactly like the old
loop. The framework's own limit raises an exception and discards the
partial run. It is set explicitly, just above the worst legitimate path
(N model calls + N tool runs + 1 capped node = 2N + 1 steps), as a
backstop for a router bug: LangGraph 1.2.14's default is about 10,000
steps, which for a paid loop means thousands of API calls.

STATE IS PLAIN DATA. Everything in AgentState is a dict, list, string
or number -- never an SDK object -- because a checkpointer (Phase 18b)
has to serialize it. Model reply blocks are converted to dicts on the
way in (see _block_to_dict). The Anthropic client and tool definitions
are NOT state; they are closed over by build_graph().

One deliberate difference from the old loop: if the model reports
stop_reason == "tool_use" but returns no tool_use block, the old code
hit a bare StopIteration. Here call_model raises an explicit
RuntimeError saying what happened. Both crash loudly; this one says why.
"""

import json
import logging
import operator
import time
from typing import Annotated, Optional, TypedDict

from anthropic import Anthropic
from langgraph.graph import END, START, StateGraph

from agent.schemas import AgentSupplierSearchResult, ToolCallRecord
from agent.supplier_agent import (
    INPUT_COST_PER_TOKEN,
    MAX_ITERATIONS,
    MODEL,
    OUTPUT_COST_PER_TOKEN,
    SYSTEM_PROMPT,
    _parse_final_answer,
    dispatch_tool,
)
from agent.tools import build_anthropic_tool_definitions

# Same logger name as the old loop, so the shared llm_calls.log handler
# (which covers the "agent" logger) captures graph runs with no change.
logger = logging.getLogger("agent")


def recursion_limit_for(max_iterations: int) -> int:
    """Backstop above the worst legitimate path (2N + 1), never below it."""
    return 2 * max_iterations + 5


class AgentState(TypedDict):
    # --- inputs (set once) ---
    item_description: str
    material_number: Optional[str]
    trace_id: Optional[str]
    max_iterations: int
    # --- the conversation and the trace (new items are appended) ---
    messages: Annotated[list[dict], operator.add]
    tool_call_records: Annotated[list[dict], operator.add]
    # --- loop bookkeeping (overwritten each step) ---
    iteration: int
    total_cost: float
    total_latency: float
    stop_reason: Optional[str]
    pending_tool_use: Optional[dict]
    final_blocks: Optional[list[dict]]
    # --- output ---
    result: Optional[dict]


def _block_to_dict(block) -> dict:
    """
    Reply blocks as plain dicts. Only text and tool_use can occur here
    (no extended thinking is enabled), and those two are rebuilt
    explicitly so the dicts sent back to the API contain exactly the
    fields the API expects. Anything else keeps what it can.
    """
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    dump = getattr(block, "model_dump", None)
    return dump(exclude_none=True) if callable(dump) else {"type": block.type}


def route_after_model(state: AgentState) -> str:
    return "run_tool" if state["stop_reason"] == "tool_use" else "finalize"


def route_after_tool(state: AgentState) -> str:
    # The cap. After run_tool, not after call_model: the old loop still
    # ran the tool on its last iteration before giving up.
    if state["iteration"] >= state["max_iterations"]:
        return "capped"
    return "call_model"


def finalize(state: AgentState) -> dict:
    blocks = state["final_blocks"] or []
    final_text = next((b["text"] for b in blocks if b["type"] == "text"), None)
    if final_text is None:
        logger.warning(
            "No text block in final response | trace_id=%s "
            "stop_reason=%s content_block_types=%s",
            state["trace_id"], state["stop_reason"], [b["type"] for b in blocks],
        )
        final_text = ""
    final_answer = _parse_final_answer(final_text, trace_id=state["trace_id"])

    result = AgentSupplierSearchResult(
        material_number=state["material_number"],
        item_description=state["item_description"],
        completed=True,
        summary=final_answer.summary,
        manufacturer_identified=final_answer.manufacturer_identified,
        supplier_candidates_found=final_answer.supplier_candidates_found,
        recommended_next_step=final_answer.recommended_next_step,
        tool_calls=[ToolCallRecord(**r) for r in state["tool_call_records"]],
        iterations_used=state["iteration"],
        total_cost_usd=round(state["total_cost"], 6),
        total_latency_seconds=round(state["total_latency"], 3),
        trace_id=state["trace_id"],
    )
    return {"result": result.model_dump()}


def capped(state: AgentState) -> dict:
    # The old code after the for-loop: a real, expected outcome, not an
    # error -- it must still produce a valid, reviewable result.
    logger.warning(
        "Agent hit max_iterations without a final answer | trace_id=%s "
        "max_iterations=%d",
        state["trace_id"], state["max_iterations"],
    )
    result = AgentSupplierSearchResult(
        material_number=state["material_number"],
        item_description=state["item_description"],
        completed=False,
        summary=(
            f"The agent did not reach a final answer within "
            f"{state['max_iterations']} iterations. Manual review required."
        ),
        manufacturer_identified=None,
        supplier_candidates_found=False,
        recommended_next_step="escalate to human sourcing",
        tool_calls=[ToolCallRecord(**r) for r in state["tool_call_records"]],
        iterations_used=state["max_iterations"],
        total_cost_usd=round(state["total_cost"], 6),
        total_latency_seconds=round(state["total_latency"], 3),
        trace_id=state["trace_id"],
    )
    return {"result": result.model_dump()}


def build_graph(client, tools):
    """
    Compiles the graph. `client` and `tools` are closed over by the two
    nodes that need them rather than stored in state: they are not
    plain data and must never be checkpointed.
    """

    def call_model(state: AgentState) -> dict:
        iteration = state["iteration"] + 1
        started = time.perf_counter()
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=tools,
            tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            messages=state["messages"],
        )
        latency = time.perf_counter() - started

        cost = (
            response.usage.input_tokens * INPUT_COST_PER_TOKEN
            + response.usage.output_tokens * OUTPUT_COST_PER_TOKEN
        )
        logger.info(
            "Agent iteration | trace_id=%s iteration=%d/%d stop_reason=%s "
            "tokens_in=%d tokens_out=%d cost_usd=%.6f latency=%.2fs",
            state["trace_id"], iteration, state["max_iterations"],
            response.stop_reason, response.usage.input_tokens,
            response.usage.output_tokens, cost, latency,
        )

        blocks = [_block_to_dict(b) for b in response.content]
        update = {
            "iteration": iteration,
            "total_cost": state["total_cost"] + cost,
            "total_latency": state["total_latency"] + latency,
            "stop_reason": response.stop_reason,
            "pending_tool_use": None,
            "final_blocks": None,
        }
        if response.stop_reason == "tool_use":
            tool_use = next((b for b in blocks if b["type"] == "tool_use"), None)
            if tool_use is None:
                raise RuntimeError(
                    "Model reported stop_reason='tool_use' but returned no "
                    f"tool_use block (block types: {[b['type'] for b in blocks]})"
                )
            update["pending_tool_use"] = tool_use
            update["messages"] = [{"role": "assistant", "content": blocks}]
        else:
            update["final_blocks"] = blocks
        return update

    def run_tool(state: AgentState) -> dict:
        tool_use = state["pending_tool_use"]
        started = time.perf_counter()
        result, is_error = dispatch_tool(
            tool_use["name"], tool_use["input"], trace_id=state["trace_id"]
        )
        latency = time.perf_counter() - started

        logger.info(
            "Tool call | trace_id=%s iteration=%d tool=%s is_error=%s latency=%.3fs",
            state["trace_id"], state["iteration"], tool_use["name"],
            is_error, latency,
        )
        record = ToolCallRecord(
            iteration=state["iteration"],
            tool_name=tool_use["name"],
            tool_input=tool_use["input"],
            tool_output=result,
            is_error=is_error,
            latency_seconds=round(latency, 3),
        )
        return {
            "tool_call_records": [record.model_dump()],
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_use["id"],
                    "content": json.dumps(result),
                    "is_error": is_error,
                }],
            }],
        }

    builder = StateGraph(AgentState)
    builder.add_node("call_model", call_model)
    builder.add_node("run_tool", run_tool)
    builder.add_node("finalize", finalize)
    builder.add_node("capped", capped)
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges("call_model", route_after_model, ["run_tool", "finalize"])
    builder.add_conditional_edges("run_tool", route_after_tool, ["capped", "call_model"])
    builder.add_edge("finalize", END)
    builder.add_edge("capped", END)
    return builder.compile()


def build_initial_state(
    item_description: str,
    material_number: Optional[str],
    known_manufacturer: Optional[str],
    known_part_number: Optional[str],
    trace_id: Optional[str],
    max_iterations: int,
) -> AgentState:
    # Identical wording to the old loop's task message.
    task = (
        f"RFQ Line Item\n"
        f"Material Number: {material_number or 'unknown'}\n"
        f"Description: {item_description}\n"
        f"Known manufacturer: {known_manufacturer or 'unknown'}\n"
        f"Known part number: {known_part_number or 'unknown'}\n\n"
        f"Find supplier candidates for this item."
    )
    return {
        "item_description": item_description,
        "material_number": material_number,
        "trace_id": trace_id,
        "max_iterations": max_iterations,
        "messages": [{"role": "user", "content": task}],
        "tool_call_records": [],
        "iteration": 0,
        "total_cost": 0.0,
        "total_latency": 0.0,
        "stop_reason": None,
        "pending_tool_use": None,
        "final_blocks": None,
        "result": None,
    }


def run_supplier_search_graph(
    item_description: str,
    material_number: Optional[str] = None,
    known_manufacturer: Optional[str] = None,
    known_part_number: Optional[str] = None,
    trace_id: Optional[str] = None,
    max_iterations: int = MAX_ITERATIONS,
) -> AgentSupplierSearchResult:
    """Same signature and return type as run_supplier_search_agent."""
    client = Anthropic()
    graph = build_graph(client, build_anthropic_tool_definitions())
    final_state = graph.invoke(
        build_initial_state(
            item_description, material_number, known_manufacturer,
            known_part_number, trace_id, max_iterations,
        ),
        {"recursion_limit": recursion_limit_for(max_iterations)},
    )
    return AgentSupplierSearchResult(**final_state["result"])
