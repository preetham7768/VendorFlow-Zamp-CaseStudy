"""
Stage 5: Duplicate Detection Check for VendorFlow.
Checks whether tax identifiers (PAN / GSTIN) already exist in the approved vendors registry.
Uses SHA-256 hashes to protect sensitive tax identifiers.
"""

from pathlib import Path
from typing import List, Optional, Tuple
from database.db import check_duplicate, hash_identifier
from .models import ValidationIssue, VendorSubmission


def check_duplicates(
    submission: VendorSubmission, db_path: Optional[Path] = None
) -> Tuple[List[str], List[ValidationIssue]]:
    """
    Checks if normalized PAN or GSTIN hashes match existing approved vendors.
    Returns (passed_checks, issues).
    """
    passed: List[str] = []
    issues: List[ValidationIssue] = []

    pan_hash = hash_identifier(submission.pan)
    gstin_hash = hash_identifier(submission.gstin)

    if not pan_hash and not gstin_hash:
        # Already handled in field validators
        return passed, issues

    is_dup, matched_vendor = check_duplicate(pan_hash, gstin_hash, db_path)

    if is_dup:
        issues.append(
            ValidationIssue(
                stage="Duplicate Detection",
                field_name="duplicate_registration",
                issue_type="WARNING",
                message=(
                    f"A possible duplicate vendor registration was identified (matches existing approved vendor "
                    f"'{matched_vendor}'). Procurement review is required before this submission can proceed."
                ),
            )
        )
    else:
        passed.append("Duplicate check passed: No prior approved registration found for submitted tax identifiers.")

    return passed, issues
