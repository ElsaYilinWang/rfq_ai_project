# eval/run_eval.py

"""
Evaluation harness v1 for the RFQ AI review workflow.

Loads known test cases from eval/test_cases.json and checks them
against ACTUAL output from the FastAPI review layer — not hardcoded
values. This uses FastAPI's TestClient, which runs the app in-process
(no `uvicorn` server needs to be running), so this script works the
same way locally and in CI.

Two kinds of cases are supported:

  - Item-level cases (expected_status / expected_next_action):
    Checked against a specific line item from GET /rfqs/sample/items,
    identified by material_number. Status/next_action are derived
    from that item's flags using the same clean/warning logic as
    parsed_rfq_to_api_response, just applied to one item instead of
    the whole RFQ.

  - Supplier-candidate cases (expected_supplier_source /
    expected_human_review_required): Checked against the actual
    GET /rfqs/sample/supplier-candidates response.

This only exercises the existing mock /rfqs/sample* endpoints — it
does not connect the real Excel parser or SQLite supplier database.
"""

import json
import sys
from pathlib import Path

# Make the project root importable regardless of where this script is
# run from. Without this, `python eval/run_eval.py` fails with
# "No module named 'api'", because Python only adds eval/ itself to
# sys.path, not the project root two levels up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"
REPORT_PATH = Path(__file__).parent / "eval_report.json"


def derive_item_status(flags):
    """
    Same clean-vs-warning logic used at the RFQ level in
    parsed_rfq_to_api_response, applied to a single item's flags.
    """
    if flags:
        return "validation_warning", "review_required"
    return "parsed_successfully", "supplier_discovery_ready"


def run_item_level_case(case, items):
    item = next(
        (i for i in items if i["material_number"] == case["material_number"]),
        None,
    )

    if item is None:
        return False, f"No item found with material_number='{case['material_number']}'."

    actual_status, actual_next_action = derive_item_status(item["flags"])

    passed = (
        actual_status == case["expected_status"]
        and actual_next_action == case["expected_next_action"]
    )

    notes = (
        f"Expected status='{case['expected_status']}', "
        f"next_action='{case['expected_next_action']}'. "
        f"Actual status='{actual_status}', next_action='{actual_next_action}'."
    )

    return passed, notes


def run_supplier_case(case, supplier_candidates):
    match = next(
        (
            c for c in supplier_candidates
            if c["source"] == case["expected_supplier_source"]
        ),
        None,
    )

    if match is None:
        return (
            False,
            f"No supplier candidate found with "
            f"source='{case['expected_supplier_source']}'."
        )

    passed = (
        match["human_review_required"] == case["expected_human_review_required"]
    )

    notes = (
        f"Found candidate with source='{match['source']}', "
        f"human_review_required={match['human_review_required']} "
        f"(expected {case['expected_human_review_required']})."
    )

    return passed, notes


def run_eval():
    test_cases = json.loads(TEST_CASES_PATH.read_text())

    # Call the real endpoints — this is the "actual" side of the check.
    items_response = client.get("/rfqs/sample/items")
    items = items_response.json()["items"]

    supplier_response = client.get("/rfqs/sample/supplier-candidates")
    supplier_candidates = supplier_response.json()["supplier_candidates"]

    results = []

    for case in test_cases:
        if "expected_supplier_source" in case:
            passed, notes = run_supplier_case(case, supplier_candidates)
        else:
            passed, notes = run_item_level_case(case, items)

        results.append({
            "case_id": case["case_id"],
            "passed": passed,
            "notes": notes,
        })

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total - passed_count

    report = {
        "total_cases": total,
        "passed": passed_count,
        "failed": failed_count,
        "results": results,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2))

    print("RFQ Evaluation Report")
    print(f"Total cases: {total}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")

    return report


if __name__ == "__main__":
    run_eval()