"""
Data models and type definitions for VendorFlow.
Supports both Phase 1 (rule-based validation) and Phase 2 (document intelligence & cross-verification).
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


class ExtractionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    UNREADABLE = "UNREADABLE"
    NOT_PROVIDED = "NOT_PROVIDED"
    MANUAL_CONFIRMED = "MANUAL_CONFIRMED"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FieldProvenance(str, Enum):
    DOCUMENT = "DOCUMENT"
    MANUAL_ENTRY = "MANUAL_ENTRY"
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"


@dataclass
class ExtractedField:
    field_name: str
    value: str
    source_doc: str
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    method: str = "REGEX"
    provenance: FieldProvenance = FieldProvenance.DOCUMENT
    is_masked: bool = False
    display_value: Optional[str] = None

    def get_display_value(self) -> str:
        if self.display_value:
            return self.display_value
        if self.is_masked and self.value:
            if len(self.value) > 4:
                return f"{'*' * (len(self.value) - 4)}{self.value[-4:]}"
            return "****"
        return self.value


@dataclass
class DocumentExtractionResult:
    document_type: str  # PAN_PROOF, GST_CERT, BANK_PROOF
    filename: str
    extraction_status: ExtractionStatus
    extracted_fields: Dict[str, str] = field(default_factory=dict)
    field_confidence: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    raw_text_snippet: str = ""
    requires_human_confirmation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_type": self.document_type,
            "filename": self.filename,
            "extraction_status": self.extraction_status.value,
            "extracted_fields": self.extracted_fields,
            "field_confidence": self.field_confidence,
            "warnings": self.warnings,
            "requires_human_confirmation": self.requires_human_confirmation,
        }


@dataclass
class CrossDocumentCheckResult:
    check_name: str
    status: str  # PASS, MISMATCH, WARNING, SKIPPED
    message: str
    fields_compared: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossDocumentSummary:
    is_all_consistent: bool = True
    pan_consistent: bool = True
    name_consistent: bool = True
    discrepancies: List[str] = field(default_factory=list)
    checks: List[CrossDocumentCheckResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_all_consistent": self.is_all_consistent,
            "pan_consistent": self.pan_consistent,
            "name_consistent": self.name_consistent,
            "discrepancies": self.discrepancies,
            "checks": [
                {
                    "check_name": c.check_name,
                    "status": c.status,
                    "message": c.message,
                    "fields_compared": c.fields_compared,
                }
                for c in self.checks
            ],
        }


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
    raw_bytes: Optional[bytes] = None
    extraction_result: Optional[DocumentExtractionResult] = None


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

    # Phase 2 extraction confirmation state
    manual_confirmations: Dict[str, bool] = field(default_factory=dict)

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
                    "extraction_status": (
                        v.extraction_result.extraction_status.value
                        if v.extraction_result
                        else "NOT_EXTRACTED"
                    ),
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
    extraction_results: Dict[str, Any] = field(default_factory=dict)
    cross_document_results: Dict[str, Any] = field(default_factory=dict)
    documents_processed_count: int = 0
    discrepancies_count: int = 0
    manual_confirmations_count: int = 0
