from datetime import datetime
from email_distribution.schemas import EmailDraft, SendResult
from email_sender.base import BaseEmailSender


class MockEmailSender(BaseEmailSender):
    """Mock email sender for testing — no real emails sent."""

    def __init__(self):
        self.sent_drafts = []

    def send(self, draft: EmailDraft) -> SendResult:
        self.sent_drafts.append(draft)
        print(f"  [MOCK] Email would be sent to: {draft.to} | Subject: {draft.subject}")
        return SendResult(
            timestamp=datetime.now().isoformat(),
            manufacturer=draft.manufacturer,
            recipient=", ".join(draft.to),
            subject=draft.subject,
            status="success",
            error_message=""
        )