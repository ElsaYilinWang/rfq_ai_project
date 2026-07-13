
# RFQ AI — Automated Procurement Workflow System

> *An AI-assisted system that transforms a repetitive, manual procurement process into a semi-automated pipeline — where the human only makes the decisions that matter.*

---

# RFQ AI — AI-Assisted Procurement Workflow System

*An AI-assisted workflow automation project for industrial RFQ processing.

This project parses RFQ-style input, validates key procurement fields, discovers likely suppliers from a local knowledge base, generates supplier-specific RFQ email drafts, and keeps the human in control before any supplier communication is sent.*

## Project Status / Data Disclaimer

This is a private portfolio project inspired by real procurement workflow experience. It was built independently and uses mock or sanitized RFQ-style data for demonstration.

It was not deployed at DECI and does not contain confidential company, client, supplier, pricing, or RFQ data.

## What This Demonstrates

- Practical workflow automation for an enterprise procurement process
- Deterministic-first engineering: rules and validation before AI assistance
- Human-in-the-loop checkpoints for supplier selection and email review
- Modular Python architecture: parser, supplier discovery, email generator, sender abstraction
- Testable components with schemas, logging, mock sender, and audit-trail outputs


## What Is This?

Every day, procurement engineers receive purchase requests from industrial clients. For each request, they must:

1. Read a complex Excel spreadsheet from SAP Ariba
2. Identify the right manufacturers and part numbers
3. Search their inbox and memory for past supplier contacts
4. Write and send individual RFQ (Request for Quotation) emails to each supplier

For a single RFQ with 10 line items across 5 manufacturers, this can mean **hours of repetitive manual work** — copying data, formatting emails, and deciding which suppliers to contact.

**This system automates that entire workflow.** It reads the Excel file, finds the right suppliers, writes the emails, and creates ready-to-send Outlook drafts — all with a single command. The engineer reviews, edits if needed, and clicks send.

Think of it like a QC analyst's lab software: the system runs the process automatically and only asks the human to intervene at the moments that genuinely require judgment.

---

## Why I Built This

I spent two years as a Procurement Engineer handling MRO (Maintenance, Repair & Operations) spare parts for Gulf and Middle East heavy industrial clients. The work involved real domain expertise — understanding manufacturers, supply chains, lead times, compliance requirements — but much of the execution was repetitive.

I built this project for three reasons:

1. **To solve a real problem** — not a toy demo, but a system designed around actual daily workflows I extracted from my own work
2. **To demonstrate AI engineering** — showing where AI genuinely helps versus where deterministic code is smarter, more reliable, and easier to maintain
3. **To transition careers** — from Procurement Engineer to AI Workflow/Automation Engineer, with a portfolio piece that bridges both worlds

---

## The Core Design Philosophy

### 1. Deterministic First, AI Only Where Needed

Many "AI projects" add AI everywhere. This one doesn't. AI is introduced only where human-like judgment is genuinely required — specifically, where the data is too ambiguous or unstructured for rules to handle reliably.

| Task | Approach | Why |
|------|----------|-----|
| Parse Excel structure | Deterministic | Structure is consistent |
| Extract part numbers | Deterministic | Clear pattern (e.g. `LU400/H - GE LIGHTING`) |
| Identify ambiguous manufacturer names | AI-assisted | Requires domain knowledge |
| Suggest new suppliers | AI-assisted | Open-ended discovery task |
| Generate email subject/body | Deterministic | Fixed template + structured data |
| Select email signature | Deterministic | Simple rule (country → signature) |

### 2. Human-in-the-Loop

The system never sends emails automatically. At every critical decision point, it pauses and asks the engineer:

- Is this supplier list correct?
- Do you want to include stale suppliers?
- Do you have attachments to add?

This is intentional. Procurement involves real money and real relationships. The human stays in control.

### 3. Modular Architecture

The system is split into three independent modules, each with clear inputs and outputs. Modules can be tested, updated, or replaced without touching the others.

### 4. Simple Infrastructure

No cloud databases, no Docker, no Kubernetes. SQLite for storage, Python standard library where possible, win32com for Outlook integration. The right tool for the right job — not the most impressive tool.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INPUT                           │
│              Path to SAP Ariba Excel (.xlsm)                │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     MODULE 1                                │
│                  RFQ Parser & Validator                     │
│                                                             │
│  • Reads SAP Ariba XLSM file                               │
│  • Extracts metadata (RFQ number, client, date)            │
│  • Parses line items (material, description, UOM, qty)     │
│  • Extracts part numbers & manufacturers                   │
│  • Flags ambiguous or missing data                         │
│  • Writes Excel comments for human review                  │
│                                                             │
│  Output: parsed_<rfq_number>.json                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     MODULE 2                                │
│                  Supplier Discovery                         │
│                                                             │
│  • Searches SQLite knowledge base by material number       │
│  • Falls back to manufacturer name if no history           │
│  • Flags stale suppliers (>12 months since last contact)   │
│  • AI layer suggests new suppliers for unknown items       │
│  • Human reviews, selects, and adds new suppliers          │
│  • Saves all decisions to knowledge base for future use    │
│                                                             │
│  Input:  parsed_<rfq_number>.json                          │
│  Output: suppliers_<rfq_number>.json                       │
│  DB:     knowledge_base/suppliers.db (SQLite)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                     MODULE 3                                │
│                 Email Distribution                          │
│                                                             │
│  • Groups line items by manufacturer                       │
│  • Matches suppliers to each manufacturer group            │
│  • Generates per-supplier email drafts:                    │
│    - Subject: DECI RFQ {ref} {client} - {MFR}             │
│    - Salutation: Dear Mike / Dear Sir/Madam (auto-detect)  │
│    - Body: fixed template + line item table                │
│    - Signature: Ireland or Saudi (based on supplier country)│
│  • Creates Outlook drafts automatically                    │
│  • Saves audit trail JSON                                  │
│                                                             │
│  Input:  parsed_<rfq_number>.json +                        │
│          suppliers_<rfq_number>.json                       │
│  Output: Outlook Drafts + send_results_<rfq_number>.json   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   HUMAN REVIEW                              │
│                                                             │
│  Engineer reviews drafts in Outlook                        │
│  Edits if needed → clicks Send                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Technical Decisions & Tradeoffs

