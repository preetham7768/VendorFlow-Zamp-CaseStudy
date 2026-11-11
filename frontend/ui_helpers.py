"""
UI Styling, Badges, and Component Helpers for VendorFlow Streamlit Frontend.
"""

import html
from typing import Any, Dict, List
import streamlit as st


def get_status_badge_html(status: str) -> str:
    """Returns an enterprise-styled status badge HTML."""
    status_upper = (status or "").upper()
    if status_upper in ("APPROVED", "COMPLETED", "PASS"):
        bg = "#ECFDF5"
        text = "#065F46"
        border = "#A7F3D0"
        icon = "✓"
    elif status_upper in ("PENDING", "NEEDS ATTENTION", "WARNING"):
        bg = "#FFFBEB"
        text = "#92400E"
        border = "#FDE68A"
        icon = "⚠"
    elif status_upper in ("REJECTED", "FAILED", "HARD_STOP", "MISSING", "INVALID_FORMAT", "INVALID_SIZE"):
        bg = "#FEF2F2"
        text = "#991B1B"
        border = "#FECACA"
        icon = "✕"
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
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.025em;
        text-transform: uppercase;
    ">
        <span>{icon}</span> {html.escape(status_upper)}
    </span>
    """


def inject_custom_css():
    """Injects high-finish enterprise CSS styling for the Streamlit app."""
    st.markdown(
        """
        <style>
        /* Base typography & containers */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Top header bar */
        .vf-header {
            background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
            color: #FFFFFF;
            padding: 24px 28px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
        }
        .vf-header h1 {
            color: #FFFFFF !important;
            font-size: 1.85rem;
            font-weight: 700;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .vf-header p {
            color: #94A3B8;
            font-size: 0.95rem;
            margin: 6px 0 0 0;
        }

        /* Metric cards */
        .vf-metric-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 18px 20px;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.03);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .vf-metric-card:hover {
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.06);
        }
        .vf-metric-title {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748B;
            margin-bottom: 6px;
        }
        .vf-metric-value {
            font-size: 1.85rem;
            font-weight: 700;
            color: #0F172A;
            line-height: 1.2;
        }
        .vf-metric-sub {
            font-size: 0.78rem;
            color: #94A3B8;
            margin-top: 4px;
        }

        /* Decision Callout Banner */
        .vf-decision-card {
            padding: 24px;
            border-radius: 12px;
            margin: 20px 0;
            border-width: 1.5px;
            border-style: solid;
        }
        .vf-decision-approved {
            background-color: #F0FDF4;
            border-color: #86EFAC;
            color: #166534;
        }
        .vf-decision-pending {
            background-color: #FFFBEB;
            border-color: #FDE68A;
            color: #92400E;
        }
        .vf-decision-rejected {
            background-color: #FEF2F2;
            border-color: #FCA5A5;
            color: #991B1B;
        }

        /* Stage Stepper item */
        .vf-stage-item {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-left: 4px solid #3B82F6;
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 12px;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02);
        }
        .vf-stage-item.completed {
            border-left-color: #10B981;
        }
        .vf-stage-item.needs-attention {
            border-left-color: #F59E0B;
        }
        .vf-stage-item.failed {
            border-left-color: #EF4444;
        }

        /* Form sections */
        .vf-section-card {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 20px 24px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.02);
        }
        .vf-section-title {
            font-size: 1.05rem;
            font-weight: 600;
            color: #1E293B;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid #F1F5F9;
            padding-bottom: 8px;
        }

        /* Disclaimer pill */
        .vf-disclaimer {
            background-color: #F8FAFC;
            border: 1px dashed #CBD5E1;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 0.82rem;
            color: #475569;
            line-height: 1.4;
            margin-top: 16px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(title: str, value: Any, sub: str = "", color_hint: str = "#0F172A"):
    """Renders a structured HTML metric card."""
    st.markdown(
        f"""
        <div class="vf-metric-card">
            <div class="vf-metric-title">{html.escape(title)}</div>
            <div class="vf-metric-value" style="color: {color_hint};">{html.escape(str(value))}</div>
            {f'<div class="vf-metric-sub">{html.escape(sub)}</div>' if sub else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_banner(status: str, summary: str, duration_ms: float, run_id: str):
    """Renders the top executive decision banner."""
    status_lower = status.lower()
    if status_lower == "approved":
        theme_class = "vf-decision-approved"
        badge_color = "#15803D"
        icon = "✅"
        badge_text = "AUTOMATED ONBOARDING APPROVED"
    elif status_lower == "pending":
        theme_class = "vf-decision-pending"
        badge_color = "#B45309"
        icon = "⏳"
        badge_text = "MANUAL REVIEW REQUIRED (PENDING)"
    else:
        theme_class = "vf-decision-rejected"
        badge_color = "#B91C1C"
        icon = "🛑"
        badge_text = "ONBOARDING STOPPED (REJECTED)"

    st.markdown(
        f"""
        <div class="vf-decision-card {theme_class}">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
                <div>
                    <span style="
                        background-color: {badge_color};
                        color: #FFFFFF;
                        padding: 4px 12px;
                        border-radius: 6px;
                        font-weight: 700;
                        font-size: 0.85rem;
                        letter-spacing: 0.05em;
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                    ">
                        {icon} {badge_text}
                    </span>
                    <h2 style="margin: 12px 0 6px 0; font-size: 1.35rem; font-weight: 700; color: inherit;">
                        {html.escape(summary)}
                    </h2>
                </div>
                <div style="text-align: right; font-size: 0.85rem; opacity: 0.85;">
                    <div><strong>Run ID:</strong> <code>{html.escape(run_id)}</code></div>
                    <div><strong>Latency:</strong> {duration_ms:.1f} ms</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stage_card(stage_number: int, stage_name: str, status: str, summary: str, details: List[str], duration_ms: float):
    """Renders an individual stage card with status badge and collapsible details."""
    status_class = status.lower().replace(" ", "-")
    badge_html = get_status_badge_html(status)

    with st.container():
        st.markdown(
            f"""
            <div class="vf-stage-item {status_class}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <div style="font-weight: 600; font-size: 0.95rem; color: #1E293B;">
                        <span style="color: #64748B; margin-right: 6px;">Stage {stage_number}:</span>
                        {html.escape(stage_name)}
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 0.78rem; color: #64748B;">{duration_ms:.1f} ms</span>
                        {badge_html}
                    </div>
                </div>
                <div style="font-size: 0.88rem; color: #334155; line-height: 1.4;">
                    {html.escape(summary)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if details:
            with st.expander(f"View Stage {stage_number} Execution Audit Logs", expanded=False):
                for d in details:
                    st.markdown(f"- `{d}`" if d.startswith("✓") or d.startswith("Issue") else f"- {d}")
