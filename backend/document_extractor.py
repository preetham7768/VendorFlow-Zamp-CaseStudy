"""
Stage 3.1 & 3.2: Document Extraction Engine for VendorFlow.
Extracts text from text-based PDFs using PyMuPDF (with pypdf fallback),
applies regular expressions for structured identifiers (PAN, GSTIN, IFSC, Account Number),
and applies label-based parsing for entity and holder names.
"""

import io
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import pymupdf  # PyMuPDF
import pypdf

from .models import (
    ConfidenceLevel,
    DocumentExtractionResult,
    ExtractedField,
    ExtractionStatus,
    FieldProvenance,
)

# Core Identification Regex Patterns
PAN_REGEX = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
GSTIN_REGEX = re.compile(r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b")
IFSC_REGEX = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
ACCOUNT_REGEX = re.compile(
    r"(?:ACCOUNT\s*(?:NUMBER|NO|NUM)?|A/C\s*(?:NO)?|ACC\s*(?:NO)?)[:\s]*([0-9]{9,18})\b",
    re.IGNORECASE,
)
STANDALONE_ACCOUNT_REGEX = re.compile(r"\b([0-9]{9,18})\b")


def extract_raw_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extracts selectable text from PDF bytes.
    First attempts PyMuPDF, falling back to pypdf if necessary.
    """
    if not pdf_bytes:
        return ""

    text = ""
    # 1. PyMuPDF attempt
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
    except Exception:
        text = ""

    # 2. pypdf fallback if empty
    if not text.strip():
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        except Exception:
            pass

    return text.strip()


def extract_pan_document(
    pdf_bytes: Optional[bytes], filename: str = "pan_card.pdf"
) -> DocumentExtractionResult:
    """Extracts PAN number and cardholder name from PAN document text."""
    if not pdf_bytes:
        return DocumentExtractionResult(
            document_type="PAN_PROOF",
            filename=filename,
            extraction_status=ExtractionStatus.NOT_PROVIDED,
            warnings=["No document bytes provided for extraction."],
            requires_human_confirmation=True,
        )

    raw_text = extract_raw_text_from_pdf(pdf_bytes)

    if not raw_text:
        return DocumentExtractionResult(
            document_type="PAN_PROOF",
            filename=filename,
            extraction_status=ExtractionStatus.UNREADABLE,
            warnings=[
                "Document contains no selectable text or is a scanned image. Text extraction was unsuccessful. Manual confirmation required."
            ],
            requires_human_confirmation=True,
        )

    extracted_fields: Dict[str, str] = {}
    field_confidence: Dict[str, str] = {}
    warnings: List[str] = []

    # 1. PAN Extraction via Regex
    pan_matches = PAN_REGEX.findall(raw_text.upper())
    if pan_matches:
        extracted_fields["pan"] = pan_matches[0]
        field_confidence["pan"] = ConfidenceLevel.HIGH.value
    else:
        warnings.append("Could not identify valid 10-character PAN syntax in document text.")

    # 2. Cardholder Name via Label Matching
    name_patterns = [
        r"(?:NAME\s*/\s*LEGAL\s*ENTITY|NAME\s*OF\s*CARDHOLDER|NAME)[:\s]+([^\n\r]+)",
        r"(?:INCOME\s*TAX\s*DEPARTMENT[^\n]*\n+)([A-Z\s]{3,40})(?:\n+[A-Z0-9])",
    ]
    extracted_name = None
    for pattern in name_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Basic sanity filter
            if len(candidate) >= 3 and not candidate.startswith("GOVERNMENT"):
                extracted_name = candidate
                break

    if extracted_name:
        extracted_fields["name"] = extracted_name
        field_confidence["name"] = ConfidenceLevel.MEDIUM.value
    else:
        warnings.append("Cardholder name label not identified with high confidence.")

    # Status evaluation
    if "pan" in extracted_fields and "name" in extracted_fields:
        status = ExtractionStatus.SUCCESS
    elif "pan" in extracted_fields:
        status = ExtractionStatus.PARTIAL
    else:
        status = ExtractionStatus.UNREADABLE

    return DocumentExtractionResult(
        document_type="PAN_PROOF",
        filename=filename,
        extraction_status=status,
        extracted_fields=extracted_fields,
        field_confidence=field_confidence,
        warnings=warnings,
        raw_text_snippet=raw_text[:200],
        requires_human_confirmation=status != ExtractionStatus.SUCCESS,
    )


def extract_gst_document(
    pdf_bytes: Optional[bytes], filename: str = "gst_certificate.pdf"
) -> DocumentExtractionResult:
    """Extracts GSTIN, embedded PAN, legal name, and trade name from GST Certificate."""
    if not pdf_bytes:
        return DocumentExtractionResult(
            document_type="GST_CERT",
            filename=filename,
            extraction_status=ExtractionStatus.NOT_PROVIDED,
            warnings=["No GST document bytes provided for extraction."],
            requires_human_confirmation=True,
        )

    raw_text = extract_raw_text_from_pdf(pdf_bytes)

    if not raw_text:
        return DocumentExtractionResult(
            document_type="GST_CERT",
            filename=filename,
            extraction_status=ExtractionStatus.UNREADABLE,
            warnings=[
                "GST certificate contains no selectable text or is an image scan. Manual confirmation required."
            ],
            requires_human_confirmation=True,
        )

    extracted_fields: Dict[str, str] = {}
    field_confidence: Dict[str, str] = {}
    warnings: List[str] = []

    # 1. GSTIN Regex
    gstin_matches = GSTIN_REGEX.findall(raw_text.upper())
    if gstin_matches:
        gstin_val = gstin_matches[0]
        extracted_fields["gstin"] = gstin_val
        field_confidence["gstin"] = ConfidenceLevel.HIGH.value
        # Embedded PAN
        embedded_pan = gstin_val[2:12]
        extracted_fields["embedded_pan"] = embedded_pan
        field_confidence["embedded_pan"] = ConfidenceLevel.HIGH.value
    else:
        warnings.append("Could not identify valid 15-character GSTIN structure in document text.")

    # 2. Legal Business Name
    legal_patterns = [
        r"(?:LEGAL\s*NAME\s*(?:OF\s*BUSINESS)?|REGISTRATION\s*NAME)[:\s]+([^\n\r]+)",
    ]
    legal_name = None
    for pattern in legal_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            cand = match.group(1).strip()
            if len(cand) >= 2:
                legal_name = cand
                break

    if legal_name:
        extracted_fields["legal_name"] = legal_name
        field_confidence["legal_name"] = ConfidenceLevel.HIGH.value
    else:
        warnings.append("Legal business name label not identified with high confidence.")

    # 3. Trade Name
    trade_patterns = [
        r"(?:TRADE\s*NAME(?:\s*\(IF\s*APPLICABLE\))?)[:\s]+([^\n\r]+)",
    ]
    for pattern in trade_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            t_cand = match.group(1).strip()
            if len(t_cand) >= 2:
                extracted_fields["trade_name"] = t_cand
                field_confidence["trade_name"] = ConfidenceLevel.MEDIUM.value
                break

    if "gstin" in extracted_fields and "legal_name" in extracted_fields:
        status = ExtractionStatus.SUCCESS
    elif "gstin" in extracted_fields:
        status = ExtractionStatus.PARTIAL
    else:
        status = ExtractionStatus.UNREADABLE

    return DocumentExtractionResult(
        document_type="GST_CERT",
        filename=filename,
        extraction_status=status,
        extracted_fields=extracted_fields,
        field_confidence=field_confidence,
        warnings=warnings,
        raw_text_snippet=raw_text[:200],
        requires_human_confirmation=status != ExtractionStatus.SUCCESS,
    )


def extract_bank_document(
    pdf_bytes: Optional[bytes], filename: str = "cancelled_cheque.pdf"
) -> DocumentExtractionResult:
    """Extracts account holder, account number, IFSC code, and bank name from Bank Proof."""
    if not pdf_bytes:
        return DocumentExtractionResult(
            document_type="BANK_PROOF",
            filename=filename,
            extraction_status=ExtractionStatus.NOT_PROVIDED,
            warnings=["No bank proof document bytes provided."],
            requires_human_confirmation=True,
        )

    raw_text = extract_raw_text_from_pdf(pdf_bytes)

    if not raw_text:
        return DocumentExtractionResult(
            document_type="BANK_PROOF",
            filename=filename,
            extraction_status=ExtractionStatus.UNREADABLE,
            warnings=[
                "Bank proof document contains no selectable text or is an unreadable scan. Manual confirmation required."
            ],
            requires_human_confirmation=True,
        )

    extracted_fields: Dict[str, str] = {}
    field_confidence: Dict[str, str] = {}
    warnings: List[str] = []

    # 1. IFSC Regex
    ifsc_matches = IFSC_REGEX.findall(raw_text.upper())
    if ifsc_matches:
        extracted_fields["ifsc"] = ifsc_matches[0]
        field_confidence["ifsc"] = ConfidenceLevel.HIGH.value
    else:
        warnings.append("Could not identify valid 11-character bank IFSC code.")

    # 2. Account Number
    acc_match = ACCOUNT_REGEX.search(raw_text)
    if acc_match:
        extracted_fields["account_number"] = acc_match.group(1).strip()
        field_confidence["account_number"] = ConfidenceLevel.HIGH.value
    else:
        # Fallback to standalone numeric strings of length 9-18 that don't match IFSC/PAN
        standalone = STANDALONE_ACCOUNT_REGEX.findall(raw_text)
        candidates = [s for s in standalone if 9 <= len(s) <= 18 and not s.startswith("27") and not s.startswith("29")]
        if candidates:
            extracted_fields["account_number"] = candidates[0]
            field_confidence["account_number"] = ConfidenceLevel.MEDIUM.value
        else:
            warnings.append("Bank account number not found.")

    # 3. Account Holder Name
    holder_patterns = [
        r"(?:ACCOUNT\s*HOLDER(?:\s*NAME)?|PAYEE(?:\s*NAME)?)[:\s]+([^\n\r]+)",
        r"(?:NAME)[:\s]+([^\n\r]+)",
    ]
    holder_name = None
    for pattern in holder_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            h_cand = match.group(1).strip()
            if len(h_cand) >= 2 and not h_cand.startswith("CANCELLED"):
                holder_name = h_cand
                break

    if holder_name:
        extracted_fields["account_holder"] = holder_name
        field_confidence["account_holder"] = ConfidenceLevel.HIGH.value
    else:
        warnings.append("Bank account holder name label not identified.")

    # 4. Bank Name
    bank_patterns = [
        r"\b(HDFC\s*BANK(?:\s*LTD)?|ICICI\s*BANK(?:\s*LTD)?|STATE\s*BANK\s*OF\s*INDIA|AXIS\s*BANK(?:\s*LTD)?|KOTAK\s*(?:MAHINDRA)?\s*BANK)\b",
    ]
    for pattern in bank_patterns:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            extracted_fields["bank_name"] = match.group(1).strip()
            field_confidence["bank_name"] = ConfidenceLevel.MEDIUM.value
            break

    if "ifsc" in extracted_fields and "account_number" in extracted_fields:
        status = ExtractionStatus.SUCCESS
    elif "ifsc" in extracted_fields or "account_number" in extracted_fields:
        status = ExtractionStatus.PARTIAL
    else:
        status = ExtractionStatus.UNREADABLE

    return DocumentExtractionResult(
        document_type="BANK_PROOF",
        filename=filename,
        extraction_status=status,
        extracted_fields=extracted_fields,
        field_confidence=field_confidence,
        warnings=warnings,
        raw_text_snippet=raw_text[:200],
        requires_human_confirmation=status != ExtractionStatus.SUCCESS,
    )
