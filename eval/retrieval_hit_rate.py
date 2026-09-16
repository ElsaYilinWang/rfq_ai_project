# eval/retrieval_hit_rate.py

"""
Semantic retrieval hit-rate measurement (Phase 14d).

Answers a different question than tests/test_semantic_retrieval.py.
That file proves the retrieval MECHANISM works correctly in isolation
(discrimination between near-duplicates, correct rejection of true
negatives). This script answers the higher-level question that
actually motivated building semantic retrieval in the first place:
across a realistic spread of ambiguous RFQ items, does adding this
fallback actually surface a usable candidate?

eval/retrieval_cases.json states, for each case, whether a relevant
match is expected at all -- including cases where the corpus
genuinely has NOTHING relevant (a flange gasket, armored cable, a
safety relay). A hit rate only means something if some cases are
supposed to miss: without correctly-failing cases, a 100% "hit rate"
would just mean the threshold is too permissive, not that retrieval
is good. The report below breaks this apart explicitly -- a single
overall accuracy number can hide a system that always says "found
something," so true-positive rate and true-negative rate are reported
separately.

Free and local (no API calls, no cost) but needs real internet access
on first run, same as tests/test_semantic_retrieval.py, to download
the embedding model -- cached locally after that.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.semantic_search import find_semantic_matches

CASES_PATH = Path(__file__).parent / "retrieval_cases.json"
REPORT_PATH = Path(__file__).parent / "retrieval_hit_rate_report.json"


def run():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    results = []
    for case in cases:
        matches = find_semantic_matches(case["description"])
        found = len(matches) > 0
        correct = found == case["expected_match"]

        top_match = None
        if matches:
            top = matches[0]
            top_match = {
                "supplier_name": top.supplier_name,
                "manufacturer": top.manufacturer,
                "similarity_score": top.similarity_score,
                "matched_description": top.matched_description,
            }

        results.append({
            "case_id": case["case_id"],
            "description": case["description"],
            "expected_match": case["expected_match"],
            "found_match": found,
            "top_match": top_match,
            "correct": correct,
        })

    total = len(results)
    correct_count = sum(1 for r in results if r["correct"])

    expected_match_cases = [r for r in results if r["expected_match"]]
    expected_no_match_cases = [r for r in results if not r["expected_match"]]

    true_positive_rate = (
        sum(1 for r in expected_match_cases if r["found_match"]) / len(expected_match_cases)
        if expected_match_cases else None
    )
    true_negative_rate = (
        sum(1 for r in expected_no_match_cases if not r["found_match"]) / len(expected_no_match_cases)
        if expected_no_match_cases else None
    )

    print("\n" + "=" * 72)
    print("SEMANTIC RETRIEVAL HIT-RATE REPORT")
    print("=" * 72)
    for r in results:
        icon = "PASS" if r["correct"] else "FAIL"
        top = r["top_match"]
        top_str = (
            f"{top['manufacturer']} (score={top['similarity_score']:.2f})"
            if top else "no match"
        )
        print(
            f"  {icon}  {r['case_id']:32}  "
            f"expected_match={str(r['expected_match']):5}  got={top_str}"
        )

    print()
    print(f"Total cases: {total}")
    print(f"Correct: {correct_count}/{total} ({correct_count / total:.0%})")
    if true_positive_rate is not None:
        print(
            f"  Of {len(expected_match_cases)} cases expecting a match: "
            f"{true_positive_rate:.0%} found one"
        )
    if true_negative_rate is not None:
        print(
            f"  Of {len(expected_no_match_cases)} cases expecting no match: "
            f"{true_negative_rate:.0%} correctly abstained"
        )

    report = {
        "total_cases": total,
        "correct": correct_count,
        "accuracy": round(correct_count / total, 3),
        "true_positive_rate": (
            round(true_positive_rate, 3) if true_positive_rate is not None else None
        ),
        "true_negative_rate": (
            round(true_negative_rate, 3) if true_negative_rate is not None else None
        ),
        "results": results,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT_PATH}")

    return report


if __name__ == "__main__":
    run()
