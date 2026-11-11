"""
Workflow Orchestrator for VendorFlow.
Executes the 8-stage verification pipeline deterministically:
1. Intake & Text Normalization
2. Field Validation
3. Document Completeness Check
4. Cross-Field Consistency Checks
5. Duplicate Detection
6. Internal Restricted-Vendor Check
7. Final Decision Engine
8. Communication Draft & Audit Persistence
"""

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Callable, List, Optional
import uuid

from database.db import (
    add_approved_vendor,
    hash_identifier,
    init_db,
    save_run,
)
from .communication import generate_communication_draft
from .consistency_checks import check_consistency
from .decision_engine import make_decision
from .document_checks import check_documents
from .duplicate_detection import check_duplicates
from .models import (
    DecisionStatus,
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
    Executes the entire onboarding verification workflow.
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
        # -------------------------------------------------------------
        # STAGE 1: Intake & Metadata Normalization
        # -------------------------------------------------------------
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

        # -------------------------------------------------------------
        # STAGE 2: Field Validation
        # -------------------------------------------------------------
        notify_running(2, "Validating Company & Tax Details")
        s2_start = time.perf_counter()
        f_passed, f_issues = validate_fields(submission)
        all_passed_checks.extend(f_passed)
        all_issues.extend(f_issues)

        s2_status = StageStatus.NEEDS_ATTENTION if f_issues else StageStatus.COMPLETED
        s2_summary = (
            f"Field validation completed with {len(f_issues)} issue(s)."
            if f_issues
            else f"All {len(f_passed)} core identity and banking fields structurally verified."
        )
        s2_details = (
            [f"Issue: {i.message}" for i in f_issues]
            if f_issues
            else [f"✓ {p}" for p in f_passed[:4]]
        )
        s2_dur = (time.perf_counter() - s2_start) * 1000
        report_stage(
            2,
            "Validating Company & Tax Details",
            s2_status,
            s2_summary,
            s2_details,
            s2_dur,
        )

        # -------------------------------------------------------------
        # STAGE 3: Document Completeness Check
        # -------------------------------------------------------------
        notify_running(3, "Checking Uploaded Documents")
        s3_start = time.perf_counter()
        updated_docs, d_passed, d_issues = check_documents(submission.documents)
        submission.documents = updated_docs
        all_passed_checks.extend(d_passed)
        all_issues.extend(d_issues)

        s3_status = StageStatus.NEEDS_ATTENTION if d_issues else StageStatus.COMPLETED
        s3_summary = (
            f"{len(d_issues)} compliance document issue(s) detected."
            if d_issues
            else "All 3 mandatory compliance documents present and valid (PDF/Images < 10MB)."
        )
        s3_details = [
            f"GST Certificate: {submission.documents['gst_cert'].status.value} - {submission.documents['gst_cert'].detail}",
            f"PAN Document: {submission.documents['pan_proof'].status.value} - {submission.documents['pan_proof'].detail}",
            f"Bank Proof: {submission.documents['bank_proof'].status.value} - {submission.documents['bank_proof'].detail}",
        ]
        s3_dur = (time.perf_counter() - s3_start) * 1000
        report_stage(
            3,
            "Checking Uploaded Documents",
            s3_status,
            s3_summary,
            s3_details,
            s3_dur,
        )

        # -------------------------------------------------------------
        # STAGE 4: Cross-Field Consistency Checks
        # -------------------------------------------------------------
        notify_running(4, "Cross-Field Consistency Verification")
        s4_start = time.perf_counter()
        c_passed, c_issues = check_consistency(submission)
        all_passed_checks.extend(c_passed)
        all_issues.extend(c_issues)

        s4_status = StageStatus.NEEDS_ATTENTION if c_issues else StageStatus.COMPLETED
        s4_summary = (
            f"{len(c_issues)} consistency mismatch(es) detected."
            if c_issues
            else "PAN-to-GSTIN alignment and legal company-to-bank holder names verified."
        )
        s4_details = (
            [f"Mismatch: {i.message}" for i in c_issues]
            if c_issues
            else [f"✓ {p}" for p in c_passed]
        )
        s4_dur = (time.perf_counter() - s4_start) * 1000
        report_stage(
            4,
            "Cross-Field Consistency Verification",
            s4_status,
            s4_summary,
            s4_details,
            s4_dur,
        )

        # -------------------------------------------------------------
        # STAGE 5: Duplicate Detection Check
        # -------------------------------------------------------------
        notify_running(5, "Checking Duplicate Registrations")
        s5_start = time.perf_counter()
        dup_passed, dup_issues = check_duplicates(submission, db_path)
        all_passed_checks.extend(dup_passed)
        all_issues.extend(dup_issues)

        s5_status = StageStatus.NEEDS_ATTENTION if dup_issues else StageStatus.COMPLETED
        s5_summary = (
            "Duplicate registration conflict identified."
            if dup_issues
            else "No existing approved vendor matches submitted tax identifier hashes."
        )
        s5_details = (
            [i.message for i in dup_issues]
            if dup_issues
            else ["Tax ID hashes (PAN & GSTIN) queried against approved registry. Result: Unique."]
        )
        s5_dur = (time.perf_counter() - s5_start) * 1000
        report_stage(
            5,
            "Checking Duplicate Registrations",
            s5_status,
            s5_summary,
            s5_details,
            s5_dur,
        )

        # -------------------------------------------------------------
        # STAGE 6: Internal Restricted-Vendor Check
        # -------------------------------------------------------------
        notify_running(6, "Checking Internal Restricted-Vendor Records")
        s6_start = time.perf_counter()
        restr_passed, restr_issues = check_restricted_registry(submission, db_path)
        all_passed_checks.extend(restr_passed)
        all_issues.extend(restr_issues)

        s6_status = StageStatus.FAILED if restr_issues else StageStatus.COMPLETED
        s6_summary = (
            "HARD STOP: Tax identifier matched internal restricted-vendor registry."
            if restr_issues
            else "Internal restricted-vendor policy check passed."
        )
        s6_details = (
            [i.message for i in restr_issues]
            if restr_issues
            else ["Screened against synthetic internal compliance watchlist. Result: Clear."]
        )
        s6_dur = (time.perf_counter() - s6_start) * 1000
        report_stage(
            6,
            "Checking Internal Restricted-Vendor Records",
            s6_status,
            s6_summary,
            s6_details,
            s6_dur,
        )

        # -------------------------------------------------------------
        # STAGE 7: Final Decision Engine
        # -------------------------------------------------------------
        notify_running(7, "Generating Onboarding Decision")
        s7_start = time.perf_counter()
        decision: OnboardingDecision = make_decision(all_passed_checks, all_issues)

        s7_details = [
            f"Outcome: {decision.status.value}",
            f"Reasoning: {decision.summary}",
            f"Checks passed: {len(decision.passed_checks)}",
            f"Issues flagged: {len(decision.issues)}",
        ]
        s7_dur = (time.perf_counter() - s7_start) * 1000
        report_stage(
            7,
            "Generating Onboarding Decision",
            StageStatus.COMPLETED,
            f"Decision reached: {decision.status.value}",
            s7_details,
            s7_dur,
        )

        # -------------------------------------------------------------
        # STAGE 8: Communication & Audit Persistence
        # -------------------------------------------------------------
        notify_running(8, "Preparing Communication & Saving Audit History")
        s8_start = time.perf_counter()
        communication_draft = generate_communication_draft(
            submission, decision, submission.run_id
        )

        total_duration_ms = (time.perf_counter() - total_start_time) * 1000

        redacted_input = submission.to_redacted_dict()

        # Save run record to SQLite
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
        }
        save_run(run_record, db_path)

        # If APPROVED and this was a real Live Submission, persist to approved_vendors
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

        s8_details = [
            f"Audit log saved to SQLite with Run ID '{submission.run_id}'.",
            f"Communication draft generated for {decision.status.value} workflow.",
            "Sensitive identifiers masked for audit trail compliance.",
        ]
        s8_dur = (time.perf_counter() - s8_start) * 1000
        report_stage(
            8,
            "Preparing Communication & Saving Audit History",
            StageStatus.COMPLETED,
            "Audit record committed to SQLite database.",
            s8_details,
            s8_dur,
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

        # Save failed record to SQLite
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
                },
                db_path,
            )
        except Exception:
            pass

        raise exc
