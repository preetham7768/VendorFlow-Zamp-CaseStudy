"""
UI Styling, Design Tokens, Badges, and Component Helpers for VendorFlow Streamlit Frontend.
Enterprise SaaS aesthetic inspired by Stripe, Linear, and Ramp.
"""

import html
from typing import Any, Dict, List, Optional
import streamlit as st


def get_status_badge_html(status: str) -> str:
    """Returns an enterprise-styled status badge HTML with consistent semantic colors."""
    status_upper = (status or "").upper().strip()

    if status_upper in ("APPROVED", "COMPLETED", "PASS", "SUCCESS", "HIGH"):
        bg = "#F0FDF4"
        text = "#15803D"
        border = "#BBF7D0"
        icon = "✓"
    elif status_upper in ("PENDING", "NEEDS ATTENTION", "NEEDS_ATTENTION", "WARNING", "PARTIAL", "MEDIUM", "MED"):
        bg = "#FFFBEB"
        text = "#B45309"
        border = "#FDE68A"
        icon = "⚠"
    elif status_upper in ("REJECTED", "FAILED", "HARD_STOP", "UNREADABLE", "MISSING", "INVALID_FORMAT", "INVALID_SIZE", "LOW"):
        bg = "#FEF2F2"
        text = "#B91C1C"
        border = "#FECACA"
        icon = "✕"
    elif status_upper in ("RUNNING", "IN_PROGRESS"):
        bg = "#EFF6FF"
        text = "#1D4ED8"
        border = "#BFDBFE"
        icon = "●"
    elif status_upper in ("QUEUED", "WAITING"):
        bg = "#F8FAFC"
        text = "#64748B"
        border = "#E2E8F0"
        icon = "○"
    else:
        bg = "#F1F5F9"
        text = "#334155"
        border = "#CBD5E1"
        icon = "•"

    return f"""
    <span style="
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background-color: {bg};
        color: {text};
        border: 1px solid {border};
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        white-space: nowrap;
        line-height: 1.35;
        box-sizing: border-box;
    ">
        <span style="font-size: 0.72rem;">{icon}</span> {html.escape(status_upper)}
    </span>
    """


def get_confidence_badge_html(confidence: str) -> str:
    """Returns a compact confidence pill."""
    conf = (confidence or "").upper().strip()
    if conf == "HIGH":
        return '<span style="background:#F0FDF4; color:#15803D; border:1px solid #BBF7D0; padding:2px 7px; border-radius:9999px; font-size:0.7rem; font-weight:700;">HIGH</span>'
    elif conf in ("MEDIUM", "MED"):
        return '<span style="background:#FFFBEB; color:#B45309; border:1px solid #FDE68A; padding:2px 7px; border-radius:9999px; font-size:0.7rem; font-weight:700;">MED</span>'
    else:
        return '<span style="background:#FEF2F2; color:#B91C1C; border:1px solid #FECACA; padding:2px 7px; border-radius:9999px; font-size:0.7rem; font-weight:700;">LOW</span>'


