from abc import ABC, abstractmethod
from email_distribution.schemas import EmailDraft, SendResult


class BaseEmailSender(ABC):
    """Abstract base class for email senders."""

    @abstractmethod
    def send(self, draft: EmailDraft) -> SendResult:
        """Send a single email draft. Must be implemented by subclasses."""
        pass