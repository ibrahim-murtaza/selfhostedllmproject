"""
Generates a long, fictional, non-confidential PDF for testing page limits,
conversion time and the context-size guard.

Every page has a unique marker line (PAGE-<n>-CODE-<xxxx>) and about a
page of filler text, so you can ask the model "what is the code on page 17?".

Run:
    python make_long_pdf.py 35        -> long_35.pdf
    python make_long_pdf.py 12        -> long_12.pdf
"""

import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

pages = int(sys.argv[1]) if len(sys.argv) > 1 else 35
output = f"long_{pages}.pdf"

styles = getSampleStyleSheet()
body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10.5, leading=15)

filler = (
    "This paragraph is filler text written for testing purposes. It describes a "
    "fictional process at a fictional company and contains no real information. "
    "Its only job is to take up space so that each page holds a realistic amount "
    "of text, which lets us measure conversion time and how many pages fit in the "
    "model's context window. "
)


def code_for(n: int) -> str:
    return f"{(n * 7919) % 10000:04d}"  # deterministic, looks arbitrary


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f"Page {doc.page}")
    canvas.restoreState()


story = []
for n in range(1, pages + 1):
    story.append(Paragraph(f"Section {n}", styles["Heading1"]))
    story.append(Paragraph(f"<b>PAGE-{n}-CODE-{code_for(n)}</b>", body))
    story.append(Spacer(1, 8))
    for _ in range(3):
        story.append(Paragraph(filler * 3, body))
        story.append(Spacer(1, 6))
    if n < pages:
        story.append(PageBreak())

SimpleDocTemplate(
    output, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
    topMargin=2 * cm, bottomMargin=2 * cm, title="Long Test Document",
).build(story, onFirstPage=footer, onLaterPages=footer)
print(f"Wrote {output} ({pages} pages). Code on page 17 = {code_for(17)}")