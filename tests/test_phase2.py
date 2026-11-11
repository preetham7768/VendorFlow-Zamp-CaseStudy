"""
Automated Unit Tests for VendorFlow Phase 2: Document Intelligence & Cross-Verification.
Tests text extraction from PDFs, regex and label parsing, cross-document consistency,
and the 13-stage end-to-end execution workflow.
"""

import tempfile
from pathlib import Path
import pytest

from backend.document_extractor import (
    extract_bank_document,
    extract_gst_document,
    extract_pan_document,
    extract_raw_text_from_pdf,
)
from backend.models import (
    DecisionStatus,
    DocumentMetadata,
    ExtractionStatus,
    VendorSubmission,
)
from backend.synthetic_docs import (
    generate_synthetic_bank_pdf,
    generate_synthetic_gst_pdf,
    generate_synthetic_pan_pdf,
    generate_unreadable_pdf,
)
from backend.workflow import execute_workflow
from database.db import get_all_runs, get_dashboard_metrics, init_db


@pytest.fixture
def test_db():
    """Temporary SQLite database for clean test isolation."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    init_db(db_path)
    yield db_path
    try:
        db_path.unlink()
    except Exception:
        pass


def test_pdf_raw_text_extraction():
    """Verifies that PyMuPDF extracts text streams from synthetic PDFs."""
    pdf_bytes = generate_synthetic_pan_pdf(pan="ABCDE1234F", name="Aster Labs Private Limited")
    text = extract_raw_text_from_pdf(pdf_bytes)

    assert "INCOME TAX DEPARTMENT" in text
    assert "ABCDE1234F" in text
    assert "ASTER LABS PRIVATE LIMITED" in text


def test_pan_document_extraction():
    """Verifies PAN and cardholder name extraction."""
    pdf_bytes = generate_synthetic_pan_pdf(pan="ABCDE1234F", name="Aster Labs Private Limited")
    res = extract_pan_document(pdf_bytes, "pan_card.pdf")

    assert res.extraction_status == ExtractionStatus.SUCCESS
    assert res.extracted_fields["pan"] == "ABCDE1234F"
    assert "ASTER LABS" in res.extracted_fields["name"]
    assert res.field_confidence["pan"] == "HIGH"


def test_gst_document_extraction():
    """Verifies GSTIN, embedded PAN, and legal business name extraction."""
    pdf_bytes = generate_synthetic_gst_pdf(
        gstin="27ABCDE1234F1Z5", legal_name="Aster Labs Private Limited", trade_name="Aster Labs"
    )
    res = extract_gst_document(pdf_bytes, "gst_cert.pdf")

    assert res.extraction_status == ExtractionStatus.SUCCESS
    assert res.extracted_fields["gstin"] == "27ABCDE1234F1Z5"
    assert res.extracted_fields["embedded_pan"] == "ABCDE1234F"
    assert "ASTER LABS" in res.extracted_fields["legal_name"]


def test_bank_document_extraction():
    """Verifies account holder, account number, and IFSC extraction from cancelled cheque."""
    pdf_bytes = generate_synthetic_bank_pdf(
        account_holder="Aster Labs",
        account_number="123456789012",
        ifsc="HDFC0001234",
        bank_name="HDFC Bank Ltd",
    )
    res = extract_bank_document(pdf_bytes, "cancelled_cheque.pdf")

    assert res.extraction_status == ExtractionStatus.SUCCESS
    assert res.extracted_fields["ifsc"] == "HDFC0001234"
    assert res.extracted_fields["account_number"] == "123456789012"
    assert "ASTER LABS" in res.extracted_fields["account_holder"]


def test_unreadable_pdf_fallback():
    """Verifies that documents without text streams fail gracefully without inventing values."""
    unreadable_bytes = generate_unreadable_pdf()
    res = extract_pan_document(unreadable_bytes, "scanned_pan.pdf")

    assert res.extraction_status == ExtractionStatus.UNREADABLE
    assert res.requires_human_confirmation is True
    assert len(res.extracted_fields) == 0
    assert any("no selectable text" in w for w in res.warnings)


def test_phase2_scenario_a_consistent_documents(test_db):
    """Phase 2 Scenario A: Real synthetic PDFs with 100% consistent details -> APPROVED."""
    pan_pdf = generate_synthetic_pan_pdf("ABCDE1234F", "Aster Labs Private Limited")
    gst_pdf = generate_synthetic_gst_pdf("27ABCDE1234F1Z5", "Aster Labs Private Limited", "Aster Labs")
    bank_pdf = generate_synthetic_bank_pdf("Aster Labs", "123456789012", "HDFC0001234")

    submission = VendorSubmission(
        company_name="Aster Labs Private Limited",
        country="India",
        registration_type="Private Limited",
        address="Plot 42, Electronic City, Bangalore, Karnataka",
        contact_name="Dr. Vikram Rao",
        contact_email="ops@asterlabs.example",
        pan="ABCDE1234F",
        gstin="27ABCDE1234F1Z5",
        bank_account_holder="Aster Labs",
        bank_account_number="123456789012",
        ifsc_code="HDFC0001234",
        bank_name="HDFC Bank Ltd",
        documents={
            "pan_proof": DocumentMetadata(
                doc_type="pan_proof",
                name="Company PAN Proof",
                filename="pan_card.pdf",
                size_bytes=len(pan_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=pan_pdf,
            ),
            "gst_cert": DocumentMetadata(
                doc_type="gst_cert",
                name="GST Registration Certificate",
                filename="gst_certificate.pdf",
                size_bytes=len(gst_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=gst_pdf,
            ),
            "bank_proof": DocumentMetadata(
                doc_type="bank_proof",
                name="Bank Proof / Cancelled Cheque",
                filename="cancelled_cheque.pdf",
                size_bytes=len(bank_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=bank_pdf,
            ),
        },
        run_type="Live Submission",
    )

    result = execute_workflow(submission, db_path=test_db)

    assert result.status == DecisionStatus.APPROVED
    assert len(result.stage_results) == 13
    assert result.cross_document_results["is_all_consistent"] is True
    assert result.documents_processed_count == 3
    assert result.discrepancies_count == 0


def test_phase2_scenario_b_pan_mismatch(test_db):
    """Phase 2 Scenario B: PAN from PAN doc differs from embedded PAN in GST cert -> PENDING."""
    pan_pdf = generate_synthetic_pan_pdf("ABCDE1234F", "Bluewave Technologies Pvt Ltd")
    # Conflicting GST document with different embedded PAN ZZZZZ9999Z
    gst_pdf = generate_synthetic_gst_pdf("36ZZZZZ9999Z1Z8", "Bluewave Technologies Pvt Ltd")
    bank_pdf = generate_synthetic_bank_pdf("Bluewave Technologies", "987654321098", "ICIC0000456")

    submission = VendorSubmission(
        company_name="Bluewave Technologies Private Limited",
        country="India",
        registration_type="Private Limited",
        address="Level 5, Cyber Gateway, HITEC City, Hyderabad",
        contact_name="Ramesh Kumar",
        contact_email="finance@bluewavetech.example",
        pan="ABCDE1234F",
        gstin="36ZZZZZ9999Z1Z8",
        bank_account_holder="Bluewave Technologies",
        bank_account_number="987654321098",
        ifsc_code="ICIC0000456",
        documents={
            "pan_proof": DocumentMetadata(
                doc_type="pan_proof",
                name="Company PAN Proof",
                filename="pan_card.pdf",
                size_bytes=len(pan_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=pan_pdf,
            ),
            "gst_cert": DocumentMetadata(
                doc_type="gst_cert",
                name="GST Registration Certificate",
                filename="gst_certificate.pdf",
                size_bytes=len(gst_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=gst_pdf,
            ),
            "bank_proof": DocumentMetadata(
                doc_type="bank_proof",
                name="Bank Proof / Cancelled Cheque",
                filename="cancelled_cheque.pdf",
                size_bytes=len(bank_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=bank_pdf,
            ),
        },
        run_type="Live Submission",
    )

    result = execute_workflow(submission, db_path=test_db)

    assert result.status == DecisionStatus.PENDING
    assert result.cross_document_results["pan_consistent"] is False
    assert any("PAN mismatch" in d for d in result.cross_document_results["discrepancies"])
    assert any("pan_inconsistency" in i.field_name for i in result.decision.issues)


def test_phase2_scenario_c_company_name_mismatch(test_db):
    """Phase 2 Scenario C: Legal business name and bank account holder materially differ -> PENDING."""
    pan_pdf = generate_synthetic_pan_pdf("BRGHT9999K", "Brightline Systems Private Limited")
    gst_pdf = generate_synthetic_gst_pdf("29BRGHT9999K1Z2", "Brightline Systems Private Limited")
    # Different bank account holder on cheque
    bank_pdf = generate_synthetic_bank_pdf("Shree Trading Enterprises", "554433221100", "SBIN0001234")

    submission = VendorSubmission(
        company_name="Brightline Systems Private Limited",
        country="India",
        registration_type="Private Limited",
        address="102 Industrial Estate, Peenya, Bangalore",
        contact_name="Ananya Sen",
        contact_email="accounts@brightline.example",
        pan="BRGHT9999K",
        gstin="29BRGHT9999K1Z2",
        bank_account_holder="Shree Trading Enterprises",
        bank_account_number="554433221100",
        ifsc_code="SBIN0001234",
        documents={
            "pan_proof": DocumentMetadata(
                doc_type="pan_proof",
                name="Company PAN Proof",
                filename="pan_card.pdf",
                size_bytes=len(pan_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=pan_pdf,
            ),
            "gst_cert": DocumentMetadata(
                doc_type="gst_cert",
                name="GST Registration Certificate",
                filename="gst_certificate.pdf",
                size_bytes=len(gst_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=gst_pdf,
            ),
            "bank_proof": DocumentMetadata(
                doc_type="bank_proof",
                name="Bank Proof / Cancelled Cheque",
                filename="cancelled_cheque.pdf",
                size_bytes=len(bank_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=bank_pdf,
            ),
        },
        run_type="Live Submission",
    )

    result = execute_workflow(submission, db_path=test_db)

    assert result.status == DecisionStatus.PENDING
    assert any("Bank account holder" in d for d in result.cross_document_results["discrepancies"])


def test_phase2_scenario_d_unreadable_document(test_db):
    """Phase 2 Scenario D: Blank/unreadable PDF requires manual confirmation -> PENDING."""
    unreadable_bytes = generate_unreadable_pdf()
    gst_pdf = generate_synthetic_gst_pdf("27ABCDE1234F1Z5", "Aster Labs Private Limited")
    bank_pdf = generate_synthetic_bank_pdf("Aster Labs", "123456789012", "HDFC0001234")

    submission = VendorSubmission(
        company_name="Aster Labs Private Limited",
        country="India",
        registration_type="Private Limited",
        pan="ABCDE1234F",
        gstin="27ABCDE1234F1Z5",
        bank_account_holder="Aster Labs",
        bank_account_number="123456789012",
        ifsc_code="HDFC0001234",
        documents={
            "pan_proof": DocumentMetadata(
                doc_type="pan_proof",
                name="Company PAN Proof",
                filename="unreadable_pan.pdf",
                size_bytes=len(unreadable_bytes),
                extension=".pdf",
                is_present=True,
                raw_bytes=unreadable_bytes,
            ),
            "gst_cert": DocumentMetadata(
                doc_type="gst_cert",
                name="GST Registration Certificate",
                filename="gst_certificate.pdf",
                size_bytes=len(gst_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=gst_pdf,
            ),
            "bank_proof": DocumentMetadata(
                doc_type="bank_proof",
                name="Bank Proof / Cancelled Cheque",
                filename="cancelled_cheque.pdf",
                size_bytes=len(bank_pdf),
                extension=".pdf",
                is_present=True,
                raw_bytes=bank_pdf,
            ),
        },
        run_type="Live Submission",
    )

    result = execute_workflow(submission, db_path=test_db)

    assert result.status == DecisionStatus.PENDING
    assert any("no selectable text" in i.message for i in result.decision.issues)
