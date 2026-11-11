"""
Stage 3: Document Completeness and Integrity Check for VendorFlow.
Verifies file presence, allowed extensions, and file size limits.
"""

from typing import Dict, List, Tuple
from .models import DocumentMetadata, DocumentStatus, ValidationIssue

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

REQUIRED_DOC_DEFINITIONS = {
    "gst_cert": "GST Registration Certificate",
    "pan_proof": "Company PAN Proof Document",
    "bank_proof": "Bank Proof / Cancelled Cheque",
}


def check_documents(
    documents: Dict[str, DocumentMetadata]
) -> Tuple[Dict[str, DocumentMetadata], List[str], List[ValidationIssue]]:
    """
    Evaluates mandatory compliance documents against presence, format, and size limits.
    Returns (updated_documents, passed_checks, issues).
    """
    updated_docs: Dict[str, DocumentMetadata] = {}
    passed: List[str] = []
    issues: List[ValidationIssue] = []

    for doc_key, doc_name in REQUIRED_DOC_DEFINITIONS.items():
        doc = documents.get(doc_key)

        if not doc or not doc.is_present:
            meta = DocumentMetadata(
                doc_type=doc_key,
                name=doc_name,
                is_present=False,
                status=DocumentStatus.MISSING,
                detail="Mandatory document was not uploaded.",
            )
            updated_docs[doc_key] = meta
            issues.append(
                ValidationIssue(
                    stage="Document Verification",
                    field_name=doc_key,
                    issue_type="ERROR",
                    message=f"{doc_name} is missing. Upload a PDF, PNG, or JPEG file.",
                )
            )
            continue

        # Check empty file
        if doc.size_bytes <= 0:
            meta = DocumentMetadata(
                doc_type=doc_key,
                name=doc_name,
                filename=doc.filename,
                size_bytes=doc.size_bytes,
                extension=doc.extension,
                is_present=True,
                status=DocumentStatus.MISSING,
                detail="Uploaded file is empty (0 bytes).",
            )
            updated_docs[doc_key] = meta
            issues.append(
                ValidationIssue(
                    stage="Document Verification",
                    field_name=doc_key,
                    issue_type="ERROR",
                    message=f"{doc_name} ('{doc.filename}') is empty (0 bytes).",
                )
            )
            continue

        # Check file extension
        ext = (doc.extension or "").lower()
        if not ext.startswith("."):
            ext = f".{ext}"

        if ext not in ALLOWED_EXTENSIONS:
            meta = DocumentMetadata(
                doc_type=doc_key,
                name=doc_name,
                filename=doc.filename,
                size_bytes=doc.size_bytes,
                extension=ext,
                is_present=True,
                status=DocumentStatus.INVALID_FORMAT,
                detail=f"Unsupported file format '{ext}'. Allowed formats: PDF, PNG, JPG, JPEG.",
            )
            updated_docs[doc_key] = meta
            issues.append(
                ValidationIssue(
                    stage="Document Verification",
                    field_name=doc_key,
                    issue_type="ERROR",
                    message=f"{doc_name} has invalid file type '{ext}'. Allowed: .pdf, .png, .jpg, .jpeg.",
                )
            )
            continue

        # Check file size
        if doc.size_bytes > MAX_FILE_SIZE_BYTES:
            size_mb = doc.size_bytes / (1024 * 1024)
            meta = DocumentMetadata(
                doc_type=doc_key,
                name=doc_name,
                filename=doc.filename,
                size_bytes=doc.size_bytes,
                extension=ext,
                is_present=True,
                status=DocumentStatus.INVALID_SIZE,
                detail=f"File size exceeds 10 MB limit ({size_mb:.2f} MB).",
            )
            updated_docs[doc_key] = meta
            issues.append(
                ValidationIssue(
                    stage="Document Verification",
                    field_name=doc_key,
                    issue_type="ERROR",
                    message=f"{doc_name} is too large ({size_mb:.2f} MB). Maximum size is 10 MB.",
                )
            )
            continue

        # Document passed checks
        size_kb = doc.size_bytes / 1024
        meta = DocumentMetadata(
            doc_type=doc_key,
            name=doc_name,
            filename=doc.filename,
            size_bytes=doc.size_bytes,
            extension=ext,
            is_present=True,
            status=DocumentStatus.PASS,
            detail=f"Valid format ({ext.upper()}) and size ({size_kb:.1f} KB).",
        )
        updated_docs[doc_key] = meta
        passed.append(f"{doc_name} verified: '{doc.filename}' ({ext.upper()}, {size_kb:.1f} KB)")

    return updated_docs, passed, issues
