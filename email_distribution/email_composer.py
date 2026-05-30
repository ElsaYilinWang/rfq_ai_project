from typing import List, Optional
from email_distribution.schemas import LineItemRow, MFRGroup, MatchedSupplier, EmailDraft


def generate_subject(internal_reference: str, client_code: str, manufacturer: str) -> str:
    
    subject = f"DECI RFQ {internal_reference} {client_code}"
    if manufacturer:
        subject = subject + f" - {manufacturer}"
    return subject


def generate_salutation(email: str, notes: Optional[str] = None) -> str:
    
    if notes:
        return f"Dear {notes},"
    
    GENERIC_PREFIXES = ["sales", "info", "enquiries", "procurement", "quotes", "quote"]
    prefix = email.split('@')[0].lower()
    if prefix in GENERIC_PREFIXES:
        return "Dear Sir/Madam,"
    
    return f"Dear {email.split('.')[0].capitalize()},"
    

def generate_body(line_items: List[LineItemRow]) -> str:
    template = (
        "I hope you are doing well.\n\n"
        "Please see below request for quotation. "
        "Kindly share a technical datasheet if possible.\n\n"
    )
    header = "Material | Long Description | UOM | Quantity | PN/MFR\n"
    divider = "-" * 60 + "\n"

    rows = ""
    for item in line_items:
        rows += f"{item.material_number} | {item.long_description} | {item.uom} | {item.quantity} | {item.part_number}\n"
    
    return template + header + divider + rows


def select_signature(country: Optional[str] = None) -> str:
    GCC_COUNTRIES = ["UAE", "Qatar", "Bahrain", "KSA", "Saudi Arabia", "Oman"]
    IRELAND_SIGNATURE = """Kind regards,
        Elsa Wang
        Procurement Engineer
        Unit 1 Enterprise Centre, Childers Road, Ballysimon, Limerick, V94 HX70, Ireland."""

    SAUDI_SIGNATURE = """Kind regards,
        Elsa Wang
        Procurement Engineer
        Unit No: 4608, Additional No: 8292, Building No: 3141, 
        Anas Ibn Malik Street, Al Malqa District, Riyadh, Kingdom of Saudi Arabia."""
    
    if country in GCC_COUNTRIES:
        return SAUDI_SIGNATURE
    
    return IRELAND_SIGNATURE

def generate_email_draft(
    manufacturer: str,
    internal_reference: str,
    client_code: str,
    line_items: List[LineItemRow],
    supplier: MatchedSupplier,
) -> EmailDraft:
    subject = generate_subject(internal_reference, client_code, manufacturer)
    salutation = generate_salutation(supplier.email, supplier.notes)
    body = generate_body(line_items)
    signature = select_signature(supplier.country)

    return EmailDraft(
        manufacturer=manufacturer,
        to=[supplier.email],
        subject=subject,
        salutation=salutation,
        body=body,
        signature=signature
    )

def compose_all_drafts(mfr_groups: List[MFRGroup], internal_reference: str, client_code: str):
    #Accept mfr_groups, internal_reference, client_code as parameters
    drafts = []
    #Loop through each MFRGroup
    for group in mfr_groups:
        #Loop through each MatchedSupplier in the group
        for supplier in group.matched_suppliers:
            #Call generate_email_draft() for each supplier
            drafts.append( generate_email_draft(group.manufacturer, internal_reference, client_code, group.line_items, supplier))

    return drafts

    