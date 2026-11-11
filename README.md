# VendorFlow — Intelligent Vendor Onboarding & Verification System

**Phase 2: Document-Driven Vendor Verification & Cross-Document Intelligence**

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![PDF Engine](https://img.shields.io/badge/pdf--extraction-PyMuPDF%20%7C%20pypdf-orange.svg)](https://pymupdf.readthedocs.io/)
[![Database](https://img.shields.io/badge/database-SQLite-003B57.svg)](https://sqlite.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 1. Executive Summary & Evolution (Phase 1 $\rightarrow$ Phase 2)

**VendorFlow** is an enterprise-grade automated vendor onboarding system that converts manual procurement reviews into a structured, deterministic, and auditable verification workflow.

- **Phase 1 (Form-Driven Rules Engine):** Validated structured user inputs, enforced tax/IFSC formatting, checked compliance document presence, detected duplicate registrations via SHA-256 hashes, screened against an internal restricted risk registry, and rendered explainable decisions (**APPROVED**, **PENDING**, **REJECTED**).
- **Phase 2 (Document-Driven Intelligence Upgrade):** Introduces **Document Intelligence**. Instead of relying exclusively on manual form entries, the system extracts text directly from uploaded compliance documents (PDFs) using **PyMuPDF**, extracts key identifiers (PAN, GSTIN, IFSC, Account Number, Legal Names), displays an **Extraction Review Interface**, executes **Cross-Document Verification**, and integrates findings directly into the existing decision engine.

---

## 2. Phase 2 Architecture & 13-Stage Pipeline

VendorFlow connects PyMuPDF document extraction, regex parsing, label matching, cross-document comparison, and rule-based validation into a single 13-stage deterministic pipeline.

```
                    VENDOR SUBMISSION & COMPLIANCE UPLOADS
                                      |
                                      v
                             STREAMLIT FRONTEND
                                      |
            +-------------------------+-------------------------+
            |                                                   |
            v                                                   v
   Step 1: Upload Documents                            Step 2: Manual Entries
   (PAN Proof, GST Cert, Cheque)                       (Company, Tax & Banking)
            |                                                   |
            v                                                   |
   EXTRACTION REVIEW INTERFACE <--------------------------------+
   (Field | Extracted | Source | Confidence | Manual | Status)
            |
            v
   13-STAGE WORKFLOW ORCHESTRATOR (backend/workflow.py)
            |
            +--> Stage 1:  Receiving Vendor Submission & Cryptographic Setup
            +--> Stage 2:  Checking Uploaded Documents (Format & Size <10MB)
            +--> Stage 3:  Extracting PDF Text Streams (PyMuPDF / pypdf)
            +--> Stage 4:  Identifying Vendor Information (Regex & Label Parsing)
            +--> Stage 5:  Structuring Extracted Fields (Confidence & Provenance)
            +--> Stage 6:  Comparing PAN & GST Information (Cross-Document)
            +--> Stage 7:  Comparing Company & Bank Information (Cross-Document)
            +--> Stage 8:  Running Existing Field Validations (Phase 1 Validators)
            +--> Stage 9:  Running Duplicate Detection (SHA-256 vs. Approved Registry)
            +--> Stage 10: Running Restricted-Vendor Checks (Internal Watchlist)
            +--> Stage 11: Generating Final Decision (Strict Precedence Engine)
            +--> Stage 12: Creating Communication Draft (Dynamic Email Notice)
            +--> Stage 13: Saving Execution History (SQLite Persistent Audit Trail)
                                      |
                                      v
                       EXECUTION DASHBOARD & TELEMETRY
```

---

## 3. Document Extraction Capabilities

VendorFlow processes three primary document types using deterministic extraction methods:

### A. PAN Card / PAN Proof Document
- **Extracted Fields:** Permanent Account Number (`\b[A-Z]{5}[0-9]{4}[A-Z]\b`) and cardholder name.
- **Method:** Regular expression matching combined with label parsing (`NAME / LEGAL ENTITY`, `NAME OF CARDHOLDER`).
- **Confidence Rating:** `HIGH` for valid 10-character PAN syntax; `MEDIUM` for parsed names.

### B. GST Registration Certificate (Form GST REG-06)
- **Extracted Fields:** GSTIN (`\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b`), embedded PAN (characters 2 to 11), legal business name, and trade name.
- **Method:** 15-character GST structural regex and label matching (`LEGAL NAME OF BUSINESS`, `TRADE NAME`).
- **Confidence Rating:** `HIGH` for GSTIN and embedded PAN.

### C. Bank Proof / Cancelled Cheque
- **Extracted Fields:** Bank account holder name, account number (masked for display/storage), IFSC routing code (`\b[A-Z]{4}0[A-Z0-9]{6}\b`), and bank name.
- **Method:** IFSC regex, account number patterns (`ACCOUNT NUMBER`, `A/C NO`), and payee/holder label parsing.
- **Confidence Rating:** `HIGH` for IFSC and Account Number.

### Scanned Documents & Unreadable File Handling
- When a document contains no selectable text (scanned image or empty PDF), the extractor flags it as `UNREADABLE` and prompts the user for manual confirmation or review.
- **Zero Hallucination:** The system **never invents values** and **never approves unreadable documents automatically**.

---

## 4. Extraction Review Interface

Before or during onboarding execution, users can review the extracted data via a clean comparison table:

| Field Name | Extracted Value | Source Document | Confidence | Extraction Status | Manual Form Value | Alignment Status |
|---|---|---|---|---|---|---|
| **PAN Number** | `ABCDE1234F` | PAN Proof | HIGH | SUCCESS | `ABCDE1234F` | **MATCH** |
| **GSTIN** | `27ABCDE1234F1Z5` | GST Certificate | HIGH | SUCCESS | `27ABCDE1234F1Z5` | **MATCH** |
| **Embedded PAN** | `ABCDE1234F` | GST Certificate | HIGH | SUCCESS | `ABCDE1234F` | **MATCH** |
| **Legal Name** | Aster Labs Pvt Ltd | GST Certificate | HIGH | SUCCESS | Aster Labs Private Limited | **ALIGNED** |
| **Account Holder** | Aster Labs | Bank Proof | HIGH | SUCCESS | Aster Labs | **MATCH** |
| **Account Number** | `********9012` | Bank Proof | HIGH | SUCCESS | `********9012` | **MATCH** |
| **Bank IFSC Code** | `HDFC0001234` | Bank Proof | HIGH | SUCCESS | `HDFC0001234` | **MATCH** |

- **Field Provenance:** The system explicitly tracks whether values originated from `DOCUMENT`, `MANUAL_ENTRY`, or were `HUMAN_CONFIRMED`.
- **Conflict Highlighting:** Inconsistencies between document extractions and manual form inputs are visibly highlighted.

---

## 5. Cross-Document Consistency Matrix

The heart of Phase 2 is multi-source cross-verification:

1. **Cross-Check 1: PAN Multi-Source Consistency:**
   - Compares PAN from the PAN Proof, embedded PAN from the GST Certificate, and manually supplied PAN.
   - All available values must match. If any conflict exists $\rightarrow$ **PENDING** with an explicit discrepancy notice.
2. **Cross-Check 2: Legal Entity Name Consistency:**
   - Compares entity names across the PAN document, GST certificate, and manual entry.
   - Normalizes corporate suffixes (`PRIVATE LIMITED`, `PVT LTD`, `LIMITED`, `LLP`, `LTD`) and punctuation.
3. **Cross-Check 3: Bank Account Holder vs. Legal Name:**
   - Compares verified legal entity name against bank account holder name on the cancelled cheque.
   - Material differences result in **PENDING** for manual ownership review (preventing payment fraud).
4. **Cross-Check 4: GSTIN & Bank Routing Alignment:**
   - Confirms GSTIN and IFSC extracted from documents match manual entries.

---

## 6. Demonstration Scenarios

Accessible via the **'🚀 Demo Scenarios'** navigation tab:

### Phase 2: Document-Driven Intelligence Scenarios
- **Scenario A (All Documents Consistent):** Real synthetic PDFs for PAN, GST, and Cancelled Cheque generated dynamically in memory with consistent details $\rightarrow$ **APPROVED**.
- **Scenario B (Cross-Document PAN Mismatch):** PAN document extracts `ABCDE1234F`, but GST certificate extracts embedded PAN `ZZZZZ9999Z` $\rightarrow$ **PENDING**.
- **Scenario C (Company vs. Bank Name Mismatch):** GST certificate extracts `Brightline Systems Private Limited`, but Cancelled Cheque extracts `Shree Trading Enterprises` $\rightarrow$ **PENDING**.
- **Scenario D (Unreadable Document Fallback):** Uploaded document is an image-only scan with no text stream $\rightarrow$ **PENDING** (Manual confirmation required, zero invented data).

### Phase 1: Form-Driven Verification Scenarios (Preserved)
- **Scenario D (Phase 1):** Duplicate registration against existing approved vendor $\rightarrow$ **PENDING**.
- **Scenario E (Phase 1):** Internal compliance risk watchlist hard-stop match $\rightarrow$ **REJECTED**.

---

## 7. Technology Stack

- **Frontend:** Streamlit 1.67+ with custom enterprise CSS, status steppers, and review tables.
- **PDF Extraction Engine:** PyMuPDF (`pymupdf`) 2.0 with `pypdf` 6.20 fallback.
- **Synthetic Document Generator:** ReportLab (`reportlab`) 5.0 for in-memory PDF generation.
- **Backend Core:** Python 3 standard library (`re`, `hashlib`, `json`, `uuid`, `dataclasses`, `datetime`, `time`).
- **Database:** SQLite3 with backward-compatible column migrations and parameterized queries.
- **Analytics:** pandas.
- **Testing:** pytest (15 automated unit tests passing).

*Zero paid API keys, zero external LLM dependencies, zero cloud API costs.*

---

## 8. Local Setup & Testing

### Installation
```bash
# Clone repository
git clone https://github.com/your-username/VendorFlow-Zamp-CaseStudy.git
cd VendorFlow-Zamp-CaseStudy

# Install dependencies
pip install -r requirements.txt
```

### Run Full Test Suite (Phase 1 + Phase 2)
```bash
python -m pytest tests/ -v
```
*Output: 15 passed in < 3s*

### Launch Application
```bash
streamlit run app.py
```
*Open [http://localhost:8501](http://localhost:8501) in your browser.*

---

## 9. Honest Scope Boundaries & Engineering Disclaimers

1. **Selectable Text PDFs vs. Heavy OCR:** Uses high-performance native text stream extraction (PyMuPDF). Does not require external OCR APIs (Tesseract/Google Cloud Vision). Scanned PDFs without text streams are safely routed to manual confirmation.
2. **No External LLM Dependencies:** All extraction, regex parsing, and cross-checks run deterministically on CPU in milliseconds without external LLM API costs or token latency.
3. **Structural Validation vs. Live Government APIs:** Validates statutory structural syntax and cross-document alignment; does not query live government portals (NSDL/GSTN).
4. **Banking Routing vs. IMPS Penny-Drop:** IFSC syntax and account number length are verified; bank account ownership is not confirmed against live banking clearing networks.
5. **Human Authority:** Automated approval marks technical qualification. Final vendor activation and payment release remains under human procurement authority.

---

## 10. License
Developed as part of the Zamp AI Solutions Analyst Case Study. Distributed under the MIT License.
