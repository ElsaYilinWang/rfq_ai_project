"""
Supplier Discovery Test Suite
==============================
Tests database operations and retrieval logic for Module 2.
Follows same pattern as test_parser.py for Module 1.
"""

import sys
import time
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from parser.logger import logger
from supplier_discovery import SupplierDiscoveryDB
from mock_data.mock_suppliers import mock_test_cases

TEST_DB_PATH = Path("knowledge_base/test_suppliers.db")


def run_single_test(test_case: dict, case_number: int, db: SupplierDiscoveryDB) -> bool:
    """
    Runs a single test case against the database functions.
    Returns True if passed, False if failed.
    """
    description = test_case["description"]
    last_supplier_id = None
    results = None
    failures = []

    for op in test_case["operations"]:
        operation = op["op"]
        params = op["params"].copy()

        # ── INSERT SUPPLIER ──────────────────────────────────────
        if operation == "insert_supplier":
            last_supplier_id = db.insert_supplier(
                supplier_name=params["supplier_name"],
                supplier_email=params["supplier_email"],
                mfr_name=params["mfr_name"]
            )

        # ── INSERT INTERACTION ───────────────────────────────────
        elif operation == "insert_interaction":
            if params.get("supplier_id") is None:
                params["supplier_id"] = last_supplier_id
            db.insert_interaction(
                supplier_id=params["supplier_id"],
                material_number=params["material_number"],
                mfr_name=params["mfr_name"],
                priority=params.get("priority"),
                status=params.get("status", "normal"),
                previous_folder_number=params.get("previous_folder_number"),
                reason=params.get("reason")
            )

        # ── INSERT INTERACTION WITH CUSTOM DATE ──────────────────
        elif operation == "insert_interaction_with_date":
            if params.get("supplier_id") is None:
                params["supplier_id"] = last_supplier_id
            conn = sqlite3.connect(TEST_DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO interaction
                (supplier_id, material_number, mfr_name, priority, status,
                 previous_folder_number, reason, date_created)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                params["supplier_id"],
                params["material_number"],
                params["mfr_name"],
                params.get("priority"),
                params.get("status", "normal"),
                params.get("previous_folder_number"),
                params.get("reason"),
                params["date_created"]
            ))
            conn.commit()
            conn.close()

        # ── SEARCH BY MATERIAL NUMBER ────────────────────────────
        elif operation == "search_by_material_number":
            results = db.search_by_material_number(params["material_number"])
            ranked = db.display_results_ranked(results)

            # Check count
            if "expected_count" in op:
                if op["expected_count"] == 0:
                    if ranked != "No suppliers found.":
                        failures.append({
                            "field": "result",
                            "expected": "No suppliers found.",
                            "got": ranked
                        })
                else:
                    total = sum(
                        len(v) for v in ranked.values()
                        if isinstance(v, list)
                    )
                    if total != op["expected_count"]:
                        failures.append({
                            "field": "count",
                            "expected": op["expected_count"],
                            "got": total
                        })

            # Check supplier email
            if "expected_email" in op:
                all_results = [
                    r for v in ranked.values()
                    if isinstance(v, list)
                    for r in v
                ]
                emails = [r["supplier_email"] for r in all_results]
                if op["expected_email"] not in emails:
                    failures.append({
                        "field": "supplier_email",
                        "expected": op["expected_email"],
                        "got": emails
                    })

            # Check staleness
            if "expected_needs_validation" in op:
                all_results = [
                    r for v in ranked.values()
                    if isinstance(v, list)
                    for r in v
                ]
                flags = [r["needs_validation"] for r in all_results]
                if op["expected_needs_validation"] not in flags:
                    failures.append({
                        "field": "needs_validation",
                        "expected": op["expected_needs_validation"],
                        "got": flags
                    })

            # Check special bucket
            if "expected_bucket" in op:
                if op["expected_bucket"] == "special":
                    if "special" not in ranked or len(ranked["special"]) == 0:
                        failures.append({
                            "field": "bucket",
                            "expected": "special",
                            "got": list(ranked.keys())
                        })
                    elif "expected_status" in op:
                        actual_status = ranked["special"][0]["status"]
                        if actual_status != op["expected_status"]:
                            failures.append({
                                "field": "status",
                                "expected": op["expected_status"],
                                "got": actual_status
                            })

        # ── SEARCH BY MFR ────────────────────────────────────────
        elif operation == "search_by_mfr":
            results = db.search_by_mfr(params["mfr_name"])
            ranked = db.display_results_ranked(results)

            if "expected_count" in op:
                total = sum(
                    len(v) for v in ranked.values()
                    if isinstance(v, list)
                )
                if total != op["expected_count"]:
                    failures.append({
                        "field": "count",
                        "expected": op["expected_count"],
                        "got": total
                    })

            if "expected_email" in op:
                all_results = [
                    r for v in ranked.values()
                    if isinstance(v, list)
                    for r in v
                ]
                emails = [r["supplier_email"] for r in all_results]
                if op["expected_email"] not in emails:
                    failures.append({
                        "field": "supplier_email",
                        "expected": op["expected_email"],
                        "got": emails
                    })

    # ── LOG RESULT ───────────────────────────────────────────────
    if not failures:
        logger.info(f"  PASS | Case {case_number}: {description}")
        return True
    else:
        logger.error(f"  FAIL | Case {case_number}: {description}")
        for failure in failures:
            logger.error(f"  Field:    {failure['field']}")
            logger.error(f"  Expected: {failure['expected']}")
            logger.error(f"  Got:      {failure['got']}")
        return False


def run_all_tests():
    """
    Runs all test cases and produces a full test report.
    """
   
    username = os.getenv('USERNAME') or os.getenv('USER') or 'unknown'
    start_time = time.time()

    # Use isolated test database
    db = SupplierDiscoveryDB(db_path=TEST_DB_PATH)

    logger.info("=" * 50)
    logger.info("TEST REPORT — Supplier Discovery Module")
    logger.info(f"Run by: {username}")
    logger.info(f"Total cases: {len(mock_test_cases)}")
    logger.info("-" * 50)

    passed = 0
    failed = 0

    for i, test_case in enumerate(mock_test_cases, start=1):
        clear_db(db)  # ← add this line
        result = run_single_test(test_case, i, db)
        if result:
            passed += 1
        else:
            failed += 1

    duration = round(time.time() - start_time, 2)

    logger.info("-" * 50)
    logger.info(f"Passed:   {passed}/{len(mock_test_cases)}")
    logger.info(f"Failed:   {failed}/{len(mock_test_cases)}")
    logger.info(f"Duration: {duration} seconds")

    if failed == 0:
        logger.info("Result: ALL TESTS PASSED")
    else:
        logger.error(f"Result: {failed} TEST(S) FAILED — review log above")

    logger.info("=" * 50)

    # Clean up test database
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

def clear_db(db):
    """Clear all tables between test cases"""
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM interaction")
    cursor.execute("DELETE FROM supplier")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    
    run_all_tests()