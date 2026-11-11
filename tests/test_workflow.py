"""
Automated Unit Tests for VendorFlow Business Logic and Verification Engine.
Tests all five primary demonstration scenarios and edge cases.
"""

import tempfile
from pathlib import Path
import pytest

from backend.models import (
    DecisionStatus,
    DocumentMetadata,
    DocumentStatus,
    VendorSubmission,
)
from backend.workflow import execute_workflow
from database.db import get_all_runs, get_dashboard_metrics, init_db


@pytest.fixture
def test_db():
    """Creates a temporary SQLite database for clean test isolation."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    init_db(db_path)
    yield db_path
    try:
        db_path.unlink()
    except Exception:
        pass


def create_sample_docs(missing_bank: bool = False, invalid_ext: bool = False):
    """Helper to generate mock DocumentMetadata dictionaries."""
    docs = {
        "gst_cert": DocumentMetadata(
            doc_type="gst_cert",
            name="GST Registration Certificate",
            filename="gst_certificate.pdf",
            size_bytes=245000,
            extension=".pdf",
            is_present=True,
        ),
        "pan_proof": DocumentMetadata(
            doc_type="pan_proof",
            name="Company PAN Proof Document",
            filename="company_pan.jpg" if not invalid_ext else "company_pan.exe",
            size_bytes=180000,
            extension=".jpg" if not invalid_ext else ".exe",
            is_present=True,
        ),
    }
    if not missing_bank:
        docs["bank_proof"] = DocumentMetadata(
            doc_type="bank_proof",
            name="Bank Proof / Cancelled Cheque",
            filename="cancelled_cheque.png",
            size_bytes=310000,
            extension=".png",
            is_present=True,
        )
    else:
        docs["bank_proof"] = DocumentMetadata(
            doc_type="bank_proof",
            name="Bank Proof / Cancelled Cheque",
            is_present=False,
        )
    return docs


def test_scenario_a_happy_path(test_db):
    """Test 1: Happy path with Aster Labs -> APPROVED."""
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
        bank_name="HDFC Bank",
        documents=create_sample_docs(),
        run_type="Live Submission",
    )

    result = execute_workflow(submission, db_path=test_db)

    assert result.status == DecisionStatus.APPROVED
    assert len(result.decision.issues) == 0
    assert result.decision.human_review_required is False
    assert "automated onboarding checks passed" in result.decision.summary.lower()
    assert "Subject: Vendor Onboarding Verification Successful" in result.communication_draft

    # Verify persistence
    runs = get_all_runs(test_db)
    assert len(runs) == 1
    assert runs[0]["status"] == "APPROVED"
    assert runs[0]["vendor_name"] == "Aster Labs Private Limited"

    # Verify metrics
    metrics = get_dashboard_metrics(test_db)
    assert metrics["total_submissions"] == 1
    assert metrics["approved"] == 1
    assert metrics["approval_rate"] == 100.0


def test_scenario_b_missing_document(test_db):
    """Test 2: Missing bank document (Bluewave) -> PENDING."""
    submission = VendorSubmission(
        company_name="Bluewave Technologies Private Limited",
        country="India",
        registration_type="Private Limited",
        address="Level 5, Cyber Gateway, HITEC City, Hyderabad",
        contact_name="Ramesh Kumar",
        contact_email="finance@bluewavetech.example",
        pan="BWAVE5678M",
        gstin="36BWAVE5678M1Z8",
        bank_account_holder="Bluewave Technologies Pvt Ltd",
        bank_account_number="987654321098",
        ifsc_code="ICIC0000456",
        documents=create_sample_docs(missing_bank=True),
        run_type="Live Submission",
    )

    result = execute_workflow(submission, db_path=test_db)

    assert result.status == DecisionStatus.PENDING
    assert any("Bank Proof" in i.message for i in result.decision.issues)
    assert result.decision.human_review_required is True
    assert "Bank Proof" in result.communication_draft
    assert "Subject: Action Required" in result.communication_draft

    runs = get_all_runs(test_db)
    assert runs[0]["status"] == "PENDING"


def test_scenario_c_bank_name_mismatch(test_db):
    """Test 3: Bank name mismatch (Brightline vs Shree Trading) -> PENDING."""
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
        documents=create_sample_docs(),
        run_type="Live Submission",
    )

    result = execute_workflow(submission, db_path=test_db)

    assert result.status == DecisionStatus.PENDING
    assert any("Name mismatch" in i.message for i in result.decision.issues)
    assert "Shree Trading Enterprises" in result.communication_draft


def test_scenario_d_duplicate_vendor(test_db):
    """Test 4: Duplicate tax identifier (Northstar Office Supplies) -> PENDING."""
    submission = VendorSubmission(
        company_name="Northstar Office Supplies Private Limited",
        country="India",
        registration_type="Private Limited",
        address="12 MG Road, Mumbai",
        contact_name="Sanjay Mehta",
        contact_email="sales@northstar.example",
        pan="LMNOP1234Q",  # Seeded in db.py
        gstin="27LMNOP1234Q1Z5",
        bank_account_holder="Northstar Office Supplies",
        bank_account_number="223344556677",
        ifsc_code="KKBK0000123",
        documents=create_sample_docs(),
        run_type="Live Submission",
    )

    result = execute_workflow(submission, db_path=test_db)

    assert result.status == DecisionStatus.PENDING
    assert any("duplicate vendor registration" in i.message.lower() for i in result.decision.issues)


def test_scenario_e_restricted_vendor(test_db):
    """Test 5: Synthetic restricted registry match (Redwood Logistics) -> REJECTED."""
    submission = VendorSubmission(
        company_name="Redwood Logistics LLP",
        country="India",
        registration_type="LLP",
        address="Transport Nagar, Sector 4, Gandhinagar",
        contact_name="Karan Verma",
        contact_email="legal@redwoodlogistics.example",
        pan="UVWXY5678Z",  # Seeded in db.py
        gstin="29UVWXY5678Z1Z5",
        bank_account_holder="Redwood Logistics LLP",
        bank_account_number="998877665544",
        ifsc_code="AXIS0000789",
        documents=create_sample_docs(),
        run_type="Live Submission",
    )

    result = execute_workflow(submission, db_path=test_db)

    assert result.status == DecisionStatus.REJECTED
    assert any("internal restricted-vendor registry" in i.message.lower() for i in result.decision.issues)
    assert "compliance and regulatory screening" in result.communication_draft
    assert "internal risk policy" in result.communication_draft


def test_edge_cases(test_db):
    """Test additional edge cases: invalid PAN, PAN/GSTIN mismatch, unsupported country, invalid file ext."""
    # Invalid PAN
    sub_inv_pan = VendorSubmission(
        company_name="Test Corp",
        country="India",
        contact_email="test@test.example",
        pan="INVALIDPAN1",
        gstin="27INVALIDPAN11Z5",
        bank_account_holder="Test Corp",
        bank_account_number="1234567890",
        ifsc_code="HDFC0001234",
        documents=create_sample_docs(),
    )
    res_pan = execute_workflow(sub_inv_pan, db_path=test_db)
    assert res_pan.status == DecisionStatus.PENDING
    assert any("PAN 'INVALIDPAN1' does not match" in i.message for i in res_pan.decision.issues)

    # PAN vs GSTIN mismatch
    sub_mismatch = VendorSubmission(
        company_name="Test Corp",
        country="India",
        contact_email="test@test.example",
        pan="ABCDE1234F",
        gstin="27ZZZZZ9999Z1Z5",  # Contains ZZZZZ9999Z
        bank_account_holder="Test Corp",
        bank_account_number="1234567890",
        ifsc_code="HDFC0001234",
        documents=create_sample_docs(),
    )
    res_mismatch = execute_workflow(sub_mismatch, db_path=test_db)
    assert res_mismatch.status == DecisionStatus.PENDING
    assert any("PAN mismatch" in i.message for i in res_mismatch.decision.issues)

    # Unsupported country
    sub_country = VendorSubmission(
        company_name="Global Exports Ltd",
        country="United States",
        contact_email="us@global.example",
        pan="ABCDE1234F",
        gstin="27ABCDE1234F1Z5",
        bank_account_holder="Global Exports",
        bank_account_number="1234567890",
        ifsc_code="HDFC0001234",
        documents=create_sample_docs(),
    )
    res_country = execute_workflow(sub_country, db_path=test_db)
    assert res_country.status == DecisionStatus.PENDING
    assert any("Unsupported jurisdiction" in i.message for i in res_country.decision.issues)

    # Invalid document extension (.exe)
    sub_doc_ext = VendorSubmission(
        company_name="Safe Softwares Ltd",
        country="India",
        contact_email="it@safesoft.example",
        pan="ABCDE1234F",
        gstin="27ABCDE1234F1Z5",
        bank_account_holder="Safe Softwares",
        bank_account_number="1234567890",
        ifsc_code="HDFC0001234",
        documents=create_sample_docs(invalid_ext=True),
    )
    res_ext = execute_workflow(sub_doc_ext, db_path=test_db)
    assert res_ext.status == DecisionStatus.PENDING
    assert any("invalid file type '.exe'" in i.message for i in res_ext.decision.issues)
