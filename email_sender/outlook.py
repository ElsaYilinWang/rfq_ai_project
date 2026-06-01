from datetime import datetime
from email_distribution.schemas import EmailDraft, SendResult
from email_sender.base import BaseEmailSender


class OutlookEmailSender(BaseEmailSender):
    """Real Outlook email sender using win32com."""

    def __init__(self, cc: list = None):
        self.cc = cc or ["mro@deci-ltd.com"]
        try:
            import win32com.client
            self.outlook = win32com.client.Dispatch("Outlook.Application")
            self.namespace = self.outlook.GetNamespace("MAPI")
        except Exception as e:
            raise RuntimeError(f"Could not connect to Outlook: {e}")

    def send(self, draft: EmailDraft) -> SendResult:
        try:
            mail = self.outlook.CreateItem(0)  # 0 = olMailItem
            mail.Subject = draft.subject
            mail.To = "; ".join(draft.to)
            mail.CC = "; ".join(self.cc)

            # assemble full body
            full_body = (
                f"{draft.salutation}<br><br>"
                f"{draft.body.replace(chr(10), '<br>')}"
                f"<br><br>{draft.signature.replace(chr(10), '<br>')}"
            )
            mail.HTMLBody = full_body

            # add attachments if any
            for attachment in draft.attachments:
                mail.Attachments.Add(attachment)

            mail.Save()  # saves to Drafts folder

            print(f"  [OUTLOOK] Draft saved for: {draft.to} | Subject: {draft.subject}")
            return SendResult(
                timestamp=datetime.now().isoformat(),
                manufacturer=draft.manufacturer,
                recipient=", ".join(draft.to),
                subject=draft.subject,
                status="success",
                error_message=""
            )
        except Exception as e:
            return SendResult(
                timestamp=datetime.now().isoformat(),
                manufacturer=draft.manufacturer,
                recipient=", ".join(draft.to),
                subject=draft.subject,
                status="failed",
                error_message=str(e)
            )