"""Generate mock packaging labels for testing the OCR + rule pipeline.

    python tools/make_test_labels.py

Writes PNGs into backend/test-images/. These are a stand-in, not a substitute:
they are clean synthetic renders, so they exercise the pipeline end to end but
say nothing about how OCR copes with real packaging — curved foil, gloss,
low-contrast print, bilingual text. Tune the regexes in rules.py against real
photos, not against these.
"""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test-images")

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

WIDTH, HEIGHT = 900, 1200
INK = (26, 26, 26)
PAPER = (247, 245, 240)


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def render(name: str, lines: list[tuple[str, int]], blur: float = 0.0) -> str:
    """Draw a stack of (text, point size) lines onto a label-shaped canvas."""
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle([24, 24, WIDTH - 24, HEIGHT - 24], outline=(200, 196, 188), width=3)

    y = 90
    for text, size in lines:
        if not text:
            y += 26
            continue
        draw.text((70, y), text, font=font(size), fill=INK)
        y += int(size * 1.7)

    if blur:
        image = image.filter(ImageFilter.GaussianBlur(blur))

    path = os.path.join(OUT_DIR, f"{name}.png")
    image.save(path)
    return path


COMPLIANT = [
    ("TASTY CRUNCH", 76),
    ("Salted Butter Biscuits", 40),
    ("", 0),
    ("MRP Rs. 45.00", 38),
    ("(inclusive of all taxes)", 26),
    ("Net Wt. 250 g", 38),
    ("MFG DATE: 03/2026", 34),
    ("Best before 9 months from packaging", 26),
    ("", 0),
    ("Marketed by: Tasty Foods Pvt Ltd", 30),
    ("Plot 14, MIDC Industrial Area,", 28),
    ("Pune, Maharashtra 411019", 28),
    ("", 0),
    ("Consumer care: 1800 123 4567", 30),
    ("care@tastyfoods.example", 28),
]


def variants() -> dict[str, tuple[list[tuple[str, int]], float]]:
    """Each case isolates one failure mode so the rule engine can be read off the result."""
    missing_mrp = [line for line in COMPLIANT if not line[0].startswith("MRP")]
    missing_mrp = [line for line in missing_mrp if "inclusive of all taxes" not in line[0]]

    missing_address = [
        line for line in COMPLIANT
        if not line[0].startswith("Marketed by")
        and "MIDC" not in line[0]
        and "411019" not in line[0]
    ]

    tiny_print = [
        (text, 8 if text.startswith("MRP") else size)
        for text, size in COMPLIANT
    ]

    return {
        "compliant": (COMPLIANT, 0.0),
        "missing_mrp": (missing_mrp, 0.0),
        "missing_address": (missing_address, 0.0),
        "tiny_mrp_print": (tiny_print, 0.0),
        "unreadable": ([("TASTY", 70)], 9.0),
    }


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, (lines, blur) in variants().items():
        print(render(name, lines, blur))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
