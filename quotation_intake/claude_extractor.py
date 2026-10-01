# quotation_intake/claude_extractor.py

"""
Thin Anthropic adapter over quotation_intake/analysis_core.py's
provider-neutral prompt/parse logic -- same split as
llm/claude_analyzer.py over llm/analysis_core.py.

Reuses llm.schemas.CallMetrics verbatim rather than inventing a
second metrics schema -- confirmed against the real class (model,
prompt_version, input_tokens, output_tokens, cost_usd,
latency_seconds, outcome) before writing this, not guessed from a log
line. outcome is threaded through at full granularity: "success" /
"invalid_json" / "schema_invalid" come from analysis_core.py's
parse_and_validate, "call_failed" covers the API call itself failing
before any response exists to parse.
"""

import logging
import time
from typing import Optional, Tuple

from anthropic import Anthropic

from llm.schemas import CallMetrics
from quotation_intake.analysis_core import PROMPT_VERSION, build_prompt, fallback, parse_and_validate
from quotation_intake.schemas import SupplierQuotation

logger = logging.getLogger("quotation_intake")

# Same tier choice as the existing ambiguous-item analyzer: this is
# structured extraction from already-readable text, not multi-step
# reasoning, so the fast/cheap model is right-sized here too -- not
# Sonnet, which is reserved for the agent loop's adaptive tool
# selection.
MODEL = "claude-haiku-4-5-20251001"

# Verified current rate (checked directly, same sourcing discipline
# as Sonnet 5's rate in llm/claude_analyzer.py), not assumed to match
# Sonnet's pricing.
INPUT_COST_PER_TOKEN = 1.00 / 1_000_000
OUTPUT_COST_PER_TOKEN = 5.00 / 1_000_000


def extract_quotation_with_claude(
    raw_text: str, trace_id: Optional[str] = None
) -> Tuple[SupplierQuotation, CallMetrics]:
    client = Anthropic()
    prompt = build_prompt(raw_text)

    start = time.perf_counter()
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        latency = time.perf_counter() - start
        logger.error(
            "Quotation extraction API call failed | trace_id=%s error=%s",
            trace_id, exc,
        )
        metrics = CallMetrics(
            model=MODEL,
            prompt_version=PROMPT_VERSION,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            latency_seconds=round(latency, 3),
            outcome="call_failed",
        )
        return fallback(f"API call failed: {exc}"), metrics

    latency = time.perf_counter() - start
    raw_response = response.content[0].text
    quotation, outcome = parse_and_validate(raw_response)

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = input_tokens * INPUT_COST_PER_TOKEN + output_tokens * OUTPUT_COST_PER_TOKEN

    metrics = CallMetrics(
        model=MODEL,
        prompt_version=PROMPT_VERSION,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost, 6),
        latency_seconds=round(latency, 3),
        outcome=outcome,
    )

    logger.info(
        "Quotation call metrics | trace_id=%s outcome=%s prompt_version=%s "
        "model=%s input_tokens=%d output_tokens=%d cost_usd=%.6f latency_seconds=%.2f",
        trace_id, metrics.outcome, PROMPT_VERSION, MODEL,
        input_tokens, output_tokens, metrics.cost_usd, latency,
    )

    return quotation, metrics
