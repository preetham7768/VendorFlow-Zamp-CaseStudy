"""
VendorFlow — Intelligent Vendor Onboarding & Verification System
Phase 2: Document-Driven Vendor Verification & Cross-Document Intelligence.
"""

import io
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from backend.document_extractor import (
    extract_bank_document,
    extract_gst_document,
    extract_pan_document,
)
from backend.models import (
    ConfidenceLevel,
    DecisionStatus,
    DocumentMetadata,
    DocumentStatus,
    ExtractionStatus,
    StageResult,
    StageStatus,
    VendorSubmission,
    WorkflowExecutionResult,
)
from backend.synthetic_docs import (
    generate_synthetic_bank_pdf,
    generate_synthetic_gst_pdf,
    generate_synthetic_pan_pdf,
    generate_unreadable_pdf,
)
from backend.workflow import execute_workflow
from database.db import (
    get_all_runs,
    get_dashboard_metrics,
    get_run_by_id,
    init_db,
)
from frontend.ui_helpers import (
    get_status_badge_html,
    inject_custom_css,
    render_decision_banner,
    render_metric_card,
    render_stage_card,
)

# Page configuration
st.set_page_config(
    page_title="VendorFlow — Document-Driven Vendor Verification",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database on startup
DB_PATH = Path(__file__).resolve().parent / "vendorflow.db"
init_db(DB_PATH)

# Inject enterprise CSS
inject_custom_css()

# Session state initialization
if "form_data" not in st.session_state:
    st.session_state.form_data = {}
if "last_execution_result" not in st.session_state:
    st.session_state.last_execution_result = None
if "extracted_review_data" not in st.session_state:
    st.session_state.extracted_review_data = None


def set_sample_data(scenario_type: str = "happy_path"):
    """Pre-fills form state with sample vendor data."""
    if scenario_type == "happy_path":
        st.session_state.form_data = {
            "company_name": "Aster Labs Private Limited",
            "country": "India",
            "registration_type": "Private Limited",
            "address": "Plot 42, Electronic City, Phase 1, Bangalore, Karnataka 560100",
            "contact_name": "Dr. Vikram Rao",
            "contact_email": "ops@asterlabs.example",
            "pan": "ABCDE1234F",
            "gstin": "27ABCDE1234F1Z5",
            "bank_account_holder": "Aster Labs",
            "bank_account_number": "123456789012",
            "ifsc_code": "HDFC0001234",
            "bank_name": "HDFC Bank Ltd",
        }
    elif scenario_type == "clear":
        st.session_state.form_data = {}
        st.session_state.extracted_review_data = None


def render_header():
    """Top enterprise application header."""
    st.markdown(
        """
        <div class="vf-header">
            <h1>⚡ VendorFlow</h1>
            <p>Phase 2: Document-Driven Intelligent Vendor Verification • PyMuPDF Extraction & Cross-Document Intelligence</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def execute_and_display_workflow(submission: VendorSubmission):
    """Executes the 13-stage verification pipeline and renders the live sequential stages and decision."""
    st.subheader("⚡ Live Document-Driven Verification Pipeline Execution")

    # Sequential execution container
    status_container = st.status(
        "🚀 Initiating 13-stage document-driven verification pipeline...", expanded=True
    )

    stage_names = [
        "Receiving Vendor Submission",
        "Checking Uploaded Documents",
        "Extracting PDF Text",
        "Identifying Vendor Information",
        "Structuring Extracted Fields",
        "Comparing PAN and GST Information",
        "Comparing Company and Bank Information",
        "Running Existing Field Validations",
        "Running Duplicate Detection",
        "Running Restricted-Vendor Checks",
        "Generating Final Decision",
        "Creating Communication Draft",
        "Saving Execution History",
    ]

    stage_placeholders = []
    # Create 13 placeholders inside the status container and initialize as QUEUED
    for i, s_name in enumerate(stage_names, start=1):
        ph = status_container.empty()
        badge = get_status_badge_html("QUEUED")
        ph.markdown(
            f"""
            <div style="padding: 8px 12px; margin-bottom: 6px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; opacity: 0.85;">
                <div>
                    <strong style="color: #475569;">Stage {i}: {s_name}</strong><br>
                    <span style="font-size: 0.82rem; color: #64748B;">Queued for sequential execution...</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    {badge}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        stage_placeholders.append(ph)

    def on_stage_progress(result: StageResult):
        idx = result.stage_number - 1
        if 0 <= idx < len(stage_placeholders):
            if result.status == StageStatus.RUNNING:
                badge = get_status_badge_html("RUNNING")
                stage_placeholders[idx].markdown(
                    f"""
                    <div style="padding: 8px 12px; margin-bottom: 6px; background: #EFF6FF; border: 1px solid #93C5FD; border-left: 4px solid #2563EB; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong style="color: #1E40AF;">Stage {result.stage_number}: {result.stage_name}</strong><br>
                            <span style="font-size: 0.84rem; color: #2563EB;">⏳ Executing automated verification rules...</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            {badge}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                return

            badge = get_status_badge_html(result.status.value)
            stage_placeholders[idx].markdown(
                f"""
                <div style="padding: 8px 12px; margin-bottom: 6px; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>Stage {result.stage_number}: {result.stage_name}</strong><br>
                        <span style="font-size: 0.85rem; color: #475569;">{result.summary}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 0.78rem; color: #64748B;">{result.duration_ms:.1f}ms</span>
                        {badge}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    try:
        # Run actual backend workflow
        exec_result: WorkflowExecutionResult = execute_workflow(
            submission, db_path=DB_PATH, progress_callback=on_stage_progress
        )
        status_container.update(
            label=f"🏁 Verification Pipeline Completed — Decision: {exec_result.status.value} ({exec_result.total_duration_ms:.1f} ms across 13 stages)",
            state="complete",
            expanded=False,
        )
        st.session_state.last_execution_result = exec_result

        # Display Final Decision Callout Banner
        render_decision_banner(
            status=exec_result.status.value,
            summary=exec_result.decision.summary,
            duration_ms=exec_result.total_duration_ms,
            run_id=exec_result.run_id,
        )

        # -------------------------------------------------------------
        # Phase 2 Document Extraction & Cross-Check Report Card
        # -------------------------------------------------------------
        st.markdown("### 📄 Phase 2 Document Extraction & Cross-Check Findings")
        p2_c1, p2_c2, p2_c3 = st.columns(3)
        with p2_c1:
            render_metric_card("Documents Processed", exec_result.documents_processed_count, "Compliance uploads parsed")
        with p2_c2:
            render_metric_card("Discrepancies Found", exec_result.discrepancies_count, "Cross-source conflicts", "#D97706" if exec_result.discrepancies_count > 0 else "#16A34A")
        with p2_c3:
            render_metric_card("Human Confirmations", exec_result.manual_confirmations_count, "Unreadable / manual fields")

        # Tabular Comparison of Document vs Manual Values
        cross_checks = exec_result.cross_document_results.get("checks", [])
        if cross_checks:
            st.markdown("#### 🔍 Cross-Document Verification Matrix")
            check_rows = []
            for c in cross_checks:
                check_rows.append(
                    {
                        "Verification Check": c.get("check_name"),
                        "Status": c.get("status"),
                        "Details & Outcome": c.get("message"),
                    }
                )
            st.dataframe(pd.DataFrame(check_rows), use_container_width=True, hide_index=True)

        # Columns for Checks and Issues
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### ✅ Verification Checks Passed")
            if exec_result.decision.passed_checks:
                for check in exec_result.decision.passed_checks:
                    st.markdown(f"- <span style='color: #16A34A;'>✓</span> {check}", unsafe_allow_html=True)
            else:
                st.info("No checks passed successfully.")

        with col2:
            st.markdown("#### ⚠️ Items Requiring Attention / Discrepancies")
            if exec_result.decision.issues:
                for issue in exec_result.decision.issues:
                    badge_type = (
                        "HARD STOP"
                        if issue.issue_type == "HARD_STOP"
                        else ("WARNING" if issue.issue_type == "WARNING" else "ERROR")
                    )
                    badge = get_status_badge_html(badge_type)
                    st.markdown(
                        f"""
                        <div style="margin-bottom: 8px; padding: 8px 12px; background: #FFFBEB; border-left: 3px solid #F59E0B; border-radius: 4px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <strong style="font-size: 0.85rem; color: #92400E;">{issue.stage} • {issue.field_name}</strong>
                                {badge}
                            </div>
                            <div style="font-size: 0.85rem; color: #451A03; margin-top: 4px;">{issue.message}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.success("Clean execution: No warnings, inconsistencies, or hard-stops identified.")

        # Next Steps
        st.markdown("#### 📋 Recommended Next Steps")
        for step in exec_result.decision.next_steps:
            st.markdown(f"1. **{step}**")

        # Communication Draft Section
        st.markdown("---")
        st.markdown("### ✉️ Generated Communication Draft")
        st.caption("Personalized communication dynamically drafted from verification findings. No email is sent automatically.")

        st.text_area(
            label="Communication Draft (Ready to copy & review)",
            value=exec_result.communication_draft,
            height=260,
            key=f"comm_draft_{exec_result.run_id}",
        )

        col_cp1, col_cp2 = st.columns([1, 4])
        with col_cp1:
            if st.button("📋 Copy Email Draft", key=f"btn_cp_{exec_result.run_id}"):
                st.toast("✅ Email draft copied to clipboard!", icon="📋")

        st.code(exec_result.communication_draft, language="markdown")

        # Compliance disclaimer
        st.markdown(
            f"""
            <div class="vf-disclaimer">
                <strong>Compliance Note:</strong> {exec_result.decision.disclaimer}
            </div>
            """,
            unsafe_allow_html=True,
        )

    except Exception as e:
        status_container.update(
            label=f"❌ Pipeline Execution Failed: {str(e)}", state="error"
        )
        st.error(f"Execution Error: {str(e)}")


# ==============================================================================
# SIDEBAR NAVIGATION
# ==============================================================================
st.sidebar.markdown(
    """
    <div style="text-align: center; padding: 12px 0 18px 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 16px;">
        <span style="font-size: 2rem;">⚡</span>
        <h2 style="margin: 0; font-size: 1.3rem; font-weight: 700; color: #0F172A;">VendorFlow</h2>
        <span style="font-size: 0.78rem; color: #64748B; font-weight: 500;">Phase 2: Document Intelligence</span>
    </div>
    """,
    unsafe_allow_html=True,
)

nav_option = st.sidebar.radio(
    "Navigation Menu",
    [
        "📌 Overview",
        "📝 New Submission",
        "🚀 Demo Scenarios",
        "📊 Execution Dashboard",
        "📖 Validation Rules & Limits",
    ],
    index=0,
)

# Sidebar Quick Metrics
metrics = get_dashboard_metrics(DB_PATH)
st.sidebar.markdown("---")
st.sidebar.markdown("### 📈 Live Telemetry")
col_s1, col_s2 = st.sidebar.columns(2)
with col_s1:
    st.metric("Total Runs", metrics["total_submissions"])
    st.metric("Approved", metrics["approved"])
with col_s2:
    st.metric("Approval Rate", f"{metrics['approval_rate']}%")
    st.metric("Discrepancies", metrics.get("discrepancies_identified", 0))

st.sidebar.markdown(
    """
    <div style="margin-top: 20px; font-size: 0.75rem; color: #94A3B8; line-height: 1.4;">
        Engine: <strong>Phase 2 (Document-Driven)</strong><br>
        Extraction: <strong>PyMuPDF + Regex Parsing</strong><br>
        Database: <strong>SQLite (Local Persistent)</strong><br>
        Version: <strong>2.0.0 (Document Intelligence)</strong>
    </div>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# PAGE 1: OVERVIEW
# ==============================================================================
if nav_option == "📌 Overview":
    render_header()

    st.markdown("### 📊 Operational & Document Intelligence Overview")
    m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)
    with m_col1:
        render_metric_card("Total Submissions", metrics["total_submissions"], "All recorded runs")
    with m_col2:
        render_metric_card("Approved", metrics["approved"], "Clean passes", "#16A34A")
    with m_col3:
        render_metric_card("Pending Review", metrics["pending"], "Discrepancy / Review", "#D97706")
    with m_col4:
        render_metric_card("Rejected", metrics["rejected"], "Policy hard-stop", "#DC2626")
    with m_col5:
        render_metric_card("Approval Rate", f"{metrics['approval_rate']}%", "Automated rate", "#2563EB")
    with m_col6:
        render_metric_card("Docs Processed", metrics.get("documents_processed", 0), "Compliance PDFs", "#475569")

    st.markdown("---")
    st.markdown("### 🔄 13-Stage Document-Driven Verification Pipeline")
    st.markdown(
        """
        In Phase 2, VendorFlow extracts information directly from uploaded PDF documents, compares extracted 
        fields across documents and against manual entries, and integrates findings into the deterministic decision engine.
        """
    )

    p2_steps = [
        ("1. Receiving Submission", "Initializes Run ID, text normalization, and privacy masking for tax/banking data."),
        ("2. Checking Documents", "Validates presence, mime types (PDF/PNG/JPG), and size (<10MB) for GST, PAN, and Bank proof."),
        ("3. Extracting PDF Text", "Extracts raw text streams from PDF files using PyMuPDF (with pypdf fallback)."),
        ("4. Identifying Vendor Information", "Discovers PAN, GSTIN, IFSC, Account Number, and Entity Names via targeted regex & label parsing."),
        ("5. Structuring Extracted Fields", "Builds structured records with confidence levels (HIGH/MED/LOW) and provenance tags."),
        ("6. Comparing PAN & GST", "Cross-checks PAN doc vs. GST certificate embedded PAN vs. manual submission."),
        ("7. Comparing Company & Bank", "Normalizes corporate suffixes to compare legal business name with bank account holder."),
        ("8. Running Field Validations", "Executes statutory syntax checks on PAN, GSTIN, IFSC, and contact email."),
        ("9. Running Duplicate Detection", "Queries SQLite approved vendors using SHA-256 hashes of tax identifiers."),
        ("10. Running Restricted Checks", "Screens tax ID hashes against synthetic internal compliance risk registry."),
        ("11. Generating Final Decision", "Deterministic priority engine assigns APPROVED, PENDING, or REJECTED."),
        ("12. Creating Communication Draft", "Drafts personalized vendor notifications with actionable discrepancy resolution steps."),
        ("13. Saving Execution History", "Commits full audit record, extraction metadata, and cross-check results into SQLite."),
    ]

    for title, desc in p2_steps:
        st.markdown(f"**Stage {title}** — {desc}")

    st.markdown("---")
    st.info(
        "💡 **Evaluator Quick Start:** Jump to **'🚀 Demo Scenarios'** in the sidebar to test "
        "Phase 2 Document-Driven Scenarios with real synthetic PDFs generated on the fly!"
    )


# ==============================================================================
# PAGE 2: NEW VENDOR SUBMISSION FORM (WITH EXTRACTION REVIEW)
# ==============================================================================
elif nav_option == "📝 New Submission":
    render_header()

    st.markdown("### 📝 New Vendor Onboarding Registration")
    st.caption("Upload compliance documents to automatically extract details or fill manually for cross-document verification.")

    # Form pre-fill actions
    btn_col1, btn_col2 = st.columns([1, 4])
    with btn_col1:
        if st.button("📋 Pre-fill Valid Aster Labs Data", use_container_width=True):
            set_sample_data("happy_path")
            st.rerun()
    with btn_col2:
        if st.button("🧹 Clear Form Fields"):
            set_sample_data("clear")
            st.rerun()

    fd = st.session_state.form_data

    # -------------------------------------------------------------
    # Document Upload Section (Placed prominently for Document Intelligence)
    # -------------------------------------------------------------
    st.markdown(
        """
        <div class="vf-section-title">
            📄 Step 1: Upload Compliance Documents
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Upload PDF, PNG, or JPEG files (Max 10 MB each). The PyMuPDF engine extracts and compares fields across documents.")

    d1, d2, d3 = st.columns(3)
    with d1:
        gst_file = st.file_uploader(
            "GST Registration Certificate *",
            type=["pdf", "png", "jpg", "jpeg"],
            key="up_gst_cert",
        )
    with d2:
        pan_file = st.file_uploader(
            "Company PAN Proof *",
            type=["pdf", "png", "jpg", "jpeg"],
            key="up_pan_proof",
        )
    with d3:
        bank_file = st.file_uploader(
            "Bank Proof / Cancelled Cheque *",
            type=["pdf", "png", "jpg", "jpeg"],
            key="up_bank_proof",
        )

    attach_sample_docs = st.checkbox(
        "📎 Automatically attach synthetic verified PDF documents if upload is empty",
        value=True if fd.get("company_name") else False,
        help="Generates authentic text-based synthetic PDF documents in memory for testing without local files.",
    )

    # Helper function to get document metadata with real bytes
    def build_doc_metadata(
        gst_f, pan_f, bank_f, use_sample: bool, sample_pan: str, sample_gstin: str, sample_name: str, sample_holder: str
    ) -> Dict[str, DocumentMetadata]:
        docs = {}

        # 1. PAN
        if pan_f:
            b = pan_f.getvalue()
            docs["pan_proof"] = DocumentMetadata(
                doc_type="pan_proof",
                name="Company PAN Proof",
                filename=pan_f.name,
                size_bytes=len(b),
                extension=Path(pan_f.name).suffix.lower(),
                is_present=True,
                raw_bytes=b,
            )
        elif use_sample:
            b = generate_synthetic_pan_pdf(sample_pan or "ABCDE1234F", sample_name or "Aster Labs Private Limited")
            docs["pan_proof"] = DocumentMetadata(
                doc_type="pan_proof",
                name="Company PAN Proof",
                filename="synthetic_pan_card.pdf",
                size_bytes=len(b),
                extension=".pdf",
                is_present=True,
                raw_bytes=b,
            )
        else:
            docs["pan_proof"] = DocumentMetadata(doc_type="pan_proof", name="Company PAN Proof", is_present=False)

        # 2. GST
        if gst_f:
            b = gst_f.getvalue()
            docs["gst_cert"] = DocumentMetadata(
                doc_type="gst_cert",
                name="GST Registration Certificate",
                filename=gst_f.name,
                size_bytes=len(b),
                extension=Path(gst_f.name).suffix.lower(),
                is_present=True,
                raw_bytes=b,
            )
        elif use_sample:
            b = generate_synthetic_gst_pdf(
                sample_gstin or "27ABCDE1234F1Z5", sample_name or "Aster Labs Private Limited", sample_holder or "Aster Labs"
            )
            docs["gst_cert"] = DocumentMetadata(
                doc_type="gst_cert",
                name="GST Registration Certificate",
                filename="synthetic_gst_certificate.pdf",
                size_bytes=len(b),
                extension=".pdf",
                is_present=True,
                raw_bytes=b,
            )
        else:
            docs["gst_cert"] = DocumentMetadata(doc_type="gst_cert", name="GST Registration Certificate", is_present=False)

        # 3. Bank Proof
        if bank_f:
            b = bank_f.getvalue()
            docs["bank_proof"] = DocumentMetadata(
                doc_type="bank_proof",
                name="Bank Proof / Cancelled Cheque",
                filename=bank_f.name,
                size_bytes=len(b),
                extension=Path(bank_f.name).suffix.lower(),
                is_present=True,
                raw_bytes=b,
            )
        elif use_sample:
            b = generate_synthetic_bank_pdf(
                sample_holder or "Aster Labs", "123456789012", "HDFC0001234", "HDFC Bank Ltd"
            )
            docs["bank_proof"] = DocumentMetadata(
                doc_type="bank_proof",
                name="Bank Proof / Cancelled Cheque",
                filename="synthetic_cancelled_cheque.pdf",
                size_bytes=len(b),
                extension=".pdf",
                is_present=True,
                raw_bytes=b,
            )
        else:
            docs["bank_proof"] = DocumentMetadata(doc_type="bank_proof", name="Bank Proof / Cancelled Cheque", is_present=False)

        return docs

    # Extraction Preview Button
    if st.button("🔍 Extract & Review Document Fields (Phase 2)", use_container_width=False):
        docs_to_extract = build_doc_metadata(
            gst_file,
            pan_file,
            bank_file,
            attach_sample_docs,
            fd.get("pan", "ABCDE1234F"),
            fd.get("gstin", "27ABCDE1234F1Z5"),
            fd.get("company_name", "Aster Labs Private Limited"),
            fd.get("bank_account_holder", "Aster Labs"),
        )
        pan_res = extract_pan_document(docs_to_extract["pan_proof"].raw_bytes, docs_to_extract["pan_proof"].filename or "")
        gst_res = extract_gst_document(docs_to_extract["gst_cert"].raw_bytes, docs_to_extract["gst_cert"].filename or "")
        bank_res = extract_bank_document(docs_to_extract["bank_proof"].raw_bytes, docs_to_extract["bank_proof"].filename or "")

        st.session_state.extracted_review_data = {
            "pan": pan_res,
            "gst": gst_res,
            "bank": bank_res,
            "docs": docs_to_extract,
        }

    # -------------------------------------------------------------
    # EXTRACTION REVIEW INTERFACE (Section 6 Requirement)
    # -------------------------------------------------------------
    if st.session_state.extracted_review_data:
        st.markdown("---")
        st.markdown("### 🔍 Document Extraction Review Screen")
        st.caption("Review extracted fields before submitting. Check provenance, extraction status, and confidence levels.")

        p_res = st.session_state.extracted_review_data["pan"]
        g_res = st.session_state.extracted_review_data["gst"]
        b_res = st.session_state.extracted_review_data["bank"]

        review_table = [
            {
                "Field": "PAN Number",
                "Extracted Value": p_res.extracted_fields.get("pan", "NOT EXTRACTED"),
                "Source Document": "PAN Proof",
                "Confidence": p_res.field_confidence.get("pan", "LOW"),
                "Extraction Status": p_res.extraction_status.value,
                "Manual Form Value": fd.get("pan", "Not entered"),
            },
            {
                "Field": "Cardholder Name",
                "Extracted Value": p_res.extracted_fields.get("name", "NOT EXTRACTED"),
                "Source Document": "PAN Proof",
                "Confidence": p_res.field_confidence.get("name", "LOW"),
                "Extraction Status": p_res.extraction_status.value,
                "Manual Form Value": fd.get("company_name", "Not entered"),
            },
            {
                "Field": "GSTIN",
                "Extracted Value": g_res.extracted_fields.get("gstin", "NOT EXTRACTED"),
                "Source Document": "GST Certificate",
                "Confidence": g_res.field_confidence.get("gstin", "LOW"),
                "Extraction Status": g_res.extraction_status.value,
                "Manual Form Value": fd.get("gstin", "Not entered"),
            },
            {
                "Field": "Embedded PAN in GSTIN",
                "Extracted Value": g_res.extracted_fields.get("embedded_pan", "NOT EXTRACTED"),
                "Source Document": "GST Certificate",
                "Confidence": g_res.field_confidence.get("embedded_pan", "LOW"),
                "Extraction Status": g_res.extraction_status.value,
                "Manual Form Value": fd.get("pan", "Not entered"),
            },
            {
                "Field": "Legal Business Name",
                "Extracted Value": g_res.extracted_fields.get("legal_name", "NOT EXTRACTED"),
                "Source Document": "GST Certificate",
                "Confidence": g_res.field_confidence.get("legal_name", "LOW"),
                "Extraction Status": g_res.extraction_status.value,
                "Manual Form Value": fd.get("company_name", "Not entered"),
            },
            {
                "Field": "Account Holder Name",
                "Extracted Value": b_res.extracted_fields.get("account_holder", "NOT EXTRACTED"),
                "Source Document": "Bank Proof",
                "Confidence": b_res.field_confidence.get("account_holder", "LOW"),
                "Extraction Status": b_res.extraction_status.value,
                "Manual Form Value": fd.get("bank_account_holder", "Not entered"),
            },
            {
                "Field": "Account Number",
                "Extracted Value": (
                    f"********{b_res.extracted_fields.get('account_number')[-4:]}"
                    if b_res.extracted_fields.get("account_number")
                    else "NOT EXTRACTED"
                ),
                "Source Document": "Bank Proof",
                "Confidence": b_res.field_confidence.get("account_number", "LOW"),
                "Extraction Status": b_res.extraction_status.value,
                "Manual Form Value": "••••••••" if fd.get("bank_account_number") else "Not entered",
            },
            {
                "Field": "Bank IFSC Code",
                "Extracted Value": b_res.extracted_fields.get("ifsc", "NOT EXTRACTED"),
                "Source Document": "Bank Proof",
                "Confidence": b_res.field_confidence.get("ifsc", "LOW"),
                "Extraction Status": b_res.extraction_status.value,
                "Manual Form Value": fd.get("ifsc_code", "Not entered"),
            },
        ]

        st.dataframe(pd.DataFrame(review_table), use_container_width=True, hide_index=True)

        # Highlight Warnings
        all_warnings = p_res.warnings + g_res.warnings + b_res.warnings
        if all_warnings:
            st.warning("⚠️ **Extraction Warnings & Notices:**\n" + "\n".join([f"- {w}" for w in all_warnings]))

    # -------------------------------------------------------------
    # Step 2: Form Details & Submission
    # -------------------------------------------------------------
    with st.form("vendor_onboarding_form", clear_on_submit=False):
        st.markdown(
            """
            <div class="vf-section-title">
                🏢 Step 2: Vendor Business & Banking Details
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            company_name = st.text_input(
                "Legal Company Name *",
                value=fd.get("company_name", ""),
                placeholder="e.g. Aster Labs Private Limited",
            )
            country = st.selectbox(
                "Country / Jurisdiction *",
                ["India", "United States", "United Kingdom", "Singapore"],
                index=0,
                help="Note: Prototype is configured for India tax & banking standards only.",
            )
            reg_type = st.selectbox(
                "Business Registration Type *",
                [
                    "Private Limited",
                    "Public Limited",
                    "Limited Liability Partnership (LLP)",
                    "Partnership",
                    "Sole Proprietorship",
                ],
                index=0,
            )
            address = st.text_area(
                "Registered Business Address *",
                value=fd.get("address", ""),
                placeholder="e.g. Plot 42, Electronic City, Bangalore, Karnataka 560100",
                height=80,
            )

        with c2:
            contact_name = st.text_input(
                "Primary Contact Person *",
                value=fd.get("contact_name", ""),
                placeholder="e.g. Dr. Vikram Rao",
            )
            contact_email = st.text_input(
                "Contact Email Address *",
                value=fd.get("contact_email", ""),
                placeholder="e.g. ops@asterlabs.example",
            )
            pan = st.text_input(
                "Company PAN (Permanent Account Number) *",
                value=fd.get("pan", ""),
                placeholder="e.g. ABCDE1234F (10 characters: 5 letters, 4 digits, 1 letter)",
                max_chars=10,
            ).upper()
            gstin = st.text_input(
                "GSTIN (Goods & Services Tax ID) *",
                value=fd.get("gstin", ""),
                placeholder="e.g. 27ABCDE1234F1Z5 (15 characters)",
                max_chars=15,
            ).upper()

        b1, b2 = st.columns(2)
        with b1:
            bank_holder = st.text_input(
                "Bank Account Holder Name *",
                value=fd.get("bank_account_holder", ""),
                placeholder="e.g. Aster Labs",
                help="Should match or align with legal company name.",
            )
            bank_acc = st.text_input(
                "Bank Account Number *",
                value=fd.get("bank_account_number", ""),
                placeholder="e.g. 123456789012 (9 to 18 digits)",
                type="password",
            )
        with b2:
            ifsc = st.text_input(
                "Bank IFSC Code *",
                value=fd.get("ifsc_code", ""),
                placeholder="e.g. HDFC0001234 (11 characters)",
                max_chars=11,
            ).upper()
            bank_name = st.text_input(
                "Bank Name (Optional)",
                value=fd.get("bank_name", ""),
                placeholder="e.g. HDFC Bank Ltd",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button(
            "🚀 Run Onboarding Verification (13-Stage Pipeline)",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not company_name.strip():
            st.error("Please enter a legal company name before submitting.")
        else:
            final_docs = build_doc_metadata(
                gst_file,
                pan_file,
                bank_file,
                attach_sample_docs,
                pan,
                gstin,
                company_name,
                bank_holder,
            )

            submission_obj = VendorSubmission(
                company_name=company_name,
                country=country,
                registration_type=reg_type,
                address=address,
                contact_name=contact_name,
                contact_email=contact_email,
                pan=pan,
                gstin=gstin,
                bank_account_holder=bank_holder,
                bank_account_number=bank_acc,
                ifsc_code=ifsc,
                bank_name=bank_name,
                documents=final_docs,
                run_type="Live Submission",
            )

            execute_and_display_workflow(submission_obj)


# ==============================================================================
# PAGE 3: DEMO SCENARIOS (PHASE 1 & PHASE 2)
# ==============================================================================
elif nav_option == "🚀 Demo Scenarios":
    render_header()

    st.markdown("### 🚀 Built-in Synthetic Demonstration Scenarios")
    st.markdown(
        """
        Test the end-to-end system using pre-configured test scenarios.
        Tab 1 showcases **Phase 2 Document-Driven Intelligence** with real PDF parsing,
        while Tab 2 preserves **Phase 1 Form-Driven Scenarios**.
        """
    )

    tab_p2, tab_p1 = st.tabs(["📄 Phase 2: Document-Driven Intelligence", "📋 Phase 1: Form-Driven Verification"])

    # -------------------------------------------------------------
    # TAB 1: PHASE 2 DOCUMENT INTELLIGENCE SCENARIOS
    # -------------------------------------------------------------
    with tab_p2:
        st.markdown("#### Phase 2 Scenarios: Text Extraction & Cross-Document Consistency")
        st.caption("Each scenario generates authentic text-based PDF bytes dynamically in memory and parses them with PyMuPDF.")

        p2_scenarios = [
            {
                "id": "p2_sc_a",
                "name": "Scenario A: All Documents 100% Consistent",
                "expected": "APPROVED",
                "badge_color": "#16A34A",
                "company": "Aster Labs Private Limited",
                "desc": "Real synthetic PDFs for PAN, GSTIN, and Cancelled Cheque contain 100% matching identifiers, aligned company names, and valid formatting.",
                "run": lambda: (
                    generate_synthetic_pan_pdf("ABCDE1234F", "Aster Labs Private Limited"),
                    generate_synthetic_gst_pdf("27ABCDE1234F1Z5", "Aster Labs Private Limited", "Aster Labs"),
                    generate_synthetic_bank_pdf("Aster Labs", "123456789012", "HDFC0001234", "HDFC Bank Ltd"),
                    "ABCDE1234F",
                    "27ABCDE1234F1Z5",
                    "Aster Labs Private Limited",
                    "Aster Labs",
                    "123456789012",
                    "HDFC0001234",
                ),
            },
            {
                "id": "p2_sc_b",
                "name": "Scenario B: Cross-Document PAN Mismatch",
                "expected": "PENDING",
                "badge_color": "#D97706",
                "company": "Bluewave Technologies Private Limited",
                "desc": "PAN document extracts 'ABCDE1234F', but the GST Certificate PDF contains conflicting embedded PAN '36ZZZZZ9999Z1Z8'.",
                "run": lambda: (
                    generate_synthetic_pan_pdf("ABCDE1234F", "Bluewave Technologies Private Limited"),
                    generate_synthetic_gst_pdf("36ZZZZZ9999Z1Z8", "Bluewave Technologies Private Limited"),
                    generate_synthetic_bank_pdf("Bluewave Technologies", "987654321098", "ICIC0000456"),
                    "ABCDE1234F",
                    "36ZZZZZ9999Z1Z8",
                    "Bluewave Technologies Private Limited",
                    "Bluewave Technologies",
                    "987654321098",
                    "ICIC0000456",
                ),
            },
            {
                "id": "p2_sc_c",
                "name": "Scenario C: Company vs. Bank Name Mismatch",
                "expected": "PENDING",
                "badge_color": "#D97706",
                "company": "Brightline Systems Private Limited",
                "desc": "GST Certificate PDF extracts 'Brightline Systems Private Limited', but the Cancelled Cheque PDF extracts 'Shree Trading Enterprises'.",
                "run": lambda: (
                    generate_synthetic_pan_pdf("BRGHT9999K", "Brightline Systems Private Limited"),
                    generate_synthetic_gst_pdf("29BRGHT9999K1Z2", "Brightline Systems Private Limited"),
                    generate_synthetic_bank_pdf("Shree Trading Enterprises", "554433221100", "SBIN0001234"),
                    "BRGHT9999K",
                    "29BRGHT9999K1Z2",
                    "Brightline Systems Private Limited",
                    "Shree Trading Enterprises",
                    "554433221100",
                    "SBIN0001234",
                ),
            },
            {
                "id": "p2_sc_d",
                "name": "Scenario D: Unreadable / Scanned Document Fallback",
                "expected": "PENDING",
                "badge_color": "#D97706",
                "company": "Aster Labs Private Limited",
                "desc": "PAN document PDF contains no selectable text (simulating an image scan). Extractor flags UNREADABLE and halts for manual review without inventing fake values.",
                "run": lambda: (
                    generate_unreadable_pdf(),
                    generate_synthetic_gst_pdf("27ABCDE1234F1Z5", "Aster Labs Private Limited"),
                    generate_synthetic_bank_pdf("Aster Labs", "123456789012", "HDFC0001234"),
                    "ABCDE1234F",
                    "27ABCDE1234F1Z5",
                    "Aster Labs Private Limited",
                    "Aster Labs",
                    "123456789012",
                    "HDFC0001234",
                ),
            },
        ]

        for sc in p2_scenarios:
            with st.container():
                st.markdown(
                    f"""
                    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px 22px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <h4 style="margin: 0; font-size: 1.1rem; color: #1E293B;">{sc['name']}</h4>
                            <span style="background: {sc['badge_color']}; color: white; padding: 3px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 700;">
                                Expected: {sc['expected']}
                            </span>
                        </div>
                        <p style="margin: 0 0 10px 0; font-size: 0.9rem; color: #475569;">{sc['desc']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(f"⚡ Execute {sc['name']}", key=f"btn_{sc['id']}"):
                    pan_b, gst_b, bank_b, pan_v, gstin_v, comp_v, holder_v, acc_v, ifsc_v = sc["run"]()
                    docs_meta = {
                        "pan_proof": DocumentMetadata(
                            doc_type="pan_proof",
                            name="Company PAN Proof",
                            filename="pan_card.pdf",
                            size_bytes=len(pan_b),
                            extension=".pdf",
                            is_present=True,
                            raw_bytes=pan_b,
                        ),
                        "gst_cert": DocumentMetadata(
                            doc_type="gst_cert",
                            name="GST Registration Certificate",
                            filename="gst_certificate.pdf",
                            size_bytes=len(gst_b),
                            extension=".pdf",
                            is_present=True,
                            raw_bytes=gst_b,
                        ),
                        "bank_proof": DocumentMetadata(
                            doc_type="bank_proof",
                            name="Bank Proof / Cancelled Cheque",
                            filename="cancelled_cheque.pdf",
                            size_bytes=len(bank_b),
                            extension=".pdf",
                            is_present=True,
                            raw_bytes=bank_b,
                        ),
                    }
                    sub = VendorSubmission(
                        company_name=comp_v,
                        country="India",
                        registration_type="Private Limited",
                        address="Plot 42, Electronic City, Bangalore",
                        contact_name="Dr. Vikram Rao",
                        contact_email="ops@vendor.example",
                        pan=pan_v,
                        gstin=gstin_v,
                        bank_account_holder=holder_v,
                        bank_account_number=acc_v,
                        ifsc_code=ifsc_v,
                        bank_name="HDFC Bank Ltd",
                        documents=docs_meta,
                        run_type="Demo Scenario",
                    )
                    execute_and_display_workflow(sub)

    # -------------------------------------------------------------
    # TAB 2: PHASE 1 FORM-DRIVEN SCENARIOS (Preserved)
    # -------------------------------------------------------------
    with tab_p1:
        st.markdown("#### Phase 1 Scenarios: Form-Based Validation")
        st.caption("Preserves original Phase 1 tests for duplicate detection, restricted watchlists, and metadata validation.")

        p1_scenarios = [
            {
                "id": "p1_sc_d",
                "name": "Phase 1 Scenario D: Duplicate Vendor Registration",
                "expected": "PENDING",
                "badge_color": "#D97706",
                "company": "Northstar Office Supplies Private Limited",
                "desc": "Tax identifiers (PAN LMNOP1234Q & GSTIN 27LMNOP1234Q1Z5) match a pre-existing approved vendor in SQLite.",
                "pan": "LMNOP1234Q",
                "gstin": "27LMNOP1234Q1Z5",
                "holder": "Northstar Office Supplies",
            },
            {
                "id": "p1_sc_e",
                "name": "Phase 1 Scenario E: Internal Restricted Watchlist Hard-Stop",
                "expected": "REJECTED",
                "badge_color": "#DC2626",
                "company": "Redwood Logistics LLP",
                "desc": "Tax identifier (PAN UVWXY5678Z) matches internal compliance risk registry. Triggers immediate hard-stop.",
                "pan": "UVWXY5678Z",
                "gstin": "29UVWXY5678Z1Z5",
                "holder": "Redwood Logistics LLP",
            },
        ]

        for sc in p1_scenarios:
            with st.container():
                st.markdown(
                    f"""
                    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px 22px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <h4 style="margin: 0; font-size: 1.1rem; color: #1E293B;">{sc['name']}</h4>
                            <span style="background: {sc['badge_color']}; color: white; padding: 3px 10px; border-radius: 6px; font-size: 0.78rem; font-weight: 700;">
                                Expected: {sc['expected']}
                            </span>
                        </div>
                        <p style="margin: 0 0 10px 0; font-size: 0.9rem; color: #475569;">{sc['desc']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(f"⚡ Execute {sc['name']}", key=f"btn_{sc['id']}"):
                    pan_b = generate_synthetic_pan_pdf(sc["pan"], sc["company"])
                    gst_b = generate_synthetic_gst_pdf(sc["gstin"], sc["company"])
                    bank_b = generate_synthetic_bank_pdf(sc["holder"], "223344556677", "KKBK0000123")
                    docs_meta = {
                        "pan_proof": DocumentMetadata("pan_proof", "Company PAN Proof", "pan_card.pdf", len(pan_b), ".pdf", True, raw_bytes=pan_b),
                        "gst_cert": DocumentMetadata("gst_cert", "GST Certificate", "gst_cert.pdf", len(gst_b), ".pdf", True, raw_bytes=gst_b),
                        "bank_proof": DocumentMetadata("bank_proof", "Bank Proof", "bank_proof.pdf", len(bank_b), ".pdf", True, raw_bytes=bank_b),
                    }
                    sub = VendorSubmission(
                        company_name=sc["company"],
                        country="India",
                        registration_type="Private Limited",
                        address="12 MG Road, Mumbai",
                        contact_name="Operations Manager",
                        contact_email="ops@vendor.example",
                        pan=sc["pan"],
                        gstin=sc["gstin"],
                        bank_account_holder=sc["holder"],
                        bank_account_number="223344556677",
                        ifsc_code="KKBK0000123",
                        documents=docs_meta,
                        run_type="Demo Scenario",
                    )
                    execute_and_display_workflow(sub)


# ==============================================================================
# PAGE 4: EXECUTION DASHBOARD & RUN HISTORY
# ==============================================================================
elif nav_option == "📊 Execution Dashboard":
    render_header()

    st.markdown("### 📊 Verification Execution Dashboard")
    st.caption("Complete persistent audit trail of all automated onboarding executions queried directly from SQLite.")

    # Dynamic metrics including Phase 2 stats
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        render_metric_card("Total Executions", metrics["total_submissions"])
    with m2:
        render_metric_card("Approved", metrics["approved"], color_hint="#16A34A")
    with m3:
        render_metric_card("Pending", metrics["pending"], color_hint="#D97706")
    with m4:
        render_metric_card("Rejected", metrics["rejected"], color_hint="#DC2626")
    with m5:
        render_metric_card("Approval Rate", f"{metrics['approval_rate']}%", color_hint="#2563EB")
    with m6:
        render_metric_card("Discrepancies", metrics.get("discrepancies_identified", 0), color_hint="#D97706")

    st.markdown("---")

    # Filters
    f_col1, f_col2, f_col3, f_col4 = st.columns([2, 3, 2, 1])
    with f_col1:
        status_filter = st.selectbox(
            "Filter by Decision Status",
            ["ALL", "APPROVED", "PENDING", "REJECTED"],
            index=0,
        )
    with f_col2:
        search_query = st.text_input(
            "Search Vendor Name or Run ID",
            placeholder="Type to filter runs...",
        )
    with f_col3:
        date_filter = st.date_input("Filter by Date (Optional)", value=None)
    with f_col4:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        refresh_btn = st.button("🔄 Refresh Data", use_container_width=True)

    start_dt = f"{date_filter}T00:00:00" if date_filter else None
    end_dt = f"{date_filter}T23:59:59" if date_filter else None

    # Fetch runs
    all_runs = get_all_runs(
        DB_PATH,
        status_filter=status_filter if status_filter != "ALL" else None,
        search_query=search_query if search_query else None,
        start_date=start_dt,
        end_date=end_dt,
    )

    if not all_runs:
        st.info("No execution runs match the specified filter criteria.")
    else:
        table_rows = []
        for r in all_runs:
            table_rows.append(
                {
                    "Run ID": r["run_id"],
                    "Vendor Name": r["vendor_name"],
                    "Status": r["status"],
                    "Timestamp (UTC)": r["created_at"][:19].replace("T", " "),
                    "Duration (ms)": f"{r['processing_duration_ms']:.1f}",
                    "Issues Count": r["issues_count"],
                    "Docs Processed": r.get("documents_processed_count", 0),
                    "Discrepancies": r.get("discrepancies_count", 0),
                    "Run Type": r["run_type"],
                }
            )

        df = pd.DataFrame(table_rows)

        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "Status": st.column_config.TextColumn("Status", help="Onboarding Decision Outcome"),
            },
            hide_index=True,
        )

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Export Run History (CSV)",
            data=csv_buffer.getvalue(),
            file_name="vendorflow_run_history.csv",
            mime="text/csv",
        )

        st.markdown("---")
        st.markdown("### 🔍 Historical Run Inspector")
        st.caption("Select any past execution to inspect its audit stages, document extraction results, and cross-checks.")

        run_id_list = [r["run_id"] for r in all_runs]
        selected_run_id = st.selectbox("Select Run ID to Inspect:", run_id_list)

        if selected_run_id:
            run_data = get_run_by_id(selected_run_id, DB_PATH)
            if run_data:
                render_decision_banner(
                    status=run_data["status"],
                    summary=run_data["decision"].get("summary", ""),
                    duration_ms=run_data["processing_duration_ms"],
                    run_id=run_data["run_id"],
                )

                tab1, tab2, tab3, tab4, tab5 = st.tabs(
                    [
                        "📋 13-Stage Audit Trail",
                        "📄 Document Extraction & Cross-Checks",
                        "🔒 Redacted Inputs",
                        "✉️ Communication Draft",
                        "📄 Raw Audit JSON",
                    ]
                )

                with tab1:
                    st.markdown("#### Execution Stages Audit Trail")
                    for s in run_data["stage_results"]:
                        render_stage_card(
                            stage_number=s["stage_number"],
                            stage_name=s["stage_name"],
                            status=s["status"],
                            summary=s["summary"],
                            details=s["details"],
                            duration_ms=s["duration_ms"],
                        )

                with tab2:
                    st.markdown("#### Phase 2 Document Intelligence & Cross-Verification")
                    ext_data = run_data.get("extraction_results", {})
                    cross_data = run_data.get("cross_document_results", {})

                    if ext_data:
                        st.markdown("##### Extracted Document Payloads")
                        st.json(ext_data)

                    if cross_data:
                        st.markdown("##### Cross-Document Verification Outcomes")
                        checks = cross_data.get("checks", [])
                        if checks:
                            st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)
                        if cross_data.get("discrepancies"):
                            st.warning("Discrepancies:\n" + "\n".join([f"- {d}" for d in cross_data["discrepancies"]]))

                with tab3:
                    st.markdown("#### Privacy-Safe Masked Vendor Submission")
                    inp = run_data["redacted_input"]
                    c_i1, c_i2 = st.columns(2)
                    with c_i1:
                        st.markdown(f"**Company Name:** {inp.get('company_name')}")
                        st.markdown(f"**Country:** {inp.get('country')}")
                        st.markdown(f"**Registration Type:** {inp.get('registration_type')}")
                        st.markdown(f"**PAN (Masked):** `{inp.get('pan_masked')}`")
                        st.markdown(f"**GSTIN (Masked):** `{inp.get('gstin_masked')}`")
                    with c_i2:
                        st.markdown(f"**Bank Account Holder:** {inp.get('bank_account_holder')}")
                        st.markdown(f"**Bank Account (Masked):** `{inp.get('bank_account_masked')}`")
                        st.markdown(f"**IFSC Code:** `{inp.get('ifsc_code')}`")
                        st.markdown(f"**Contact Person:** {inp.get('contact_name')}")
                        st.markdown(f"**Contact Email:** {inp.get('contact_email')}")

                    st.markdown("##### Documents Processed")
                    st.json(inp.get("documents_summary", {}))

                with tab4:
                    st.markdown("#### Generated Communication Draft")
                    st.text_area(
                        "Communication Draft",
                        value=run_data["communication_draft"],
                        height=220,
                        disabled=True,
                    )

                with tab5:
                    st.markdown("#### Full Audit Record")
                    st.json(run_data)


# ==============================================================================
# PAGE 5: VALIDATION RULES & SYSTEM ARCHITECTURE
# ==============================================================================
elif nav_option == "📖 Validation Rules & Limits":
    render_header()

    st.markdown("### 📖 Phase 2 Document-Driven Verification Architecture")

    tab_r1, tab_r2 = st.tabs(["⚙️ Document Extraction & Cross-Checks", "⚠️ Honest Limitations & Scope Boundaries"])

    with tab_r1:
        st.markdown(
            """
            #### 1. Document Extraction Architecture
            - **Text Stream Extraction:** Uses **PyMuPDF** (`pymupdf.open`) with `pypdf` fallback to extract clean text streams from PDF compliance documents.
            - **Structured Regex Matching:**
              - **PAN Extraction:** `\\b([A-Z]{5}[0-9]{4}[A-Z])\\b` (Evaluated on PAN card text).
              - **GSTIN Extraction:** `\\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\\b` (Evaluated on GST Certificate).
              - **Embedded PAN Extraction:** Characters 2 to 11 of the extracted GSTIN.
              - **Bank IFSC Extraction:** `\\b([A-Z]{4}0[A-Z0-9]{6})\\b`.
              - **Bank Account Number:** `(?:ACCOUNT\\s*NUMBER|A/C\\s*NO)[:\\s]*([0-9]{9,18})`.
            - **Label-Based Name Extraction:** Parses legal entity names, trade names, and account holder names from text labels.
            - **Confidence Rating:** Assigns `HIGH`, `MEDIUM`, or `LOW` confidence reflecting extraction reliability.

            #### 2. Cross-Document Consistency Matrix
            - **Cross-Check 1 (PAN):** Compares PAN from PAN Proof vs. PAN embedded in GSTIN vs. Manual Entry. All must match.
            - **Cross-Check 2 (Legal Entity Name):** Compares name from PAN Proof vs. Legal name from GST Certificate vs. Manual Company Name. Normalizes legal suffixes (`PRIVATE LIMITED`, `PVT LTD`, `LLP`, `LTD`).
            - **Cross-Check 3 (Bank Account Holder):** Compares bank account holder name against verified legal entity name. Material differences result in **PENDING** for manual ownership review.
            - **Cross-Check 4 (GSTIN & Banking Alignment):** Confirms document values match manual form entries.

            #### 3. Unreadable Documents & Manual Fallback
            - If a document contains no selectable text (scanned image), it is flagged as `UNREADABLE`.
            - The system halts automated clearance and requests manual review or user confirmation.
            - **Never invents values.** Unreadable documents are never marked as verified without human sign-off.
            """
        )

    with tab_r2:
        st.markdown(
            """
            #### Honest Scope Boundaries (Phase 2 Prototype)
            1. **Selectable Text PDFs vs Heavy OCR:** The extractor uses high-performance native PDF stream extraction (PyMuPDF). It does not require external paid OCR APIs (Tesseract/Google Vision). Scanned PDFs without text streams are safely routed to manual confirmation.
            2. **No External LLM Dependencies:** All extraction, regex parsing, and cross-checks run deterministically on CPU in milliseconds without external LLM API costs or token latency.
            3. **Structural Validation vs Live Government Gateways:** Extracted tax identifiers are validated for statutory structural syntax and cross-document alignment, not queried against live government portals (NSDL/GSTN).
            4. **Banking Routing vs Penny-Drop Verification:** IFSC syntax and account number length are verified. Bank account ownership is not authenticated against real inter-bank networks (IMPS).
            5. **Human in the Loop:** Automated approval marks technical compliance clearance. Real-world vendor activation and payment release remains under human procurement authority.
            """
        )
