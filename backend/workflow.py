"""
Workflow Orchestrator for VendorFlow Phase 2.
Executes the comprehensive 13-stage document-driven verification pipeline:
1. Receiving vendor submission
2. Checking uploaded documents
3. Extracting PDF text
4. Identifying vendor information
5. Structuring extracted fields
6. Comparing PAN and GST information
7. Comparing company and bank information
8. Running existing field validations
9. Running duplicate detection
10. Running restricted-vendor checks
11. Generating final decision
12. Creating communication draft
13. Saving execution history
"""

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Callable, Dict, List, Optional
import uuid

from database.db import (
    add_approved_vendor,
    hash_identifier,
    init_db,
    save_run,
)
from .communication import generate_communication_draft
from .consistency_checks import check_consistency, normalize_business_name
from .cross_document_verifier import verify_cross_documents
from .decision_engine import make_decision
from .document_checks import check_documents
from .document_extractor import (
    extract_bank_document,
    extract_gst_document,
    extract_pan_document,
    extract_raw_text_from_pdf,
)
from .duplicate_detection import check_duplicates
from .models import (
    CrossDocumentSummary,
    DecisionStatus,
    DocumentExtractionResult,
    ExtractionStatus,
    OnboardingDecision,
    StageResult,
    StageStatus,
    ValidationIssue,
    VendorSubmission,
    WorkflowExecutionResult,
)
from .restricted_check import check_restricted_registry
from .validators import validate_fields


