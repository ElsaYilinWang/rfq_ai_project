"""
RFQ Extraction Evaluator
==========================
Runs extract_rfq() against the test dataset and reports results.
"""

from main import extract_rfq, validate_rfq
from test_data import test_rfqs


def compare_field(field_name, expected, actual):
    """
    Compares a single field between expected and actual results.
    Returns 'pass', 'fail', or 'missing'.
    """
    if field_name not in actual:
        return "missing"

    expected_val = expected.get(field_name)
    actual_val = actual.get(field_name)

    # Both None means the field was correctly identified as absent
    if expected_val is None and actual_val is None:
        return "pass"

    # Quantity: compare as numbers
    if field_name == "quantity":
        try:
            return "pass" if int(actual_val) == int(expected_val) else "fail"
        except (TypeError, ValueError):
            return "fail"

    # Strings: compare lowercase to ignore case differences
    if isinstance(expected_val, str) and isinstance(actual_val, str):
        if expected_val.lower() in actual_val.lower() or actual_val.lower() in expected_val.lower():
            return "pass"

    # Fallback: exact match
    return "pass" if expected_val == actual_val else "fail"


def run_evaluation():
    """
    Runs extraction on all test cases and prints a detailed report.
    """
    fields_to_check = ["manufacturer", "product", "quantity", "delivery_time"]

    total_fields = 0
    passed_fields = 0
    failed_cases = []

    print("\n" + "=" * 60)
    print("RFQ EXTRACTION EVALUATION REPORT")
    print("=" * 60)

    for i, test in enumerate(test_rfqs):
        rfq_text = test["input"]
        expected = test["expected"]

        print(f"\n--- Test {i + 1} ---")
        print(f"Input: {rfq_text}")

        result = extract_rfq(rfq_text)

        if result is None:
            print("RESULT: Extraction failed (no JSON returned)")
            failed_cases.append(i + 1)
            total_fields += len(fields_to_check)
            continue

        case_passed = True

        for field in fields_to_check:
            status = compare_field(field, expected, result)
            total_fields += 1

            if status == "pass":
                passed_fields += 1
                icon = "PASS"
            else:
                icon = "FAIL"
                case_passed = False

            expected_val = expected.get(field)
            actual_val = result.get(field)
            print(f"  {field}: {icon}  (expected: {expected_val} | got: {actual_val})")

        if not case_passed:
            failed_cases.append(i + 1)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total test cases:  {len(test_rfqs)}")
    print(f"Field accuracy:    {passed_fields}/{total_fields} ({100 * passed_fields // total_fields}%)")

    if failed_cases:
        print(f"Cases with issues: {failed_cases}")
    else:
        print("All cases passed!")

    print("=" * 60)


if __name__ == "__main__":
    run_evaluation()