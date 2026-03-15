from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RFQMetadata:
    source_file_path: str
    internal_reference: str
    rfq_number: str
    client_contact: str
    date: str


@dataclass
class SourcingIdentifier:
    part_number: Optional[str] = None
    manufacturer: Optional[str] = None


@dataclass
class ExtractedReference:
    type: str
    value: str


@dataclass
class LineItem:
    material_number: str
    long_description: str
    uom: str
    quantity: int
    lead_time_date: Optional[str] = None
    lead_time_weeks: Optional[int] = None
    sourcing_identifiers: List[SourcingIdentifier] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    extracted_references: List[ExtractedReference] = field(default_factory=list)


@dataclass
class ParsedRFQ:
    metadata: RFQMetadata
    items: List[LineItem] = field(default_factory=list)
    overall_flags: List[str] = field(default_factory=list)