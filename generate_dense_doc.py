"""
Generates a dense, single-page test image (PNG) with real, known text for
the ministral3-8b vision context-extension test (8192 vs 16384 num_ctx).

Renders directly to PNG via PIL -- no PDF intermediate, no gen-AI text
garbling risk. Also writes the ground-truth text to a .txt file so the
model's transcription output can be diffed against something exact.

Requires Pillow:
    pip install Pillow

Run:
    python generate_dense_doc.py
"""

import os

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# CONFIG -- tune density here if the test needs to push harder or softer
# ---------------------------------------------------------------------------

OUTPUT_IMAGE = "images/dense_context_test.png"
OUTPUT_GROUND_TRUTH = "dense_context_test_ground_truth.txt"

PAGE_WIDTH = 1700          # ~200 DPI on a US Letter page (8.5in)
PAGE_HEIGHT = 2200         # ~200 DPI on a US Letter page (11in)
MARGIN = 90
FONT_SIZE_BODY = 15        # small, dense -- mimics a 9-10pt printed page
FONT_SIZE_HEADER = 13
LINE_SPACING = 4

FONT_PATH_REGULAR = "C:/Windows/Fonts/arial.ttf"
FONT_PATH_BOLD = "C:/Windows/Fonts/arialbd.ttf"

# ---------------------------------------------------------------------------
# CONTENT -- real text, exact ground truth. Edit CLAUSES to change density.
# ---------------------------------------------------------------------------

HEADER_TEXT = "MASTER SERVICES AGREEMENT -- INTERNAL REVIEW COPY, NOT FOR DISTRIBUTION"
FOOTER_TEXT = "Page 1 of 1 -- Confidential"

CLAUSES = [
    ("1. Definitions", "In this Agreement, \"Client\" means the party receiving the services described in Schedule A, and \"Provider\" means the party delivering those services. \"Confidential Information\" means any non-public technical, financial, or operational information disclosed by either party, whether marked confidential or not, that a reasonable person would understand to be confidential given the nature of the information and the circumstances of disclosure."),
    ("2. Scope of Services", "The Provider shall perform the services set out in Schedule A in a professional and workmanlike manner consistent with generally accepted industry standards. Any material change to the scope of services must be agreed in writing by both parties before work begins, and no verbal instruction shall be treated as amending this Agreement."),
    ("3. Term and Termination", "This Agreement commences on the Effective Date and continues until terminated by either party giving no less than thirty days written notice. Either party may terminate immediately for material breach that remains uncured fifteen days after written notice of the breach is given to the breaching party."),
    ("4. Fees and Payment", "The Client shall pay the fees set out in Schedule B within thirty days of the date of each invoice. Late payments accrue interest at one and a half percent per month or the maximum rate permitted by law, whichever is lower. All fees are exclusive of applicable taxes unless stated otherwise."),
    ("5. Confidentiality", "Each party agrees to protect the other's Confidential Information using at least the same degree of care it uses to protect its own confidential information, and in no event less than a reasonable degree of care. Confidential Information may not be disclosed to any third party without prior written consent, except as required by law."),
    ("6. Intellectual Property", "Except as expressly stated in Schedule A, each party retains all right, title, and interest in its own pre-existing intellectual property. Any new intellectual property created specifically for the Client under this Agreement shall be assigned to the Client upon full payment of all fees due."),
    ("7. Warranties", "The Provider warrants that the services will be performed with reasonable skill and care and will materially conform to the specifications in Schedule A. Except as expressly stated in this Agreement, all other warranties, whether express or implied, including fitness for a particular purpose, are disclaimed to the fullest extent permitted by law."),
    ("8. Limitation of Liability", "Neither party shall be liable to the other for any indirect, incidental, special, or consequential damages arising out of or related to this Agreement, even if advised of the possibility of such damages. Each party's total aggregate liability under this Agreement shall not exceed the total fees paid under this Agreement in the twelve months preceding the claim."),
    ("9. Indemnification", "Each party shall indemnify and hold harmless the other party from third-party claims arising from the indemnifying party's gross negligence or willful misconduct, provided the indemnified party gives prompt written notice of the claim and reasonable cooperation in its defense."),
    ("10. Data Protection", "Each party shall comply with all applicable data protection laws in connection with any personal data processed under this Agreement. The Provider shall implement appropriate technical and organizational measures to protect personal data against unauthorized access, loss, or disclosure."),
    ("11. Force Majeure", "Neither party shall be liable for any failure or delay in performance caused by circumstances beyond its reasonable control, including natural disasters, labor disputes, governmental action, or failures of third-party infrastructure, provided the affected party gives prompt notice and uses reasonable efforts to resume performance."),
    ("12. Assignment", "Neither party may assign or transfer this Agreement, in whole or in part, without the prior written consent of the other party, except to a successor in interest through merger, acquisition, or sale of substantially all assets, provided the successor agrees in writing to be bound by this Agreement."),
    ("13. Governing Law", "This Agreement shall be governed by and construed in accordance with the laws of the jurisdiction in which the Provider is incorporated, without regard to its conflict of laws principles. Any dispute arising under this Agreement shall be subject to the exclusive jurisdiction of the courts of that jurisdiction."),
    ("14. Notices", "All notices under this Agreement shall be in writing and delivered by email with confirmation of receipt, or by courier to the address specified in the signature block below. Notices are deemed received on the date of confirmed delivery."),
    ("15. Entire Agreement", "This Agreement, together with its Schedules, constitutes the entire agreement between the parties with respect to its subject matter and supersedes all prior discussions, negotiations, and agreements, whether written or oral, relating to that subject matter."),
]