### Why SQLite instead of PostgreSQL or Oracle?
Oracle requires significant infrastructure and IT authorisation. PostgreSQL needs a server. SQLite is a single file, zero setup, runs anywhere. For a personal workflow tool processing tens to hundreds of RFQs, SQLite is the right choice — simple, reliable, portable.

### Why not just use ChatGPT for everything?
Because reliability matters more than impressiveness. A deterministic function that builds an email subject line will always produce the correct format. An LLM might hallucinate a field, change the format, or fail unpredictably. AI is reserved for tasks where deterministic rules genuinely cannot work — like identifying manufacturer names from messy, unstructured text.

### Why three separate modules?
Each module has a single responsibility and can be tested, updated, or replaced independently. If the email template changes, only Module 3 needs updating. If the supplier database schema changes, only Module 2 is affected. This is the separation of concerns principle in practice.

### Why human-in-the-loop at every stage?
Procurement involves real supplier relationships and real money. An automated system that sends the wrong email to the wrong supplier causes real damage. The system is designed to be a powerful assistant, not an autonomous agent.

### Why an email sender abstraction layer?
The `email_sender/` module defines a base interface (`BaseEmailSender`) that any email provider can implement. Currently supports Outlook (via `win32com`) and a Mock sender (for testing). Adding Gmail or another provider in future requires zero changes to the rest of the codebase — just a new implementation file.

---

## Project Structure

```
rfq_ai_project/
├── parser/                    # Module 1 — RFQ Parser
│   ├── parser.py              # RFQParser class
│   ├── validators.py          # field validation rules
│   ├── schemas.py             # data structures
│   └── logger.py              # rotating file logger
│
├── supplier_discovery.py      # Module 2 — core DB operations
├── ai_supplier_suggestion.py  # Module 2 — AI suggestion layer
├── cli.py                     # Module 2 — interactive CLI
│
├── email_distribution/        # Module 3 — Email Pipeline
│   ├── rfq_grouper.py         # group line items by manufacturer
│   ├── supplier_matcher.py    # match suppliers from DB to groups
│   ├── email_composer.py      # generate email content
│   ├── outlook_sender.py      # orchestrate sending + audit trail
│   ├── schemas.py             # Module 3 data structures
│   └── logger.py              # rotating file logger
│
├── email_sender/              # Email provider abstraction
│   ├── base.py                # abstract interface
│   ├── outlook.py             # Outlook implementation (win32com)
│   └── mock.py                # mock for testing
│
├── tests/                     # full test suite — 45/45 passing
├── mock_data/                 # mock inputs for testing
├── knowledge_base/            # suppliers.db (gitignored)
├── output/                    # JSON outputs (gitignored)
├── logs/                      # rotating logs (gitignored)
└── main.py                    # interactive pipeline entry point
```

---

## How to Run

### Prerequisites
```bash
pip install -r requirements.txt
```

### Run the full pipeline
```bash
python main.py
```

You will be guided through:
1. Enter the path to your RFQ Excel file
2. Review the supplier list found
3. Confirm attachments (if any)
4. Review generated Outlook drafts
5. Send when ready

### Run tests
```bash
python tests/test_parser.py
python tests/test_supplier_discovery.py
python tests/test_rfq_grouper.py
python tests/test_supplier_matcher.py
python tests/test_email_composer.py
python tests/test_outlook_sender.py
```

---

## Test Results

```
Module 1 — RFQ Parser:          8/8  ✓
Module 2 — Supplier Discovery:  6/6  ✓
Module 3 — RFQ Grouper:         7/7  ✓
Module 3 — Supplier Matcher:    8/8  ✓
Module 3 — Email Composer:      9/9  ✓
Module 3 — Outlook Sender:      7/7  ✓
──────────────────────────────────────
TOTAL:                         45/45 ✓
```

End-to-end workflow tested using realistic RFQ-style scenarios based on hands-on procurement experience. The portfolio/demo version uses mock and sanitized data only and does not include confidential company, client, supplier, pricing, or RFQ data.

---

## What I Learned Building This

**On system design:** Spending time extracting and mapping a real workflow before writing code is not slow — it is the work. The architecture decisions made early (modular design, deterministic-first, human-in-the-loop) held up through all three modules without needing to be revisited.

**On AI engineering:** The most important skill is knowing when *not* to use AI. Every place where I introduced deterministic logic instead of an LLM is a place where the system is faster, more reliable, and easier to test.

**On learning:** I used a Socratic approach with AI assistance throughout — reasoning through every decision before receiving guidance, rather than copying answers. This made the learning stick and the design genuinely mine.

---

## About the Developer

**Elsa (Yilin) Wang**
Procurement Engineer → AI Workflow/Automation Engineer

- MEng Industrial Engineering & Operations Research — UC Berkeley
- MSc International Software Development (First Class Honours) — University of Limerick
- 2+ years SaaS application support (Navis, Oakland CA)
- 2+ years MRO procurement engineering (DECI Ltd, Limerick Ireland)

This project sits at the intersection of both worlds: deep procurement domain knowledge combined with software engineering and AI workflow design.


---

*Built with Python, SQLite, OpenAI API, win32com, and a lot of real procurement experience.*