def inject_custom_css():
    """Injects high-finish enterprise CSS styling for the Streamlit app with strict overflow handling."""
    st.markdown(
        """
        <style>
        /* Modern Inter font typography & smooth font rendering */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

        *, *::before, *::after {
            box-sizing: border-box !important;
        }

        html, body, [class*="css"], .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
            background-color: #F8FAFC !important;
            color: #111827 !important;
            -webkit-font-smoothing: antialiased;
            overflow-x: hidden !important;
        }

        /* Prevent text overflowing container cards */
        p, span, div, h1, h2, h3, h4, h5, h6, label {
            overflow-wrap: anywhere;
            word-break: break-word;
        }

        /* ------------------------------------------------------------------ */
        /* SIDEBAR (Dark Enterprise Theme: #111827)                           */
        /* ------------------------------------------------------------------ */
        [data-testid="stSidebar"] {
            background-color: #111827 !important;
            border-right: 1px solid #1F2937 !important;
            padding-top: 1.25rem !important;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {
            color: #E2E8F0 !important;
        }
        [data-testid="stSidebar"] hr {
            border-color: #1F2937 !important;
            margin: 1rem 0 !important;
        }

        /* Sidebar Navigation Section Headers */
        .vf-nav-section-title {
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #64748B !important;
            padding: 6px 12px 3px 12px;
            margin-top: 8px;
        }

        /* Sidebar Navigation Buttons */
        [data-testid="stSidebar"] .stButton > button {
            width: 100% !important;
            text-align: left !important;
            justify-content: flex-start !important;
            background-color: transparent !important;
            border: 1px solid transparent !important;
            color: #94A3B8 !important;
            font-size: 0.85rem !important;
            font-weight: 500 !important;
            padding: 7px 12px !important;
            border-radius: 6px !important;
            transition: all 0.15s ease !important;
            margin-bottom: 2px !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background-color: #1E293B !important;
            color: #FFFFFF !important;
            border-color: #334155 !important;
        }
        [data-testid="stSidebar"] .stButton > button[kind="primary"],
        [data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
            background-color: #4F46E5 !important;
            color: #FFFFFF !important;
            border-color: #4F46E5 !important;
            font-weight: 600 !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3) !important;
        }

        /* Sidebar Metric Cards */
        .vf-sidebar-metric {
            background: #1E293B;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 8px 10px;
            margin-bottom: 6px;
        }
        .vf-sidebar-metric-label {
            font-size: 0.68rem;
            color: #94A3B8;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .vf-sidebar-metric-value {
            font-size: 1.15rem;
            color: #FFFFFF;
            font-weight: 700;
            margin-top: 2px;
        }

        /* Sidebar Health Badge */
        .vf-sidebar-status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.72rem;
            color: #94A3B8;
            background: #1E293B;
            padding: 4px 10px;
            border-radius: 9999px;
            border: 1px solid #334155;
        }
        .vf-pulse-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: #10B981;
            box-shadow: 0 0 6px #10B981;
            display: inline-block;
        }

        /* ------------------------------------------------------------------ */
        /* MAIN CONTENT AREA & SHELL                                          */
        /* ------------------------------------------------------------------ */
        .main .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2.5rem !important;
            max-width: 1320px !important;
            min-width: 0 !important;
        }

        /* Page Header & Breadcrumb */
        .vf-page-header {
            margin-bottom: 1.25rem;
            padding-bottom: 0.85rem;
            border-bottom: 1px solid #E5E7EB;
            min-width: 0;
            max-width: 100%;
        }
        .vf-breadcrumb {
            font-size: 0.75rem;
            font-weight: 600;
            color: #64748B;
            letter-spacing: 0.03em;
            text-transform: uppercase;
            margin-bottom: 0.25rem;
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }
        .vf-breadcrumb span.sep {
            color: #CBD5E1;
            font-size: 0.7rem;
        }
        .vf-page-title {
            font-size: 1.65rem;
            font-weight: 700;
            color: #0F172A;
            margin: 0 0 0.25rem 0;
            letter-spacing: -0.02em;
            line-height: 1.25;
            word-break: break-word;
        }
        .vf-page-subtitle {
            font-size: 0.9rem;
            color: #64748B;
            margin: 0;
            line-height: 1.45;
            word-break: break-word;
        }

        /* ------------------------------------------------------------------ */
        /* KPI METRIC CARDS (EQUAL HEIGHT, RESPONSIVE, NO OVERFLOW)            */
        /* ------------------------------------------------------------------ */
        .vf-kpi-card {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 14px 16px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
            box-sizing: border-box !important;
            min-width: 0 !important;
            max-width: 100% !important;
            width: 100% !important;
            height: 104px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: space-between !important;
            overflow: hidden !important;
            transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .vf-kpi-card:hover {
            border-color: #CBD5E1;
            box-shadow: 0 3px 6px -1px rgba(0, 0, 0, 0.04);
        }
        .vf-kpi-label {
            font-size: 0.72rem !important;
            font-weight: 700 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            color: #64748B !important;
            display: flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            margin: 0 !important;
            line-height: 1.2 !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }
        .vf-kpi-value {
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: #0F172A;
            line-height: 1.1 !important;
            letter-spacing: -0.02em !important;
            margin: 2px 0 !important;
            overflow-wrap: anywhere !important;
            word-break: break-word !important;
        }
        .vf-kpi-subtext {
            font-size: 0.72rem !important;
            color: #94A3B8 !important;
            line-height: 1.2 !important;
            margin: 0 !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }

        /* ------------------------------------------------------------------ */
        /* SCENARIO CARD WORKSPACE STYLES                                     */
        /* ------------------------------------------------------------------ */
        .vf-scenario-card {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 16px 18px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
            box-sizing: border-box;
            min-width: 0;
            max-width: 100%;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            height: 100%;
            margin-bottom: 12px;
        }
        .vf-scenario-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
            flex-wrap: wrap;
            gap: 6px;
        }
        .vf-scenario-tag {
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #4F46E5;
            background: #EEF2FF;
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid #C7D2FE;
        }
        .vf-scenario-title {
            font-size: 0.98rem;
            font-weight: 700;
            color: #0F172A;
            margin: 0 0 6px 0;
            line-height: 1.3;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .vf-scenario-desc {
            font-size: 0.82rem;
            color: #475569;
            line-height: 1.45;
            margin: 0 0 10px 0;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .vf-scenario-meta {
            font-size: 0.74rem;
            color: #64748B;
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 4px;
            padding: 6px 10px;
            margin-bottom: 10px;
            font-family: 'JetBrains Mono', Consolas, monospace;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .vf-scenario-outcome-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 8px;
            border-top: 1px solid #F1F5F9;
            margin-bottom: 12px;
            font-size: 0.78rem;
        }

        /* Native Streamlit border container override */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E5E7EB !important;
            border-radius: 8px !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
            box-sizing: border-box !important;
            min-width: 0 !important;
            max-width: 100% !important;
        }

        /* Executive Decision Hero Banner */
        .vf-decision-hero {
            background: #FFFFFF;
            border-radius: 8px;
            padding: 18px 20px;
            margin: 16px 0;
            border: 1.5px solid #E5E7EB;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
            box-sizing: border-box;
            min-width: 0;
            max-width: 100%;
        }
        .vf-decision-hero.approved {
            border-color: #86EFAC;
            background: linear-gradient(180deg, #F0FDF4 0%, #FFFFFF 100%);
        }
        .vf-decision-hero.pending {
            border-color: #FDE68A;
            background: linear-gradient(180deg, #FFFBEB 0%, #FFFFFF 100%);
        }
        .vf-decision-hero.rejected {
            border-color: #FCA5A5;
            background: linear-gradient(180deg, #FEF2F2 0%, #FFFFFF 100%);
        }

        /* Horizontal Pipeline Stepper (Overview) */
        .vf-pipeline-container {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 16px 20px;
            margin: 16px 0;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02);
            box-sizing: border-box;
        }
        .vf-pipeline-track {
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: relative;
            gap: 10px;
            flex-wrap: wrap;
        }
        .vf-pipeline-step {
            flex: 1;
            min-width: 130px;
            text-align: center;
            padding: 10px 8px;
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 6px;
            box-sizing: border-box;
        }
        .vf-pipeline-step.active {
            background: #EEF2FF;
            border-color: #C7D2FE;
        }
        .vf-step-num {
            display: inline-block;
            width: 20px;
            height: 20px;
            line-height: 20px;
            border-radius: 50%;
            background: #4F46E5;
            color: #FFFFFF;
            font-size: 0.7rem;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .vf-step-title {
            font-size: 0.8rem;
            font-weight: 600;
            color: #0F172A;
            margin-bottom: 2px;
        }
        .vf-step-desc {
            font-size: 0.68rem;
            color: #64748B;
            line-height: 1.3;
        }

        /* Surface Card */
        .vf-surface-card {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
            padding: 18px 20px;
            margin-bottom: 16px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02);
            box-sizing: border-box;
            min-width: 0;
            max-width: 100%;
        }
        .vf-section-header {
            font-size: 0.98rem;
            font-weight: 600;
            color: #0F172A;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #F1F5F9;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* Stepper Stage Row */
        .vf-stage-row {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-left: 4px solid #4F46E5;
            border-radius: 6px;
            padding: 10px 14px;
            margin-bottom: 6px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02);
            box-sizing: border-box;
            min-width: 0;
            max-width: 100%;
        }
        .vf-stage-row.completed {
            border-left-color: #16A34A;
        }
        .vf-stage-row.needs-attention {
            border-left-color: #D97706;
        }
        .vf-stage-row.failed {
            border-left-color: #DC2626;
        }
        .vf-stage-row.running {
            border-left-color: #2563EB;
            background: #F8FAFC;
        }

        /* Monospace typography */
        code, .code, .vf-mono {
            font-family: 'JetBrains Mono', SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
            font-size: 0.8rem !important;
            background: #F1F5F9;
            padding: 2px 5px;
            border-radius: 4px;
            color: #0F172A;
            border: 1px solid #E2E8F0;
            word-break: break-all;
        }

        /* Disclaimer */
        .vf-disclaimer {
            background-color: #F8FAFC;
            border: 1px dashed #CBD5E1;
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 0.78rem;
            color: #64748B;
            line-height: 1.4;
            margin-top: 14px;
            box-sizing: border-box;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(
    breadcrumb: str,
    title: str,
    subtitle: str,
    badge_text: str = "",
    badge_type: str = "PASS",
):
    """Renders a clean SaaS header with breadcrumbs and title."""
    crumb_parts = [p.strip() for p in breadcrumb.split(">")]
    crumb_html = ""
    for idx, part in enumerate(crumb_parts):
        crumb_html += f"<span>{html.escape(part)}</span>"
        if idx < len(crumb_parts) - 1:
            crumb_html += ' <span class="sep">/</span> '

    badge_markup = ""
    if badge_text:
        badge_markup = get_status_badge_html(badge_text)

    st.markdown(
        f"""
        <div class="vf-page-header">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
                <div style="flex: 1; min-width: 250px;">
                    <div class="vf-breadcrumb">{crumb_html}</div>
                    <h1 class="vf-page-title">{html.escape(title)}</h1>
                    <p class="vf-page-subtitle">{html.escape(subtitle)}</p>
                </div>
                {f'<div style="margin-top: 4px;">{badge_markup}</div>' if badge_markup else ''}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(
    title: str,
    value: Any,
    sub: str = "",
    color_hint: str = "#0F172A",
    icon_label: str = "",
):
    """Renders an enterprise KPI metric card with consistent height and overflow immunity."""
    st.markdown(
        f"""
        <div class="vf-kpi-card">
            <div class="vf-kpi-label">
                <span>{html.escape(title)}</span>
                {f'<span style="font-size: 0.75rem; color: #94A3B8;">{html.escape(icon_label)}</span>' if icon_label else ''}
            </div>
            <div class="vf-kpi-value" style="color: {color_hint};">{html.escape(str(value))}</div>
            <div class="vf-kpi-subtext" title="{html.escape(sub)}">{html.escape(sub)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Backward-compatible alias
render_metric_card = render_kpi_card


def render_pipeline_stepper():
    """Renders the 5-step horizontal high-level pipeline diagram for the Overview page."""
    steps = [
        ("1", "Submission", "Details & compliance PDFs"),
        ("2", "Extraction", "PyMuPDF text extraction"),
        ("3", "Cross-Check", "PAN & banking reconciliation"),
        ("4", "Validation", "Deduplication & screening"),
        ("5", "Decision", "Status & communication draft"),
    ]

    steps_html = ""
    for num, title, desc in steps:
        steps_html += f"""
        <div class="vf-pipeline-step active">
            <div class="vf-step-num">{num}</div>
            <div class="vf-step-title">{html.escape(title)}</div>
            <div class="vf-step-desc">{html.escape(desc)}</div>
        </div>
        """

    st.markdown(
        f"""
        <div class="vf-pipeline-container">
            <div style="font-size: 0.7rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px;">
                Automated Verification Architecture
            </div>
            <div class="vf-pipeline-track">
                {steps_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_banner(
    status: str,
    summary: str,
    duration_ms: float,
    run_id: str,
    timestamp: str = "",
):
    """Renders the executive decision hero card."""
    status_lower = status.lower()
    if status_lower == "approved":
        theme_class = "approved"
        badge_text = "AUTOMATED ONBOARDING APPROVED"
    elif status_lower == "pending":
        theme_class = "pending"
        badge_text = "MANUAL REVIEW REQUIRED (PENDING)"
    else:
        theme_class = "rejected"
        badge_text = "ONBOARDING STOPPED (REJECTED)"

    badge_html = get_status_badge_html(status)

    st.markdown(
        f"""
        <div class="vf-decision-hero {theme_class}">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
                <div style="flex: 1; min-width: 260px;">
                    <div style="margin-bottom: 6px; display: flex; align-items: center; gap: 8px;">
                        {badge_html}
                        <span style="font-size: 0.72rem; font-weight: 600; color: #64748B; text-transform: uppercase; letter-spacing: 0.04em;">
                            {html.escape(badge_text)}
                        </span>
                    </div>
                    <h2 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: #0F172A; line-height: 1.35; word-break: break-word;">
                        {html.escape(summary)}
                    </h2>
                </div>
                <div style="text-align: right; font-size: 0.78rem; color: #64748B; background: #F8FAFC; padding: 6px 12px; border-radius: 6px; border: 1px solid #E2E8F0; min-width: 180px;">
                    <div><strong>Run ID:</strong> <span class="vf-mono">{html.escape(run_id)}</span></div>
                    <div style="margin-top: 3px;"><strong>Latency:</strong> {duration_ms:.1f} ms</div>
                    {f'<div style="margin-top: 3px;"><strong>Date:</strong> {html.escape(timestamp)}</div>' if timestamp else ''}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stage_card(
    stage_number: int,
    stage_name: str,
    status: str,
    summary: str,
    details: List[str],
    duration_ms: float,
):
    """Renders an individual stage card with status badge and collapsible details."""
    status_class = status.lower().replace(" ", "-")
    badge_html = get_status_badge_html(status)

    with st.container():
        st.markdown(
            f"""
            <div class="vf-stage-row {status_class}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; flex-wrap: wrap; gap: 6px;">
                    <div style="font-weight: 600; font-size: 0.88rem; color: #0F172A;">
                        <span style="color: #64748B; margin-right: 6px; font-weight: 500;">Stage {stage_number}:</span>
                        {html.escape(stage_name)}
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 0.72rem; color: #64748B;">{duration_ms:.1f} ms</span>
                        {badge_html}
                    </div>
                </div>
                <div style="font-size: 0.82rem; color: #334155; line-height: 1.4; word-break: break-word;">
                    {html.escape(summary)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if details:
            with st.expander(f"Stage {stage_number} Execution Audit Logs ({len(details)} events)", expanded=False):
                for d in details:
                    st.markdown(f"- `{d}`" if d.startswith("✓") or d.startswith("Issue") else f"- {d}")
