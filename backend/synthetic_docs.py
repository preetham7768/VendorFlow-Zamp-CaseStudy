"""
Synthetic Document Generator for VendorFlow.
Generates authentic text-based PDF bytes using ReportLab for testing and demonstration.
"""

import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def generate_synthetic_pan_pdf(pan: str, name: str) -> bytes:
    """Generates a text-based synthetic Indian PAN card PDF."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    # Card boundary
    c.setLineWidth(1)
    c.rect(50, height - 250, 400, 200)

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(70, height - 80, "INCOME TAX DEPARTMENT")
    c.setFont("Helvetica", 10)
    c.drawString(70, height - 95, "GOVERNMENT OF INDIA")

    # Name
    c.setFont("Helvetica-Bold", 10)
    c.drawString(70, height - 130, "NAME / LEGAL ENTITY:")
    c.setFont("Helvetica", 11)
    c.drawString(70, height - 145, name.upper())

    # PAN Number
    c.setFont("Helvetica-Bold", 10)
    c.drawString(70, height - 180, "PERMANENT ACCOUNT NUMBER (PAN):")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(70, height - 198, pan.upper())

    # Footer note
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(70, height - 230, "Synthetic PAN Card for Automated Verification Testing.")

    c.showPage()
    c.save()
    return buf.getvalue()


def generate_synthetic_gst_pdf(gstin: str, legal_name: str, trade_name: str = "") -> bytes:
    """Generates a text-based synthetic GST Registration Certificate PDF."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 60, "GOVERNMENT OF INDIA")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 80, "CENTRAL GOODS AND SERVICES TAX REGISTRATION CERTIFICATE")

    c.setLineWidth(0.5)
    c.line(50, height - 90, width - 50, height - 90)

    # Details
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 120, "Registration Number (GSTIN):")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(240, height - 120, gstin.upper())

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 150, "Legal Name of Business:")
    c.setFont("Helvetica", 11)
    c.drawString(240, height - 150, legal_name.upper())

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 180, "Trade Name (if applicable):")
    c.setFont("Helvetica", 11)
    c.drawString(240, height - 180, (trade_name or legal_name).upper())

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 210, "Constitution of Business:")
    c.setFont("Helvetica", 11)
    c.drawString(240, height - 210, "Private Limited Company")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 240, "Date of Liability:")
    c.setFont("Helvetica", 11)
    c.drawString(240, height - 240, "01/04/2018")

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, height - 300, "Synthetic Form GST REG-06 for Automated Verification Testing.")

    c.showPage()
    c.save()
    return buf.getvalue()


def generate_synthetic_bank_pdf(
    account_holder: str,
    account_number: str,
    ifsc: str,
    bank_name: str = "HDFC Bank Ltd"
) -> bytes:
    """Generates a text-based synthetic Bank Proof / Cancelled Cheque PDF."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    # Cheque border
    c.setLineWidth(1)
    c.rect(50, height - 260, 480, 200)

    # Bank Name & Watermark
    c.setFont("Helvetica-Bold", 14)
    c.drawString(70, height - 90, bank_name.upper())
    c.setFont("Helvetica-Bold", 24)
    c.setFillColorRGB(0.8, 0.8, 0.8)
    c.drawString(200, height - 170, "CANCELLED")
    c.setFillColorRGB(0, 0, 0)

    # Account holder
    c.setFont("Helvetica-Bold", 10)
    c.drawString(70, height - 130, "ACCOUNT HOLDER NAME:")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(220, height - 130, account_holder.upper())

    # Account number
    c.setFont("Helvetica-Bold", 10)
    c.drawString(70, height - 160, "BANK ACCOUNT NUMBER:")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(220, height - 160, str(account_number))

    # IFSC
    c.setFont("Helvetica-Bold", 10)
    c.drawString(70, height - 190, "RTGS / NEFT IFSC CODE:")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(220, height - 190, ifsc.upper())

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(70, height - 240, "Synthetic Cancelled Cheque / Bank Proof for Testing.")

    c.showPage()
    c.save()
    return buf.getvalue()


def generate_unreadable_pdf() -> bytes:
    """Generates an empty/blank PDF with no selectable text to test unreadable fallback."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # Empty page without any text strings
    c.rect(50, 50, 400, 400, stroke=1, fill=0)
    c.showPage()
    c.save()
    return buf.getvalue()
