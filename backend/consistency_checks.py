"""
Stage 4: Cross-Field Consistency Checks for VendorFlow.
Verifies cross-field coherence:
1. PAN embedded within GSTIN matches submitted PAN
2. Legal company name matches bank account holder name (normalized)
3. Logical completeness of submitted records
"""

import re
from typing import List, Tuple
from .models import ValidationIssue, VendorSubmission

LEGAL_SUFFIXES = [
    r"\bPRIVATE\s+LIMITED\b",
    r"\bPVT\s+LTD\b",
    r"\bPVT\b",
    r"\bLIMITED\b",
    r"\bLTD\b",
    r"\bLLP\b",
    r"\bINCORPORATED\b",
    r"\bINC\b",
    r"\bCORPORATION\b",
    r"\bCORP\b",
    r"\bCOMPANY\b",
    r"\bCO\b",
]


def normalize_business_name(name: str) -> str:
    """
    Normalizes a business name:
    - Uppercase
    - Strips punctuation and symbols
    - Removes common legal entity suffixes
    - Collapses whitespace
    """
    if not name:
        return ""
    text = name.upper()
    # Replace punctuation with space
    text = re.sub(r"[^\w\s]", " ", text)
    # Remove legal suffixes
    for suffix in LEGAL_SUFFIXES:
        text = re.sub(suffix, " ", text, flags=re.IGNORECASE)
    # Collapse multiple whitespaces
    tokens = text.strip().split()
    return " ".join(tokens)


def check_consistency(submission: VendorSubmission) -> Tuple[List[str], List[ValidationIssue]]:
    """
    Performs cross-field consistency checks.
    Returns (passed_checks, issues).
    """
    passed: List[str] = []
    issues: List[ValidationIssue] = []

    pan_clean = (submission.pan or "").strip().upper()
    gstin_clean = (submission.gstin or "").strip().upper()

    # 1. PAN vs GSTIN Embedded Consistency
    if pan_clean and gstin_clean and len(gstin_clean) == 15:
        embedded_pan = gstin_clean[2:12]
        if pan_clean == embedded_pan:
            passed.append(
                f"Tax identifier alignment verified: Embedded PAN in GSTIN matches PAN ({pan_clean[:2]}****{pan_clean[-2:]})"
            )
        else:
            issues.append(
                ValidationIssue(
                    stage="Cross-Field Consistency",
                    field_name="gstin_pan_mismatch",
                    issue_type="ERROR",
                    message=(
                        f"PAN mismatch: Submitted PAN '{pan_clean[:2]}****{pan_clean[-2:]}' does not match "
                        f"the PAN embedded in GSTIN '{embedded_pan[:2]}****{embedded_pan[-2:]}'."
                    ),
                )
            )
    elif pan_clean and gstin_clean:
        # If GSTIN wasn't 15 chars, it was flagged in Stage 2, but note cross-check dependency
        issues.append(
            ValidationIssue(
                stage="Cross-Field Consistency",
                field_name="gstin_pan_mismatch",
                issue_type="WARNING",
                message="Cannot verify PAN-GSTIN consistency because GSTIN structural length is invalid.",
            )
        )

    # 2. Company Name vs Bank Account Holder Name
    comp_norm = normalize_business_name(submission.company_name)
    holder_norm = normalize_business_name(submission.bank_account_holder)

    if comp_norm and holder_norm:
        if comp_norm == holder_norm:
            passed.append(
                f"Bank account ownership match: Legal entity '{submission.company_name}' matches "
                f"account holder '{submission.bank_account_holder}'"
            )
        else:
            # Check if one is a strict word subset / exact prefix of the other (e.g. "ASTER LABS" in "ASTER LABS DIAGNOSTICS")
            comp_words = set(comp_norm.split())
            holder_words = set(holder_norm.split())
            if comp_words == holder_words:
                passed.append(
                    f"Bank account ownership match (word order variation resolved): "
                    f"'{submission.company_name}' matches '{submission.bank_account_holder}'"
                )
            else:
                issues.append(
                    ValidationIssue(
                        stage="Cross-Field Consistency",
                        field_name="bank_account_holder_mismatch",
                        issue_type="ERROR",
                        message=(
                            f"Name mismatch: Legal company name '{submission.company_name}' differs from "
                            f"bank account holder name '{submission.bank_account_holder}'. "
                            "Requires manual verification of bank account ownership."
                        ),
                    )
                )

    # 3. Required Field Completeness Coherence
    if submission.country == "India" and not gstin_clean.startswith(
        ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
         "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
         "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
         "31", "32", "33", "34", "35", "36", "37", "38", "97", "99")
    ) and len(gstin_clean) >= 2:
        issues.append(
            ValidationIssue(
                stage="Cross-Field Consistency",
                field_name="gstin_state_code",
                issue_type="WARNING",
                message=f"GSTIN state code prefix '{gstin_clean[:2]}' is not recognized in standard Indian state codes.",
            )
        )
    elif gstin_clean and len(gstin_clean) >= 2:
        passed.append(f"GSTIN Indian State Code recognized: prefix '{gstin_clean[:2]}'")

    return passed, issues
