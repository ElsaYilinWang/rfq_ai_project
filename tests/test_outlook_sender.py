import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from email_distribution.schemas import MFRGroup, LineItemRow, MatchedSupplier, EmailDraft
from email_distribution.email_composer import compose_all_drafts
from email_distribution.outlook_sender import send_all_drafts
from email_sender.mock import MockEmailSender


def run_tests():
    passed = 0
    failed = 0
    start_time = time.time()

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

    print("\nTEST REPORT — Outlook Sender Module")
    print("=" * 40)

    # --- mock data ---
    mock_supplier_1 = MatchedSupplier(
        supplier_id=1,
        name="Parker Global",
        email="sales@parker.com",
        priority="P1",
        is_stale=False,
        country="USA"
    )

    mock_supplier_2 = MatchedSupplier(
        supplier_id=2,
        name="Parker EU",
        email="jason.will@exp1.com",
        priority="P2",
        is_stale=False,
        country="Germany"
    )

    mock_line_item = LineItemRow(
        material_number="1000124166",
        long_description="HYDRAULIC FILTER ELEMENT",
        uom="EA",
        quantity=4,
        part_number="HF-123"
    )

    mock_group = MFRGroup(
        manufacturer="PARKER",
        line_items=[mock_line_item],
        matched_suppliers=[mock_supplier_1, mock_supplier_2]
    )

    # --- compose drafts ---
    drafts = compose_all_drafts([mock_group], "26-2904", "SOH")
    check("compose_all_drafts produces 2 drafts", len(drafts), 2)

    # --- send drafts using mock sender ---
    sender = MockEmailSender()
    results = send_all_drafts(drafts, sender, "6000184918")

    # --- check results ---
    check("send_all_drafts returns 2 results", len(results), 2)
    check("first result status is success", results[0].status, "success")
    check("second result status is success", results[1].status, "success")
    check("first recipient correct", results[0].recipient, "sales@parker.com")
    check("second recipient correct", results[1].recipient, "jason.will@exp1.com")
    check("mock sender stored 2 drafts", len(sender.sent_drafts), 2)

    # --- summary ---
    print("=" * 40)
    print(f"Total cases: {passed + failed}")
    print(f"Passed: {passed}/{passed + failed}")
    print(f"Failed: {failed}/{passed + failed}")
    print(f"Duration: {time.time() - start_time:.2f} seconds")
    print(f"Result: {'ALL TESTS PASSED' if failed == 0 else 'SOME TESTS FAILED'}")


if __name__ == "__main__":
    run_tests()