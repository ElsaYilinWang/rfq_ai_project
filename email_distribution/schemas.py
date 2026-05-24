from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LineItemRow:
    material_number: str
    long_description: str
    uom: str
    quantity: int
    part_number: Optional[str] = None


@dataclass
class MFRGroup:
    manufacturer: str
    line_items: List[LineItemRow]


@dataclass
class EmailDraft:
    manufacturer: str
    to: List[str]
    subject: str
    salutation: str
    body: str
    signature: str
    cc: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)


@dataclass
class SendResult:
    timestamp: str
    manufacturer: str
    recipient: str
    subject: str
    status: str
    error_message: str = ""