"""
Stage 6: Internal Restricted-Vendor Check for VendorFlow.
Screens tax identifiers against a synthetic internal restricted-vendor registry.
Demonstrates internal risk policy / hard-stop conditions.
"""

from pathlib import Path
from typing import List, Optional, Tuple
from database.db import check_restricted, hash_identifier
from .models import ValidationIssue, VendorSubmission


def check_restricted_registry(
    submission: VendorSubmission, db_path: Optional[Path] = None
) -> Tuple[List[str], List[ValidationIssue]]:
    """
    Checks if normalized PAN or GSTIN hashes match any synthetic internal restricted registry entry.
    Returns (passed_checks, issues).
    """
    passed: List[str] = []
    issues: List[ValidationIssue] = []

    pan_hash = hash_identifier(submission.pan)
    gstin_hash = hash_identifier(submission.gstin)

    if not pan_hash and not gstin_hash:
        return passed, issues

    is_restricted, reason = check_restricted(pan_hash, gstin_hash, db_path)

    if is_restricted:
        issues.append(
            ValidationIssue(
                stage="Internal Restricted Check",
                field_name="restricted_registry_match",
                issue_type="HARD_STOP",
                message=(
                    f"HARD STOP: The submitted tax identifier matches an entry in the prototype's "
                    f"internal restricted-vendor registry ({reason}). Automatic onboarding has been halted. "
                    "Manual procurement and compliance review is required."
                ),
            )
        )
    else:
        passed.append("Internal restricted screening passed: No match found in prototype restricted registry.")

    return passed, issues
