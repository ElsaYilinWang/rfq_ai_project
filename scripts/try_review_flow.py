# scripts/try_review_flow.py

"""
Phase 18b live check: one REAL agent run, a real pause, and you decide.

    python scripts/try_review_flow.py

What happens:
  1. The agent runs on the ABB circuit-breaker sample item, told the
     RFQ quantity (2 EA), so the draft should say 2 EA, not a guess
     (a real, paid Sonnet run, about $0.03).
  2. If it produced a draft, the run PAUSES and you see exactly what a
     reviewer would see.
  3. You approve, or reject with a note (a rejection without a note is
     refused and you are asked again).
  4. The script then tries to decide the same run a second time. That
     must be refused, and it must cost nothing.

Nothing is ever sent. Approval records the decision only.

Start and resume both happen in this one process, so the in-memory
checkpointer is enough here. Paused runs do not survive a restart.

Sonnet does not always draft an email (in earlier live runs it did in
roughly two of three). If this run produces no draft there is nothing
to approve, and the script says so: just run it again.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from pydantic import ValidationError

ITEM = {
    "item_description": "ABB circuit breaker 10A",
    "material_number": "MAT-001",
    "known_manufacturer": "ABB",
    "known_part_number": "CB-10A",
    "quantity": 2,
    "uom": "EA",
}


def show_request(request, out):
    out("\n" + "=" * 70)
    out("THE RUN IS PAUSED. A reviewer would see:")
    out("=" * 70)
    out(f"  run id        : {request['trace_id']}")
    out(f"  item          : {request['item_description']}")
    out(f"  summary       : {request['summary']}")
    out(f"  next step     : {request['recommended_next_step']}")
    for i, d in enumerate(request["drafts"], 1):
        out(f"\n  --- draft {i} (status: {d['status']}) ---")
        out(f"  to      : {d['to']}")
        out(f"  subject : {d['subject']}")
        for line in d["body"].splitlines():
            out(f"  | {line}")
    for m in request["semantic_matches"]:
        out(f"\n  weak match: {m.get('supplier_name')} "
            f"(similarity {m.get('similarity_score')}) -- not a confirmed match")


def run_flow(start_fn, resume_fn, ask=input, out=print, not_pending_error=Exception):
    outcome = start_fn(**ITEM)
    out(f"\nAgent finished. cost ${outcome.result.total_cost_usd:.4f}, "
        f"{outcome.result.iterations_used} iterations, completed={outcome.result.completed}")

    if outcome.status != "awaiting_approval":
        out("\nThis run produced no draft, so there is nothing to approve. "
            "That is normal for this model: run the script again.")
        return outcome

    show_request(outcome.review_request, out)
    run_id = outcome.trace_id

    while True:
        choice = ask("\napprove or reject? ").strip().lower()
        note = None
        if choice == "reject":
            note = ask("reason for rejecting (required): ")
        try:
            decided = resume_fn(run_id, choice, note=note)
            break
        except ValidationError as exc:
            out(f"  refused ({exc.errors()[0]['msg']}); the run is still waiting. Try again.")

    out(f"\nDecision recorded: {decided.status}"
        + (f" -- note: {decided.decision_note}" if decided.decision_note else ""))
    out(f"human_review_required on the result is still: {decided.result.human_review_required}")

    out("\nNow trying to decide the same run again (must be refused, must cost nothing)...")
    try:
        resume_fn(run_id, "approve")
        out("  !! a second decision was ACCEPTED. That is a bug.")
    except not_pending_error as exc:
        out(f"  refused, as it should be: {exc}")

    out("\nNothing was sent. Approval only records the decision.")
    return decided


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set (checked after load_dotenv()). "
              "Refusing to run: the agent call would fail.")
        sys.exit(1)

    from agent.supplier_review import (
        ReviewNotPending, resume_supplier_review, start_supplier_review,
    )

    print("About to make ONE real agent run (~$0.03).")
    run_flow(start_supplier_review, resume_supplier_review, not_pending_error=ReviewNotPending)


if __name__ == "__main__":
    main()
