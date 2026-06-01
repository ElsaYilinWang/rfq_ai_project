import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from parser.parser import parse_rfq
from email_distribution.rfq_grouper import load_parsed_rfq, group_by_manufacturer
from email_distribution.supplier_matcher import match_suppliers_to_groups
from email_distribution.email_composer import compose_all_drafts
from email_distribution.outlook_sender import send_all_drafts
from email_distribution.logger import get_logger

logger = get_logger()

DB_PATH = Path(__file__).parent / "knowledge_base" / "suppliers.db"


def extract_client_code(file_path: Path) -> str:
    """Extract client code from file path — to be refined with work laptop."""
    # placeholder until work laptop session confirms exact path structure
    return "UNKNOWN"


def main():
    print("\nDECI RFQ AI System — Main Pipeline")
    print("=" * 40)

    # --- Step 1: get RFQ file path ---
    print("\nStep 1: Enter path to RFQ Excel file:")
    raw_path = input("> ").strip()
    rfq_path = Path(raw_path)

    if not rfq_path.exists():
        print(f"❌ File not found: {rfq_path}")
        sys.exit(1)

    # --- parse RFQ ---
    print("\nParsing RFQ...")
    try:
        parse_rfq(str(rfq_path))
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        logger.error(f"Parsing failed: {e}")
        sys.exit(1)

    # --- load parsed output ---
    # extract rfq number from filename
    rfq_number = rfq_path.stem.split("_")[-1]
    parsed_rfq = load_parsed_rfq(rfq_number)

    internal_reference = parsed_rfq["metadata"]["internal_reference"]
    client_code = extract_client_code(rfq_path)

    print(f"✓ RFQ Number: {parsed_rfq['metadata']['rfq_number']}")
    print(f"✓ Internal Reference: {internal_reference}")
    print(f"✓ Client Code: {client_code}")
    print(f"✓ Line items found: {len(parsed_rfq['items'])}")

    # --- Step 2: supplier lookup ---
    print("\nStep 2: Looking up suppliers...")
    mfr_groups = group_by_manufacturer(parsed_rfq)
    mfr_groups = match_suppliers_to_groups(mfr_groups, DB_PATH)

    for group in mfr_groups:
        stale_count = sum(1 for s in group.matched_suppliers if s.is_stale)
        stale_warning = f"({stale_count} stale ⚠️)" if stale_count > 0 else ""
        no_supplier_warning = "⚠️ no suppliers found" if len(group.matched_suppliers) == 0 else ""
        print(f"  {group.manufacturer} — {len(group.matched_suppliers)} suppliers found {stale_warning} {no_supplier_warning}")

    # --- Step 3: human review ---
    print("\nStep 3: Review supplier list?")
    print("[Y] to continue / [N] to abort")
    choice = input("> ").strip().upper()
    if choice != "Y":
        print("Aborted by user.")
        sys.exit(0)

    # --- Step 4: attachments ---
    print("\nStep 4: Do you have any attachments? (nameplate photo, datasheet, drawing)")
    print("[Y] Yes / [N] No")
    has_attachments = input("> ").strip().upper()
    attachments = []
    if has_attachments == "Y":
        print("Enter attachment path(s), one per line. Empty line to finish:")
        while True:
            attachment = input("> ").strip()
            if not attachment:
                break
            if Path(attachment).exists():
                attachments.append(attachment)
                print(f"  ✓ Added: {attachment}")
            else:
                print(f"  ⚠️ File not found, skipping: {attachment}")

    # --- Step 5: generate and send drafts ---
    print("\nStep 5: Generating email drafts...")
    drafts = compose_all_drafts(mfr_groups, internal_reference, client_code)

    # add attachments to all drafts
    for draft in drafts:
        draft.attachments = attachments

    # use mock sender on private laptop, outlook sender on work laptop
    try:
        from email_sender.outlook import OutlookEmailSender
        sender = OutlookEmailSender()
        print("  Using Outlook sender.")
    except Exception:
        from email_sender.mock import MockEmailSender
        sender = MockEmailSender()
        print("  Outlook not available — using mock sender.")

    results = send_all_drafts(drafts, sender, parsed_rfq['metadata']['rfq_number'])

    print("\nResults:")
    for result in results:
        icon = "✓" if result.status == "success" else "❌"
        print(f"  {icon} {result.manufacturer} — {result.recipient}")

    print("\n" + "=" * 40)
    print("Drafts saved to Outlook Drafts folder.")
    print("Please review and send manually.")
    print("=" * 40)


if __name__ == "__main__":
    main()