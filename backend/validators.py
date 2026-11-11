"""
Stage 2: Field-level validators for VendorFlow.
Validates business and banking fields deterministically.
"""

import re
from typing import List, Tuple
from .models import ValidationIssue, VendorSubmission

# Validation Regex patterns
PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
IFSC_REGEX = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
ACCOUNT_REGEX = re.compile(r"^\d{9,18}$")

SUPPORTED_COUNTRIES = {"INDIA", "IN"}


def validate_fields(submission: VendorSubmission) -> Tuple[List[str], List[ValidationIssue]]:
    """
    Validates company information, tax identifiers, banking details, and contact info.
    Returns (passed_checks, issues).
    """
    passed: List[str] = []
    issues: List[ValidationIssue] = []

    # 1. Company Name
    comp_name = (submission.company_name or "").strip()
    if not comp_name:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="company_name",
                issue_type="ERROR",
                message="Legal company name is required.",
            )
        )
    elif len(comp_name) < 2 or len(comp_name) > 150:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="company_name",
                issue_type="ERROR",
                message="Company name must be between 2 and 150 characters.",
            )
        )
    else:
        passed.append(f"Company name valid: '{comp_name}'")

    # 2. Country / Jurisdiction
    country_norm = (submission.country or "").strip().upper()
    if not country_norm:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="country",
                issue_type="ERROR",
                message="Country is required.",
            )
        )
    elif country_norm not in SUPPORTED_COUNTRIES:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="country",
                issue_type="WARNING",
                message=f"Unsupported jurisdiction: '{submission.country}'. VendorFlow currently supports India only.",
            )
        )
    else:
        passed.append(f"Jurisdiction supported: {submission.country}")

    # 3. Business Address
    address = (submission.address or "").strip()
    if not address:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="address",
                issue_type="ERROR",
                message="Registered business address is required.",
            )
        )
    else:
        passed.append("Registered business address provided.")

    # 4. Contact Person
    contact_name = (submission.contact_name or "").strip()
    if not contact_name:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="contact_name",
                issue_type="ERROR",
                message="Primary contact person name is required.",
            )
        )
    else:
        passed.append(f"Contact person recorded: '{contact_name}'")

    # 5. Contact Email
    email = (submission.contact_email or "").strip()
    if not email:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="contact_email",
                issue_type="ERROR",
                message="Contact email is required.",
            )
        )
    elif not EMAIL_REGEX.match(email):
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="contact_email",
                issue_type="ERROR",
                message=f"Contact email format is invalid: '{email}'.",
            )
        )
    else:
        passed.append(f"Contact email format valid: '{email}'")

    # 6. PAN Validation
    pan = (submission.pan or "").strip().upper()
    if not pan:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="pan",
                issue_type="ERROR",
                message="Permanent Account Number (PAN) is required.",
            )
        )
    elif not PAN_REGEX.match(pan):
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="pan",
                issue_type="ERROR",
                message=(
                    f"PAN '{pan}' does not match standard Indian PAN format "
                    "(5 letters, 4 digits, 1 letter, e.g., ABCDE1234F)."
                ),
            )
        )
    else:
        passed.append(f"PAN format structurally valid: '{pan[:2]}****{pan[-2:]}'")

    # 7. GSTIN Validation
    gstin = (submission.gstin or "").strip().upper()
    if not gstin:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="gstin",
                issue_type="ERROR",
                message="Goods and Services Tax Identification Number (GSTIN) is required.",
            )
        )
    elif not GSTIN_REGEX.match(gstin):
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="gstin",
                issue_type="ERROR",
                message=(
                    f"GSTIN '{gstin}' does not match standard 15-character structural format "
                    "(e.g., 27ABCDE1234F1Z5)."
                ),
            )
        )
    else:
        passed.append(f"GSTIN format structurally valid: '{gstin[:3]}*******{gstin[-3:]}'")

    # 8. Bank Account Holder Name
    holder = (submission.bank_account_holder or "").strip()
    if not holder:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="bank_account_holder",
                issue_type="ERROR",
                message="Bank account holder name is required.",
            )
        )
    else:
        passed.append(f"Bank account holder specified: '{holder}'")

    # 9. Bank Account Number
    acc_num = (submission.bank_account_number or "").strip()
    if not acc_num:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="bank_account_number",
                issue_type="ERROR",
                message="Bank account number is required.",
            )
        )
    elif not ACCOUNT_REGEX.match(acc_num):
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="bank_account_number",
                issue_type="ERROR",
                message="Bank account number must be numeric and between 9 and 18 digits.",
            )
        )
    else:
        passed.append(f"Bank account number format valid: '...{acc_num[-4:]}'")

    # 10. IFSC Code Validation
    ifsc = (submission.ifsc_code or "").strip().upper()
    if not ifsc:
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="ifsc_code",
                issue_type="ERROR",
                message="Bank IFSC code is required.",
            )
        )
    elif not IFSC_REGEX.match(ifsc):
        issues.append(
            ValidationIssue(
                stage="Field Validation",
                field_name="ifsc_code",
                issue_type="ERROR",
                message=(
                    f"IFSC code '{ifsc}' is invalid. Must be 11 characters, 4 letters, "
                    "5th character '0', and 6 alphanumeric characters (e.g., HDFC0001234)."
                ),
            )
        )
    else:
        passed.append(f"Bank IFSC code format valid: '{ifsc}'")

    return passed, issues
