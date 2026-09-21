"""
Generates test_document.pdf: a fictional, non-confidential 3-page policy
document for testing document upload / ingestion.

Contains: title, headings, body text, bullet list, two tables, page numbers,
and known "marker facts" (start / middle / end) so you can check whether the
model actually saw the whole document.

Run:
    pip install reportlab
    python make_test_pdf.py
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT = "test_document.pdf"

styles = getSampleStyleSheet()
body = ParagraphStyle(
    "Body", parent=styles["Normal"], fontSize=10.5, leading=15, alignment=TA_JUSTIFY
)
h1 = styles["Heading1"]
h2 = styles["Heading2"]
title = styles["Title"]


def page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f"Page {doc.page}")
    canvas.drawString(2 * cm, 1.2 * cm, "Northwind Test Corp - Sample Document")
    canvas.restoreState()


def make_table(data, col_widths):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F6E6E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F5")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(i, body), leftIndent=12) for i in items],
        bulletType="bullet",
        start="\u2022",
        leftIndent=14,
    )


lorem = (
    "This paragraph is filler text written for testing purposes. It describes a "
    "fictional process at a fictional company and contains no real information. "
    "The purpose of this document is to check that text, headings, lists and "
    "tables survive upload and extraction intact. "
)

story = []

# ---------------- Page 1 ----------------
story += [
    Paragraph("Northwind Test Corp", title),
    Paragraph("Equipment Loan and Remote Work Policy (Sample)", h2),
    Spacer(1, 10),
    Paragraph("1. Purpose", h1),
    Paragraph(
        "This policy explains how employees borrow company equipment and work "
        "remotely. <b>Reference code: ALPHA-7421.</b> " + lorem * 2,
        body,
    ),
    Spacer(1, 8),
    Paragraph("2. Scope", h1),
    Paragraph(
        "This policy applies to all full-time and part-time staff in the "
        "Operations, Finance, Support and Engineering departments. " + lorem,
        body,
    ),
    Spacer(1, 8),
    Paragraph("3. Eligible Equipment", h1),
    bullets(
        [
            "Laptops (maximum loan period: 90 days)",
            "External monitors (maximum loan period: 180 days)",
            "Headsets and webcams (maximum loan period: 365 days)",
            "Docking stations (maximum loan period: 180 days)",
        ]
    ),
    PageBreak(),
]

# ---------------- Page 2 ----------------
story += [
    Paragraph("4. Loan Limits by Department", h1),
    Paragraph(
        "The table below lists how many items each department may hold on loan "
        "at any one time.",
        body,
    ),
    Spacer(1, 8),
    make_table(
        [
            ["Department", "Headcount", "Max Laptops", "Max Monitors"],
            ["Operations", "14", "6", "10"],
            ["Finance", "9", "4", "6"],
            ["Support", "22", "8", "12"],
            ["Engineering", "31", "12", "20"],
        ],
        [5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm],
    ),
    Spacer(1, 14),
    Paragraph("5. Remote Work Rules", h1),
    Paragraph(
        "Remote work is permitted up to three days per week with manager "
        "approval. <b>The approval window is 5 business days.</b> " + lorem * 2,
        body,
    ),
    Spacer(1, 8),
    Paragraph("5.1 Security Requirements", h2),
    bullets(
        [
            "Use only company-issued devices for work tasks.",
            "Lock the screen whenever the device is unattended.",
            "Report a lost or stolen device within 24 hours.",
            "Do not connect to public Wi-Fi without the company VPN.",
        ]
    ),
    PageBreak(),
]

# ---------------- Page 3 ----------------
story += [
    Paragraph("6. Cost Allocation", h1),
    Paragraph(
        "Loan costs are charged back to the borrowing department each quarter "
        "using the rates below (fictional figures).",
        body,
    ),
    Spacer(1, 8),
    make_table(
        [
            ["Item", "Quarterly Cost (USD)", "Replacement Value (USD)"],
            ["Laptop", "120", "1,400"],
            ["Monitor", "35", "300"],
            ["Headset", "10", "90"],
            ["Docking station", "25", "220"],
        ],
        [5 * cm, 5 * cm, 5 * cm],
    ),
    Spacer(1, 14),
    Paragraph("7. Returns and Damage", h1),
    Paragraph(
        "Equipment must be returned within 5 business days of the loan end "
        "date. Damage beyond normal wear is reported to the IT desk. " + lorem,
        body,
    ),
    Spacer(1, 8),
    Paragraph("8. Contact", h1),
    Paragraph(
        "Questions go to the IT desk. <b>Closing code: OMEGA-9036.</b> "
        "The policy owner is the Head of Operations, Jordan Avery (fictional).",
        body,
    ),
]

doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=A4,
    leftMargin=2 * cm,
    rightMargin=2 * cm,
    topMargin=2 * cm,
    bottomMargin=2 * cm,
    title="Equipment Loan and Remote Work Policy (Sample)",
    author="Northwind Test Corp",
)
doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
print(f"Wrote {OUTPUT}")