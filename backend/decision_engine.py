"""
Stage 7: Final Decision Engine for VendorFlow.
Synthesizes all validation, document, consistency, duplicate, and restricted screening results
using deterministic precedence rules:
1. Restricted registry match -> REJECTED (Hard Stop)
2. Incomplete, invalid, duplicate, or mismatched items -> PENDING (Action Required)
3. All checks clean -> APPROVED (Automated Approval)
"""

from typing import List
from .models import DecisionStatus, OnboardingDecision, ValidationIssue


def make_decision(
    passed_checks: List[str],
    all_issues: List[ValidationIssue]
) -> OnboardingDecision:
    """
    Applies deterministic business rules to generate an explainable onboarding decision.
    """
    # 1. Check for HARD_STOP (Restricted Vendor Match)
    hard_stop_issues = [i for i in all_issues if i.issue_type == "HARD_STOP"]
    if hard_stop_issues:
        summary = (
            "The submission matched the prototype's internal restricted-vendor registry. "
            "Automatic onboarding has been stopped."
        )
        next_steps = [
            "Halt automated onboarding process immediately.",
            "Escalate to Senior Procurement Officer and Compliance Legal Counsel.",
            "Conduct manual review of entity registration and beneficial ownership.",
            "Issue formal notification to vendor via designated compliance inquiry channel.",
        ]
        return OnboardingDecision(
            status=DecisionStatus.REJECTED,
            summary=summary,
            passed_checks=passed_checks,
            issues=all_issues,
            next_steps=next_steps,
            human_review_required=True,
            disclaimer=(
                "REJECTED indicates that a hard-stop compliance policy rule was triggered in the prototype's "
                "internal restricted registry. Real-world legal determinations remain subject to human review."
            ),
        )

    # 2. Check for PENDING conditions (Errors or Warnings)
    actionable_issues = [i for i in all_issues if i.issue_type in ("ERROR", "WARNING")]
    if actionable_issues:
        summary = (
            "The submission requires further attention. One or more required checks did not pass. "
            "The identified items need correction or manual verification."
        )
        next_steps = []

        # Construct specific next steps based on issue fields
        field_set = {i.field_name for i in actionable_issues}
        if "country" in field_set:
            next_steps.append("Review cross-border registration details manually with international tax counsel.")
        if any("proof" in f or "cert" in f for f in field_set):
            next_steps.append("Request vendor to upload missing or valid compliance documents.")
        if "bank_account_holder_mismatch" in field_set:
            next_steps.append("Request bank passbook, bank confirmation letter, or authorization certificate confirming entity ownership.")
        if "gstin_pan_mismatch" in field_set:
            next_steps.append("Request vendor to resubmit matching PAN and GSTIN certificates.")
        if "duplicate_registration" in field_set:
            next_steps.append("Check existing vendor database records to merge or reconcile duplicate vendor account.")
        if any(f in ("pan", "gstin", "ifsc_code", "bank_account_number", "contact_email") for f in field_set):
            next_steps.append("Vendor must rectify formatting errors in submitted tax or banking identifiers.")

        if not next_steps:
            next_steps.append("Vendor must provide corrected registration data.")

        return OnboardingDecision(
            status=DecisionStatus.PENDING,
            summary=summary,
            passed_checks=passed_checks,
            issues=all_issues,
            next_steps=next_steps,
            human_review_required=True,
            disclaimer=(
                "PENDING indicates automated onboarding is held awaiting resolution of missing or conflicting information. "
                "Human procurement intervention is required to proceed."
            ),
        )

    # 3. Clean pass -> APPROVED
    summary = (
        "All configured automated onboarding checks passed. Mandatory documents were supplied, "
        "tax identifiers passed structural validation, cross-field consistency checks passed, "
        "and no duplicate or restricted-registry match was detected."
    )
    next_steps = [
        "Procurement officer to perform final operational sign-off.",
        "Activate vendor record in ERP/Financial accounts payable system.",
        "Dispatch automated onboarding completion welcome email with vendor portal credentials.",
    ]

    return OnboardingDecision(
        status=DecisionStatus.APPROVED,
        summary=summary,
        passed_checks=passed_checks,
        issues=[],
        next_steps=next_steps,
        human_review_required=False,
        disclaimer=(
            "APPROVED indicates the submission passed all configured automated validation checks in this prototype. "
            "It does not certify real-world government certificate authenticity or banking network verification. "
            "An authorized human procurement reviewer retains final authority for operational vendor activation."
        ),
    )
