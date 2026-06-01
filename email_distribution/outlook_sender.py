import json
from datetime import datetime
from pathlib import Path
from typing import List

from email_distribution.schemas import EmailDraft, SendResult
from email_distribution.logger import get_logger
from email_sender.base import BaseEmailSender

logger = get_logger()


def send_all_drafts(
    drafts: List[EmailDraft],
    sender: BaseEmailSender,
    rfq_number: str
) -> List[SendResult]:
    """Send all email drafts and log results."""

    results = []
    logger.info(f"Starting email distribution for RFQ {rfq_number}. Total drafts: {len(drafts)}")

    for draft in drafts:
        logger.info(f"Sending to {draft.to} | Subject: {draft.subject}")
        result = sender.send(draft)
        results.append(result)

        if result.status == "success":
            logger.info(f"SUCCESS — {result.recipient}")
        else:
            logger.error(f"FAILED — {result.recipient} | Error: {result.error_message}")

    # save audit trail
    _save_results(results, rfq_number)
    logger.info(f"Distribution complete. {len(results)} emails processed.")
    return results


def _save_results(results: List[SendResult], rfq_number: str):
    """Save send results to JSON for audit trail."""
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"send_results_{rfq_number}.json"
    data = [
        {
            "timestamp": r.timestamp,
            "manufacturer": r.manufacturer,
            "recipient": r.recipient,
            "subject": r.subject,
            "status": r.status,
            "error_message": r.error_message
        }
        for r in results
    ]
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Audit trail saved to {output_path}")