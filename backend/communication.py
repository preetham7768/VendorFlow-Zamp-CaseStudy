"""
Stage 8: Communication Draft Generator for VendorFlow.
Generates clear, dynamic, personalized email drafts based on execution decisions and identified issues.
"""

from typing import List
from .models import DecisionStatus, OnboardingDecision, ValidationIssue, VendorSubmission


def generate_communication_draft(
    submission: VendorSubmission,
    decision: OnboardingDecision,
    run_id: str
) -> str:
    """
    Generates a personalized communication draft for the vendor based on the decision outcome.
    Never sends an actual email.
    """
    contact_name = submission.contact_name.strip() if submission.contact_name else "Vendor Partner"
    company_name = submission.company_name.strip() if submission.company_name else "your organization"

    if decision.status == DecisionStatus.APPROVED:
        return f"""Subject: Vendor Onboarding Verification Successful — {company_name} (Ref: {run_id[:8]})

Dear {contact_name},

Thank you for submitting your vendor registration for {company_name}.

We are pleased to inform you that your submission has successfully passed all automated compliance, banking, and tax validation checks.

Your onboarding profile is now forwarded to the Procurement Operations team for final administrative activation in our financial systems. You will receive an operational confirmation once payment routing is active.

Application Reference: {run_id}
Submitted On: {submission.submitted_at}

Sincerely,
Procurement & Accounts Payable Operations
VendorFlow Automated Verification Desk"""

    elif decision.status == DecisionStatus.PENDING:
        # Build specific issue bullet points
        issue_bullets: List[str] = []
        for issue in decision.issues:
            issue_bullets.append(f"• [{issue.stage}] {issue.message}")

        if not issue_bullets:
            issue_bullets.append("• Verification discrepancies identified requiring manual document resubmission.")

        issues_formatted = "\n".join(issue_bullets)

        return f"""Subject: Action Required: Additional Information Needed for Vendor Onboarding — {company_name} (Ref: {run_id[:8]})

Dear {contact_name},

Thank you for submitting your vendor registration for {company_name}.

We have conducted an automated verification of your submission. Before your onboarding can proceed, the following items require your attention and correction:

{issues_formatted}

Next Steps:
Please log in to the secure VendorFlow onboarding portal and upload the requested documents or provide corrected business details.

Your application will remain in PENDING status until these verification items are resolved.

If you have questions regarding these requirements, please reply directly to this notice or contact procurement-support@example.com referencing Application ID {run_id}.

Sincerely,
Vendor Onboarding Team
Corporate Procurement Division"""

    else:  # REJECTED
        return f"""Subject: Update Regarding Vendor Onboarding Application — {company_name} (Ref: {run_id[:8]})

Dear {contact_name},

Thank you for your interest in registering as an approved vendor for {company_name}.

Following our automated compliance and regulatory screening, we regret to inform you that your registration could not be automatically approved and has been stopped in accordance with our internal procurement compliance policy.

Reason:
• The application matched an internal risk policy criterion or restricted vendor registry rule requiring formal administrative review.

If you believe this record was flagged in error, or if your organization has completed recent corporate restructuring, you may request a formal manual compliance review by contacting compliance-inquiries@example.com referencing Application ID {run_id}.

Thank you for your patience and cooperation.

Sincerely,
Global Compliance & Risk Management
Procurement Oversight Office"""
