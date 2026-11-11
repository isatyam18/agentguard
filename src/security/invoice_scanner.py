"""Direct alias for security.invoice_scanner."""

from agentguard.security.invoice_scanner import InvoiceScanner
from agentguard.security.schemas import (
    ContactDetails,
    InvoiceLineItem,
    NormalizedInvoice,
    ScanResult,
    ThreatCategory,
)

__all__ = [
    "ContactDetails",
    "InvoiceLineItem",
    "InvoiceScanner",
    "NormalizedInvoice",
    "ScanResult",
    "ThreatCategory",
]