def execute_workflow(
    submission: VendorSubmission,
    db_path: Optional[Path] = None,
    progress_callback: Optional[Callable[[StageResult], None]] = None,
) -> WorkflowExecutionResult:
    """
    Executes the complete 13-stage document-driven verification workflow.
    Invokes optional progress_callback at each stage transition for real-time live UI updates.
    """
    init_db(db_path)
    total_start_time = time.perf_counter()

    if not submission.run_id:
        submission.run_id = f"VF-{uuid.uuid4().hex[:8].upper()}"

    stage_results: List[StageResult] = []
    all_passed_checks: List[str] = []
    all_issues: List[ValidationIssue] = []

    def notify_running(stage_num: int, name: str):
        if progress_callback:
            progress_callback(
                StageResult(
                    stage_number=stage_num,
                    stage_name=name,
                    status=StageStatus.RUNNING,
                    summary="Executing stage rules...",
                    details=[],
                    duration_ms=0.0,
                )
            )

    def report_stage(
        stage_num: int,
        name: str,
        status: StageStatus,
        summary: str,
        details: List[str],
        duration_ms: float,
    ) -> StageResult:
        res = StageResult(
            stage_number=stage_num,
            stage_name=name,
            status=status,
            summary=summary,
            details=details,
            duration_ms=round(duration_ms, 2),
        )
        stage_results.append(res)
        if progress_callback:
            progress_callback(res)
        return res

    try:
        # =============================================================
        # STAGE 1: Receiving Vendor Submission
        # =============================================================
        notify_running(1, "Receiving Vendor Submission")
        s1_start = time.perf_counter()
        submission.company_name = (submission.company_name or "").strip()
        submission.pan = (submission.pan or "").strip().upper()
        submission.gstin = (submission.gstin or "").strip().upper()
        submission.ifsc_code = (submission.ifsc_code or "").strip().upper()
        submission.bank_account_holder = (submission.bank_account_holder or "").strip()
        submission.bank_account_number = (submission.bank_account_number or "").strip()

        s1_details = [
            f"Run ID allocated: {submission.run_id}",
            f"Submission source type: {submission.run_type}",
            f"Vendor name normalized: '{submission.company_name}'",
            f"Jurisdiction registered: {submission.country}",
        ]
        all_passed_checks.append("Submission intake and payload normalization completed.")
        s1_dur = (time.perf_counter() - s1_start) * 1000
        report_stage(
            1,
            "Receiving Vendor Submission",
            StageStatus.COMPLETED,
            "Submission intake and cryptographic identifiers initialized.",
            s1_details,
            s1_dur,
        )

        # =============================================================
        # STAGE 2: Checking Uploaded Documents
        # =============================================================
        notify_running(2, "Checking Uploaded Documents")
        s2_start = time.perf_counter()
        updated_docs, d_passed, d_issues = check_documents(submission.documents)
        submission.documents = updated_docs
        all_passed_checks.extend(d_passed)
        all_issues.extend(d_issues)

        s2_status = StageStatus.NEEDS_ATTENTION if d_issues else StageStatus.COMPLETED
        s2_summary = (
            f"{len(d_issues)} compliance document issue(s) detected."
            if d_issues
            else "All mandatory compliance documents present and valid (PDF/Images < 10MB)."
        )
        s2_details = [
            f"GST Certificate: {submission.documents.get('gst_cert', None).status.value if 'gst_cert' in submission.documents else 'MISSING'}",
            f"PAN Document: {submission.documents.get('pan_proof', None).status.value if 'pan_proof' in submission.documents else 'MISSING'}",
            f"Bank Proof: {submission.documents.get('bank_proof', None).status.value if 'bank_proof' in submission.documents else 'MISSING'}",
        ]
        s2_dur = (time.perf_counter() - s2_start) * 1000
        report_stage(
            2,
            "Checking Uploaded Documents",
            s2_status,
            s2_summary,
            s2_details,
            s2_dur,
        )

        # =============================================================
        # STAGE 3: Extracting PDF Text
        # =============================================================
        notify_running(3, "Extracting PDF Text")
        s3_start = time.perf_counter()
        doc_texts: Dict[str, str] = {}
        s3_details: List[str] = []
        docs_with_bytes = 0

        for key, doc_meta in submission.documents.items():
            if doc_meta.is_present and doc_meta.raw_bytes:
                docs_with_bytes += 1
                txt = extract_raw_text_from_pdf(doc_meta.raw_bytes)
                doc_texts[key] = txt
                s3_details.append(
                    f"{doc_meta.name}: Extracted {len(txt)} chars of selectable text."
                    if txt
                    else f"{doc_meta.name}: No selectable text detected (scanned or image)."
                )
            elif doc_meta.is_present:
                s3_details.append(f"{doc_meta.name}: File metadata verified ({doc_meta.filename}).")

        s3_dur = (time.perf_counter() - s3_start) * 1000
        report_stage(
            3,
            "Extracting PDF Text",
            StageStatus.COMPLETED,
            f"Text extraction completed for {len(submission.documents)} document(s).",
            s3_details if s3_details else ["No PDF byte payloads available for text stream extraction."],
            s3_dur,
        )

        # =============================================================
        # STAGE 4: Identifying Vendor Information
        # =============================================================
        notify_running(4, "Identifying Vendor Information")
        s4_start = time.perf_counter()

        # Extract PAN
        pan_meta = submission.documents.get("pan_proof")
        pan_bytes = pan_meta.raw_bytes if pan_meta else None
        pan_fname = pan_meta.filename if pan_meta and pan_meta.filename else "pan_document.pdf"
        pan_ext_res = extract_pan_document(pan_bytes, pan_fname)

        # Extract GST
        gst_meta = submission.documents.get("gst_cert")
        gst_bytes = gst_meta.raw_bytes if gst_meta else None
        gst_fname = gst_meta.filename if gst_meta and gst_meta.filename else "gst_certificate.pdf"
        gst_ext_res = extract_gst_document(gst_bytes, gst_fname)

        # Extract Bank
        bank_meta = submission.documents.get("bank_proof")
        bank_bytes = bank_meta.raw_bytes if bank_meta else None
        bank_fname = bank_meta.filename if bank_meta and bank_meta.filename else "bank_proof.pdf"
        bank_ext_res = extract_bank_document(bank_bytes, bank_fname)

        if pan_meta:
            pan_meta.extraction_result = pan_ext_res
        if gst_meta:
            gst_meta.extraction_result = gst_ext_res
        if bank_meta:
            bank_meta.extraction_result = bank_ext_res

        s4_details = [
            f"PAN Document: {pan_ext_res.extraction_status.value} (Found: {list(pan_ext_res.extracted_fields.keys())})",
            f"GST Certificate: {gst_ext_res.extraction_status.value} (Found: {list(gst_ext_res.extracted_fields.keys())})",
            f"Bank Proof: {bank_ext_res.extraction_status.value} (Found: {list(bank_ext_res.extracted_fields.keys())})",
        ]
        s4_dur = (time.perf_counter() - s4_start) * 1000
        report_stage(
            4,
            "Identifying Vendor Information",
            StageStatus.COMPLETED,
            "Applied tax and banking regex patterns and label-based field parsing.",
            s4_details,
            s4_dur,
        )

        # =============================================================
        # STAGE 5: Structuring Extracted Fields
        # =============================================================
        notify_running(5, "Structuring Extracted Fields")
        s5_start = time.perf_counter()

        extraction_dict = {
            "pan_proof": pan_ext_res.to_dict(),
            "gst_cert": gst_ext_res.to_dict(),
            "bank_proof": bank_ext_res.to_dict(),
        }

        # Check for unreadable documents that require manual confirmation
        unreadable_issues = []
        for d_key, ext_res in [("pan_proof", pan_ext_res), ("gst_cert", gst_ext_res), ("bank_proof", bank_ext_res)]:
            d_obj = submission.documents.get(d_key)
            if d_obj and d_obj.is_present and ext_res.extraction_status == ExtractionStatus.UNREADABLE:
                if not submission.manual_confirmations.get(d_key, False):
                    unreadable_issues.append(
                        ValidationIssue(
                            stage="Document Extraction",
                            field_name="unreadable_document",
                            issue_type="WARNING",
                            message=f"{d_obj.name} contains no selectable text and requires human confirmation.",
                        )
                    )

        all_issues.extend(unreadable_issues)
        s5_status = StageStatus.NEEDS_ATTENTION if unreadable_issues else StageStatus.COMPLETED
        s5_summary = (
            f"{len(unreadable_issues)} document(s) require manual confirmation."
            if unreadable_issues
            else "All document extractions successfully converted into structured fields."
        )
        s5_details = [
            f"Extracted fields recorded with confidence ratings and source provenance.",
            f"PAN Document status: {pan_ext_res.extraction_status.value}",
            f"GST Certificate status: {gst_ext_res.extraction_status.value}",
            f"Bank Proof status: {bank_ext_res.extraction_status.value}",
        ]
        s5_dur = (time.perf_counter() - s5_start) * 1000
        report_stage(
            5,
            "Structuring Extracted Fields",
            s5_status,
            s5_summary,
            s5_details,
            s5_dur,
        )

        # =============================================================
        # STAGE 6: Comparing PAN and GST Information (Cross-Document)
        # =============================================================
        notify_running(6, "Comparing PAN and GST Information")
        s6_start = time.perf_counter()
        cross_summary, cross_issues = verify_cross_documents(
            submission, pan_ext_res, gst_ext_res, bank_ext_res
        )
        # Separate PAN vs Company issues
        pan_gst_issues = [i for i in cross_issues if "pan" in i.field_name or "gstin" in i.field_name]
        all_issues.extend(pan_gst_issues)

        s6_status = StageStatus.NEEDS_ATTENTION if pan_gst_issues else StageStatus.COMPLETED
        s6_summary = (
            f"PAN / GST discrepancy detected across records."
            if pan_gst_issues
            else "Tax identifiers (PAN & GSTIN) match consistently across documents and submission."
        )
        s6_details = [
            c.message for c in cross_summary.checks if "PAN" in c.check_name or "GSTIN" in c.check_name
        ]
        s6_dur = (time.perf_counter() - s6_start) * 1000
        report_stage(
            6,
            "Comparing PAN and GST Information",
            s6_status,
            s6_summary,
            s6_details if s6_details else ["PAN and GST cross-comparison clean."],
            s6_dur,
        )

        # =============================================================
        # STAGE 7: Comparing Company and Bank Information
        # =============================================================
        notify_running(7, "Comparing Company and Bank Information")
        s7_start = time.perf_counter()
        name_bank_issues = [i for i in cross_issues if i not in pan_gst_issues]
        all_issues.extend(name_bank_issues)

        # Also run Phase 1 consistency check to ensure legacy cross-checks are covered
        p1_c_passed, p1_c_issues = check_consistency(submission)
        # Avoid duplicate messages
        for pi in p1_c_issues:
            if not any(ei.message == pi.message for ei in all_issues):
                all_issues.append(pi)

        s7_status = StageStatus.NEEDS_ATTENTION if (name_bank_issues or p1_c_issues) else StageStatus.COMPLETED
        s7_summary = (
            "Company name or bank account holder mismatch identified."
            if (name_bank_issues or p1_c_issues)
            else "Legal entity name and bank account holder verified across all sources."
        )
        s7_details = [
            c.message for c in cross_summary.checks if "Name" in c.check_name or "Bank" in c.check_name
        ]
        s7_dur = (time.perf_counter() - s7_start) * 1000
        report_stage(
            7,
            "Comparing Company and Bank Information",
            s7_status,
            s7_summary,
            s7_details if s7_details else ["Entity name and bank details consistent."],
            s7_dur,
        )

        # =============================================================
        # STAGE 8: Running Existing Field Validations (Phase 1)
        # =============================================================
        notify_running(8, "Running Existing Field Validations")
        s8_start = time.perf_counter()
        f_passed, f_issues = validate_fields(submission)
        all_passed_checks.extend(f_passed)
        all_issues.extend(f_issues)

        s8_status = StageStatus.NEEDS_ATTENTION if f_issues else StageStatus.COMPLETED
        s8_summary = (
            f"Field validation completed with {len(f_issues)} issue(s)."
            if f_issues
            else f"All {len(f_passed)} core identity and banking fields structurally verified."
        )
        s8_details = (
            [f"Issue: {i.message}" for i in f_issues]
            if f_issues
            else [f"✓ {p}" for p in f_passed[:4]]
        )
        s8_dur = (time.perf_counter() - s8_start) * 1000
        report_stage(
            8,
            "Running Existing Field Validations",
            s8_status,
            s8_summary,
            s8_details,
            s8_dur,
        )

        # =============================================================
        # STAGE 9: Running Duplicate Detection (Phase 1)
        # =============================================================
        notify_running(9, "Running Duplicate Detection")
        s9_start = time.perf_counter()
        dup_passed, dup_issues = check_duplicates(submission, db_path)
        all_passed_checks.extend(dup_passed)
        all_issues.extend(dup_issues)

        s9_status = StageStatus.NEEDS_ATTENTION if dup_issues else StageStatus.COMPLETED
        s9_summary = (
            "Duplicate registration conflict identified."
            if dup_issues
            else "No existing approved vendor matches submitted tax identifier hashes."
        )
        s9_details = (
            [i.message for i in dup_issues]
            if dup_issues
            else ["Tax ID hashes (PAN & GSTIN) queried against approved registry. Result: Unique."]
        )
        s9_dur = (time.perf_counter() - s9_start) * 1000
        report_stage(
            9,
            "Running Duplicate Detection",
            s9_status,
            s9_summary,
            s9_details,
            s9_dur,
        )

        # =============================================================
        # STAGE 10: Running Restricted-Vendor Checks (Phase 1)
        # =============================================================
        notify_running(10, "Running Restricted-Vendor Checks")
        s10_start = time.perf_counter()
        restr_passed, restr_issues = check_restricted_registry(submission, db_path)
        all_passed_checks.extend(restr_passed)
        all_issues.extend(restr_issues)

        s10_status = StageStatus.FAILED if restr_issues else StageStatus.COMPLETED
        s10_summary = (
            "HARD STOP: Tax identifier matched internal restricted-vendor registry."
            if restr_issues
            else "Internal restricted-vendor policy check passed."
        )
        s10_details = (
            [i.message for i in restr_issues]
            if restr_issues
            else ["Screened against synthetic internal compliance watchlist. Result: Clear."]
        )
        s10_dur = (time.perf_counter() - s10_start) * 1000
        report_stage(
            10,
            "Running Restricted-Vendor Checks",
            s10_status,
            s10_summary,
            s10_details,
            s10_dur,
        )

        # =============================================================
        # STAGE 11: Generating Final Decision (Phase 1 Engine Reused)
        # =============================================================
        notify_running(11, "Generating Final Decision")
        s11_start = time.perf_counter()
        decision: OnboardingDecision = make_decision(all_passed_checks, all_issues)

        s11_details = [
            f"Outcome: {decision.status.value}",
            f"Reasoning: {decision.summary}",
            f"Checks passed: {len(decision.passed_checks)}",
            f"Issues flagged: {len(decision.issues)}",
        ]
        s11_dur = (time.perf_counter() - s11_start) * 1000
        report_stage(
            11,
            "Generating Final Decision",
            StageStatus.COMPLETED,
            f"Decision reached: {decision.status.value}",
            s11_details,
            s11_dur,
        )

        # =============================================================
        # STAGE 12: Creating Communication Draft
        # =============================================================
        notify_running(12, "Creating Communication Draft")
        s12_start = time.perf_counter()
        communication_draft = generate_communication_draft(
            submission, decision, submission.run_id
        )
        s12_dur = (time.perf_counter() - s12_start) * 1000
        report_stage(
            12,
            "Creating Communication Draft",
            StageStatus.COMPLETED,
            f"Personalized draft generated for {decision.status.value} workflow.",
            [f"Ready for procurement operations sign-off."],
            s12_dur,
        )

        # =============================================================
        # STAGE 13: Saving Execution History
        # =============================================================
        notify_running(13, "Saving Execution History")
        s13_start = time.perf_counter()
        total_duration_ms = (time.perf_counter() - total_start_time) * 1000
        redacted_input = submission.to_redacted_dict()

        # Count documents processed, discrepancies, manual confirmations
        docs_processed = sum(1 for d in submission.documents.values() if d.is_present)
        discrepancies_count = len(cross_summary.discrepancies)
        manual_conf_count = len(submission.manual_confirmations)

        run_record = {
            "run_id": submission.run_id,
            "created_at": submission.submitted_at,
            "vendor_name": submission.company_name or "Unknown Vendor",
            "status": decision.status.value,
            "processing_duration_ms": round(total_duration_ms, 2),
            "run_type": submission.run_type,
            "issues_count": len(decision.issues),
            "redacted_input": redacted_input,
            "stage_results": [
                {
                    "stage_number": s.stage_number,
                    "stage_name": s.stage_name,
                    "status": s.status.value,
                    "summary": s.summary,
                    "details": s.details,
                    "duration_ms": s.duration_ms,
                }
                for s in stage_results
            ],
            "decision": decision.to_dict(),
            "communication_draft": communication_draft,
            "extraction_results": extraction_dict,
            "cross_document_results": cross_summary.to_dict(),
            "documents_processed_count": docs_processed,
            "discrepancies_count": discrepancies_count,
            "manual_confirmations_count": manual_conf_count,
        }
        save_run(run_record, db_path)

        # If APPROVED and real Live Submission, persist to approved_vendors
        if decision.status == DecisionStatus.APPROVED and submission.run_type != "Demo Scenario":
            pan_h = hash_identifier(submission.pan)
            gstin_h = hash_identifier(submission.gstin)
            vendor_id = f"VEND-{uuid.uuid4().hex[:6].upper()}"
            add_approved_vendor(
                vendor_id,
                submission.company_name,
                pan_h,
                gstin_h,
                submission.run_id,
                db_path,
            )

        s13_details = [
            f"Audit log committed to SQLite database with Run ID '{submission.run_id}'.",
            f"Persisted Phase 2 document extraction metadata & cross-verification summary.",
            f"Total pipeline latency: {total_duration_ms:.1f} ms across 13 stages.",
        ]
        s13_dur = (time.perf_counter() - s13_start) * 1000
        report_stage(
            13,
            "Saving Execution History",
            StageStatus.COMPLETED,
            "Audit record committed to SQLite database.",
            s13_details,
            s13_dur,
        )

        return WorkflowExecutionResult(
            run_id=submission.run_id,
            vendor_name=submission.company_name,
            status=decision.status,
            total_duration_ms=round(total_duration_ms, 2),
            created_at=submission.submitted_at,
            run_type=submission.run_type,
            stage_results=stage_results,
            decision=decision,
            communication_draft=communication_draft,
            redacted_input=redacted_input,
            extraction_results=extraction_dict,
            cross_document_results=cross_summary.to_dict(),
            documents_processed_count=docs_processed,
            discrepancies_count=discrepancies_count,
            manual_confirmations_count=manual_conf_count,
        )

    except Exception as exc:
        total_dur = (time.perf_counter() - total_start_time) * 1000
        error_msg = f"Unexpected execution error: {str(exc)}"
        fail_stage = StageResult(
            stage_number=len(stage_results) + 1,
            stage_name="Workflow Execution Failure",
            status=StageStatus.FAILED,
            summary=error_msg,
            details=[f"Exception type: {type(exc).__name__}", f"Message: {str(exc)}"],
            duration_ms=0.0,
        )
        stage_results.append(fail_stage)

        try:
            fail_decision = OnboardingDecision(
                status=DecisionStatus.REJECTED,
                summary="Workflow execution encountered an unexpected system fault.",
                passed_checks=all_passed_checks,
                issues=[
                    ValidationIssue(
                        stage="Workflow Orchestrator",
                        field_name="system_error",
                        issue_type="HARD_STOP",
                        message=error_msg,
                    )
                ],
                next_steps=["Contact system administrator to inspect runtime logs."],
                human_review_required=True,
            )
            save_run(
                {
                    "run_id": submission.run_id,
                    "created_at": submission.submitted_at,
                    "vendor_name": submission.company_name or "Unknown Vendor",
                    "status": "FAILED",
                    "processing_duration_ms": round(total_dur, 2),
                    "run_type": submission.run_type,
                    "issues_count": 1,
                    "redacted_input": submission.to_redacted_dict(),
                    "stage_results": [
                        {
                            "stage_number": s.stage_number,
                            "stage_name": s.stage_name,
                            "status": s.status.value,
                            "summary": s.summary,
                            "details": s.details,
                            "duration_ms": s.duration_ms,
                        }
                        for s in stage_results
                    ],
                    "decision": fail_decision.to_dict(),
                    "communication_draft": "System error occurred during verification. Please try again.",
                    "extraction_results": {},
                    "cross_document_results": {},
                    "documents_processed_count": 0,
                    "discrepancies_count": 0,
                    "manual_confirmations_count": 0,
                },
                db_path,
            )
        except Exception:
            pass

        raise exc
