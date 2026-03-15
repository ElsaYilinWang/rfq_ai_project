"""
RFQ Parser Test Suite
======================
Tests parsing and validation logic against known test cases.
Produces a detailed test report in the log file.
"""

import sys
import time
import os
from pathlib import Path
from dataclasses import asdict

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from parser.logger import logger
from parser.schemas import LineItem, SourcingIdentifier
from parser.validators import validate_sourcing_identifiers
from parser.parser import RFQParser
from tests.test_data import all_test_cases


def compare_field(field_name, expected, actual):
    """
    Compares a single field between expected and actual.
    Returns 'pass' or 'fail' with a reason.
    """
    expected_val = expected.get(field_name)
    actual_val = actual.get(field_name)

    if expected_val == actual_val:
        return "pass", None

    return "fail", {
        "field": field_name,
        "expected": expected_val,
        "got": actual_val
    }


def run_single_test(test_case: dict, case_number: int) -> bool:
    """
    Runs a single test case against the parser functions.
    Logs detailed results.
    Returns True if passed, False if failed.
    """
    description = test_case["description"]
    input_data = test_case["input"]
    expected = test_case["expected"]

    # Build a parser instance without a file
    # so we can test individual functions in isolation
    parser = RFQParser.__new__(RFQParser)

    # Test PN/MODEL/MFR parsing
    sourcing_identifiers, extracted_refs, pn_flags = parser._parse_pn_model_mfr(
        input_data["pn_model_mfr"]
    )

    # Test lead time parsing
    lead_time_date, lead_time_weeks = parser._parse_lead_time(
        input_data["lead_time_str"]
    )

    # Build LineItem
    item = LineItem(
        material_number=input_data["material_number"],
        long_description=input_data["long_description"],
        uom=input_data["uom"],
        quantity=input_data["quantity"],
        lead_time_date=lead_time_date,
        lead_time_weeks=lead_time_weeks,
        sourcing_identifiers=sourcing_identifiers,
        flags=pn_flags,
        extracted_references=extracted_refs
    )

    # Run validation
    item.flags = validate_sourcing_identifiers(item)

    # Convert to dict for comparison
    actual = {
        "material_number": item.material_number,
        "uom": item.uom,
        "quantity": item.quantity,
        "lead_time_date": item.lead_time_date,
        "lead_time_weeks": item.lead_time_weeks,
        "sourcing_identifiers": [
            asdict(si) for si in item.sourcing_identifiers
        ],
        "flags": item.flags
    }

    # Compare fields
    fields_to_check = [
        "material_number",
        "uom",
        "quantity",
        "lead_time_date",
        "lead_time_weeks",
        "sourcing_identifiers",
        "flags"
    ]

    failures = []
    for field in fields_to_check:
        status, reason = compare_field(field, expected, actual)
        if status == "fail":
            failures.append(reason)

    # Log result
    if not failures:
        logger.info(
            f"TEST | Case {case_number}: PASS | {description}"
        )
        return True
    else:
        logger.error(
            f"TEST | Case {case_number}: FAIL | {description}"
        )
        for failure in failures:
            logger.error(
                f"TEST |   Field:    {failure['field']}"
            )
            logger.error(
                f"TEST |   Expected: {failure['expected']}"
            )
            logger.error(
                f"TEST |   Got:      {failure['got']}"
            )
        return False


def run_all_tests():
    """
    Runs all test cases and produces a full test report in the log.
    """
    username = os.getenv('USERNAME') or os.getenv('USER') or 'unknown'
    start_time = time.time()

    logger.info("=" * 50)
    logger.info("TEST REPORT — RFQ Parser")
    logger.info(f"Run by: {username}")
    logger.info(f"Total cases: {len(all_test_cases)}")
    logger.info("-" * 50)

    passed = 0
    failed = 0

    for i, test_case in enumerate(all_test_cases, start=1):
        result = run_single_test(test_case, i)
        if result:
            passed += 1
        else:
            failed += 1

    duration = round(time.time() - start_time, 2)

    logger.info("-" * 50)
    logger.info(f"Passed:   {passed}/{len(all_test_cases)}")
    logger.info(f"Failed:   {failed}/{len(all_test_cases)}")
    logger.info(f"Duration: {duration} seconds")

    if failed == 0:
        logger.info("Result: ALL TESTS PASSED")
    else:
        logger.error(
            f"Result: {failed} TEST(S) FAILED — review log above"
        )

    logger.info("=" * 50)


if __name__ == "__main__":
    run_all_tests()