# ---------------------------------------------------------------------------


def wrap_text(draw, text, font, max_width):
    """Wrap text to fit max_width pixels, word by word."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        print(f"WARNING: could not load {path}, falling back to PIL default font "
              f"(will look blocky -- install/point to a real .ttf for a realistic test).")
        return ImageFont.load_default()


def render():
    img = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(img)

    font_body = load_font(FONT_PATH_REGULAR, FONT_SIZE_BODY)
    font_bold = load_font(FONT_PATH_BOLD, FONT_SIZE_BODY)
    font_header = load_font(FONT_PATH_REGULAR, FONT_SIZE_HEADER)

    max_width = PAGE_WIDTH - 2 * MARGIN
    y = MARGIN

    ground_truth_lines = [HEADER_TEXT, ""]

    # Header
    draw.text((MARGIN, y), HEADER_TEXT, font=font_header, fill="black")
    y += FONT_SIZE_HEADER + 20
    draw.line([(MARGIN, y), (PAGE_WIDTH - MARGIN, y)], fill="black", width=1)
    y += 20

    for title, body in CLAUSES:
        draw.text((MARGIN, y), title, font=font_bold, fill="black")
        y += FONT_SIZE_BODY + LINE_SPACING
        ground_truth_lines.append(title)

        for line in wrap_text(draw, body, font_body, max_width):
            draw.text((MARGIN, y), line, font=font_body, fill="black")
            y += FONT_SIZE_BODY + LINE_SPACING
            ground_truth_lines.append(line)

        y += 10  # gap between clauses
        ground_truth_lines.append("")

        if y > PAGE_HEIGHT - MARGIN - 40:
            print(f"WARNING: content overflowed the page at clause '{title}' -- "
                  f"reduce FONT_SIZE_BODY or trim CLAUSES.")
            break

    # Footer
    draw.line(
        [(MARGIN, PAGE_HEIGHT - MARGIN), (PAGE_WIDTH - MARGIN, PAGE_HEIGHT - MARGIN)],
        fill="black", width=1,
    )
    draw.text((MARGIN, PAGE_HEIGHT - MARGIN + 15), FOOTER_TEXT, font=font_header, fill="black")
    ground_truth_lines.append(FOOTER_TEXT)

    os.makedirs("images", exist_ok=True)
    img.save(OUTPUT_IMAGE)

    with open(OUTPUT_GROUND_TRUTH, "w", encoding="utf-8") as f:
        f.write("\n".join(ground_truth_lines))

    word_count = sum(len(body.split()) for _, body in CLAUSES)
    print(f"Image saved to: {OUTPUT_IMAGE}")
    print(f"Ground truth saved to: {OUTPUT_GROUND_TRUTH}")
    print(f"Body word count: {word_count}")


if __name__ == "__main__":
    render()