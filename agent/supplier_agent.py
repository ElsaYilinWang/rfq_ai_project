# agent/supplier_agent.py

"""
The Phase 13 agent loop: multi-step, tool-calling supplier search for
one ambiguous RFQ line item.

This is the project's first genuinely agentic component — every prior
AI call (Phase 11's analyzer) is one call in, one structured result
out, with no ability to see an intermediate result and decide what to
do next. This loop can: search for suppliers, notice none matched,
decide to analyze the description first, search again with a
suggested manufacturer, and only then produce a final answer. How
many steps that takes is not fixed in advance.

Uses Sonnet 5, not Haiku — deciding WHICH tool to call based on
intermediate results is a harder reasoning task than the Phase 11
analyzer's single-shot extraction, and this is the one place in the
project where the smarter model is deliberately worth its higher cost.

Safety properties, all enforced in code, not just prompted for:
  - Hard max_iterations cap. An agent loop that can call tools
    indefinitely is an agent that can spend money indefinitely; this
    is not optional.
  - Every tool_use block is validated and dispatched by
    agent/tools.py, never executed by trusting the model's claim
    about what a tool does.
  - An unknown tool name or invalid arguments returns a tool_result
    with is_error=True instead of crashing the loop — proven by
    test_agent_tools.py and the mocked-loop tests here.
  - human_review_required is unconditionally True on every result
    (agent/schemas.py) — completion, confidence, or tool success
    never change this.
  - There is no send-email tool in the registry this loop can call
    (see agent/tools.py's module docstring for why that is
    architectural, not a prompted instruction).

Logging: each iteration and each tool call is logged with the run's
trace_id, following the same structured pattern established in
llm/claude_analyzer.py (Phase 12c). Wiring this logger to the shared
llm_calls.log file handler happens where the trace_id is generated —
Phase 13c, when this loop is called from an API route.
"""

import json
import logging
import re
import time
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from agent.schemas import AgentFinalAnswer, AgentSupplierSearchResult, ToolCallRecord
from agent.tools import TOOL_REGISTRY, build_anthropic_tool_definitions

logger = logging.getLogger("agent")

load_dotenv()

MODEL = "claude-sonnet-5"

# Sonnet 5 pricing, checked 2026-09-15 against Anthropic's own
# announcement post: the $2/$10 introductory rate was made PERMANENT
# via an edit dated 2026-08-10, overriding an earlier-announced
# reversion to $3/$15 that was scheduled for (and never took effect
# on) 2026-09-01. If this project is revisited well after this date,
# re-verify — several third-party aggregators still show the old
# $3/$15 figure, which is stale.
INPUT_COST_PER_TOKEN = 2.00 / 1_000_000
OUTPUT_COST_PER_TOKEN = 10.00 / 1_000_000

MAX_ITERATIONS = 6

SYSTEM_PROMPT = """You are a procurement sourcing assistant. Your job is \
to find supplier candidates for ONE RFQ line item using the tools available \
to you.

Tools available to you search the supplier database, check for stale \
suppliers, analyze an ambiguous description, and draft a supplier email. \
There is NO tool to send email. You cannot send anything under any \
circumstances — drafting is the only email-related action available, and \
a human must send it manually.

Your approach:
1. If the item already has a known manufacturer, search for suppliers by \
that manufacturer directly.
2. If the manufacturer is unknown, use the item-analysis tool first. Only \
search for suppliers using a manufacturer that tool actually returned — \
never guess a manufacturer yourself from the description.
3. If suppliers are found, you may check whether they are stale.
4. If you find a good supplier candidate, you may draft an outreach email \
for human review. Never claim or imply that an email was sent.
5. If no manufacturer can be identified and no suppliers are found, say so \
plainly — do not fabricate a candidate.

Never invent supplier names, emails, or manufacturer identifications that \
did not come from a tool result.

When you are done gathering information, respond with ONLY a JSON object \
in this exact shape, no other text, no markdown code fences:

{
  "summary": "one to three sentences describing what you found",
  "manufacturer_identified": "name or null",
  "supplier_candidates_found": true or false,
  "recommended_next_step": "a short phrase, e.g. 'draft and route for review' or 'escalate to human sourcing'"
}"""


def dispatch_tool(tool_name: str, raw_input: dict) -> tuple[dict, bool]:
    """
    Validates and executes one tool call. Never raises — every failure
    mode (unknown tool, bad arguments, an exception inside the tool
    itself) returns a structured error result instead, so a single bad
    tool call degrades gracefully rather than crashing the whole loop.
    """
    entry = TOOL_REGISTRY.get(tool_name)
    if entry is None:
        return (
            {"error": f"Unknown tool: '{tool_name}'. No such tool is registered."},
            True,
        )

    try:
        validated_input = entry["input_model"](**raw_input)
    except ValidationError as exc:
        return (
            {"error": f"Invalid arguments for '{tool_name}': {exc.errors()}"},
            True,
        )

    try:
        result = entry["function"](validated_input)
    except Exception as exc:  # noqa: BLE001 — deliberately broad, see docstring
        return (
            {"error": f"Tool '{tool_name}' raised an unexpected error: {exc}"},
            True,
        )

    return result, False


