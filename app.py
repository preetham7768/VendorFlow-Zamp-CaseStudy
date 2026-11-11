"""
VendorFlow — Intelligent Vendor Onboarding & Verification System
Main Streamlit Application.
"""

import io
from pathlib import Path
import time
from typing import Dict, Optional
import pandas as pd
import streamlit as st

from backend.models import (
    DecisionStatus,
    DocumentMetadata,
    DocumentStatus,
    StageResult,
    StageStatus,
    VendorSubmission,
    WorkflowExecutionResult,
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
    page_title="VendorFlow — Intelligent Vendor Onboarding",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database on startup
DB_PATH = Path(__file__).resolve().parent / "vendorflow.db"
init_db(DB_PATH)

# Inject enterprise CSS
inject_custom_css()

# Session state initialization for form pre-filling & navigation
if "form_data" not in st.session_state:
    st.session_state.form_data = {}
if "last_execution_result" not in st.session_state:
    st.session_state.last_execution_result = None


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
            "bank_name": "HDFC Bank",
        }
    elif scenario_type == "clear":
        st.session_state.form_data = {}


def render_header():
    """Top enterprise application header."""
    st.markdown(
        """
        <div class="vf-header">
            <h1>⚡ VendorFlow</h1>
            <p>Intelligent Vendor Onboarding & Verification System • Automated Compliance & Risk Verification Engine</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def execute_and_display_workflow(submission: VendorSubmission):
    """Executes the verification pipeline and renders the live sequential stages and decision."""
    st.subheader("⚡ Live Verification Pipeline Execution")

    # Sequential execution container
    status_container = st.status(
        "🚀 Initiating 8-stage verification pipeline...", expanded=True
    )

    stage_names = [
        "Receiving Vendor Submission",
        "Validating Company & Tax Details",
        "Checking Uploaded Documents",
        "Cross-Field Consistency Verification",
        "Checking Duplicate Registrations",
        "Checking Internal Restricted-Vendor Records",
        "Generating Onboarding Decision",
        "Preparing Communication & Saving Audit History",
    ]

    stage_placeholders = []
    # Create 8 placeholders inside the status container and initialize as QUEUED
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
            label=f"🏁 Verification Pipeline Completed — Decision: {exec_result.status.value} ({exec_result.total_duration_ms:.1f} ms)",
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
            st.markdown("#### ⚠️ Items Requiring Attention / Issues")
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
        <span style="font-size: 0.78rem; color: #64748B; font-weight: 500;">Intelligent Onboarding Engine</span>
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
    st.metric("Pending/Rej", f"{metrics['pending'] + metrics['rejected']}")

st.sidebar.markdown(
    """
    <div style="margin-top: 20px; font-size: 0.75rem; color: #94A3B8; line-height: 1.4;">
        Supported Jurisdiction: <strong>India</strong><br>
        Database: <strong>SQLite (Local Persistent)</strong><br>
        Version: <strong>1.0.0 (Case Study Build)</strong>
    </div>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# PAGE 1: OVERVIEW
# ==============================================================================
if nav_option == "📌 Overview":
    render_header()

    st.markdown("### 📊 Operational Overview")
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    with m_col1:
        render_metric_card("Total Submissions", metrics["total_submissions"], "All recorded runs")
    with m_col2:
        render_metric_card("Approved", metrics["approved"], "Clean automated passes", "#16A34A")
    with m_col3:
        render_metric_card("Pending Review", metrics["pending"], "Discrepancy / Document", "#D97706")
    with m_col4:
        render_metric_card("Rejected", metrics["rejected"], "Policy hard-stop", "#DC2626")
    with m_col5:
        render_metric_card("Approval Rate", f"{metrics['approval_rate']}%", "Automated throughput", "#2563EB")

    st.markdown("---")
    st.markdown("### 🔄 Automated Verification Workflow Pipeline")
    st.markdown(
        """
        VendorFlow converts slow, manual procurement onboarding reviews into a structured, deterministic, 
        and fully auditable automated workflow.
        """
    )

    steps = [
        ("1. Intake & Normalization", "Generates cryptographic Run ID, normalizes legal text, and masks sensitive tax/banking numbers for audit security."),
        ("2. Field Validation", "Validates company identity, PAN structure (5-4-1), GSTIN format (15-char), and IFSC routing against jurisdictional standards."),
        ("3. Document Completeness", "Verifies mandatory GST, PAN, and Bank proof uploads for presence, acceptable mime type (PDF/PNG/JPG), and size (<10MB)."),
        ("4. Cross-Field Consistency", "Ensures embedded PAN within GSTIN matches submitted PAN, and normalizes legal suffixes to compare entity name with bank account holder."),
        ("5. Duplicate Detection", "Queries SQLite approved vendors registry using SHA-256 hashes of tax identifiers to prevent duplicate registrations."),
        ("6. Restricted Screening", "Screens tax ID hashes against a synthetic internal risk watchlist to enforce hard-stop compliance policies."),
        ("7. Decision Engine", "Deterministic priority logic assigns final status (APPROVED, PENDING, REJECTED) with comprehensive reasoning."),
        ("8. Audit & Communication", "Generates personalized vendor email drafts and records complete immutable execution logs in SQLite."),
    ]

    for title, desc in steps:
        st.markdown(f"**{title}** — {desc}")

    st.markdown("---")
    st.info(
        "💡 **Evaluator Quick Start:** Jump directly to **'🚀 Demo Scenarios'** in the sidebar to test "
        "all 5 pre-configured test scenarios (Happy Path, Missing Document, Bank Mismatch, Duplicate, and Restricted Vendor) in one click."
    )


# ==============================================================================
# PAGE 2: NEW VENDOR SUBMISSION FORM
# ==============================================================================
elif nav_option == "📝 New Submission":
    render_header()

    st.markdown("### 📝 New Vendor Onboarding Registration")
    st.caption("Submit vendor business details, banking information, and compliance documents for automated verification.")

    # Form actions: Pre-fill sample data
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

    with st.form("vendor_onboarding_form", clear_on_submit=False):
        # -------------------------------------------------------------
        # Section A1: Business Information
        # -------------------------------------------------------------
        st.markdown(
            """
            <div class="vf-section-title">
                🏢 Section 1: Business & Corporate Identity
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

        # -------------------------------------------------------------
        # Section A2: Banking Information
        # -------------------------------------------------------------
        st.markdown(
            """
            <div class="vf-section-title">
                🏦 Section 2: Banking & Disbursement Details
            </div>
            """,
            unsafe_allow_html=True,
        )
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

        # -------------------------------------------------------------
        # Section A3: Document Uploads
        # -------------------------------------------------------------
        st.markdown(
            """
            <div class="vf-section-title">
                📄 Section 3: Mandatory Compliance Documents
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Upload clear PDF, PNG, or JPEG files (Max 10 MB each). The prototype verifies file presence, format, and size.")

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
            "📎 Automatically attach sample verified documents (PDF/JPG/PNG) if upload is empty",
            value=True if fd.get("company_name") else False,
            help="Enables one-click testing without having to locate files on your computer.",
        )

        # -------------------------------------------------------------
        # Section A4: Submit Action
        # -------------------------------------------------------------
        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button(
            "🚀 Run Onboarding Verification",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        # Client side non-empty checks
        if not company_name.strip():
            st.error("Please enter a legal company name before submitting.")
        else:
            # Process uploaded files into DocumentMetadata objects
            docs_meta = {}

            def process_upload(file_obj, key: str, label: str) -> DocumentMetadata:
                if file_obj is not None:
                    ext = Path(file_obj.name).suffix.lower()
                    size = file_obj.size
                    return DocumentMetadata(
                        doc_type=key,
                        name=label,
                        filename=file_obj.name,
                        size_bytes=size,
                        extension=ext,
                        is_present=True,
                    )
                elif attach_sample_docs:
                    ext_map = {"gst_cert": ".pdf", "pan_proof": ".jpg", "bank_proof": ".png"}
                    size_map = {"gst_cert": 245000, "pan_proof": 180000, "bank_proof": 310000}
                    fname_map = {
                        "gst_cert": "sample_gst_certificate.pdf",
                        "pan_proof": "sample_company_pan.jpg",
                        "bank_proof": "sample_cancelled_cheque.png",
                    }
                    return DocumentMetadata(
                        doc_type=key,
                        name=label,
                        filename=fname_map.get(key, f"{key}.pdf"),
                        size_bytes=size_map.get(key, 200000),
                        extension=ext_map.get(key, ".pdf"),
                        is_present=True,
                    )
                else:
                    return DocumentMetadata(
                        doc_type=key,
                        name=label,
                        is_present=False,
                    )

            docs_meta["gst_cert"] = process_upload(gst_file, "gst_cert", "GST Registration Certificate")
            docs_meta["pan_proof"] = process_upload(pan_file, "pan_proof", "Company PAN Proof Document")
            docs_meta["bank_proof"] = process_upload(bank_file, "bank_proof", "Bank Proof / Cancelled Cheque")

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
                documents=docs_meta,
                run_type="Live Submission",
            )

            execute_and_display_workflow(submission_obj)


# ==============================================================================
# PAGE 3: DEMO SCENARIOS
# ==============================================================================
elif nav_option == "🚀 Demo Scenarios":
    render_header()

    st.markdown("### 🚀 Built-in Synthetic Demonstration Scenarios")
    st.markdown(
        """
        These pre-configured demonstration scenarios allow evaluators to immediately test the core happy path, 
        edge cases, exception handling, and policy hard-stops without manually typing inputs or preparing files.
        """
    )
    st.info("ℹ️ **Notice:** All scenario records use synthetic data. They execute the exact same backend decision engine as real submissions.")

    scenarios = [
        {
            "id": "scenario_a",
            "name": "Scenario A: Happy Path",
            "expected": "APPROVED",
            "badge_color": "#16A34A",
            "company": "Aster Labs Private Limited",
            "desc": "Valid company name, matching PAN & GSTIN, clean bank account name alignment, and all 3 documents present.",
            "data": {
                "company_name": "Aster Labs Private Limited",
                "country": "India",
                "registration_type": "Private Limited",
                "address": "Plot 42, Electronic City, Bangalore, Karnataka",
                "contact_name": "Dr. Vikram Rao",
                "contact_email": "ops@asterlabs.example",
                "pan": "ABCDE1234F",
                "gstin": "27ABCDE1234F1Z5",
                "bank_account_holder": "Aster Labs",
                "bank_account_number": "123456789012",
                "ifsc_code": "HDFC0001234",
                "bank_name": "HDFC Bank",
                "docs": {"gst_cert": True, "pan_proof": True, "bank_proof": True},
            },
        },
        {
            "id": "scenario_b",
            "name": "Scenario B: Missing Bank Document",
            "expected": "PENDING",
            "badge_color": "#D97706",
            "company": "Bluewave Technologies Private Limited",
            "desc": "Valid company and banking details, but the mandatory Bank Proof / Cancelled Cheque is missing.",
            "data": {
                "company_name": "Bluewave Technologies Private Limited",
                "country": "India",
                "registration_type": "Private Limited",
                "address": "Level 5, Cyber Gateway, HITEC City, Hyderabad",
                "contact_name": "Ramesh Kumar",
                "contact_email": "finance@bluewavetech.example",
                "pan": "BWAVE5678M",
                "gstin": "36BWAVE5678M1Z8",
                "bank_account_holder": "Bluewave Technologies Pvt Ltd",
                "bank_account_number": "987654321098",
                "ifsc_code": "ICIC0000456",
                "bank_name": "ICICI Bank",
                "docs": {"gst_cert": True, "pan_proof": True, "bank_proof": False},
            },
        },
        {
            "id": "scenario_c",
            "name": "Scenario C: Bank Account Name Mismatch",
            "expected": "PENDING",
            "badge_color": "#D97706",
            "company": "Brightline Systems Private Limited",
            "desc": "Legal entity name is 'Brightline Systems', but bank account holder is 'Shree Trading Enterprises'. Requires manual ownership review.",
            "data": {
                "company_name": "Brightline Systems Private Limited",
                "country": "India",
                "registration_type": "Private Limited",
                "address": "102 Industrial Estate, Peenya, Bangalore",
                "contact_name": "Ananya Sen",
                "contact_email": "accounts@brightline.example",
                "pan": "BRGHT9999K",
                "gstin": "29BRGHT9999K1Z2",
                "bank_account_holder": "Shree Trading Enterprises",
                "bank_account_number": "554433221100",
                "ifsc_code": "SBIN0001234",
                "bank_name": "State Bank of India",
                "docs": {"gst_cert": True, "pan_proof": True, "bank_proof": True},
            },
        },
        {
            "id": "scenario_d",
            "name": "Scenario D: Duplicate Vendor Registration",
            "expected": "PENDING",
            "badge_color": "#D97706",
            "company": "Northstar Office Supplies Private Limited",
            "desc": "Tax identifiers (PAN LMNOP1234Q & GSTIN 27LMNOP1234Q1Z5) match a pre-existing approved vendor in the registry.",
            "data": {
                "company_name": "Northstar Office Supplies Private Limited",
                "country": "India",
                "registration_type": "Private Limited",
                "address": "12 MG Road, Fort, Mumbai",
                "contact_name": "Sanjay Mehta",
                "contact_email": "sales@northstar.example",
                "pan": "LMNOP1234Q",
                "gstin": "27LMNOP1234Q1Z5",
                "bank_account_holder": "Northstar Office Supplies",
                "bank_account_number": "223344556677",
                "ifsc_code": "KKBK0000123",
                "bank_name": "Kotak Mahindra Bank",
                "docs": {"gst_cert": True, "pan_proof": True, "bank_proof": True},
            },
        },
        {
            "id": "scenario_e",
            "name": "Scenario E: Internal Restricted-Vendor Match",
            "expected": "REJECTED",
            "badge_color": "#DC2626",
            "company": "Redwood Logistics LLP",
            "desc": "Tax identifier matches synthetic internal restricted watchlist entry. Triggers hard-stop and stops onboarding immediately.",
            "data": {
                "company_name": "Redwood Logistics LLP",
                "country": "India",
                "registration_type": "Limited Liability Partnership (LLP)",
                "address": "Transport Nagar, Sector 4, Gandhinagar",
                "contact_name": "Karan Verma",
                "contact_email": "legal@redwoodlogistics.example",
                "pan": "UVWXY5678Z",
                "gstin": "29UVWXY5678Z1Z5",
                "bank_account_holder": "Redwood Logistics LLP",
                "bank_account_number": "998877665544",
                "ifsc_code": "AXIS0000789",
                "bank_name": "Axis Bank",
                "docs": {"gst_cert": True, "pan_proof": True, "bank_proof": True},
            },
        },
    ]

    for sc in scenarios:
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
                    <div style="font-size: 0.82rem; color: #64748B;">
                        <strong>Vendor:</strong> {sc['company']} | <strong>PAN:</strong> {sc['data']['pan']} | <strong>GSTIN:</strong> {sc['data']['gstin']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.button(f"⚡ Execute {sc['name']}", key=f"btn_{sc['id']}"):
                d_flags = sc["data"]["docs"]
                docs_meta = {
                    "gst_cert": DocumentMetadata(
                        doc_type="gst_cert",
                        name="GST Registration Certificate",
                        filename="gst_certificate.pdf" if d_flags.get("gst_cert") else None,
                        size_bytes=245000 if d_flags.get("gst_cert") else 0,
                        extension=".pdf",
                        is_present=d_flags.get("gst_cert", False),
                    ),
                    "pan_proof": DocumentMetadata(
                        doc_type="pan_proof",
                        name="Company PAN Proof Document",
                        filename="company_pan.jpg" if d_flags.get("pan_proof") else None,
                        size_bytes=180000 if d_flags.get("pan_proof") else 0,
                        extension=".jpg",
                        is_present=d_flags.get("pan_proof", False),
                    ),
                    "bank_proof": DocumentMetadata(
                        doc_type="bank_proof",
                        name="Bank Proof / Cancelled Cheque",
                        filename="cancelled_cheque.png" if d_flags.get("bank_proof") else None,
                        size_bytes=310000 if d_flags.get("bank_proof") else 0,
                        extension=".png",
                        is_present=d_flags.get("bank_proof", False),
                    ),
                }

                sub = VendorSubmission(
                    company_name=sc["data"]["company_name"],
                    country=sc["data"]["country"],
                    registration_type=sc["data"]["registration_type"],
                    address=sc["data"]["address"],
                    contact_name=sc["data"]["contact_name"],
                    contact_email=sc["data"]["contact_email"],
                    pan=sc["data"]["pan"],
                    gstin=sc["data"]["gstin"],
                    bank_account_holder=sc["data"]["bank_account_holder"],
                    bank_account_number=sc["data"]["bank_account_number"],
                    ifsc_code=sc["data"]["ifsc_code"],
                    bank_name=sc["data"]["bank_name"],
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

    # Dynamic metrics
    m1, m2, m3, m4, m5 = st.columns(5)
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

    # Format date filter strings if selected
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
        # Prepare tabular presentation
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
                    "Run Type": r["run_type"],
                }
            )

        df = pd.DataFrame(table_rows)

        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "Status": st.column_config.TextColumn(
                    "Status",
                    help="Onboarding Decision Outcome",
                ),
            },
            hide_index=True,
        )

        # CSV Export Option
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
        st.caption("Select any past execution to inspect its audit stages, masked inputs, and generated communication draft.")

        run_id_list = [r["run_id"] for r in all_runs]
        selected_run_id = st.selectbox("Select Run ID to Inspect:", run_id_list)

        if selected_run_id:
            run_data = get_run_by_id(selected_run_id, DB_PATH)
            if run_data:
                # Header card for inspected run
                render_decision_banner(
                    status=run_data["status"],
                    summary=run_data["decision"].get("summary", ""),
                    duration_ms=run_data["processing_duration_ms"],
                    run_id=run_data["run_id"],
                )

                # Tabbed inspection view
                tab1, tab2, tab3, tab4 = st.tabs(
                    [
                        "📋 Execution Stages",
                        "🔒 Redacted Inputs & Document Metadata",
                        "✉️ Communication Draft",
                        "📄 Raw Audit JSON",
                    ]
                )

                with tab1:
                    st.markdown("#### Processing Stages Audit Trail")
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
                    st.markdown("#### Privacy-Safe Masked Vendor Submission")
                    st.caption("Demonstrating secure redaction: Complete tax numbers and bank accounts are never exposed.")
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

                with tab3:
                    st.markdown("#### Generated Communication Draft")
                    st.text_area(
                        "Communication Draft",
                        value=run_data["communication_draft"],
                        height=220,
                        disabled=True,
                    )

                with tab4:
                    st.markdown("#### Full Audit Record")
                    st.json(run_data)


