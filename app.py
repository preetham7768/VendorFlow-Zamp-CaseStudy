"""
VendorFlow — Intelligent Vendor Onboarding & Verification System
Phase 2: Document-Driven Vendor Verification & Cross-Document Intelligence.
Enterprise SaaS Frontend — Fully Refined Execution Dashboard & Demo Scenarios.
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
    get_confidence_badge_html,
    get_status_badge_html,
    inject_custom_css,
    render_decision_banner,
    render_kpi_card,
    render_page_header,
    render_pipeline_stepper,
    render_stage_card,
)

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="VendorFlow — Intelligent Vendor Verification",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database on startup
DB_PATH = Path(__file__).resolve().parent / "vendorflow.db"
init_db(DB_PATH)

# Inject enterprise CSS styling
inject_custom_css()

# Session state initialization
if "current_page" not in st.session_state:
    st.session_state.current_page = "Overview"
if "form_data" not in st.session_state:
    st.session_state.form_data = {}
if "last_execution_result" not in st.session_state:
    st.session_state.last_execution_result = None
if "extracted_review_data" not in st.session_state:
    st.session_state.extracted_review_data = None
if "selected_inspector_run_id" not in st.session_state:
    st.session_state.selected_inspector_run_id = None


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


def execute_and_display_workflow(submission: VendorSubmission):
    """Executes the 13-stage verification pipeline and renders the live sequential stages and decision."""
    st.markdown(
        """
        <div style="margin-top: 1.25rem; margin-bottom: 0.65rem;">
            <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.06em;">
                Sequential Execution Telemetry
            </div>
            <h3 style="margin: 0; font-size: 1.2rem; font-weight: 700; color: #0F172A;">
                13-Stage Verification Pipeline Execution
            </h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
    # Create 13 placeholders inside status container and initialize as QUEUED
    for i, s_name in enumerate(stage_names, start=1):
        ph = status_container.empty()
        badge = get_status_badge_html("QUEUED")
        ph.markdown(
            f"""
            <div style="padding: 8px 12px; margin-bottom: 5px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; opacity: 0.85;">
                <div style="min-width: 0;">
                    <span style="font-size: 0.72rem; color: #64748B; font-weight: 600; margin-right: 6px;">Stage {i}:</span>
                    <strong style="color: #334155; font-size: 0.85rem;">{s_name}</strong><br>
                    <span style="font-size: 0.75rem; color: #94A3B8;">Queued for sequential execution...</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
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
                    <div style="padding: 8px 12px; margin-bottom: 5px; background: #EFF6FF; border: 1px solid #BFDBFE; border-left: 4px solid #2563EB; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                        <div style="min-width: 0;">
                            <span style="font-size: 0.72rem; color: #1D4ED8; font-weight: 600; margin-right: 6px;">Stage {result.stage_number}:</span>
                            <strong style="color: #1E40AF; font-size: 0.85rem;">{result.stage_name}</strong><br>
                            <span style="font-size: 0.76rem; color: #2563EB;">Executing automated verification rules...</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                            {badge}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                return

            badge = get_status_badge_html(result.status.value)
            border_left = (
                "#16A34A"
                if result.status == StageStatus.COMPLETED
                else ("#D97706" if result.status == StageStatus.NEEDS_ATTENTION else "#DC2626")
            )
            stage_placeholders[idx].markdown(
                f"""
                <div style="padding: 8px 12px; margin-bottom: 5px; background: #FFFFFF; border: 1px solid #E2E8F0; border-left: 4px solid {border_left}; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                    <div style="min-width: 0;">
                        <span style="font-size: 0.72rem; color: #64748B; font-weight: 600; margin-right: 6px;">Stage {result.stage_number}:</span>
                        <strong style="color: #0F172A; font-size: 0.85rem;">{result.stage_name}</strong><br>
                        <span style="font-size: 0.78rem; color: #475569;">{result.summary}</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                        <span style="font-size: 0.72rem; color: #64748B;">{result.duration_ms:.1f}ms</span>
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

        # Display Final Decision Hero Card
        render_decision_banner(
            status=exec_result.status.value,
            summary=exec_result.decision.summary,
            duration_ms=exec_result.total_duration_ms,
            run_id=exec_result.run_id,
        )

        # Quick navigation link to inspect run in Execution Dashboard
        nav_col1, nav_col2 = st.columns([2, 5])
        with nav_col1:
            if st.button("🔍 Inspect Run in Execution Dashboard", key=f"nav_inspect_{exec_result.run_id}", use_container_width=True):
                st.session_state.current_page = "Execution Dashboard"
                st.session_state.selected_inspector_run_id = exec_result.run_id
                st.rerun()

        # -------------------------------------------------------------
        # Phase 2 Document Extraction & Cross-Check Findings
        # -------------------------------------------------------------
        st.markdown(
            """
            <div style="margin-top: 1.25rem; margin-bottom: 0.65rem;">
                <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.06em;">
                    Reconciliation & Verification Outcomes
                </div>
                <h3 style="margin: 0; font-size: 1.2rem; font-weight: 700; color: #0F172A;">
                    Document Extraction & Cross-Check Findings
                </h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

        p2_c1, p2_c2, p2_c3 = st.columns(3)
        with p2_c1:
            render_kpi_card(
                "Documents Processed",
                exec_result.documents_processed_count,
                "Compliance PDFs parsed",
                color_hint="#0F172A",
                icon_label="📄",
            )
        with p2_c2:
            render_kpi_card(
                "Discrepancies Found",
                exec_result.discrepancies_count,
                "Cross-document conflicts",
                color_hint="#D97706" if exec_result.discrepancies_count > 0 else "#16A34A",
                icon_label="⚠️",
            )
        with p2_c3:
            render_kpi_card(
                "Human Confirmations",
                exec_result.manual_confirmations_count,
                "Unreadable / manual fields",
                color_hint="#4F46E5",
                icon_label="👤",
            )

        # Tabular Comparison of Document vs Manual Values
        cross_checks = exec_result.cross_document_results.get("checks", [])
        if cross_checks:
            st.markdown(
                """
                <div style="font-size: 0.85rem; font-weight: 600; color: #1E293B; margin-top: 0.85rem; margin-bottom: 0.4rem;">
                    Cross-Document Verification Matrix
                </div>
                """,
                unsafe_allow_html=True,
            )
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

        # Two-Column Breakdown: Passed Checks vs. Issues Requiring Attention
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(
                """
                <div class="vf-surface-card">
                    <div class="vf-section-header" style="color: #15803D;">
                        <span>✓</span> Automated Verification Checks Passed
                    </div>
                """,
                unsafe_allow_html=True,
            )
            if exec_result.decision.passed_checks:
                for check in exec_result.decision.passed_checks:
                    st.markdown(f"- <span style='color: #16A34A; font-weight: 700;'>✓</span> {check}", unsafe_allow_html=True)
            else:
                st.info("No checks passed successfully.")
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown(
                """
                <div class="vf-surface-card">
                    <div class="vf-section-header" style="color: #B45309;">
                        <span>⚠</span> Items Requiring Attention / Policy Flags
                    </div>
                """,
                unsafe_allow_html=True,
            )
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
                        <div style="margin-bottom: 8px; padding: 9px 12px; background: #FFFBEB; border-left: 3px solid #D97706; border-radius: 4px;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <strong style="font-size: 0.8rem; color: #92400E;">{issue.stage} • {issue.field_name}</strong>
                                {badge}
                            </div>
                            <div style="font-size: 0.8rem; color: #78350F; margin-top: 3px;">{issue.message}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.success("Clean execution: No warnings, inconsistencies, or hard-stops identified.")
            st.markdown("</div>", unsafe_allow_html=True)

        # Recommended Next Steps
        st.markdown(
            """
            <div class="vf-surface-card">
                <div class="vf-section-header">
                    <span>📋</span> Recommended Operational Next Steps
                </div>
            """,
            unsafe_allow_html=True,
        )
        for step in exec_result.decision.next_steps:
            st.markdown(f"- **{step}**")
        st.markdown("</div>", unsafe_allow_html=True)

        # Communication Draft Section
        st.markdown(
            """
            <div class="vf-surface-card">
                <div class="vf-section-header">
                    <span>✉️</span> Generated Communication Draft
                </div>
                <p style="font-size: 0.82rem; color: #64748B; margin-top: -6px; margin-bottom: 10px;">
                    Personalized vendor communication dynamically generated from verification findings. No email is sent automatically.
                </p>
            """,
            unsafe_allow_html=True,
        )

        st.text_area(
            label="Communication Draft (Ready to copy & review)",
            value=exec_result.communication_draft,
            height=240,
            key=f"comm_draft_{exec_result.run_id}",
        )

        col_cp1, col_cp2 = st.columns([1, 4])
        with col_cp1:
            if st.button("📋 Copy Email Draft", key=f"btn_cp_{exec_result.run_id}"):
                st.toast("Email draft copied to clipboard!", icon="📋")

        st.markdown("</div>", unsafe_allow_html=True)

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
# SIDEBAR NAVIGATION (Dark Enterprise Sidebar #111827)
# ==============================================================================
with st.sidebar:
    # Product Header
    st.markdown(
        """
        <div style="padding: 4px 10px 14px 10px; border-bottom: 1px solid #1F2937; margin-bottom: 10px;">
            <div style="display: flex; align-items: center; gap: 9px;">
                <div style="width: 30px; height: 30px; border-radius: 7px; background: #4F46E5; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.95rem; color: #FFFFFF; box-shadow: 0 1px 3px rgba(79, 70, 229, 0.4);">
                    V
                </div>
                <div>
                    <div style="font-size: 1.05rem; font-weight: 700; color: #FFFFFF; letter-spacing: -0.01em;">VENDORFLOW</div>
                    <div style="font-size: 0.64rem; font-weight: 600; color: #94A3B8; letter-spacing: 0.06em; text-transform: uppercase;">Intelligent Onboarding</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Navigation Group 1: WORKSPACE
    st.markdown('<div class="vf-nav-section-title">WORKSPACE</div>', unsafe_allow_html=True)
    workspace_nav = [
        ("Overview", "Overview", "⊞"),
        ("New Submission", "New Submission", "＋"),
        ("Execution Dashboard", "Execution Dashboard", "☷"),
    ]
    for p_id, p_label, p_icon in workspace_nav:
        is_active = (st.session_state.current_page == p_id)
        if st.button(
            f"{p_icon}  {p_label}",
            key=f"side_nav_{p_id}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.current_page = p_id
            st.rerun()

    # Navigation Group 2: TOOLS
    st.markdown('<div class="vf-nav-section-title">TOOLS</div>', unsafe_allow_html=True)
    tools_nav = [
        ("Demo Scenarios", "Demo Scenarios", "⚡"),
        ("Validation Rules", "Validation Rules", "☰"),
    ]
    for p_id, p_label, p_icon in tools_nav:
        is_active = (st.session_state.current_page == p_id)
        if st.button(
            f"{p_icon}  {p_label}",
            key=f"side_nav_{p_id}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.current_page = p_id
            st.rerun()

    # Sidebar Live Telemetry
    metrics = get_dashboard_metrics(DB_PATH)
    st.markdown("---")
    st.markdown(
        """
        <div style="font-size: 0.68rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; padding-left: 6px;">
            Live Telemetry
        </div>
        """,
        unsafe_allow_html=True,
    )

    sb_c1, sb_c2 = st.columns(2)
    with sb_c1:
        st.markdown(
            f"""
            <div class="vf-sidebar-metric">
                <div class="vf-sidebar-metric-label">Total Runs</div>
                <div class="vf-sidebar-metric-value">{metrics["total_submissions"]}</div>
            </div>
            <div class="vf-sidebar-metric">
                <div class="vf-sidebar-metric-label">Approved</div>
                <div class="vf-sidebar-metric-value" style="color: #4ADE80;">{metrics["approved"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with sb_c2:
        st.markdown(
            f"""
            <div class="vf-sidebar-metric">
                <div class="vf-sidebar-metric-label">Pass Rate</div>
                <div class="vf-sidebar-metric-value">{metrics["approval_rate"]}%</div>
            </div>
            <div class="vf-sidebar-metric">
                <div class="vf-sidebar-metric-label">Conflicts</div>
                <div class="vf-sidebar-metric-value" style="color: #FBBF24;">{metrics.get("discrepancies_identified", 0)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Sidebar Footer & Status
    st.markdown(
        """
        <div style="padding: 10px 6px 4px 6px; margin-top: 10px; border-top: 1px solid #1F2937;">
            <div class="vf-sidebar-status-pill">
                <span class="vf-pulse-dot"></span>
                <span>System Online • PyMuPDF</span>
            </div>
            <div style="font-size: 0.67rem; color: #64748B; margin-top: 6px; line-height: 1.35;">
                Version 2.0 • Zamp Case Study<br>
                Local SQLite Persistent
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# PAGE 1: OVERVIEW
# ==============================================================================
if st.session_state.current_page == "Overview":
    render_page_header(
        breadcrumb="Workspace > Overview",
        title="Vendor Operations Overview",
        subtitle="Live operational telemetry, automated verification throughput, and recent onboarding decisions.",
    )

    # 4 Key Dynamic KPI Cards
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        render_kpi_card(
            title="Total Submissions",
            value=metrics["total_submissions"],
            sub="All recorded runs in database",
            color_hint="#0F172A",
            icon_label="📊",
        )
    with kpi2:
        render_kpi_card(
            title="Approval Rate",
            value=f"{metrics['approval_rate']}%",
            sub="Automated zero-touch pass rate",
            color_hint="#4F46E5",
            icon_label="📈",
        )
    with kpi3:
        render_kpi_card(
            title="Pending Review",
            value=metrics["pending"],
            sub="Discrepancies / manual review",
            color_hint="#D97706",
            icon_label="⏳",
        )
    with kpi4:
        render_kpi_card(
            title="Rejected",
            value=metrics["rejected"],
            sub="Restricted or critical failures",
            color_hint="#DC2626",
            icon_label="🛑",
        )

    # Connected High-Level Pipeline Stepper Diagram
    render_pipeline_stepper()

    # Quick Action CTA & Recent 5 Runs Section
    st.markdown(
        """
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1.25rem; margin-bottom: 0.65rem;">
            <div>
                <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.06em;">
                    Audit Trail Activity
                </div>
                <h3 style="margin: 0; font-size: 1.2rem; font-weight: 700; color: #0F172A;">
                    Recent Onboarding Executions
                </h3>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    all_recent_runs = get_all_runs(DB_PATH)
    recent_5 = all_recent_runs[:5] if all_recent_runs else []

    col_btn_action, col_spacer = st.columns([2, 5])
    with col_btn_action:
        if st.button("＋ Start New Vendor Onboarding", type="primary", use_container_width=True):
            st.session_state.current_page = "New Submission"
            st.rerun()

    if recent_5:
        recent_rows = []
        for r in recent_5:
            recent_rows.append(
                {
                    "Vendor": r["vendor_name"],
                    "Run ID": f"...{r['run_id'][-8:]}" if len(r["run_id"]) > 16 else r["run_id"],
                    "Timestamp (UTC)": r["created_at"][:19].replace("T", " "),
                    "Decision": r["status"],
                    "Duration": f"{r['processing_duration_ms']:.1f} ms",
                    "Issues": f"{r['issues_count']} flag" if r["issues_count"] == 1 else f"{r['issues_count']} flags",
                }
            )
        st.dataframe(
            pd.DataFrame(recent_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Vendor": st.column_config.TextColumn("Vendor", width="large"),
                "Run ID": st.column_config.TextColumn("Run ID", width="small"),
                "Timestamp (UTC)": st.column_config.TextColumn("Timestamp (UTC)", width="medium"),
                "Decision": st.column_config.TextColumn("Decision", width="small"),
                "Duration": st.column_config.TextColumn("Duration", width="small"),
                "Issues": st.column_config.TextColumn("Issues", width="small"),
            },
        )
    else:
        st.info("No execution runs recorded yet. Use 'Start New Vendor Onboarding' or run a Demo Scenario.")


# ==============================================================================
# PAGE 2: NEW SUBMISSION (DOCUMENT-DRIVEN REGISTRATION)
# ==============================================================================
elif st.session_state.current_page == "New Submission":
    render_page_header(
        breadcrumb="Workspace > New Submission",
        title="New Vendor Onboarding Registration",
        subtitle="Submit vendor details and compliance documents for automated extraction, cross-document verification, and statutory screening.",
    )

    # Top Action Toolbar for pre-fill
    tb_c1, tb_c2, tb_spacer = st.columns([2, 2, 4])
    with tb_c1:
        if st.button("⚡ Pre-fill Sample (Aster Labs)", use_container_width=True):
            set_sample_data("happy_path")
            st.rerun()
    with tb_c2:
        if st.button("🧹 Clear All Fields", use_container_width=True):
            set_sample_data("clear")
            st.rerun()

    fd = st.session_state.form_data

    # Step 1: Compliance Documents Upload
    st.markdown(
        """
        <div class="vf-surface-card">
            <div class="vf-section-header">
                <span>📄</span> Step 1: Upload Compliance Documents
            </div>
            <p style="font-size: 0.82rem; color: #64748B; margin-top: -6px; margin-bottom: 12px;">
                Upload PDF, PNG, or JPEG files (Max 10 MB each). The PyMuPDF engine extracts readable text streams and compares identifiers across documents.
            </p>
        """,
        unsafe_allow_html=True,
    )

    d1, d2, d3 = st.columns(3)
    with d1:
        gst_file = st.file_uploader(
            "GST Registration Certificate *",
            type=["pdf", "png", "jpg", "jpeg"],
            key="up_gst_cert",
            help="Extracts GSTIN, Legal Name, Trade Name, and embedded PAN.",
        )
    with d2:
        pan_file = st.file_uploader(
            "Company PAN Proof *",
            type=["pdf", "png", "jpg", "jpeg"],
            key="up_pan_proof",
            help="Extracts 10-digit Permanent Account Number and cardholder name.",
        )
    with d3:
        bank_file = st.file_uploader(
            "Bank Proof / Cancelled Cheque *",
            type=["pdf", "png", "jpg", "jpeg"],
            key="up_bank_proof",
            help="Extracts Account Holder Name, Bank Account Number, and IFSC Code.",
        )

    attach_sample_docs = st.checkbox(
        "📎 Automatically attach synthetic verified PDF documents if upload is empty",
        value=True if fd.get("company_name") else False,
        help="Generates authentic text-based synthetic PDF documents in memory for testing without local files.",
    )

    def build_doc_metadata(
        gst_f, pan_f, bank_f, use_sample: bool, sample_pan: str, sample_gstin: str, sample_name: str, sample_holder: str
    ) -> Dict[str, DocumentMetadata]:
        docs = {}

        # 1. PAN Proof
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

        # 2. GST Certificate
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

    st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
    if st.button("🔍 Extract & Review Document Fields", use_container_width=False):
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

    st.markdown("</div>", unsafe_allow_html=True)

    # Extraction Review Screen (If triggered)
    if st.session_state.extracted_review_data:
        p_res = st.session_state.extracted_review_data["pan"]
        g_res = st.session_state.extracted_review_data["gst"]
        b_res = st.session_state.extracted_review_data["bank"]

        st.markdown(
            """
            <div class="vf-surface-card" style="border-left: 4px solid #4F46E5;">
                <div class="vf-section-header">
                    <span>🔍</span> Document Extraction Review Screen
                </div>
                <p style="font-size: 0.82rem; color: #64748B; margin-top: -6px; margin-bottom: 12px;">
                    Review extracted fields before submitting. Check provenance, extraction status, and confidence levels.
                </p>
            """,
            unsafe_allow_html=True,
        )

        rev_c1, rev_c2, rev_c3, rev_c4 = st.columns(4)
        with rev_c1:
            render_kpi_card("Documents Processed", 3, "PAN, GST, Bank Proof", icon_label="📄")
        with rev_c2:
            extracted_count = len([v for v in {**p_res.extracted_fields, **g_res.extracted_fields, **b_res.extracted_fields}.values() if v])
            render_kpi_card("Fields Extracted", extracted_count, "Regex & label parsed", icon_label="⚡")
        with rev_c3:
            all_confidences = list(p_res.field_confidence.values()) + list(g_res.field_confidence.values()) + list(b_res.field_confidence.values())
            low_count = all_confidences.count("LOW")
            render_kpi_card("Review Needed", low_count, "Low confidence fields", color_hint="#D97706" if low_count > 0 else "#16A34A", icon_label="⚠️")
        with rev_c4:
            total_warn = len(p_res.warnings) + len(g_res.warnings) + len(b_res.warnings)
            render_kpi_card("Extraction Warnings", total_warn, "Flags from parsers", color_hint="#DC2626" if total_warn > 0 else "#16A34A", icon_label="🛑")

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
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

        all_warnings = p_res.warnings + g_res.warnings + b_res.warnings
        if all_warnings:
            st.warning("⚠️ **Extraction Warnings & Notices:**\n" + "\n".join([f"- {w}" for w in all_warnings]))

        st.markdown("</div>", unsafe_allow_html=True)

    # Step 2: Vendor Business & Banking Details Form
    with st.form("vendor_onboarding_form", clear_on_submit=False):
        st.markdown(
            """
            <div class="vf-surface-card">
                <div class="vf-section-header">
                    <span>🏢</span> Step 2: Vendor Business & Banking Details
                </div>
            """,
            unsafe_allow_html=True,
        )

        c_biz, c_bank = st.columns(2)

        with c_biz:
            st.markdown(
                """
                <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
                    Business Information
                </div>
                """,
                unsafe_allow_html=True,
            )
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

        with c_bank:
            st.markdown(
                """
                <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
                    Tax & Banking Details
                </div>
                """,
                unsafe_allow_html=True,
            )
            pan = st.text_input(
                "Company PAN (Permanent Account Number) *",
                value=fd.get("pan", ""),
                placeholder="e.g. ABCDE1234F (10 characters)",
                max_chars=10,
            ).upper()
            gstin = st.text_input(
                "GSTIN (Goods & Services Tax ID) *",
                value=fd.get("gstin", ""),
                placeholder="e.g. 27ABCDE1234F1Z5 (15 characters)",
                max_chars=15,
            ).upper()
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
        st.markdown("</div>", unsafe_allow_html=True)

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
# PAGE 3: DEMO SCENARIOS (RESTRUCTURED WORKSPACE)
# ==============================================================================
elif st.session_state.current_page == "Demo Scenarios":
    render_page_header(
        breadcrumb="Tools > Demo Scenarios",
        title="Demo & Testing Scenarios",
        subtitle="Explore how VendorFlow handles successful onboarding and complex operational exceptions.",
        badge_text="SYNTHETIC DEMO DATA",
    )

    st.markdown(
        """
        <div style="font-size: 0.78rem; color: #64748B; background: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 6px; padding: 7px 12px; margin-bottom: 14px;">
            ℹ️ <strong>Demonstration Environment:</strong> All scenarios execute actual automated verification pipelines using synthetic test vendors and memory-generated documents. No external live registries are contacted.
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_p1, tab_p2 = st.tabs(["📋 Phase 1: Structured Validation (5 Scenarios)", "📄 Phase 2: Document Intelligence (4 Scenarios)"])

    # -------------------------------------------------------------
    # TAB 1: PHASE 1 — STRUCTURED VALIDATION (5 SCENARIOS)
    # -------------------------------------------------------------
    with tab_p1:
        st.markdown(
            """
            <div style="margin-bottom: 12px;">
                <div style="font-size: 0.92rem; font-weight: 700; color: #0F172A;">
                    Phase 1: Deterministic Governance & Statutory Validation
                </div>
                <div style="font-size: 0.8rem; color: #64748B;">
                    Tests core statutory rules, metadata integrity, duplicate detection against existing database records, and compliance watchlist screening.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        p1_scenarios = [
            {
                "id": "p1_sc_happy",
                "num": "SCENARIO 1",
                "name": "Happy Path: Clean Verification",
                "category": "PHASE 1 • BASELINE",
                "expected": "APPROVED",
                "company": "Aster Labs Private Limited",
                "desc": "Validates an unblemished submission: statutory syntax passes for PAN and GSTIN, bank holder aligns, and all 3 documents are present.",
                "meta": "PAN: ABCDE1234F • GSTIN: 27ABCDE1234F1Z5 • IFSC: HDFC0001234",
                "run": lambda: (
                    generate_synthetic_pan_pdf("ABCDE1234F", "Aster Labs Private Limited"),
                    generate_synthetic_gst_pdf("27ABCDE1234F1Z5", "Aster Labs Private Limited", "Aster Labs"),
                    generate_synthetic_bank_pdf("Aster Labs", "123456789012", "HDFC0001234", "HDFC Bank Ltd"),
                    "Aster Labs Private Limited", "India", "Private Limited", "Plot 42, Electronic City, Bangalore",
                    "Dr. Vikram Rao", "ops@asterlabs.example", "ABCDE1234F", "27ABCDE1234F1Z5",
                    "Aster Labs", "123456789012", "HDFC0001234", "HDFC Bank Ltd", True,
                ),
            },
            {
                "id": "p1_sc_missing",
                "num": "SCENARIO 2",
                "name": "Missing Document: Bank Proof",
                "category": "PHASE 1 • GOVERNANCE",
                "expected": "PENDING",
                "company": "Bluewave Technologies Private Limited",
                "desc": "Vendor submits corporate details and tax identifiers but fails to upload required Bank Proof / Cancelled Cheque. Pipeline halts for document request.",
                "meta": "Missing: Bank Proof / Cancelled Cheque • Required for disbursement",
                "run": lambda: (
                    generate_synthetic_pan_pdf("BWAVE5678M", "Bluewave Technologies Private Limited"),
                    generate_synthetic_gst_pdf("36BWAVE5678M1Z8", "Bluewave Technologies Private Limited"),
                    None,  # Missing Bank Proof
                    "Bluewave Technologies Private Limited", "India", "Private Limited", "Level 5, Cyber Gateway, HITEC City, Hyderabad",
                    "Ramesh Kumar", "finance@bluewavetech.example", "BWAVE5678M", "36BWAVE5678M1Z8",
                    "Bluewave Technologies Pvt Ltd", "987654321098", "ICIC0000456", "ICICI Bank", False,
                ),
            },
            {
                "id": "p1_sc_mismatch",
                "num": "SCENARIO 3",
                "name": "Bank Name Mismatch: Third Party",
                "category": "PHASE 1 • FRAUD CHECK",
                "expected": "PENDING",
                "company": "Brightline Systems Private Limited",
                "desc": "Legal entity name 'Brightline Systems' conflicts with bank account holder 'Shree Trading Enterprises'. Flags potential third-party payment risk.",
                "meta": "Company: Brightline Systems • Bank Account: Shree Trading Enterprises",
                "run": lambda: (
                    generate_synthetic_pan_pdf("BRGHT9999K", "Brightline Systems Private Limited"),
                    generate_synthetic_gst_pdf("29BRGHT9999K1Z2", "Brightline Systems Private Limited"),
                    generate_synthetic_bank_pdf("Shree Trading Enterprises", "554433221100", "SBIN0001234"),
                    "Brightline Systems Private Limited", "India", "Private Limited", "102 Industrial Estate, Peenya, Bangalore",
                    "Ananya Sen", "accounts@brightline.example", "BRGHT9999K", "29BRGHT9999K1Z2",
                    "Shree Trading Enterprises", "554433221100", "SBIN0001234", "State Bank of India", True,
                ),
            },
            {
                "id": "p1_sc_dup",
                "num": "SCENARIO 4",
                "name": "Duplicate Vendor Registration",
                "category": "PHASE 1 • DEDUPLICATION",
                "expected": "PENDING",
                "company": "Northstar Office Supplies Private Limited",
                "desc": "Tax identifiers (PAN LMNOP1234Q & GSTIN 27LMNOP1234Q1Z5) match a pre-existing approved vendor in SQLite. Halts for procurement deduplication review.",
                "meta": "PAN: LMNOP1234Q • GSTIN: 27LMNOP1234Q1Z5 (Seeded in SQLite)",
                "run": lambda: (
                    generate_synthetic_pan_pdf("LMNOP1234Q", "Northstar Office Supplies Private Limited"),
                    generate_synthetic_gst_pdf("27LMNOP1234Q1Z5", "Northstar Office Supplies Private Limited"),
                    generate_synthetic_bank_pdf("Northstar Office Supplies", "223344556677", "KKBK0000123"),
                    "Northstar Office Supplies Private Limited", "India", "Private Limited", "12 MG Road, Mumbai",
                    "Sanjay Mehta", "sales@northstar.example", "LMNOP1234Q", "27LMNOP1234Q1Z5",
                    "Northstar Office Supplies", "223344556677", "KKBK0000123", "Kotak Mahindra Bank", True,
                ),
            },
            {
                "id": "p1_sc_restricted",
                "num": "SCENARIO 5",
                "name": "Restricted Risk Registry Hard-Stop",
                "category": "PHASE 1 • SCREENING",
                "expected": "REJECTED",
                "company": "Redwood Logistics LLP",
                "desc": "Tax identifier (PAN UVWXY5678Z) matches an internal compliance risk registry. Triggers immediate hard-stop rejection without manual bypass.",
                "meta": "PAN: UVWXY5678Z • Restricted Blacklist: HIGH_RISK_FINANCIAL_FRAUD",
                "run": lambda: (
                    generate_synthetic_pan_pdf("UVWXY5678Z", "Redwood Logistics LLP"),
                    generate_synthetic_gst_pdf("29UVWXY5678Z1Z5", "Redwood Logistics LLP"),
                    generate_synthetic_bank_pdf("Redwood Logistics LLP", "334455667788", "UTIB0000789"),
                    "Redwood Logistics LLP", "India", "Limited Liability Partnership (LLP)", "45 Harbor Road, Chennai",
                    "David D'Souza", "compliance@redwood.example", "UVWXY5678Z", "29UVWXY5678Z1Z5",
                    "Redwood Logistics LLP", "334455667788", "UTIB0000789", "Axis Bank", True,
                ),
            },
        ]

        # Render Phase 1 cards in a balanced 2-column grid
        for i in range(0, len(p1_scenarios), 2):
            cols = st.columns(2)
            pair = p1_scenarios[i : i + 2]
            for col_idx, sc in enumerate(pair):
                with cols[col_idx]:
                    with st.container(border=True):
                        st.markdown(
                            f"""
                            <div class="vf-scenario-header">
                                <span class="vf-scenario-tag">{sc['category']}</span>
                                {get_status_badge_html(sc['expected'])}
                            </div>
                            <div class="vf-scenario-title">{sc['name']}</div>
                            <div class="vf-scenario-desc">{sc['desc']}</div>
                            <div class="vf-scenario-meta">{sc['meta']}</div>
                            <div class="vf-scenario-outcome-row">
                                <span style="font-size: 0.75rem; font-weight: 600; color: #64748B;">Target Entity:</span>
                                <strong style="font-size: 0.78rem; color: #0F172A;">{sc['company']}</strong>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if st.button(f"⚡ Run {sc['num']}", key=f"btn_p1_{sc['id']}", use_container_width=True):
                            (
                                pan_b, gst_b, bank_b, comp_v, ctry_v, reg_v, addr_v,
                                c_name, c_email, pan_v, gstin_v, b_holder, b_acc, b_ifsc, b_name, bank_present,
                            ) = sc["run"]()

                            docs_meta = {
                                "pan_proof": DocumentMetadata("pan_proof", "Company PAN Proof", "pan_card.pdf", len(pan_b) if pan_b else 0, ".pdf", True if pan_b else False, raw_bytes=pan_b),
                                "gst_cert": DocumentMetadata("gst_cert", "GST Certificate", "gst_cert.pdf", len(gst_b) if gst_b else 0, ".pdf", True if gst_b else False, raw_bytes=gst_b),
                                "bank_proof": DocumentMetadata("bank_proof", "Bank Proof", "bank_proof.pdf", len(bank_b) if bank_b else 0, ".pdf", bank_present, raw_bytes=bank_b if bank_present else None),
                            }
                            sub = VendorSubmission(
                                company_name=comp_v,
                                country=ctry_v,
                                registration_type=reg_v,
                                address=addr_v,
                                contact_name=c_name,
                                contact_email=c_email,
                                pan=pan_v,
                                gstin=gstin_v,
                                bank_account_holder=b_holder,
                                bank_account_number=b_acc,
                                ifsc_code=b_ifsc,
                                bank_name=b_name,
                                documents=docs_meta,
                                run_type=f"Demo: {sc['num']}",
                            )
                            execute_and_display_workflow(sub)

    # -------------------------------------------------------------
    # TAB 2: PHASE 2 — DOCUMENT INTELLIGENCE (4 SCENARIOS)
    # -------------------------------------------------------------
    with tab_p2:
        st.markdown(
            """
            <div style="margin-bottom: 12px;">
                <div style="font-size: 0.92rem; font-weight: 700; color: #0F172A;">
                    Phase 2: PyMuPDF Extraction & Cross-Document Intelligence
                </div>
                <div style="font-size: 0.8rem; color: #64748B;">
                    Tests automated text-stream extraction from raw compliance PDFs, cross-document identifier reconciliation, and unreadable document fallback.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        p2_scenarios = [
            {
                "id": "p2_sc_a",
                "num": "SCENARIO A",
                "name": "Consistent Documents: Full Coherence",
                "category": "PHASE 2 • MULTI-DOCUMENT",
                "expected": "APPROVED",
                "company": "Aster Labs Private Limited",
                "desc": "Real synthetic PDFs for PAN, GST Certificate, and Cancelled Cheque contain 100% coherent identifiers extracted via PyMuPDF regex & label parsers.",
                "meta": "PAN: ABCDE1234F • Embedded PAN: ABCDE1234F • IFSC: HDFC0001234",
                "run": lambda: (
                    generate_synthetic_pan_pdf("ABCDE1234F", "Aster Labs Private Limited"),
                    generate_synthetic_gst_pdf("27ABCDE1234F1Z5", "Aster Labs Private Limited", "Aster Labs"),
                    generate_synthetic_bank_pdf("Aster Labs", "123456789012", "HDFC0001234", "HDFC Bank Ltd"),
                    "ABCDE1234F", "27ABCDE1234F1Z5", "Aster Labs Private Limited", "Aster Labs", "123456789012", "HDFC0001234",
                ),
            },
            {
                "id": "p2_sc_b",
                "num": "SCENARIO B",
                "name": "Cross-Doc Conflict: PAN Mismatch",
                "category": "PHASE 2 • TAX CONFLICT",
                "expected": "PENDING",
                "company": "Bluewave Technologies Private Limited",
                "desc": "PAN document extracts 'ABCDE1234F', but the GST Certificate PDF contains conflicting embedded PAN '36ZZZZZ9999Z1Z8'. Extractor halts for tax audit.",
                "meta": "PAN Doc: ABCDE1234F • GST Doc Embedded: ZZZZZ9999Z",
                "run": lambda: (
                    generate_synthetic_pan_pdf("ABCDE1234F", "Bluewave Technologies Private Limited"),
                    generate_synthetic_gst_pdf("36ZZZZZ9999Z1Z8", "Bluewave Technologies Private Limited"),
                    generate_synthetic_bank_pdf("Bluewave Technologies", "987654321098", "ICIC0000456"),
                    "ABCDE1234F", "36ZZZZZ9999Z1Z8", "Bluewave Technologies Private Limited", "Bluewave Technologies", "987654321098", "ICIC0000456",
                ),
            },
            {
                "id": "p2_sc_c",
                "num": "SCENARIO C",
                "name": "Entity Conflict: Name Mismatch",
                "category": "PHASE 2 • SUFFIX NORMALIZATION",
                "expected": "PENDING",
                "company": "Brightline Systems Private Limited",
                "desc": "GST Certificate extracts 'Brightline Systems', but Cancelled Cheque extracts 'Shree Trading Enterprises'. Flags company name divergence.",
                "meta": "GST Doc: Brightline Systems • Cheque Doc: Shree Trading Enterprises",
                "run": lambda: (
                    generate_synthetic_pan_pdf("BRGHT9999K", "Brightline Systems Private Limited"),
                    generate_synthetic_gst_pdf("29BRGHT9999K1Z2", "Brightline Systems Private Limited"),
                    generate_synthetic_bank_pdf("Shree Trading Enterprises", "554433221100", "SBIN0001234"),
                    "BRGHT9999K", "29BRGHT9999K1Z2", "Brightline Systems Private Limited", "Shree Trading Enterprises", "554433221100", "SBIN0001234",
                ),
            },
            {
                "id": "p2_sc_d",
                "num": "SCENARIO D",
                "name": "Extraction Fallback: Scanned / Unreadable",
                "category": "PHASE 2 • RESILIENCE",
                "expected": "PENDING",
                "company": "Aster Labs Private Limited",
                "desc": "PAN document PDF contains no selectable text (simulating image scan). System safely flags UNREADABLE and halts for human review without hallucinating.",
                "meta": "Text Stream: 0 selectable chars • Status: UNREADABLE (No fake data)",
                "run": lambda: (
                    generate_unreadable_pdf(),
                    generate_synthetic_gst_pdf("27ABCDE1234F1Z5", "Aster Labs Private Limited"),
                    generate_synthetic_bank_pdf("Aster Labs", "123456789012", "HDFC0001234"),
                    "ABCDE1234F", "27ABCDE1234F1Z5", "Aster Labs Private Limited", "Aster Labs", "123456789012", "HDFC0001234",
                ),
            },
        ]

        # Render Phase 2 cards in a balanced 2-column grid
        for i in range(0, len(p2_scenarios), 2):
            cols = st.columns(2)
            pair = p2_scenarios[i : i + 2]
            for col_idx, sc in enumerate(pair):
                with cols[col_idx]:
                    with st.container(border=True):
                        st.markdown(
                            f"""
                            <div class="vf-scenario-header">
                                <span class="vf-scenario-tag">{sc['category']}</span>
                                {get_status_badge_html(sc['expected'])}
                            </div>
                            <div class="vf-scenario-title">{sc['name']}</div>
                            <div class="vf-scenario-desc">{sc['desc']}</div>
                            <div class="vf-scenario-meta">{sc['meta']}</div>
                            <div class="vf-scenario-outcome-row">
                                <span style="font-size: 0.75rem; font-weight: 600; color: #64748B;">Target Entity:</span>
                                <strong style="font-size: 0.78rem; color: #0F172A;">{sc['company']}</strong>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if st.button(f"⚡ Run {sc['num']}", key=f"btn_p2_{sc['id']}", use_container_width=True):
                            pan_b, gst_b, bank_b, pan_v, gstin_v, comp_v, holder_v, acc_v, ifsc_v = sc["run"]()
                            docs_meta = {
                                "pan_proof": DocumentMetadata("pan_proof", "Company PAN Proof", "pan_card.pdf", len(pan_b), ".pdf", True, raw_bytes=pan_b),
                                "gst_cert": DocumentMetadata("gst_cert", "GST Registration Certificate", "gst_certificate.pdf", len(gst_b), ".pdf", True, raw_bytes=gst_b),
                                "bank_proof": DocumentMetadata("bank_proof", "Bank Proof / Cancelled Cheque", "cancelled_cheque.pdf", len(bank_b), ".pdf", True, raw_bytes=bank_b),
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
                                run_type=f"Demo: {sc['num']}",
                            )
                            execute_and_display_workflow(sub)


# ==============================================================================
# PAGE 4: EXECUTION DASHBOARD & RUN HISTORY (ENTERPRISE REDESIGN)
# ==============================================================================
elif st.session_state.current_page == "Execution Dashboard":
    render_page_header(
        breadcrumb="Workspace > Execution Dashboard",
        title="Execution Dashboard",
        subtitle="Monitor vendor onboarding activity, verification outcomes and operational exceptions.",
    )

    # 4 Key Dynamic KPI Cards (Clean, Responsive, Equal Height)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("Total Runs", metrics["total_submissions"], "All recorded runs in database", color_hint="#0F172A", icon_label="📊")
    with k2:
        render_kpi_card("Approved", metrics["approved"], f"{metrics['approval_rate']}% zero-touch pass rate", color_hint="#16A34A", icon_label="✓")
    with k3:
        render_kpi_card("Pending", metrics["pending"], "Requires review / discrepancy", color_hint="#D97706", icon_label="⏳")
    with k4:
        render_kpi_card("Rejected", metrics["rejected"], "Compliance hard-stop flag", color_hint="#DC2626", icon_label="🛑")

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # Clean Filter Toolbar (3 balanced columns, no cramped layout)
    with st.container(border=True):
        f_col1, f_col2, f_col3 = st.columns([3, 2, 2])
        with f_col1:
            search_query = st.text_input(
                "Search Vendor Name or Run ID",
                placeholder="Type vendor name or ID...",
            )
        with f_col2:
            status_filter = st.selectbox(
                "Filter by Decision Status",
                ["ALL", "APPROVED", "PENDING", "REJECTED"],
                index=0,
            )
        with f_col3:
            date_filter = st.date_input("Filter by Date (Optional)", value=None)

    start_dt = f"{date_filter}T00:00:00" if date_filter else None
    end_dt = f"{date_filter}T23:59:59" if date_filter else None

    # Fetch runs from SQLite
    all_runs = get_all_runs(
        DB_PATH,
        status_filter=status_filter if status_filter != "ALL" else None,
        search_query=search_query if search_query else None,
        start_date=start_dt,
        end_date=end_dt,
    )

    # Empty State Check
    if not all_runs:
        st.markdown(
            """
            <div class="vf-surface-card" style="text-align: center; padding: 40px 20px; margin-top: 10px;">
                <div style="font-size: 2.2rem; margin-bottom: 10px;">📂</div>
                <h4 style="margin: 0 0 6px 0; color: #0F172A; font-size: 1.1rem;">No Execution Runs Found</h4>
                <p style="margin: 0 0 16px 0; font-size: 0.85rem; color: #64748B;">
                    No recorded verification runs match your current filter criteria or have been executed yet.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        empty_col1, empty_col2, empty_spacer = st.columns([2, 2, 3])
        with empty_col1:
            if st.button("＋ Start New Submission", use_container_width=True, type="primary"):
                st.session_state.current_page = "New Submission"
                st.rerun()
        with empty_col2:
            if st.button("⚡ Run Demo Scenario", use_container_width=True):
                st.session_state.current_page = "Demo Scenarios"
                st.rerun()
    else:
        # Rebuilt 6-column historical runs table
        table_rows = []
        for r in all_runs:
            raw_id = r["run_id"]
            short_id = f"...{raw_id[-8:]}" if len(raw_id) > 16 else raw_id
            table_rows.append(
                {
                    "Vendor": r["vendor_name"],
                    "Run ID": short_id,
                    "Submission Timestamp": r["created_at"][:19].replace("T", " "),
                    "Decision": r["status"],
                    "Processing Duration": f"{r['processing_duration_ms']:.1f} ms",
                    "Issues": f"{r['issues_count']} flag" if r["issues_count"] == 1 else f"{r['issues_count']} flags",
                    "_full_run_id": r["run_id"],
                }
            )

        df = pd.DataFrame(table_rows)

        # Render structured table with fixed column configuration
        st.dataframe(
            df.drop(columns=["_full_run_id"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Vendor": st.column_config.TextColumn(
                    "Vendor",
                    help="Legal registered business name",
                    width="large",
                ),
                "Run ID": st.column_config.TextColumn(
                    "Run ID",
                    help="Execution run identifier",
                    width="small",
                ),
                "Submission Timestamp": st.column_config.TextColumn(
                    "Submission Timestamp (UTC)",
                    help="Date and time when the onboarding run was submitted",
                    width="medium",
                ),
                "Decision": st.column_config.TextColumn(
                    "Decision",
                    help="Automated onboarding decision",
                    width="small",
                ),
                "Processing Duration": st.column_config.TextColumn(
                    "Duration",
                    help="Total execution latency across all verification stages",
                    width="small",
                ),
                "Issues": st.column_config.TextColumn(
                    "Issues",
                    help="Number of policy flags or verification issues identified",
                    width="small",
                ),
            },
        )

        csv_buffer = io.StringIO()
        df.drop(columns=["_full_run_id"]).to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Export Run History (CSV)",
            data=csv_buffer.getvalue(),
            file_name="vendorflow_run_history.csv",
            mime="text/csv",
        )

        st.markdown("---")

        # -------------------------------------------------------------
        # INDIVIDUAL RUN INSPECTOR (HUMAN-READABLE FIRST)
        # -------------------------------------------------------------
        st.markdown(
            """
            <div style="margin-top: 1.25rem; margin-bottom: 0.65rem;">
                <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.06em;">
                    Audit Trail Deep Dive
                </div>
                <h3 style="margin: 0; font-size: 1.2rem; font-weight: 700; color: #0F172A;">
                    Individual Run Inspector
                </h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Select Run
        run_ids = [r["run_id"] for r in all_runs]
        default_idx = 0
        if st.session_state.selected_inspector_run_id in run_ids:
            default_idx = run_ids.index(st.session_state.selected_inspector_run_id)

        selected_run_id = st.selectbox(
            "Select Run ID to Inspect:",
            run_ids,
            index=default_idx,
            format_func=lambda rid: f"{next((r['vendor_name'] for r in all_runs if r['run_id'] == rid), '')} — {next((r['status'] for r in all_runs if r['run_id'] == rid), '')} ({rid})",
        )

        if selected_run_id:
            run_data = get_run_by_id(selected_run_id, DB_PATH)
            if run_data:
                # Top Decision Banner
                render_decision_banner(
                    status=run_data["status"],
                    summary=run_data["decision"].get("summary", ""),
                    duration_ms=run_data["processing_duration_ms"],
                    run_id=run_data["run_id"],
                    timestamp=run_data["created_at"][:19].replace("T", " "),
                )

                # 6 Human-Readable Tabs
                insp_tab1, insp_tab2, insp_tab3, insp_tab4, insp_tab5, insp_tab6 = st.tabs(
                    [
                        "🏢 Vendor Overview",
                        "📄 Document Extraction",
                        "🔍 Cross-Checks",
                        "⚡ Execution Stages (13)",
                        "🏁 Final Decision & Plan",
                        "✉️ Communication Draft",
                    ]
                )

                # TAB 1: VENDOR OVERVIEW
                with insp_tab1:
                    inp = run_data.get("redacted_input", {})
                    v_col1, v_col2 = st.columns(2)
                    with v_col1:
                        with st.container(border=True):
                            st.markdown(
                                f"""
                                <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase; margin-bottom: 8px;">
                                    Legal Entity & Business Profile
                                </div>
                                <div style="font-size: 0.85rem; line-height: 1.6;">
                                    <strong>Company Name:</strong> {inp.get('company_name', 'N/A')}<br>
                                    <strong>Country:</strong> {inp.get('country', 'N/A')}<br>
                                    <strong>Registration Type:</strong> {inp.get('registration_type', 'N/A')}<br>
                                    <strong>Registered Address:</strong> {inp.get('address', 'N/A')}<br>
                                    <strong>Contact Person:</strong> {inp.get('contact_name', 'N/A')}<br>
                                    <strong>Contact Email:</strong> {inp.get('contact_email', 'N/A')}
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                    with v_col2:
                        with st.container(border=True):
                            st.markdown(
                                f"""
                                <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase; margin-bottom: 8px;">
                                    Tax & Banking Identifiers (Privacy-Masked)
                                </div>
                                <div style="font-size: 0.85rem; line-height: 1.6;">
                                    <strong>Company PAN:</strong> <code>{inp.get('pan_masked', 'N/A')}</code><br>
                                    <strong>GSTIN:</strong> <code>{inp.get('gstin_masked', 'N/A')}</code><br>
                                    <strong>Bank Account Holder:</strong> {inp.get('bank_account_holder', 'N/A')}<br>
                                    <strong>Account Number:</strong> <code>{inp.get('bank_account_masked', 'N/A')}</code><br>
                                    <strong>Bank IFSC Code:</strong> <code>{inp.get('ifsc_code', 'N/A')}</code><br>
                                    <strong>Bank Name:</strong> {inp.get('bank_name', 'N/A')}
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                    # Documents attached summary table
                    doc_sum = inp.get("documents_summary", {})
                    if doc_sum:
                        st.markdown(
                            """
                            <div style="font-size: 0.82rem; font-weight: 600; color: #1E293B; margin-top: 10px; margin-bottom: 4px;">
                                Attached Compliance Documents
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        doc_rows = []
                        for d_key, d_val in doc_sum.items():
                            doc_rows.append(
                                {
                                    "Document Type": d_key.replace("_", " ").title(),
                                    "Filename": d_val.get("filename", "N/A"),
                                    "Size": f"{d_val.get('size_bytes', 0) / 1024:.1f} KB" if d_val.get("size_bytes") else "0 KB",
                                    "Attached": "✓ Attached" if d_val.get("is_present") else "✕ Missing",
                                }
                            )
                        st.dataframe(pd.DataFrame(doc_rows), use_container_width=True, hide_index=True)

                # TAB 2: DOCUMENT EXTRACTION RESULTS
                with insp_tab2:
                    ext_data = run_data.get("extraction_results", {})
                    if ext_data:
                        # 3 Document summary cards
                        dc1, dc2, dc3 = st.columns(3)
                        p_ext = ext_data.get("pan_proof", {})
                        g_ext = ext_data.get("gst_cert", {})
                        b_ext = ext_data.get("bank_proof", {})

                        with dc1:
                            with st.container(border=True):
                                st.markdown(
                                    f"""
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                        <strong style="font-size: 0.85rem;">PAN Card Proof</strong>
                                        {get_status_badge_html(p_ext.get('extraction_status', 'N/A'))}
                                    </div>
                                    <div style="font-size: 0.78rem; color: #64748B;">
                                        PAN: <strong>{p_ext.get('extracted_fields', {}).get('pan', 'N/A')}</strong><br>
                                        Name: <strong>{p_ext.get('extracted_fields', {}).get('name', 'N/A')}</strong>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                        with dc2:
                            with st.container(border=True):
                                st.markdown(
                                    f"""
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                        <strong style="font-size: 0.85rem;">GST Certificate</strong>
                                        {get_status_badge_html(g_ext.get('extraction_status', 'N/A'))}
                                    </div>
                                    <div style="font-size: 0.78rem; color: #64748B;">
                                        GSTIN: <strong>{g_ext.get('extracted_fields', {}).get('gstin', 'N/A')}</strong><br>
                                        Legal: <strong>{g_ext.get('extracted_fields', {}).get('legal_name', 'N/A')}</strong>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                        with dc3:
                            with st.container(border=True):
                                st.markdown(
                                    f"""
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                        <strong style="font-size: 0.85rem;">Cancelled Cheque</strong>
                                        {get_status_badge_html(b_ext.get('extraction_status', 'N/A'))}
                                    </div>
                                    <div style="font-size: 0.78rem; color: #64748B;">
                                        Holder: <strong>{b_ext.get('extracted_fields', {}).get('account_holder', 'N/A')}</strong><br>
                                        IFSC: <strong>{b_ext.get('extracted_fields', {}).get('ifsc', 'N/A')}</strong>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

                        # Extraction comparison rows
                        comp_rows = []
                        if p_ext:
                            for f_name, f_val in p_ext.get("extracted_fields", {}).items():
                                comp_rows.append(
                                    {
                                        "Field": f"PAN Doc: {f_name.title()}",
                                        "Extracted Value": str(f_val),
                                        "Source": "PAN Card Proof",
                                        "Confidence": p_ext.get("field_confidence", {}).get(f_name, "LOW"),
                                        "Status": p_ext.get("extraction_status", "N/A"),
                                    }
                                )
                        if g_ext:
                            for f_name, f_val in g_ext.get("extracted_fields", {}).items():
                                comp_rows.append(
                                    {
                                        "Field": f"GST Doc: {f_name.title()}",
                                        "Extracted Value": str(f_val),
                                        "Source": "GST Certificate",
                                        "Confidence": g_ext.get("field_confidence", {}).get(f_name, "LOW"),
                                        "Status": g_ext.get("extraction_status", "N/A"),
                                    }
                                )
                        if b_ext:
                            for f_name, f_val in b_ext.get("extracted_fields", {}).items():
                                display_val = f"********{str(f_val)[-4:]}" if f_name == "account_number" and f_val else str(f_val)
                                comp_rows.append(
                                    {
                                        "Field": f"Bank Doc: {f_name.title()}",
                                        "Extracted Value": display_val,
                                        "Source": "Cancelled Cheque",
                                        "Confidence": b_ext.get("field_confidence", {}).get(f_name, "LOW"),
                                        "Status": b_ext.get("extraction_status", "N/A"),
                                    }
                                )
                        if comp_rows:
                            st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)
                    else:
                        st.info("Phase 1 run: Document extraction details were not recorded for this execution.")

                # TAB 3: CROSS-DOCUMENT VERIFICATION
                with insp_tab3:
                    cross_data = run_data.get("cross_document_results", {})
                    checks = cross_data.get("checks", [])
                    if checks:
                        st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)
                        if cross_data.get("discrepancies"):
                            st.warning("⚠️ **Reconciliation Discrepancies:**\n" + "\n".join([f"- {d}" for d in cross_data["discrepancies"]]))
                        else:
                            st.success("✓ Clean Cross-Document Alignment: All identifiers reconcile across uploaded documents.")
                    else:
                        st.info("Standard statutory checks applied without cross-source conflicts.")

                # TAB 4: WORKFLOW EXECUTION STAGES
                with insp_tab4:
                    st.markdown(
                        """
                        <div style="font-size: 0.85rem; font-weight: 600; color: #1E293B; margin-bottom: 8px;">
                            Sequential Execution Audit Trail (13 Stages)
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    for s in run_data.get("stage_results", []):
                        render_stage_card(
                            stage_number=s["stage_number"],
                            stage_name=s["stage_name"],
                            status=s["status"],
                            summary=s["summary"],
                            details=s.get("details", []),
                            duration_ms=s.get("duration_ms", 0.0),
                        )

                # TAB 5: FINAL DECISION & ACTION PLAN
                with insp_tab5:
                    dec = run_data.get("decision", {})
                    d_col1, d_col2 = st.columns(2)
                    with d_col1:
                        with st.container(border=True):
                            st.markdown(
                                """
                                <div style="font-size: 0.78rem; font-weight: 700; color: #15803D; text-transform: uppercase; margin-bottom: 6px;">
                                    ✓ Passed Verification Checks
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            if dec.get("passed_checks"):
                                for c in dec["passed_checks"]:
                                    st.markdown(f"- <span style='color: #16A34A; font-weight: 700;'>✓</span> {c}", unsafe_allow_html=True)
                            else:
                                st.info("No checks passed.")
                    with d_col2:
                        with st.container(border=True):
                            st.markdown(
                                """
                                <div style="font-size: 0.78rem; font-weight: 700; color: #B45309; text-transform: uppercase; margin-bottom: 6px;">
                                    ⚠ Items Requiring Attention / Flags
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            if dec.get("issues"):
                                for iss in dec["issues"]:
                                    badge = get_status_badge_html(iss.get("issue_type", "WARNING"))
                                    st.markdown(
                                        f"""
                                        <div style="margin-bottom: 6px; padding: 6px 10px; background: #FFFBEB; border-left: 3px solid #D97706; border-radius: 4px; font-size: 0.8rem;">
                                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                                <strong>{iss.get('stage')} • {iss.get('field_name')}</strong>
                                                {badge}
                                            </div>
                                            <div style="color: #78350F; margin-top: 2px;">{iss.get('message')}</div>
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )
                            else:
                                st.success("No policy flags or verification issues identified.")

                    st.markdown(
                        """
                        <div class="vf-surface-card" style="margin-top: 10px;">
                            <div class="vf-section-header">
                                <span>📋</span> Recommended Operational Next Steps
                            </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    for step in dec.get("next_steps", []):
                        st.markdown(f"- **{step}**")
                    st.markdown("</div>", unsafe_allow_html=True)

                # TAB 6: COMMUNICATION DRAFT
                with insp_tab6:
                    st.text_area(
                        "Generated Communication Draft",
                        value=run_data.get("communication_draft", ""),
                        height=240,
                        disabled=True,
                    )

                # Collapsed Raw JSON at bottom
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                with st.expander("🛠️ Advanced: View Raw Audit Record (JSON)", expanded=False):
                    st.json(run_data)


# ==============================================================================
# PAGE 5: VALIDATION RULES & SYSTEM ARCHITECTURE
# ==============================================================================
elif st.session_state.current_page == "Validation Rules":
    render_page_header(
        breadcrumb="Tools > Validation Rules",
        title="Statutory Rules, Limits & System Architecture",
        subtitle="Definitive technical specifications, validation constraints, and extraction models governing VendorFlow.",
    )

    tab_r1, tab_r2 = st.tabs(["⚙️ Document Extraction & Cross-Checks", "⚠️ Honest Limitations & Scope Boundaries"])

    with tab_r1:
        st.markdown(
            """
            <div class="vf-surface-card">
                <div class="vf-section-header">
                    <span>1.</span> Document Extraction Architecture & Regular Expressions
                </div>
                <ul>
                    <li><strong>Text Stream Extraction:</strong> Uses <strong>PyMuPDF</strong> (<code>fitz / pymupdf.open</code>) with <code>pypdf</code> fallback to extract clean text streams from PDF compliance documents.</li>
                    <li><strong>Structured Regex Matching:</strong>
                        <ul>
                            <li><strong>PAN Extraction:</strong> <code>\\b([A-Z]{5}[0-9]{4}[A-Z])\\b</code> (Evaluated on PAN card text).</li>
                            <li><strong>GSTIN Extraction:</strong> <code>\\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\\b</code> (Evaluated on GST Certificate).</li>
                            <li><strong>Embedded PAN Extraction:</strong> Characters 2 to 11 of the extracted GSTIN.</li>
                            <li><strong>Bank IFSC Extraction:</strong> <code>\\b([A-Z]{4}0[A-Z0-9]{6})\\b</code>.</li>
                            <li><strong>Bank Account Number:</strong> <code>(?:ACCOUNT\\s*NUMBER|A/C\\s*NO)[:\\s]*([0-9]{9,18})</code>.</li>
                        </ul>
                    </li>
                    <li><strong>Label-Based Name Extraction:</strong> Parses legal entity names, trade names, and account holder names from text labels.</li>
                    <li><strong>Confidence Rating:</strong> Assigns <code>HIGH</code>, <code>MEDIUM</code>, or <code>LOW</code> confidence reflecting extraction reliability.</li>
                </ul>
            </div>

            <div class="vf-surface-card">
                <div class="vf-section-header">
                    <span>2.</span> Cross-Document Consistency Matrix
                </div>
                <ul>
                    <li><strong>Cross-Check 1 (PAN):</strong> Compares PAN from PAN Proof vs. PAN embedded in GSTIN vs. Manual Entry. All must match.</li>
                    <li><strong>Cross-Check 2 (Legal Entity Name):</strong> Compares name from PAN Proof vs. Legal name from GST Certificate vs. Manual Company Name. Normalizes legal suffixes (<code>PRIVATE LIMITED</code>, <code>PVT LTD</code>, <code>LLP</code>, <code>LTD</code>).</li>
                    <li><strong>Cross-Check 3 (Bank Account Holder):</strong> Compares bank account holder name against verified legal entity name. Material differences result in <strong>PENDING</strong> for manual ownership review.</li>
                    <li><strong>Cross-Check 4 (GSTIN & Banking Alignment):</strong> Confirms document values match manual form entries.</li>
                </ul>
            </div>

            <div class="vf-surface-card">
                <div class="vf-section-header">
                    <span>3.</span> Duplicate Detection & Restricted Screening Engines
                </div>
                <ul>
                    <li><strong>SHA-256 Privacy Hashing:</strong> Tax identifiers (PAN and GSTIN) are hashed using SHA-256 before duplicate and restricted lookups.</li>
                    <li><strong>Internal Restricted Registry:</strong> Tax hashes are screened against an internal compliance blacklist. Matches trigger an immediate <strong>REJECTED</strong> hard-stop.</li>
                    <li><strong>Duplicate Vendor Detection:</strong> Matches against existing approved records in SQLite trigger a <strong>PENDING</strong> state for procurement deduplication review.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with tab_r2:
        st.markdown(
            """
            <div class="vf-surface-card">
                <div class="vf-section-header">
                    <span>⚠️</span> Honest Scope Boundaries (Phase 2 Prototype)
                </div>
                <ol>
                    <li><strong>Selectable Text PDFs vs Heavy OCR:</strong> The extractor uses high-performance native PDF stream extraction (PyMuPDF). It does not require external paid OCR APIs (Tesseract/Google Vision). Scanned PDFs without text streams are safely routed to manual confirmation without fabricating values.</li>
                    <li><strong>No External LLM Dependencies:</strong> All extraction, regex parsing, and cross-checks run deterministically on CPU in milliseconds without external LLM API costs or token latency.</li>
                    <li><strong>Structural Validation vs Live Government Gateways:</strong> Extracted tax identifiers are validated for statutory structural syntax and cross-document alignment, not queried against live government portals (NSDL/GSTN).</li>
                    <li><strong>Banking Routing vs Penny-Drop Verification:</strong> IFSC syntax and account number length are verified. Bank account ownership is not authenticated against real inter-bank networks (IMPS).</li>
                    <li><strong>Human in the Loop:</strong> Automated approval marks technical compliance clearance. Real-world vendor activation and payment release remains under human procurement authority.</li>
                </ol>
            </div>
            """,
            unsafe_allow_html=True,
        )
