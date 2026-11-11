# VendorFlow — Intelligent Vendor Onboarding & Verification System

**Automated Compliance, Tax & Banking Verification Engine for Enterprise Procurement**

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![Database](https://img.shields.io/badge/database-SQLite-003B57.svg)](https://sqlite.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 1. Executive Summary & Business Problem

Companies must rigorously verify prospective vendors before entering them into enterprise procurement systems and releasing disbursements. In traditional operations, procurement teams manually inspect submissions across disconnected documents, cross-reference registration numbers, chase missing paperwork, and resolve identity discrepancies.

### Core Operational Bottlenecks
- **Incomplete Submissions & Missing Documents:** Onboarding halts when mandatory tax certificates or bank proofs are omitted or illegible.
- **Structural Inconsistencies:** Typographical and formatting errors in tax identifiers (PAN, GSTIN) and bank routing codes (IFSC).
- **Entity Identity Mismatches:** Differences between the legal business name and bank account holder name creating payment fraud risks.
- **Duplicate Vendor Registrations:** Multiple departments unknowingly submitting the same vendor.
- **Internal Compliance Hard-Stops:** Vendors matching internal risk watchlists being approved due to oversight.
- **Manual Back-and-Forth & Poor Auditability:** Procurement agents manually authoring follow-up emails with no standardized audit trail.

### The Solution: VendorFlow
**VendorFlow** automates the end-to-end intake, validation, cross-field consistency checking, duplicate screening, and decisioning workflow. It processes structured inputs and uploaded compliance documents, executes an 8-stage verification pipeline, and delivers an explainable onboarding decision:

- **APPROVED:** All automated checks cleanly passed; ready for final human sign-off.
- **PENDING:** Specific discrepancies or missing documents identified; dynamic action-oriented communication draft generated for the vendor.
- **REJECTED:** Internal restricted registry policy match triggered; automated onboarding stopped with administrative review escalation.

---

## 2. Architecture & Pipeline Stages

VendorFlow follows a clean modular architecture separating the Streamlit interface, deterministic validation rules, decision engine, and SQLite persistence layer.

```
                    VENDOR SUBMISSION
                            |
                            v
                   STREAMLIT FRONTEND
                            |
                            v
              WORKFLOW ORCHESTRATOR (backend/workflow.py)
                            |
   +------------------------+------------------------+
   |                                                 |
   v                                                 v
Stage 1: Intake & Normalization             Stage 2: Field Validation
(UUID, Masking, Timestamp)                  (Company, PAN, GSTIN, IFSC)
   |                                                 |
   +------------------------+------------------------+
                            |
                            v
             Stage 3: Document Completeness Check
             (GST Cert, PAN Proof, Bank Proof < 10MB)
                            |
                            v
             Stage 4: Cross-Field Consistency Checks
             (PAN in GSTIN match, Legal Name vs Bank Holder)
                            |
                            v
             Stage 5: Cryptographic Duplicate Detection
             (SHA-256 Hashes vs Approved Vendors Table)
                            |
                            v
             Stage 6: Internal Restricted Watchlist Screening
             (SHA-256 Hashes vs Restricted Vendors Table)
                            |
                            v
             Stage 7: Deterministic Decision Engine
             (APPROVED / PENDING / REJECTED)
                            |
   +------------------------+------------------------+
   |                                                 |
   v                                                 v
Stage 8: Dynamic Communication Draft        SQLite Persistence Layer
(Personalized vendor email notice)          (Runs, Approved, Metrics)
                            |
                            v
                   EXECUTION DASHBOARD
```

### The 8 Verification Stages
1. **Intake & Cryptographic Identifier Setup:** Allocates a unique Run ID (`VF-XXXXXXXX`), normalizes entity names, and generates privacy-safe masked identifiers for audit trails.
2. **Field Validation:** Deterministically validates legal entity name length, Indian jurisdiction, contact email syntax, PAN format (`^[A-Z]{5}[0-9]{4}[A-Z]$`), GSTIN structure (`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$`), and IFSC routing code (`^[A-Z]{4}0[A-Z0-9]{6}$`).
3. **Document Completeness Check:** Verifies presence, accepted file extensions (`.pdf`, `.png`, `.jpg`, `.jpeg`), and file size limits (<= 10 MB) across 3 mandatory compliance documents.
4. **Cross-Field Consistency Verification:**
   - *PAN vs. GSTIN:* Confirms the 10-character PAN matches characters 2–11 embedded in the 15-character GSTIN.
   - *Entity Name vs. Bank Holder Name:* Normalizes legal entity suffixes (`PRIVATE LIMITED`, `PVT LTD`, `LIMITED`, `LLP`, etc.) and punctuation to verify account ownership alignment without aggressive fuzzy matching.
5. **Duplicate Detection Check:** Queries existing approved vendors using SHA-256 hashes of normalized tax identifiers to prevent duplicate vendor master records.
6. **Internal Restricted Screening:** Checks tax identifier hashes against a synthetic internal compliance watchlist to identify hard-stop entities.
7. **Final Decision Engine:** Synthesizes all findings using strict precedence rules to assign `APPROVED`, `PENDING`, or `REJECTED` with visible executive reasoning and required next steps.
8. **Communication Draft & Audit Persistence:** Dynamically drafts actionable email notifications and commits immutable execution records into SQLite.

---

## 3. Technology Stack

- **Frontend Interface:** Streamlit (Python components, forms, metric cards, status containers, data tables, file uploaders)
- **Backend Core:** Modular Python 3 standard library (`re`, `hashlib`, `json`, `uuid`, `dataclasses`, `datetime`, `time`)
- **Database:** SQLite3 (`sqlite3`) with parameterized queries and indexed cryptographic hash lookups
- **Analytics & Tables:** pandas
- **Automated Testing:** pytest

*Zero external API dependencies: Runs without OpenAI, Gemini, Anthropic, or paid OCR API requirements.*

---

## 4. Project File Structure

```
VendorFlow-Zamp-CaseStudy/
│
├── app.py                      # Main Streamlit web application & routing
├── requirements.txt            # Minimal runtime dependencies
├── README.md                   # Comprehensive system specification & documentation
├── .gitignore                  # Git hygiene rules (excludes DB, cache, temp files)
│
├── database/
│   ├── __init__.py             # Database package exports
│   └── db.py                   # SQLite schema, connection pool, queries & seeds
│
├── backend/
│   ├── __init__.py             # Backend package exports
│   ├── models.py               # Data models, Enums, StageResult, VendorSubmission
│   ├── validators.py           # Stage 2: Field regex and syntax validators
│   ├── document_checks.py      # Stage 3: Document presence, type & size checks
│   ├── consistency_checks.py   # Stage 4: PAN-GSTIN & Entity-Bank name matching
│   ├── duplicate_detection.py  # Stage 5: SHA-256 tax ID duplicate detection
│   ├── restricted_check.py     # Stage 6: Synthetic internal restricted list check
│   ├── decision_engine.py      # Stage 7: Deterministic decision precedence engine
│   ├── communication.py        # Stage 8: Dynamic personalized email drafting
│   └── workflow.py             # Orchestrator linking stages 1 to 8
│
├── frontend/
│   ├── __init__.py             # Frontend package exports
│   └── ui_helpers.py           # CSS design, badges, metric cards & stepper components
│
├── tests/
│   ├── __init__.py
│   └── test_workflow.py        # Automated test suite covering all scenarios & edges
│
└── .streamlit/
    └── config.toml             # Enterprise light theme styling configuration
```

---

## 5. Demonstration Scenarios & Edge Cases

The application includes 5 built-in, one-click demonstration scenarios accessible from the **'🚀 Demo Scenarios'** tab:

| Scenario | Vendor Name | Submitted Condition | Expected Outcome | Decision Reasoning |
|---|---|---|---|---|
| **Scenario A: Happy Path** | Aster Labs Private Limited | Complete documents, matching PAN/GSTIN, aligned bank name | **APPROVED** | All 8 automated verification checks passed cleanly. |
| **Scenario B: Missing Document** | Bluewave Technologies Pvt Ltd | Valid business & tax data, but missing Bank Proof | **PENDING** | Mandatory bank proof document missing. Actionable email draft generated. |
| **Scenario C: Name Mismatch** | Brightline Systems Pvt Ltd | Entity: Brightline Systems; Bank: Shree Trading Enterprises | **PENDING** | Material mismatch between entity name and bank account holder. Manual ownership check required. |
| **Scenario D: Duplicate Vendor** | Northstar Office Supplies Pvt Ltd | Tax IDs (PAN `LMNOP1234Q`) match existing approved record | **PENDING** | Duplicate registration detected in approved registry. Human reconciliation required. |
| **Scenario E: Restricted Watchlist** | Redwood Logistics LLP | Tax IDs (PAN `UVWXY5678Z`) match synthetic restricted registry | **REJECTED** | Compliance policy hard-stop triggered. Automated onboarding halted immediately. |

### Additional Tested Edge Cases
- **Invalid PAN Format:** `INVALIDPAN1` -> Caught by Stage 2 regex -> PENDING.
- **Embedded PAN/GSTIN Mismatch:** PAN `ABCDE1234F` vs GSTIN `27ZZZZZ9999Z1Z5` -> Caught by Stage 4 -> PENDING.
- **Invalid IFSC Code:** Missing 5th-character '0' or improper length -> Caught by Stage 2 -> PENDING.
- **Unsupported Jurisdiction:** Countries outside India (e.g. United States) -> Routed to PENDING for manual cross-border handling.
- **Invalid Document Format:** Uploading `.exe` or disallowed files -> Caught by Stage 3 -> PENDING.
- **Oversized Documents:** Files > 10 MB -> Flagged as `INVALID_SIZE` -> PENDING.

---

## 6. Local Setup & Execution Guide

### Prerequisites
- Python 3.10+ (Tested up to Python 3.14)
- Git

### Installation Steps

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/your-username/VendorFlow-Zamp-CaseStudy.git
   cd VendorFlow-Zamp-CaseStudy
   ```

2. **Create & Activate Virtual Environment:**
   ```bash
   # On macOS/Linux:
   python3 -m venv venv
   source venv/bin/activate

   # On Windows (PowerShell):
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Execute Automated Unit Tests:**
   ```bash
   python -m pytest tests/ -v
   ```
   *Expected Output: 6 passed in < 0.5s*

5. **Launch the VendorFlow Application:**
   ```bash
   streamlit run app.py
   ```
   *The application will open in your browser at `http://localhost:8501`.*

---

## 7. Cloud Deployment Guide (Streamlit Community Cloud)

1. Push this repository to GitHub:
   ```bash
   git init
   git add .
   git commit -m "feat: complete VendorFlow automated vendor onboarding engine"
   git remote add origin https://github.com/<your-github-username>/VendorFlow-Zamp-CaseStudy.git
   git branch -M main
   git push -u origin main
   ```
2. Navigate to [share.streamlit.io](https://share.streamlit.io).
3. Connect your GitHub account and select the `VendorFlow-Zamp-CaseStudy` repository.
4. Set Main file path: `app.py`.
5. Click **Deploy**. The platform automatically installs dependencies from `requirements.txt` and publishes the live public URL.

---

## 8. Five-Minute Demo Video Script & Walkthrough

Record a concise 5-minute screen recording following this exact sequence:

- **0:00 – 0:30 | Introduction & Problem Framing:**
  *"Hello, I'm presenting VendorFlow, an automated vendor onboarding and verification system. In corporate procurement, reviewing vendor submissions across company data, tax IDs, and bank proofs is historically manual, prone to errors, and risky. VendorFlow transforms this manual review into an auditable 8-stage verification pipeline with clear explainability."*
- **0:30 – 1:30 | Happy Path Live Execution (Scenario A):**
  - Navigate to **New Submission** or **Demo Scenarios**.
  - Show Aster Labs submission with all 3 documents and matching tax IDs.
  - Click **Run Onboarding Verification**.
  - Point to the live execution view showing all 8 stages completing cleanly.
  - Highlight the **APPROVED** banner and explain that the vendor record was safely persisted to SQLite.
- **1:30 – 2:20 | Explain Decision & Masking:**
  - Review the executive summary, checks passed, and next steps.
  - Highlight the privacy-safe masked identifiers (PAN `AB****4F`, Account `********9012`).
  - Show the clean communication draft ready for procurement operations.
- **2:20 – 3:30 | Edge Case 1 — Missing Document & Name Mismatch (Scenarios B & C):**
  - Trigger **Scenario B** (Bluewave Technologies missing bank proof).
  - Show the **PENDING** status and point to the dynamically generated email requesting the specific missing bank proof.
  - Trigger **Scenario C** (Brightline Systems vs Shree Trading Enterprises).
  - Show how legal suffix normalization flagged the material entity name mismatch.
- **3:30 – 4:20 | Edge Case 2 — Hard-Stop Screening (Scenario E):**
  - Trigger **Scenario E** (Redwood Logistics).
  - Point out that tax identifier matching against the internal restricted watchlist triggered an immediate **REJECTED** hard-stop.
  - Review the tailored formal rejection communication draft.
- **4:20 – 4:50 | Execution Dashboard & Audit Trail:**
  - Open the **Execution Dashboard**.
  - Show real-time metrics (Total, Approved, Pending, Rejected, Approval Rate).
  - Filter by status and search by vendor name.
  - Open an old run in the **Historical Run Inspector** to demonstrate full reproducibility.
- **4:50 – 5:00 | Conclusion:**
  *"VendorFlow delivers a deterministic, auditable, and secure onboarding workflow. It automates repetitive checks while keeping authorized human procurement officers firmly in control for final activation."*

---

## 9. Honest Scope Boundaries & Engineering Limitations

In accordance with professional engineering integrity, the following boundaries are explicitly declared:

1. **Jurisdiction Scope:** Configured specifically for Indian tax and corporate structures (PAN, GSTIN, IFSC). Submissions from other jurisdictions are routed to PENDING for specialized cross-border handling.
2. **Structural Format Checks vs. Live Government APIs:** PAN and GSTIN numbers are rigorously validated against statutory structural regex rules. They are not checked against live government servers (such as live NSDL/GSTN APIs), which require paid enterprise government gateway tokens.
3. **Banking Route Validation vs. Core Banking Networks:** Bank IFSC codes and account structures are validated. Direct bank account ownership is not confirmed against live inter-bank networks (e.g. IMPS penny-drop verification).
4. **Document Integrity vs. Certified OCR:** Uploaded documents are verified for presence, allowed file extension, and size limits (< 10 MB). The prototype does not claim OCR content extraction or document tampering verification.
5. **Synthetic Internal Restricted Registry:** Demonstrates internal risk policy enforcement using synthetic watchlist records; it does not replace a production global sanctions (OFAC/PEP) screening provider.
6. **Communication Drafting:** Dynamic, context-aware email drafts are created for human review and copy; automatic background SMTP transmission is omitted.
7. **Human-in-the-Loop Authority:** Automated approval certifies that all automated validation rules succeeded. Final financial vendor activation and payment authorization remains subject to manual sign-off by an authorized procurement officer.

---

## 10. License
Developed as part of the Zamp AI Solutions Analyst Case Study. Distributed under the MIT License.
