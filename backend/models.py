"""
Data models and type definitions for VendorFlow.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional


class StageStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    NEEDS_ATTENTION = "NEEDS ATTENTION"
    FAILED = "FAILED"


class DecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


class DocumentStatus(str, Enum):
    PASS = "PASS"
    MISSING = "MISSING"
    INVALID_FORMAT = "INVALID_FORMAT"
    INVALID_SIZE = "INVALID_SIZE"


@dataclass
class DocumentMetadata:
    doc_type: str  # gst_cert, pan_proof, bank_proof
    name: str  # Human readable name
    filename: Optional[str] = None
    size_bytes: int = 0
    extension: Optional[str] = None
    is_present: bool = False
    status: DocumentStatus = DocumentStatus.MISSING
    detail: str = ""


@dataclass
class VendorSubmission:
    # Business Info
    company_name: str
    country: str = "India"
    registration_type: str = "Private Limited"
    address: str = ""
    contact_name: str = ""
    contact_email: str = ""
    pan: str = ""
    gstin: str = ""

    # Banking Info
    bank_account_holder: str = ""
    bank_account_number: str = ""
    ifsc_code: str = ""
    bank_name: Optional[str] = ""

    # Documents
    documents: Dict[str, DocumentMetadata] = field(default_factory=dict)

    # Metadata
    run_id: str = ""
    run_type: str = "Live Submission"  # "Live Submission" or "Demo Scenario"
    submitted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_redacted_dict(self) -> Dict[str, Any]:
        """Creates a privacy-safe representation without exposing full identifiers or bank details."""

        def mask_pan(val: str) -> str:
            val = val.strip().upper()
            if len(val) == 10:
                return f"{val[:2]}****{val[-2:]}"
            return "****" if val else "NOT_PROVIDED"

        def mask_gstin(val: str) -> str:
            val = val.strip().upper()
            if len(val) == 15:
                return f"{val[:3]}*******{val[-3:]}"
            return "****" if val else "NOT_PROVIDED"

        def mask_bank_account(val: str) -> str:
            val = val.strip()
            if len(val) >= 4:
                return f"{'*' * (len(val) - 4)}{val[-4:]}"
            return "****" if val else "NOT_PROVIDED"

        return {
            "company_name": self.company_name,
            "country": self.country,
            "registration_type": self.registration_type,
            "address": self.address,
            "contact_name": self.contact_name,
            "contact_email": self.contact_email,
            "pan_masked": mask_pan(self.pan),
            "gstin_masked": mask_gstin(self.gstin),
            "bank_account_holder": self.bank_account_holder,
            "bank_account_masked": mask_bank_account(self.bank_account_number),
            "ifsc_code": self.ifsc_code.strip().upper(),
            "bank_name": self.bank_name or "Not Specified",
            "documents_summary": {
                k: {
                    "filename": v.filename,
                    "size_bytes": v.size_bytes,
                    "status": v.status.value,
                    "detail": v.detail,
                }
                for k, v in self.documents.items()
            },
        }


@dataclass
class ValidationIssue:
    stage: str
    field_name: str
    issue_type: str  # ERROR, WARNING, HARD_STOP
    message: str


@dataclass
class StageResult:
    stage_number: int
    stage_name: str
    status: StageStatus
    summary: str
    details: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class OnboardingDecision:
    status: DecisionStatus
    summary: str
    passed_checks: List[str] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    human_review_required: bool = False
    disclaimer: str = (
        "APPROVED indicates that all automated checks passed. Final activation and payment "
        "authorization remains subject to review by an authorized procurement officer."
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "summary": self.summary,
            "passed_checks": self.passed_checks,
            "issues": [
                {
                    "stage": i.stage,
                    "field_name": i.field_name,
                    "issue_type": i.issue_type,
                    "message": i.message,
                }
                for i in self.issues
            ],
            "next_steps": self.next_steps,
            "human_review_required": self.human_review_required,
            "disclaimer": self.disclaimer,
        }


@dataclass
class WorkflowExecutionResult:
    run_id: str
    vendor_name: str
    status: DecisionStatus
    total_duration_ms: float
    created_at: str
    run_type: str
    stage_results: List[StageResult]
    decision: OnboardingDecision
    communication_draft: str
    redacted_input: Dict[str, Any]
