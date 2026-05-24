import sys
import time
from pathlib import Path
from typing import List, Optional

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from email_distribution.rfq_grouper import load_parsed_rfq, group_by_manufacturer

MOCK_DIR = Path(__file__).parent.parent / "mock_data"



def run_tests():
    passed = 0
    failed = 0

    def check(description, actual, expected):
        nonlocal passed, failed
        if actual == expected:
            print(f"  PASS — {description}")
            passed += 1
        else:
            print(f"  FAIL — {description}")
            print(f"         expected: {expected}")
            print(f"         actual:   {actual}")
            failed += 1

    print("\nTEST REPORT — RFQ Grouper Module")
    print("=" * 40)

    # --- load and group ---
    parsed_rfq = load_parsed_rfq("6000184918", base_dir=MOCK_DIR)
    result = group_by_manufacturer(parsed_rfq)

    # --- find groups by manufacturer name ---
    frick_group = next((g for g in result if g.manufacturer == "FRICK"), None)
    parker_group = next((g for g in result if g.manufacturer == "PARKER"), None)

    # --- test cases ---
    check("Total number of MFR groups", len(result), 2)
    check("FRICK group exists", frick_group is not None, True)
    check("PARKER group exists", parker_group is not None, True)
    check("FRICK has 2 line items", len(frick_group.line_items) if frick_group else 0, 2)
    check("PARKER has 1 line item", len(parker_group.line_items) if parker_group else 0, 1)
    check("FRICK first item material number", frick_group.line_items[0].material_number, "1000124164")
    check("PARKER item has no part number", parker_group.line_items[0].part_number, None)

    # --- summary ---
    print("=" * 40)
    print(f"Total cases: {passed + failed}")
    print(f"Passed: {passed}/{passed + failed}")
    print(f"Failed: {failed}/{passed + failed}")
    print(f"Duration: {time.time():.2f} seconds")
    print(f"Result: {'ALL TESTS PASSED' if failed == 0 else 'SOME TESTS FAILED'}")


if __name__ == "__main__":
    run_tests()