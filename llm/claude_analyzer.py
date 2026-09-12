# llm/claude_analyzer.py

"""
Anthropic adapter for the ambiguous RFQ item analyzer (thinned in
Phase 12a).

Everything provider-neutral — the prompt, fence-stripping, JSON
parsing, the human-review override, schema validation, fallbacks —
lives in llm/analysis_core.py. This file is only the glue that:

  1. knows the Anthropic SDK and model name exist,
  2. sends the prompt the core built,
  3. hands the raw response text back to the core for validation,
  4. degrades to the core's safe fallback if the call itself fails.

Swapping providers means writing another adapter with this same shape
against analysis_core — nothing else in the project changes.

Same signature as llm.ambiguous_item_analyzer.analyze_ambiguous_item,
so either can be passed as the `analyzer` argument to
parsed_rfq_to_items_response. That interchangeability is the point:
the rest of the workflow never knows which one it got.
"""


import logging
import os
import time

from anthropic import Anthropic
from dotenv import load_dotenv

from llm.analysis_core import PROMPT_VERSION, build_prompt, fallback, parse_and_validate
from llm.schemas import AmbiguousItemAnalysis, CallMetrics

logger = logging.getLogger(__name__)

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"

# Haiku 4.5 pricing, checked 2026-09: $1 per million input tokens,
# $5 per million output. Hardcoded deliberately — if these go stale,
# the dated comment makes that visible instead of silently wrong.
INPUT_COST_PER_TOKEN = 1.00 / 1_000_000
OUTPUT_COST_PER_TOKEN = 5.00 / 1_000_000

def analyze_with_metrics(description: str) -> tuple[AmbiguousItemAnalysis, CallMetrics]:
    """
    Same analysis as analyze_ambiguous_item_with_claude, but also
    returns per-call metrics: tokens, cost, latency, and which outcome
    path fired. Used by evaluation and comparison tooling.
    """
    logger.info(
        "Analyzing ambiguous item | prompt_version=%s model=%s input_length=%d",
        PROMPT_VERSION, MODEL, len(description),
    )

    started = time.perf_counter()

    try:
        client = Anthropic()
        message = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": build_prompt(description)}],
        )
        raw_response = message.content[0].text
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
    except Exception as exc:
        latency = time.perf_counter() - started
        logger.error(
            "Model call failed | prompt_version=%s error=%s", PROMPT_VERSION, exc
        )
        return (
            fallback("Analysis unavailable: the model call failed."),
            CallMetrics(
                model=MODEL,
                prompt_version=PROMPT_VERSION,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_seconds=latency,
                outcome="call_failed",
            ),
        )

    latency = time.perf_counter() - started
    analysis = parse_and_validate(raw_response)

    if analysis.reason.startswith("Analysis unavailable"):
        outcome = (
            "invalid_json"
            if "invalid JSON" in analysis.reason
            else "schema_invalid"
        )
    else:
        outcome = "success"

    metrics = CallMetrics(
        model=MODEL,
        prompt_version=PROMPT_VERSION,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=input_tokens * INPUT_COST_PER_TOKEN
        + output_tokens * OUTPUT_COST_PER_TOKEN,
        latency_seconds=latency,
        outcome=outcome,
    )

    logger.info(
        "Call metrics | outcome=%s tokens_in=%d tokens_out=%d cost_usd=%.6f latency=%.2fs",
        outcome, input_tokens, output_tokens, metrics.cost_usd, latency,
    )

    return analysis, metrics


def analyze_ambiguous_item_with_claude(description: str) -> AmbiguousItemAnalysis:
    """Signature-compatible wrapper: analysis only, metrics discarded."""
    analysis, _ = analyze_with_metrics(description)
    return analysis


def get_analyzer():
    """
    Returns the real Claude analyzer when an API key is configured,
    otherwise the deterministic mock.

    This is what lets the same route work locally with a key, in CI
    without one, and in tests without either — no branching at the
    call site.
    """
    if os.getenv("ANTHROPIC_API_KEY"):
        return analyze_ambiguous_item_with_claude

    from llm.ambiguous_item_analyzer import analyze_ambiguous_item
    logger.info("No ANTHROPIC_API_KEY found — falling back to the mock analyzer.")
    return analyze_ambiguous_item
