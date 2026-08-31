"""PaddleOCR wrapper for label photos.

Phase 1 deliverable (SPEC_backend.md). Runnable standalone:

    python ocr.py path/to/label.jpg

Prints every detected (text, confidence, bounding box) so OCR output quality can
be judged by eye against real product photos before any rule logic runs on it.

Design note: PaddlePaddle is imported lazily inside `_get_engine()`, never at
module scope. That is deliberate — it lets `rules.py` and `test_rules.py` do
`from ocr import OCRResult` and run the entire checklist against hardcoded OCR
output with paddle absent, which is what SPEC_backend.md Phase 2 asks for.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any

# PaddleX pings its model hosts before every load to decide which mirror to use.
# On a slow link that check can hang for minutes before any OCR starts, and the
# models are cached locally after the first run anyway. Set this in the
# environment to override.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

# KNOWN GAP: English-only recognition model. Indian packaged goods are frequently
# bilingual (English + Hindi or a regional script), and PaddleOCR ships models for
# other scripts. Auto-detecting script and switching models is deliberately out of
# scope for this build — see SPEC_tier1_roadmap.md item 9.
OCR_LANG = "en"

_engine: Any = None


@dataclass
class OCRResult:
    """One text region detected on the label."""

    text: str
    confidence: float
    # Polygon as returned by PaddleOCR: 4 corner points, each [x, y].
    bbox: list[list[float]] = field(default_factory=list)

    @property
    def height_px(self) -> float:
        """Vertical extent of the region's bounding polygon.

        Field 6 of SPEC_rule_checklist.md compares these across regions to flag
        text that is disproportionately small relative to the rest of the label.
        """
        if not self.bbox:
            return 0.0
        ys = [point[1] for point in self.bbox]
        return max(ys) - min(ys)


def _get_engine():
    """Load PaddleOCR once and reuse it.

    The model load costs several seconds; doing it per request would add that to
    every single scan.
    """
    global _engine
    if _engine is not None:
        return _engine

    from paddleocr import PaddleOCR

    # PaddleOCR renamed `use_angle_cls` to `use_textline_orientation` in 3.x and
    # dropped the old name. Try the current name, fall back to the 2.x one so this
    # works against whichever version resolves.
    #
    # Document orientation classification and unwarping are switched off. Both are
    # built for scanned paper documents — detecting a page rotated 90 degrees, and
    # flattening the curl of a book spine. A product label photographed head-on is
    # neither, and running them costs two extra model downloads plus real latency
    # on every scan for no gain. Textline orientation stays on: individual lines on
    # packaging genuinely do run sideways.
    # oneDNN is off because paddlepaddle 3.3.1's CPU build crashes with it on:
    #
    #   NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute
    #   not support [pir::ArrayAttribute<pir::DoubleAttribute>]
    #
    # raised inside the text detection model on any image. oneDNN is a CPU
    # acceleration layer, so turning it off costs some speed and changes no
    # output. Worth retrying on a future paddle release.
    try:
        _engine = PaddleOCR(
            lang=OCR_LANG,
            use_textline_orientation=True,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            enable_mkldnn=False,
        )
    except (TypeError, ValueError):
        _engine = PaddleOCR(use_angle_cls=True, lang=OCR_LANG)
    return _engine


def _normalise_v3(payload: dict) -> list[OCRResult]:
    """PaddleOCR 3.x returns parallel arrays keyed by name."""
    texts = payload.get("rec_texts") or []
    scores = payload.get("rec_scores") or []
    polys = payload.get("rec_polys")
    if polys is None:
        polys = payload.get("dt_polys") or []

    results = []
    for i, text in enumerate(texts):
        score = float(scores[i]) if i < len(scores) else 0.0
        poly = [[float(x), float(y)] for x, y in polys[i]] if i < len(polys) else []
        results.append(OCRResult(text=str(text), confidence=score, bbox=poly))
    return results


def _normalise_v2(page: list) -> list[OCRResult]:
    """PaddleOCR 2.x returns [[bbox, (text, score)], ...] per page."""
    results = []
    for line in page:
        if not line:
            continue
        bbox, (text, score) = line[0], line[1]
        poly = [[float(x), float(y)] for x, y in bbox]
        results.append(OCRResult(text=str(text), confidence=float(score), bbox=poly))
    return results


def run_ocr(image_path: str) -> list[OCRResult]:
    """Run OCR on one image and return every detected text region."""
    engine = _get_engine()

    if hasattr(engine, "predict"):
        raw = engine.predict(image_path)
    else:
        raw = engine.ocr(image_path, cls=True)

    results: list[OCRResult] = []
    for page in raw or []:
        # 3.x pages behave like dicts; 2.x pages are plain lists of lines.
        if isinstance(page, dict) or hasattr(page, "get"):
            results.extend(_normalise_v3(page))
        elif isinstance(page, list):
            results.extend(_normalise_v2(page))
    return results


def raw_text(results: list[OCRResult]) -> str:
    """Every detected region joined into one newline-separated block.

    Stored on the scan row so a judge can see what the model actually read.
    """
    return "\n".join(r.text for r in results)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python ocr.py path/to/image.jpg", file=sys.stderr)
        return 2

    image_path = sys.argv[1]
    print(f"Running OCR on {image_path} (lang={OCR_LANG})...\n")
    results = run_ocr(image_path)

    if not results:
        print("No text detected. The image may be blurry, dark, or badly framed.")
        return 1

    for r in results:
        corners = " ".join(f"({x:.0f},{y:.0f})" for x, y in r.bbox)
        print(f"{r.confidence:.3f}  h={r.height_px:6.1f}px  {r.text!r}")
        print(f"        bbox: {corners}")

    print(f"\n{len(results)} region(s) detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
