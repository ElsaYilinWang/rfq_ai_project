# RFQ AI Project

## Overview
A production-oriented, human-supervised AI-assisted procurement workflow system.
Built to support real procurement operations involving RFQ handling, supplier sourcing,
quote comparison, and supplier follow-up.

> This project uses simple deterministic code where possible, and AI only where
> ambiguity or fuzzy matching is genuinely needed.

---

## Project Status
🚧 Module 1 — RFQ Parser & Validation — In Progress

---

## Module 1: RFQ Parser & Validation

### What it does
Takes an RFQ spreadsheet (`.xlsm`) exported from SAP Ariba and already entered
into the master tracker, and produces:

1. A **normalized JSON object** — structured, machine-readable, ready for downstream modules
2. A **modified Excel file** — the original spreadsheet with Excel comments added to
   each Material cell, surfacing flags and extracted references for human review

### What it does NOT do
- It does not discover suppliers
- It does not send emails
- It does not compare quotes
- It does not make sourcing decisions
- It does not use AI or LLMs — this module is fully deterministic

---

### Input
A full file path to an RFQ `.xlsm` file, for example:

```
C:/Users/ElsaWang/deci-ltd.com/DECI - Documents/700_Procurement/
2. SADARA RFQ/3434.0 6000186510/3434.0 6000186510.xlsm
```

The parser accepts the file path as a clean input parameter — it does not care
how the path was provided. This keeps the parser decoupled from the input method,
making it easy to plug in a UI later without changing the parser itself.

**v1 (current):** User provides file path manually via terminal input.

**Planned UI:** A web-based interface (Streamlit) supporting both file picker and
drag-and-drop, designed for non-technical procurement staff. Streamlit runs in a
browser — nothing to install for end users. Drag-and-drop is prioritised because
the procurement history contains 3400+ individual RFQ folders, making manual
folder navigation impractical.

The parser reads the **SPREADSHEET** sheet only.

Sheet structure:
- **Row 1** — RFQ-level metadata (RFQ number, client contact, date)
- **Row 2** — Column headers
- **Row 3 onwards** — Line items (one row per item)

---

### Client-side fields parsed (per line item)

| Field | Column | Notes |
|---|---|---|
| Material number | `Material` | Internal SAP material code |
| Long description | `Long description` | Full technical description, preserved as-is |
| Unit of measure | `UOM` | e.g. each, kg, meter |
| Quantity | `Quantity` | Integer |
| Sourcing identifier | `PN/MODEL/MFR` | Part number / model / manufacturer — may contain multiple entries |
| Lead time requested | `Lead time Requested` | Contains date and week count |

---

### Output schema

#### RFQ-level
```json
{
  "metadata": {
    "source_file_path": "/path/to/3434.0_6000186510.xlsm",
    "internal_reference": "3434",
    "rfq_number": "6000186510",
    "client_contact": "Mr. AlDossari, Mohammed F",
    "date": "3/11/2026"
  },
  "items": [ ],
  "overall_flags": []
}
```

#### Line item level
```json
{
  "material_number": "1000148955",
  "long_description": "GEAR,BEVEL: SET WITH PINION SHAFT...",
  "uom": "each",
  "quantity": 2,
  "lead_time_date": "23/08/2028",
  "lead_time_weeks": 128,
  "sourcing_identifiers": [
    {
      "part_number": "C29-0320B251",
      "manufacturer": "HANSEN"
    }
  ],
  "flags": [],
  "extracted_references": []
}
```

---

### Validation rules

#### Hard errors (parser stops immediately)
| Condition | Behaviour |
|---|---|
| RFQ number missing from cell A1 | Raise error, stop parsing |
| RFQ number in filename does not match cell A1 | Raise error, stop parsing |
| No line items found in SPREADSHEET sheet | Raise error, stop parsing |

#### Item-level flags (parsing continues, item is flagged)
| Condition | Flag |
|---|---|
| `PN/MODEL/MFR` field is entirely blank | `missing_sourcing_identifier` |
| A sourcing identifier entry has no part number | `missing_part_number` |
| A sourcing identifier entry has no manufacturer | `missing_manufacturer` |

#### RFQ-level overall flags
Populated if any line items carry flags. Signals to the reviewer that
at least one item needs attention.

---

### PN/MODEL/MFR parsing rules
- Multiple entries are separated by newline `\n`
- Each entry is split into `part_number` and `manufacturer` using ` - ` or ` / ` as separator
- Validation runs **after** parsing is complete — not during
- If blank, item is flagged as `missing_sourcing_identifier`

---

### Lead time parsing rules
- Expected format: `28/05/2026\n11 Weeks`
- Date extracted using pattern `DD/MM/YYYY`
- Weeks extracted using pattern `<number> Weeks`
- Both stored separately as `lead_time_date` and `lead_time_weeks`

---

### Output files

#### 1. JSON file
- Saved to a user-specified output folder
- Named: `parsed_<rfq_number>.json`
- Contains the full normalized RFQ object

#### 2. Modified Excel file
- Saved back to the original file location (overwrites original)
- Original data is completely unchanged
- Excel comments are added to the **Material cell** of each line item
- Each comment contains all flags and extracted references for that item
- No new columns are added

---

### Project structure
```
rfq_ai_project/
│
├── .env                    # API keys — never committed
├── .gitignore
├── README.md
│
├── parser/
│   ├── __init__.py
│   ├── parser.py           # Main RFQParser class — file I/O, orchestration
│   ├── validators.py       # Flag generation logic
│   └── schemas.py          # Dataclasses: ParsedRFQ, LineItem, SourcingIdentifier
│
├── output/                 # JSON output files — gitignored
│
├── mock_data/              # Test RFQ files — .xlsm files gitignored
│   └── README.md
│
└── tests/
    ├── __init__.py
    └── test_parser.py
```

---

### Known limitations and future considerations
- **BPA (Blanket Purchase Agreement) files** — RFQs with hundreds or thousands of
  line items are out of scope for v1. In practice these are rare (~10% of RFQs) and
  are strategically split into chunks before processing. BPA support is a planned
  future enhancement.
- **File path formats** — the parser handles both Windows (`C:\Users\...`) and
  Unix-style (`/Users/...`) paths via Python's `pathlib`, making it portable across
  machines and operating systems.

---

### Dependencies
```
openpyxl
pathlib
dataclasses
re
json
```

---

### Usage (planned)
```python
from parser.parser import RFQParser

parser = RFQParser(file_path="path/to/3434.0_6000186510.xlsm")
result = parser.parse(output_json_folder="path/to/output/")
```

---

## Future Modules (Planned)
- **Module 2** — Supplier Discovery Assistant
- **Module 3** — Quote Extraction Assistant
- **Module 4** — Supplier Comparison Assistant
- **Module 5** — Human-supervised Submission Support

---

*Built as part of a career transition toward AI Workflow / AI Automation Engineering roles.*
