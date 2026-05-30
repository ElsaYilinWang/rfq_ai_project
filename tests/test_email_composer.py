import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from email_distribution.email_composer import (
    generate_subject, generate_salutation, 
    generate_body, select_signature, compose_all_drafts
)
from email_distribution.schemas import MFRGroup, LineItemRow, MatchedSupplier

# --- mock data ---
mock_supplier_generic = MatchedSupplier(
    supplier_id=1,
    name="Parker Global",
    email="sales@parker.com",
    priority="P1",
    is_stale=False,
    country="USA"
)

mock_supplier_personal = MatchedSupplier(
    supplier_id=2,
    name="Parker EU",
    email="jason.will@exp1.com",
    priority="P2",
    is_stale=True,
    country="Germany"
)

mock_supplier_gcc = MatchedSupplier(
    supplier_id=3,
    name="Parker KSA",
    email="ahmed.ali@parker.com.sa",
    priority="P1",
    is_stale=False,
    country="KSA"
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
    matched_suppliers=[mock_supplier_generic, mock_supplier_personal]
)


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

    print("\nTEST REPORT — Email Composer Module")
    print("=" * 40)

    # --- test generate_subject ---
    check("Subject with manufacturer",
        generate_subject("26-2904", "SOH", "PARKER"),
        "DECI RFQ 26-2904 SOH - PARKER")
    
    check("Subject without manufacturer",
        generate_subject("26-2904", "SOH", ""),
        "DECI RFQ 26-2904 SOH")

    # --- test generate_salutation ---
    check("Salutation generic email",
        generate_salutation("sales@parker.com"),
        'Dear Sir/Madam,')
    
    check("Salutation personal email",
        generate_salutation("jason.will@exp1.com"),
        'Dear Jason,')
    
    check("Salutation with notes",
        generate_salutation("jason.will@exp1.com", notes="Jason"),
        'Dear Jason,')

    # --- test select_signature ---
    check("Ireland signature for USA supplier",
        "Ireland" in select_signature("USA"),
        True)
    
    check("Saudi signature for KSA supplier",
        "Riyadh" in select_signature("KSA"),
        True)

    # --- test compose_all_drafts ---
    drafts = compose_all_drafts([mock_group], "26-2904", "SOH")
    check("compose_all_drafts returns 2 drafts",
        len(drafts),
        2)
    
    check("First draft subject correct",
        drafts[0].subject,
        "DECI RFQ 26-2904 SOH - PARKER")

    # --- summary ---
    print("=" * 40)
    print(f"Total cases: {passed + failed}")
    print(f"Passed: {passed}/{passed + failed}")
    print(f"Failed: {failed}/{passed + failed}")
    print(f"Result: {'ALL TESTS PASSED' if failed == 0 else 'SOME TESTS FAILED'}")


if __name__ == "__main__":
    run_tests()