# eval/quotation_extraction_eval.py

"""
Measures real field-extraction accuracy for the Docling + Claude
supplier quotation pipeline (Phase 17f) -- same discipline as
eval/compare_analyzers.py (Phase 11c) and eval/retrieval_hit_rate.py
(Phase 14d): a hand-labeled set of cases, scored field by field, not
just "it looked right" on a single example.

Only the fields a given case is actually designed to test are
checked (same precedent as 11c's expected_manufacturer/
expected_part_number, not every field on every case) -- checking an
unrelated field on every case would just add noise, not signal.
Comparison runs against quotation.model_dump() rather than individual
attributes, so nested fields like `certificates` (a list of
CertificateMention objects) compare correctly as plain dicts/lists
with no special-casing needed.

Makes real, paid Claude calls (Haiku-tier, same model as
quotation_intake/claude_extractor.py) and needs Docling's layout
model available (real internet access on first run, same as
scripts/semantic_retrieval_diagnostic.py). Not run in CI, for the
same reason eval/compare_analyzers.py and eval/retrieval_hit_rate.py
aren't: real cost per run.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from quotation_intake.claude_extractor import extract_quotation_with_claude
from quotation_intake.docling_extractor import extract_raw_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = Path(__file__).parent / "quotation_extraction_cases.json"
REPORT_PATH = Path(__file__).parent / "quotation_extraction_report.json"


def score_case(expected: dict, actual: dict) -> dict:
    """Compares only the fields `expected` names, against the actual
    quotation's full dict representation. Returns a per-field
    correct/incorrect breakdown for this one case."""
    field_results = {}
    for field, expected_value in expected.items():
        actual_value = actual.get(field)
        field_results[field] = {
            "expected": expected_value,
            "actual": actual_value,
            "correct": actual_value == expected_value,
        }
    return field_results


def run():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    results = []
    field_correct_count = {}
    field_total_count = {}
    total_cost = 0.0

    for case in cases:
        file_path = PROJECT_ROOT / case["file"]
        raw_text = extract_raw_text(str(file_path))
        quotation, metrics = extract_quotation_with_claude(
            raw_text, trace_id=f"eval_{case['case_id']}"
        )
        actual = quotation.model_dump()

        field_results = score_case(case["expected"], actual)
        for field, outcome in field_results.items():
            field_total_count[field] = field_total_count.get(field, 0) + 1
            if outcome["correct"]:
                field_correct_count[field] = field_correct_count.get(field, 0) + 1

        case_correct = all(f["correct"] for f in field_results.values())
        total_cost += metrics.cost_usd

        results.append({
            "case_id": case["case_id"],
            "note": case.get("note", ""),
            "all_checked_fields_correct": case_correct,
            "fields": field_results,
            "cost_usd": metrics.cost_usd,
        })

    print("\n" + "=" * 72)
    print("SUPPLIER QUOTATION EXTRACTION -- FIELD ACCURACY REPORT")
    print("=" * 72)
    for r in results:
        icon = "PASS" if r["all_checked_fields_correct"] else "FAIL"
        print(f"\n  {icon}  {r['case_id']}")
        for field, outcome in r["fields"].items():
            mark = "OK" if outcome["correct"] else "**WRONG**"
            print(f"         {field:25} expected={outcome['expected']!r:30} actual={outcome['actual']!r:30} {mark}")

    print("\n" + "-" * 72)
    print("Per-field accuracy:")
    overall_correct = sum(field_correct_count.values())
    overall_total = sum(field_total_count.values())
    for field in sorted(field_total_count):
        c, t = field_correct_count.get(field, 0), field_total_count[field]
        print(f"  {field:25} {c}/{t}  ({c/t:.0%})")

    cases_fully_correct = sum(1 for r in results if r["all_checked_fields_correct"])
    print(f"\nCases with ALL checked fields correct: {cases_fully_correct}/{len(cases)}")
    print(f"Overall field accuracy: {overall_correct}/{overall_total} ({overall_correct/overall_total:.1%})")
    print(f"Total cost: ${total_cost:.4f}")

    report = {
        "cases_fully_correct": cases_fully_correct,
        "total_cases": len(cases),
        "overall_field_accuracy": round(overall_correct / overall_total, 3),
        "field_accuracy": {
            field: round(field_correct_count.get(field, 0) / field_total_count[field], 3)
            for field in field_total_count
        },
        "total_cost_usd": round(total_cost, 4),
        "results": results,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT_PATH}")
    return report


if __name__ == "__main__":
    run()
