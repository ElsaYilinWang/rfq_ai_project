"""
Supplier Discovery Test Suite
==============================
Tests insert, search, and staleness logic.
Follows same pattern as test_parser.py for Module 1.
"""

import sys
import os
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from supplier_discovery import SupplierDiscoveryDB
from mock_data.mock_suppliers import mock_supplier_test_cases

# Use a separate test database — never touch real knowledge base
TEST_DB_PATH = Path("knowledge_base/test_suppliers.db")


def setup_test_db():
    """Create a fresh test database before each run"""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    return SupplierDiscoveryDB(db_path=TEST_DB_PATH)


def insert_with_override_date(db, supplier_id, test_case):
    """
    Special insert for stale test case —
    overrides date_created to simulate old record
    """
    override_date = test_case["input"].get("override_date")
    if not override_date:
        return

    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE interaction
        SET date_created = ?
        WHERE supplier_id = ?
    ''', (override_date.isoformat(), supplier_id))
    conn.commit()
    conn.close()


def run_single_test(db, test_case, case_number):
    """
    Runs a single test case.
    Returns True if passed, False if failed.
    """
    description = test_case["description"]
    input_data = test_case["input"]
    search = test_case["search"]
    expected = test_case["expected"]

    failures = []

    # Step 1 — Insert data if provided
    supplier_id = None
    if input_data:
        supplier_id = db.insert_supplier(
            supplier_name=input_data["supplier_name"],
            supplier_email=input_data["supplier_email"],
            mfr_name=input_data["mfr_name"]
        )
        db.insert_interaction(
            supplier_id=supplier_id,
            material_number=input_data["material_number"],
            mfr_name=input_data["mfr_name"],
            priority=input_data["priority"],
            previous_folder_number=input_data.get("previous_folder_number"),
            reason=input_data.get("reason")
        )

        # Override date if stale test case
        if input_data.get("override_date"):
            insert_with_override_date(db, supplier_id, test_case)

    # Step 2 — Search
    if search["type"] == "material_number":
        results = db.search_by_material_number(search["value"])
    else:
        results = db.search_by_mfr(search["value"])

    # Step 3 — Check result count
    if len(results) != expected["result_count"]:
        failures.append({
            "field": "result_count",
            "expected": expected["result_count"],
            "got": len(results)
        })

    # Step 4 — Check supplier details if results exist
    if results and expected["result_count"] > 0:
        ranked = db.display_results_ranked(results)

        # Flatten ranked results for checking
        all_results = []
        for tier in ['P1', 'P2', 'P3']:
            all_results.extend(ranked.get(tier, []))

        # Check supplier email
        if "supplier_email" in expected:
            emails = [r["supplier_email"] for r in all_results]
            if expected["supplier_email"] not in emails:
                failures.append({
                    "field": "supplier_email",
                    "expected": expected["supplier_email"],
                    "got": emails
                })

        # Check priority
        if "priority" in expected:
            priorities = [r["priority"] for r in all_results]
            if expected["priority"] not in priorities:
                failures.append({
                    "field": "priority",
                    "expected": expected["priority"],
                    "got": priorities
                })

        # Check staleness flag
        if "needs_validation" in expected:
            flags = [r["needs_validation"] for r in all_results]
            if expected["needs_validation"] not in flags:
                failures.append({
                    "field": "needs_validation",
                    "expected": expected["needs_validation"],
                    "got": flags
                })

    # Step 5 — Report
    if not failures:
        print(f"  PASS | Case {case_number}: {description}")
        return True
    else:
        print(f"  FAIL | Case {case_number}: {description}")
        for f in failures:
            print(f"         Field:    {f['field']}")
            print(f"         Expected: {f['expected']}")
            print(f"         Got:      {f['got']}")
        return False


def run_all_tests():
    """
    Runs all supplier discovery test cases.
    Produces a clean test report.
    """
    username = os.getenv('USERNAME') or os.getenv('USER') or 'unknown'
    start_time = time.time()

    print("=" * 50)
    print("TEST REPORT — Supplier Discovery Module")
    print(f"Run by: {username}")
    print(f"Total cases: {len(mock_supplier_test_cases)}")
    print("-" * 50)

    # Fresh test database for every run
    db = setup_test_db()

    passed = 0
    failed = 0

    for i, test_case in enumerate(mock_supplier_test_cases, start=1):
        result = run_single_test(db, test_case, i)
        if result:
            passed += 1
        else:
            failed += 1

    # Cleanup test database
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    duration = round(time.time() - start_time, 2)

    print("-" * 50)
    print(f"Passed:   {passed}/{len(mock_supplier_test_cases)}")
    print(f"Failed:   {failed}/{len(mock_supplier_test_cases)}")
    print(f"Duration: {duration} seconds")

    if failed == 0:
        print("Result: ALL TESTS PASSED")
    else:
        print(f"Result: {failed} TEST(S) FAILED — review output above")

    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()