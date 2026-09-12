# eval/compare_analyzers.py

"""
Analyzer comparison harness (Phase 11c, extended with cost/latency in
Phase 12b).

Runs the same labelled cases through BOTH ambiguous-item analyzers:

  - the deterministic mock (llm/ambiguous_item_analyzer.py)
  - the real Claude-backed analyzer (llm/claude_analyzer.py)

and reports, per analyzer: field accuracy, total API cost, and median
latency. Accuracy alone doesn't answer "should this run on every
item?" — the accuracy/cost/latency triple is the actual tradeoff an
operations decision is made on.

Latency is measured HERE, identically for both analyzers, so the
mock/model contrast is apples-to-apples (~0ms vs ~2s). Token counts
and cost come from the adapter's CallMetrics (mock has no tokens, so
its cost is structurally zero).

This is a measurement artifact, not a regression check — it is NOT
wired into CI, because it makes real (paid) API calls. Run it by hand:

    python eval/compare_analyzers.py

Requires ANTHROPIC_API_KEY for the Claude side; without it, only the
mock is scored.

Scoring is exact match after case/whitespace normalisation, with every
disagreement printed in full. Label changes are recorded in the case
notes in analyzer_cases.json rather than made silently.
"""

import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from llm.ambiguous_item_analyzer import analyze_ambiguous_item

CASES_PATH = Path(__file__).parent / "analyzer_cases.json"
REPORT_PATH = Path(__file__).parent / "analyzer_comparison.json"


def normalise(value):
    """Lowercase and strip so casing/spacing differences don't count as errors."""
    if value is None:
        return None
    return " ".join(str(value).split()).lower()


def score_case(case, analysis):
    manufacturer_correct = normalise(analysis.possible_manufacturer) == normalise(
        case["expected_manufacturer"]
    )
    part_number_correct = normalise(analysis.possible_part_number) == normalise(
        case["expected_part_number"]
    )

    return {
        "manufacturer_correct": manufacturer_correct,
        "part_number_correct": part_number_correct,
        "got_manufacturer": analysis.possible_manufacturer,
        "got_part_number": analysis.possible_part_number,
        "confidence": analysis.confidence,
        "human_review_required": analysis.human_review_required,
    }


def run_analyzer(label, analyze_fn, cases):
    """
    analyze_fn takes a description and returns (analysis, metrics_or_None).
    Latency is measured here for both analyzers so the comparison is
    apples-to-apples; adapter metrics supply tokens/cost when present.
    """
    print(f"\n{'=' * 72}")
    print(f"{label}")
    print("=" * 72)

    results = []
    for case in cases:
        started = time.perf_counter()
        analysis, metrics = analyze_fn(case["description"])
        latency = time.perf_counter() - started

        scored = score_case(case, analysis)
        scored["case_id"] = case["case_id"]
        scored["latency_seconds"] = round(latency, 3)

        if metrics is not None:
            scored["input_tokens"] = metrics.input_tokens
            scored["output_tokens"] = metrics.output_tokens
            scored["cost_usd"] = round(metrics.cost_usd, 6)
            scored["outcome"] = metrics.outcome
        else:
            scored["cost_usd"] = 0.0

        results.append(scored)

        mfr_icon = "PASS" if scored["manufacturer_correct"] else "FAIL"
        pn_icon = "PASS" if scored["part_number_correct"] else "FAIL"

        print(f"\n  {case['case_id']}  ({scored['latency_seconds']:.2f}s)")
        print(
            f"    manufacturer  {mfr_icon}  "
            f"expected={case['expected_manufacturer']!r}  "
            f"got={scored['got_manufacturer']!r}"
        )
        print(
            f"    part_number   {pn_icon}  "
            f"expected={case['expected_part_number']!r}  "
            f"got={scored['got_part_number']!r}"
        )

    return results


def summarise(label, results):
    total = len(results)
    mfr = sum(1 for r in results if r["manufacturer_correct"])
    pn = sum(1 for r in results if r["part_number_correct"])
    both = sum(
        1 for r in results
        if r["manufacturer_correct"] and r["part_number_correct"]
    )
    review = sum(1 for r in results if r["human_review_required"])
    latencies = [r["latency_seconds"] for r in results]

    return {
        "analyzer": label,
        "total_cases": total,
        "manufacturer_correct": mfr,
        "part_number_correct": pn,
        "both_fields_correct": both,
        "field_accuracy": round((mfr + pn) / (total * 2), 3),
        "human_review_required_count": review,
        "total_cost_usd": round(sum(r["cost_usd"] for r in results), 6),
        "median_latency_seconds": round(statistics.median(latencies), 3),
        "max_latency_seconds": round(max(latencies), 3),
    }


def main():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    mock_results = run_analyzer(
        "MOCK ANALYZER (regex + hardcoded manufacturer list)",
        lambda d: (analyze_ambiguous_item(d), None),
        cases,
    )
    mock_summary = summarise("mock", mock_results)

    report = {"summaries": [mock_summary], "mock_results": mock_results}

    claude_summary = None
    if os.getenv("ANTHROPIC_API_KEY"):
        from llm.claude_analyzer import analyze_with_metrics

        claude_results = run_analyzer(
            "CLAUDE ANALYZER (real API call)",
            analyze_with_metrics,
            cases,
        )
        claude_summary = summarise("claude", claude_results)
        report["summaries"].append(claude_summary)
        report["claude_results"] = claude_results
    else:
        print("\nNo ANTHROPIC_API_KEY set — skipping the Claude side.")

    print(f"\n{'=' * 72}")
    print("SUMMARY")
    print("=" * 72)
    header = f"{'':<26}{'mock':>12}"
    if claude_summary:
        header += f"{'claude':>12}"
    print(header)

    def row(label, mock_value, claude_value):
        line = f"{label:<26}{mock_value:>12}"
        if claude_summary:
            line += f"{claude_value:>12}"
        print(line)

    total = mock_summary["total_cases"]
    cs = claude_summary or {}
    row("manufacturer correct",
        f"{mock_summary['manufacturer_correct']}/{total}",
        f"{cs.get('manufacturer_correct', '')}/{total}" if claude_summary else "")
    row("part number correct",
        f"{mock_summary['part_number_correct']}/{total}",
        f"{cs.get('part_number_correct', '')}/{total}" if claude_summary else "")
    row("both fields correct",
        f"{mock_summary['both_fields_correct']}/{total}",
        f"{cs.get('both_fields_correct', '')}/{total}" if claude_summary else "")
    row("field accuracy",
        format(mock_summary["field_accuracy"], ".0%"),
        format(cs["field_accuracy"], ".0%") if claude_summary else "")
    row("human review required",
        f"{mock_summary['human_review_required_count']}/{total}",
        f"{cs.get('human_review_required_count', '')}/{total}" if claude_summary else "")
    row("total cost",
        f"${mock_summary['total_cost_usd']:.4f}",
        f"${cs['total_cost_usd']:.4f}" if claude_summary else "")
    row("median latency",
        f"{mock_summary['median_latency_seconds'] * 1000:.0f}ms",
        f"{cs['median_latency_seconds']:.2f}s" if claude_summary else "")
    row("max latency",
        f"{mock_summary['max_latency_seconds'] * 1000:.0f}ms",
        f"{cs['max_latency_seconds']:.2f}s" if claude_summary else "")

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
