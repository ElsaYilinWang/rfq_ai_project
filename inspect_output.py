import sys
sys.path.insert(0, '.')
from parser.parser import RFQParser
from parser.schemas import ExtractedReference
import openpyxl

# Test with a synthetic unstructured PN/MODEL/MFR entry
parser = RFQParser.__new__(RFQParser)

# Simulate what _parse_pn_model_mfr returns for unstructured entries
result = parser._parse_pn_model_mfr(
    "BUTTING\nJARO OY\nSitai Inox Srl\nAlthammer GmbH u. Co.KG\n2000766198 UNKNOWN NL Arcus Nederland BV"
)

sourcing_identifiers, extracted_refs, flags = result

print("sourcing_identifiers:", sourcing_identifiers)
print("extracted_refs:", extracted_refs)
print("flags:", flags)
print()

if extracted_refs:
    print("First ref type:", type(extracted_refs[0]))
    print("First ref:", extracted_refs[0])
    print("ref.type:", extracted_refs[0].type)
    print("ref.value:", extracted_refs[0].value)

from parser.schemas import LineItem, SourcingIdentifier

# Build a LineItem with the extracted refs
item = LineItem(
    material_number="1000090583",
    long_description="TEST",
    uom="each",
    quantity=1,
    sourcing_identifiers=sourcing_identifiers,
    flags=flags,
    extracted_references=extracted_refs
)

print("\nLineItem extracted_references:")
print(item.extracted_references)
print("Is empty?", not item.extracted_references)

# Simulate comment building
comment_lines = []

if item.flags:
    comment_lines.append("FLAGS:")
    for flag in item.flags:
        comment_lines.append(f"  - {flag}")

if item.extracted_references:
    comment_lines.append("REFERENCES:")
    for ref in item.extracted_references:
        comment_lines.append(f"  - {ref.type}: {ref.value}")

comment_text = "\n".join(comment_lines)
print("\nGenerated comment:")
print(comment_text)