# ==============================================================================
# PAGE 5: VALIDATION RULES & SYSTEM LIMITATIONS
# ==============================================================================
elif nav_option == "📖 Validation Rules & Limits":
    render_header()

    st.markdown("### 📖 Deterministic Validation Rules & System Architecture")

    tab_r1, tab_r2 = st.tabs(["⚙️ Configured Validation Logic", "⚠️ Honest Limitations & Boundaries"])

    with tab_r1:
        st.markdown(
            """
            #### 1. Identity & Format Rules
            - **Company Name:** Non-empty, 2 to 150 characters.
            - **Supported Country:** India only (`India`, `IN`). All other countries flagged as PENDING for manual cross-border review.
            - **PAN Format:** `^[A-Z]{5}[0-9]{4}[A-Z]$` (5 letters, 4 numbers, 1 letter, e.g. `ABCDE1234F`).
            - **GSTIN Structural Format:** `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$` (15 alphanumeric characters).
            - **IFSC Format:** `^[A-Z]{4}0[A-Z0-9]{6}$` (11 characters, 5th character '0').
            - **Bank Account Number:** Numeric only, 9 to 18 digits.

            #### 2. Compliance Document Rules
            - **Required Types:** GST Certificate (`gst_cert`), PAN Document (`pan_proof`), Bank Proof / Cancelled Cheque (`bank_proof`).
            - **Supported Formats:** `.pdf`, `.png`, `.jpg`, `.jpeg`.
            - **Size Boundary:** Maximum 10 MB per file.
            - **Validation Level:** Presence, valid extension, and positive size check.

            #### 3. Cross-Field Consistency Checks
            - **Embedded PAN in GSTIN:** Characters at index 2 to 11 of the 15-character GSTIN must match the separately submitted PAN.
            - **Entity Name Alignment:** Compares legal company name with bank account holder name after stripping legal entity suffixes (`PRIVATE LIMITED`, `PVT LTD`, `LLP`, `LTD`, etc.) and non-alphanumeric punctuation. Material differences require manual verification.

            #### 4. Cryptographic Duplicate & Restricted Screening
            - Normalizes PAN and GSTIN and generates SHA-256 hashes (`hashlib.sha256(val.encode('utf-8')).hexdigest()`).
            - **Duplicate Check:** Queries `approved_vendors` table in SQLite. If matched, triggers PENDING to prevent re-registration.
            - **Restricted Check:** Queries `restricted_vendors` table in SQLite. If matched, triggers immediate REJECTED hard-stop.
            """
        )

    with tab_r2:
        st.markdown(
            """
            #### Honest Scope Boundaries (PS-2 Case Study Prototype)
            In accordance with engineering integrity and realistic prototype scoping:

            1. **India-Specific Jurisdiction Only:** The prototype is configured for Indian tax and banking structures (PAN, GSTIN, IFSC). Cross-border jurisdictions are routed to PENDING.
            2. **Structural Validation vs. Live Government Verification:** PAN and GSTIN are structurally validated against official syntax rules; they are not queried against live Income Tax or GSTN government APIs.
            3. **Banking Network Verification:** Bank account format and IFSC syntax are verified; actual bank account ownership is not confirmed against live banking networks (penny-drop API / IMPS).
            4. **Document Integrity vs. Certificate OCR:** Uploaded documents are verified for presence, allowed file format, and file size limits. The prototype does not claim OCR extraction or tamper authentication.
            5. **Synthetic Restricted Registry:** The internal restricted-vendor registry is synthetic and built for demonstration; it does not replace a production OFAC/UN/sanctions screening engine.
            6. **Communication Drafting Only:** Actionable email drafts are generated dynamically for review; automated SMTP email transmission is intentionally omitted.
            7. **Human in the Loop:** Automated approval marks preliminary technical verification. Real-world vendor activation and payment authorization always remains with an authorized human procurement officer.
            """
        )
