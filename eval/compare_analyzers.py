# eval/compare_analyzers.py

"""
Analyzer comparison harness (Phase 11c).

Runs the same labelled cases through BOTH ambiguous-item analyzers:

  - the deterministic mock (llm/ambiguous_item_analyzer.py): a hardcoded
    manufacturer list plus a part-number-shaped regex
  - the real Claude-backed analyzer (llm/claude_analyzer.py)

and reports how often each one recovers the manufacturer and part
number that a human labelled.

Why this exists: the project's deterministic-first principle says AI
should only be introduced where genuine ambiguity exists. That's a
claim, and this script is how the claim gets tested rather than
assumed. If the regex scored just as well, the LLM would not be
earning its place here.

This is a measurement artifact, not a regression check — it is NOT
wired into CI, because it makes real (paid) API calls. Run it by hand
when you want a number:

    python eval/compare_analyzers.py

Requires ANTHROPIC_API_KEY for the Claude side. Without it, only the
mock is scored and the comparison is skipped.

Scoring is exact match after case/whitespace normalisation. The
archived previous_approach/evaluate.py used bidirectional substring
matching, which scored "part" as a match against "spare part" and
inflated results. Every disagreement is printed in full below so
near-misses (e.g. "Schneider" vs "Schneider Electric") stay visible
rather than being silently counted either way.
"""

import json
import os
import sys
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


def run_analyzer(label, analyzer, cases):
    print(f"\n{'=' * 72}")
    print(f"{label}")
    print("=" * 72)

    results = []
    for case in cases:
        analysis = analyzer(case["description"])
        scored = score_case(case, analysis)
        scored["case_id"] = case["case_id"]
        results.append(scored)

        mfr_icon = "PASS" if scored["manufacturer_correct"] else "FAIL"
        pn_icon = "PASS" if scored["part_number_correct"] else "FAIL"

        print(f"\n  {case['case_id']}")
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

    return {
        "analyzer": label,
        "total_cases": total,
        "manufacturer_correct": mfr,
        "part_number_correct": pn,
        "both_fields_correct": both,
        "field_accuracy": round((mfr + pn) / (total * 2), 3),
        "human_review_required_count": review,
    }


def main():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    mock_results = run_analyzer(
        "MOCK ANALYZER (regex + hardcoded manufacturer list)",
        analyze_ambiguous_item,
        cases,
    )
    mock_summary = summarise("mock", mock_results)

    report = {"summaries": [mock_summary], "mock_results": mock_results}

    if os.getenv("ANTHROPIC_API_KEY"):
        from llm.claude_analyzer import analyze_ambiguous_item_with_claude

        claude_results = run_analyzer(
            "CLAUDE ANALYZER (real API call)",
            analyze_ambiguous_item_with_claude,
            cases,
        )
        claude_summary = summarise("claude", claude_results)
        report["summaries"].append(claude_summary)
        report["claude_results"] = claude_results
    else:
        claude_summary = None
        print("\nNo ANTHROPIC_API_KEY set — skipping the Claude side.")

    print(f"\n{'=' * 72}")
    print("SUMMARY")
    print("=" * 72)
    header = f"{'':<26}{'mock':>10}"
    if claude_summary:
        header += f"{'claude':>10}"
    print(header)

    rows = [
        ("manufacturer correct", "manufacturer_correct"),
        ("part number correct", "part_number_correct"),
        ("both fields correct", "both_fields_correct"),
        ("human review required", "human_review_required_count"),
    ]
    total = mock_summary["total_cases"]
    for label, key in rows:
        line = f"{label:<26}{f'{mock_summary[key]}/{total}':>10}"
        if claude_summary:
            line += f"{f'{claude_summary[key]}/{total}':>10}"
        print(line)

    accuracy_line = f"{'field accuracy':<26}{format(mock_summary['field_accuracy'], '.0%'):>10}"
    if claude_summary:
        accuracy_line += format(claude_summary["field_accuracy"], ".0%").rjust(10)
    print(accuracy_line)

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
