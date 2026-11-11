"""
Stage 6 & 7: Cross-Document Consistency Engine for VendorFlow Phase 2.
Compares extracted fields across documents and validates them against manually submitted form values.
"""

from typing import Any, Dict, List, Optional, Tuple

from .consistency_checks import normalize_business_name
from .models import (
    CrossDocumentCheckResult,
    CrossDocumentSummary,
    DocumentExtractionResult,
    ValidationIssue,
    VendorSubmission,
)


def verify_cross_documents(
    submission: VendorSubmission,
    pan_doc_result: Optional[DocumentExtractionResult],
    gst_doc_result: Optional[DocumentExtractionResult],
    bank_doc_result: Optional[DocumentExtractionResult],
) -> Tuple[CrossDocumentSummary, List[ValidationIssue]]:
    """
    Performs comprehensive cross-document and document-to-form consistency checks.
    Returns (CrossDocumentSummary, List[ValidationIssue]).
    """
    checks: List[CrossDocumentCheckResult] = []
    issues: List[ValidationIssue] = []
    discrepancies: List[str] = []

    # -------------------------------------------------------------
    # CHECK 1: PAN Consistency Across All Available Sources
    # -------------------------------------------------------------
    pan_from_doc = (
        pan_doc_result.extracted_fields.get("pan")
        if pan_doc_result and pan_doc_result.extracted_fields
        else None
    )
    pan_from_gst = (
        gst_doc_result.extracted_fields.get("embedded_pan")
        if gst_doc_result and gst_doc_result.extracted_fields
        else None
    )
    pan_manual = (submission.pan or "").strip().upper() or None

    pan_sources = {}
    if pan_from_doc:
        pan_sources["PAN Document"] = pan_from_doc
    if pan_from_gst:
        pan_sources["GST Certificate (Embedded)"] = pan_from_gst
    if pan_manual:
        pan_sources["Manual Submission Form"] = pan_manual

    unique_pans = set(pan_sources.values())
    pan_consistent = True

    if len(unique_pans) > 1:
        pan_consistent = False
        msg = (
            f"PAN mismatch identified across sources: "
            + ", ".join([f"{k}='{v[:2]}****{v[-2:]}'" for k, v in pan_sources.items()])
            + ". Manual review or corrected documentation is required."
        )
        discrepancies.append(msg)
        issues.append(
            ValidationIssue(
                stage="Cross-Document Verification",
                field_name="pan_inconsistency",
                issue_type="ERROR",
                message=msg,
            )
        )
        checks.append(
            CrossDocumentCheckResult(
                check_name="PAN Cross-Source Consistency",
                status="MISMATCH",
                message=msg,
                fields_compared=pan_sources,
            )
        )
    elif len(unique_pans) == 1:
        matched_val = list(unique_pans)[0]
        masked = f"{matched_val[:2]}****{matched_val[-2:]}" if len(matched_val) == 10 else "****"
        checks.append(
            CrossDocumentCheckResult(
                check_name="PAN Cross-Source Consistency",
                status="PASS",
                message=f"Consistent PAN '{masked}' verified across all available sources ({', '.join(pan_sources.keys())}).",
                fields_compared=pan_sources,
            )
        )
    else:
        checks.append(
            CrossDocumentCheckResult(
                check_name="PAN Cross-Source Consistency",
                status="WARNING",
                message="No PAN was extractable or supplied for cross-document comparison.",
                fields_compared={},
            )
        )

    # -------------------------------------------------------------
    # CHECK 2: Company Name Consistency Across Sources
    # -------------------------------------------------------------
    name_from_pan = (
        pan_doc_result.extracted_fields.get("name")
        if pan_doc_result and pan_doc_result.extracted_fields
        else None
    )
    name_from_gst = (
        gst_doc_result.extracted_fields.get("legal_name")
        if gst_doc_result and gst_doc_result.extracted_fields
        else None
    )
    name_manual = (submission.company_name or "").strip() or None
    holder_from_bank = (
        bank_doc_result.extracted_fields.get("account_holder")
        if bank_doc_result and bank_doc_result.extracted_fields
        else None
    )
    holder_manual = (submission.bank_account_holder or "").strip() or None

    name_sources = {}
    if name_from_pan:
        name_sources["PAN Document"] = name_from_pan
    if name_from_gst:
        name_sources["GST Certificate"] = name_from_gst
    if name_manual:
        name_sources["Manual Company Name"] = name_manual

    # Normalized comparison between legal entity name sources
    normalized_names = {k: normalize_business_name(v) for k, v in name_sources.items() if v}
    unique_norm_names = set(normalized_names.values())
    name_consistent = True

    if len(unique_norm_names) > 1:
        name_consistent = False
        msg = (
            "Discrepancy identified between legal company name sources: "
            + ", ".join([f"{k}='{v}'" for k, v in name_sources.items()])
            + ". Requires manual confirmation."
        )
        discrepancies.append(msg)
        issues.append(
            ValidationIssue(
                stage="Cross-Document Verification",
                field_name="company_name_inconsistency",
                issue_type="WARNING",
                message=msg,
            )
        )
        checks.append(
            CrossDocumentCheckResult(
                check_name="Legal Entity Name Cross-Source Consistency",
                status="MISMATCH",
                message=msg,
                fields_compared=name_sources,
            )
        )
    elif len(unique_norm_names) == 1:
        checks.append(
            CrossDocumentCheckResult(
                check_name="Legal Entity Name Cross-Source Consistency",
                status="PASS",
                message=f"Legal entity name aligned across {len(name_sources)} sources ({', '.join(name_sources.keys())}).",
                fields_compared=name_sources,
            )
        )

    # Compare Legal Name with Bank Account Holder Name (Extracted or Manual)
    bank_holder_val = holder_from_bank or holder_manual
    primary_legal_name = name_from_gst or name_from_pan or name_manual

    if primary_legal_name and bank_holder_val:
        norm_legal = normalize_business_name(primary_legal_name)
        norm_holder = normalize_business_name(bank_holder_val)

        if norm_legal != norm_holder:
            holder_msg = (
                f"Bank account holder name '{bank_holder_val}' does not align with legal entity name "
                f"'{primary_legal_name}'. Manual verification of account ownership is required."
            )
            discrepancies.append(holder_msg)
            issues.append(
                ValidationIssue(
                    stage="Cross-Document Verification",
                    field_name="bank_holder_mismatch",
                    issue_type="WARNING",
                    message=holder_msg,
                )
            )
            checks.append(
                CrossDocumentCheckResult(
                    check_name="Bank Account Holder vs. Legal Name",
                    status="MISMATCH",
                    message=holder_msg,
                    fields_compared={
                        "Legal Entity": primary_legal_name,
                        "Bank Account Holder": bank_holder_val,
                    },
                )
            )
        else:
            checks.append(
                CrossDocumentCheckResult(
                    check_name="Bank Account Holder vs. Legal Name",
                    status="PASS",
                    message=f"Bank account holder '{bank_holder_val}' matches legal entity '{primary_legal_name}'.",
                    fields_compared={
                        "Legal Entity": primary_legal_name,
                        "Bank Account Holder": bank_holder_val,
                    },
                )
            )

    # -------------------------------------------------------------
    # CHECK 3: GSTIN Validation and Embedded Consistency
    # -------------------------------------------------------------
    gstin_from_doc = (
        gst_doc_result.extracted_fields.get("gstin")
        if gst_doc_result and gst_doc_result.extracted_fields
        else None
    )
    gstin_manual = (submission.gstin or "").strip().upper() or None

    if gstin_from_doc and gstin_manual:
        if gstin_from_doc == gstin_manual:
            checks.append(
                CrossDocumentCheckResult(
                    check_name="GSTIN Document vs. Manual Alignment",
                    status="PASS",
                    message=f"Extracted GSTIN '{gstin_from_doc[:3]}*******{gstin_from_doc[-3:]}' matches manual submission.",
                    fields_compared={"Extracted": gstin_from_doc, "Manual": gstin_manual},
                )
            )
        else:
            gst_msg = (
                f"GSTIN mismatch: Extracted GSTIN '{gstin_from_doc}' differs from manual entry '{gstin_manual}'."
            )
            discrepancies.append(gst_msg)
            issues.append(
                ValidationIssue(
                    stage="Cross-Document Verification",
                    field_name="gstin_discrepancy",
                    issue_type="ERROR",
                    message=gst_msg,
                )
            )
            checks.append(
                CrossDocumentCheckResult(
                    check_name="GSTIN Document vs. Manual Alignment",
                    status="MISMATCH",
                    message=gst_msg,
                    fields_compared={"Extracted": gstin_from_doc, "Manual": gstin_manual},
                )
            )

    # -------------------------------------------------------------
    # CHECK 4: Bank Account & IFSC Document vs. Manual Alignment
    # -------------------------------------------------------------
    ifsc_from_doc = (
        bank_doc_result.extracted_fields.get("ifsc")
        if bank_doc_result and bank_doc_result.extracted_fields
        else None
    )
    ifsc_manual = (submission.ifsc_code or "").strip().upper() or None

    if ifsc_from_doc and ifsc_manual:
        if ifsc_from_doc == ifsc_manual:
            checks.append(
                CrossDocumentCheckResult(
                    check_name="Bank IFSC Routing Consistency",
                    status="PASS",
                    message=f"Extracted IFSC '{ifsc_from_doc}' matches manual entry.",
                    fields_compared={"Extracted": ifsc_from_doc, "Manual": ifsc_manual},
                )
            )
        else:
            ifsc_msg = f"IFSC code mismatch: Extracted '{ifsc_from_doc}' differs from manual entry '{ifsc_manual}'."
            discrepancies.append(ifsc_msg)
            issues.append(
                ValidationIssue(
                    stage="Cross-Document Verification",
                    field_name="ifsc_discrepancy",
                    issue_type="WARNING",
                    message=ifsc_msg,
                )
            )
            checks.append(
                CrossDocumentCheckResult(
                    check_name="Bank IFSC Routing Consistency",
                    status="MISMATCH",
                    message=ifsc_msg,
                    fields_compared={"Extracted": ifsc_from_doc, "Manual": ifsc_manual},
                )
            )

    is_all_clean = len(discrepancies) == 0

    return CrossDocumentSummary(
        is_all_consistent=is_all_clean,
        pan_consistent=pan_consistent,
        name_consistent=name_consistent,
        discrepancies=discrepancies,
        checks=checks,
    ), issues