def _parse_final_answer(raw_text: str) -> AgentFinalAnswer:
    """
    Same fence-stripping / parse / validate / fallback shape as
    llm.analysis_core.parse_and_validate, applied to the agent's
    smaller final-answer schema instead of AmbiguousItemAnalysis.
    """
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        payload = json.loads(cleaned)
        return AgentFinalAnswer(**payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("Failed to parse agent final answer | error=%s", exc)
        return AgentFinalAnswer(
            summary="The agent did not return a valid final answer.",
            manufacturer_identified=None,
            supplier_candidates_found=False,
            recommended_next_step="escalate to human sourcing",
        )


def run_supplier_search_agent(
    item_description: str,
    material_number: Optional[str] = None,
    known_manufacturer: Optional[str] = None,
    known_part_number: Optional[str] = None,
    trace_id: Optional[str] = None,
    max_iterations: int = MAX_ITERATIONS,
) -> AgentSupplierSearchResult:
    client = Anthropic()
    tools = build_anthropic_tool_definitions()

    task = (
        f"RFQ Line Item\n"
        f"Material Number: {material_number or 'unknown'}\n"
        f"Description: {item_description}\n"
        f"Known manufacturer: {known_manufacturer or 'unknown'}\n"
        f"Known part number: {known_part_number or 'unknown'}\n\n"
        f"Find supplier candidates for this item."
    )
    messages = [{"role": "user", "content": task}]

    tool_call_records: list[ToolCallRecord] = []
    total_cost = 0.0
    total_latency = 0.0

    for iteration in range(1, max_iterations + 1):
        started = time.perf_counter()
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=tools,
            tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            messages=messages,
        )
        latency = time.perf_counter() - started
        total_latency += latency

        cost = (
            response.usage.input_tokens * INPUT_COST_PER_TOKEN
            + response.usage.output_tokens * OUTPUT_COST_PER_TOKEN
        )
        total_cost += cost

        logger.info(
            "Agent iteration | trace_id=%s iteration=%d/%d stop_reason=%s "
            "tokens_in=%d tokens_out=%d cost_usd=%.6f latency=%.2fs",
            trace_id, iteration, max_iterations, response.stop_reason,
            response.usage.input_tokens, response.usage.output_tokens,
            cost, latency,
        )

        if response.stop_reason != "tool_use":
            final_text = next(
                (b.text for b in response.content if b.type == "text"), ""
            )
            final_answer = _parse_final_answer(final_text)

            return AgentSupplierSearchResult(
                material_number=material_number,
                item_description=item_description,
                completed=True,
                summary=final_answer.summary,
                manufacturer_identified=final_answer.manufacturer_identified,
                supplier_candidates_found=final_answer.supplier_candidates_found,
                recommended_next_step=final_answer.recommended_next_step,
                tool_calls=tool_call_records,
                iterations_used=iteration,
                total_cost_usd=round(total_cost, 6),
                total_latency_seconds=round(total_latency, 3),
                trace_id=trace_id,
            )

        # tool_choice disables parallel calls, so exactly one
        # tool_use block is expected per iteration.
        tool_use_block = next(
            b for b in response.content if b.type == "tool_use"
        )

        tool_started = time.perf_counter()
        result, is_error = dispatch_tool(tool_use_block.name, tool_use_block.input)
        tool_latency = time.perf_counter() - tool_started

        logger.info(
            "Tool call | trace_id=%s iteration=%d tool=%s is_error=%s latency=%.3fs",
            trace_id, iteration, tool_use_block.name, is_error, tool_latency,
        )

        tool_call_records.append(
            ToolCallRecord(
                iteration=iteration,
                tool_name=tool_use_block.name,
                tool_input=tool_use_block.input,
                tool_output=result,
                is_error=is_error,
                latency_seconds=round(tool_latency, 3),
            )
        )

        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_block.id,
                "content": json.dumps(result),
                "is_error": is_error,
            }],
        })

    # Iteration cap reached without a final answer. This is a real,
    # expected outcome path — not an error — and it must still produce
    # a valid, reviewable result rather than raising.
    logger.warning(
        "Agent hit max_iterations without a final answer | trace_id=%s "
        "max_iterations=%d",
        trace_id, max_iterations,
    )
    return AgentSupplierSearchResult(
        material_number=material_number,
        item_description=item_description,
        completed=False,
        summary=(
            f"The agent did not reach a final answer within "
            f"{max_iterations} iterations. Manual review required."
        ),
        manufacturer_identified=None,
        supplier_candidates_found=False,
        recommended_next_step="escalate to human sourcing",
        tool_calls=tool_call_records,
        iterations_used=max_iterations,
        total_cost_usd=round(total_cost, 6),
        total_latency_seconds=round(total_latency, 3),
        trace_id=trace_id,
    )
