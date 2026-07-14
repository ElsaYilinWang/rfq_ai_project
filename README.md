
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

I spent one year as a Procurement Engineer handling MRO (Maintenance, Repair & Operations) spare parts for Gulf and Middle East heavy industrial clients. The work involved real domain expertise — understanding manufacturers, supply chains, lead times, compliance requirements — but much of the execution was repetitive.

I built this project for three reasons:

1. **To solve a real problem** — not a toy demo, but a system designed around actual daily workflows I extracted from my own work
2. **To demonstrate AI engineering** — showing where AI genuinely helps versus where deterministic code is smarter, more reliable, and easier to maintain
3. **To transition careers** — from Procurement Engineer to AI Workflow/Automation Engineer, with a portfolio piece that bridges both worlds

---

## Production-Oriented Workflow Design

This project is a private portfolio implementation using mock and sanitized RFQ-style data. It was not deployed in a production environment, but it was designed around production-oriented workflow concerns: evaluation, observability, permission control, traceability, and human review.

The goal is not to build a fully autonomous procurement agent. The goal is to demonstrate how an AI-assisted workflow can support procurement engineers while keeping high-risk decisions under human control.

---

## Evaluation Approach

The system can be evaluated at multiple points in the RFQ workflow rather than only at the final output.

### 1. RFQ Extraction Accuracy

Module 1 parses RFQ-style input into structured fields such as RFQ number, client, material number, manufacturer, part number, description, quantity, and unit of measure.

Useful evaluation metrics include:

* Field-level extraction accuracy
* Missing-field detection rate
* Manufacturer extraction accuracy
* Part-number extraction accuracy
* Validation flag accuracy

Example bad-case categories:

* Missing manufacturer
* Missing part number
* Ambiguous manufacturer name
* Description-only item with no clear part number
* Replacement or superseded part reference
* Invalid quantity or unit of measure
* Incomplete RFQ metadata

This matters because downstream supplier discovery and email generation depend on clean structured data. If extraction fails silently, the system may contact the wrong supplier or generate an incomplete RFQ email.

### 2. Supplier Matching Quality

Module 2 searches a local supplier knowledge base and matches suppliers to manufacturer or material information.

Useful evaluation metrics include:

* Top-1 supplier match correctness
* Top-k supplier coverage
* Match source distribution: historical match, manufacturer fallback, AI suggestion, or manual entry
* Stale supplier detection rate
* Human override rate

Example bad-case categories:

* No supplier found for manufacturer
* Supplier found but marked stale
* Supplier matched by manufacturer but not by exact material number
* Duplicate supplier records
* Supplier country or contact information missing
* AI-suggested supplier requires human verification

This matters because supplier discovery is not only a search problem. It also involves trust, freshness, prior experience, and human judgment.

### 3. Human Edit Rate

The system should be judged not only by whether it produces an output, but by how much human correction is needed.

Useful metrics include:

* Percentage of generated emails edited by the user
* Average number of edited fields per draft
* Supplier list approval rate
* Supplier list override rate
* Number of RFQ items requiring manual review
* Number of drafts blocked before sending

A lower human edit rate suggests the workflow is reducing repetitive work effectively. A higher edit rate may indicate weak parsing, poor supplier matching, unclear email formatting, or missing business rules.

### 4. End-to-End Workflow Success

An end-to-end run can be evaluated by checking whether:

* The RFQ input is parsed without crashing
* Required fields are either extracted or flagged
* Supplier candidates are returned with evidence
* Email drafts are generated in the expected format
* No real email is sent without human review
* An audit trail is saved for later inspection

The evaluation goal is not to claim perfect automation. The goal is to make system behavior measurable, reviewable, and improvable.

---

## Observability and Logging

The project uses logging and JSON outputs to make workflow behavior inspectable. In a production enterprise workflow, observability is important because silent failures can create operational risk.

For each workflow run, the system should ideally record:

* Input file name or RFQ identifier
* Parsed RFQ metadata
* Number of line items processed
* Number of validation warnings
* Supplier matching source for each item or manufacturer
* Generated draft count
* Execution time per module
* Errors or exceptions
* Human intervention points
* Final user decision: approved, edited, skipped, or blocked

Example log events:

* RFQ file received
* RFQ parsing started
* RFQ parsing completed
* Validation warning generated
* Supplier lookup started
* Supplier found from history
* Supplier marked stale
* AI suggestion requested
* Human approval required
* Email draft generated
* Email sending blocked pending review
* Audit trail saved

This makes the system easier to debug and safer to operate. Instead of only seeing the final draft, the user can understand what happened at each step.

---

## Safety and Permission Model

The system is intentionally designed as a human-supervised workflow, not a fully autonomous procurement agent.

### Automatic Read Actions

The system can safely perform read-only actions such as:

* Reading mock RFQ-style input files
* Parsing structured RFQ fields
* Searching a local supplier knowledge base
* Reading historical supplier records
* Loading email templates
* Loading validation rules

These actions do not create external business impact.

### Automatic Low-Risk Actions

The system can automatically perform low-risk internal actions such as:

* Generating structured JSON output
* Creating validation warnings
* Ranking supplier candidates
* Grouping RFQ line items by manufacturer
* Generating draft email content
* Saving logs and audit trails

These actions support the human user but do not contact suppliers or commit business decisions.

### Approval-Required Actions

The following actions require human approval:

* Selecting final suppliers to contact
* Using stale supplier records
* Accepting AI-suggested suppliers
* Adding new supplier records to the knowledge base
* Attaching files to RFQ emails
* Sending RFQ emails externally
* Proceeding when required RFQ fields are missing or ambiguous

These steps involve supplier relationships, commercial risk, or incomplete data, so the human remains responsible.

### Prohibited Actions

The system should not:

* Send emails without human review
* Invent missing supplier contact details
* Invent manufacturer names, part numbers, prices, certificates, or lead times
* Override validation warnings without user confirmation
* Access confidential company systems without authorization
* Store confidential client, supplier, pricing, or RFQ data in the public/demo version

This permission model keeps the system useful while reducing the risk of incorrect or unauthorized actions.

---

## Traceability and Explainability

Each recommendation or warning should be explainable to the user.

For supplier selection, the system should show:

* Which supplier was selected
* Which manufacturer or material number triggered the match
* Whether the match came from historical data, manufacturer fallback, AI suggestion, or manual entry
* Whether the supplier is stale
* What human approval is required before proceeding

For validation failures, the system should show:

* Which RFQ line item failed validation
* Which field is missing or ambiguous
* Why the issue matters
* Whether the workflow can continue or should pause for review

For human approval, the system should show:

* What action is being requested
* Why approval is required
* What evidence the system used
* What the risk is if the user proceeds

This makes the workflow easier to trust. The user is not asked to blindly accept an AI recommendation; they are shown the evidence and the reason for review.

---

## Feedback Loop

The workflow can improve over time through human feedback.

Examples of useful feedback include:

* User accepts a supplier recommendation
* User rejects a supplier recommendation
* User marks a supplier as stale or no longer useful
* User manually adds a better supplier
* User edits generated email wording
* User flags missing manufacturer or part-number information
* User blocks an email draft before sending

This feedback can be used to improve:

* Supplier ranking
* Supplier freshness rules
* Manufacturer normalization
* Validation rules
* Email templates
* Bad-case handling

The important design principle is that feedback should be captured as structured workflow data, not only as informal user memory. This allows future evaluation and improvement without making the system fully autonomous.


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
