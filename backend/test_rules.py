"""Checklist tests for rules.py.

    python test_rules.py

These run against hardcoded OCR output — no image, no PaddleOCR call — so the
compliance logic can be verified independently of OCR accuracy, per
SPEC_backend.md Phase 2.

Bounding boxes are synthetic rectangles whose height is what matters: Field 6
compares region heights, so the boxes here are shaped to exercise that.
"""

from __future__ import annotations

import sys

from ocr import OCRResult
from rules import check_compliance, PASS, FAIL, NEEDS_REVIEW


def region(text: str, confidence: float = 0.95, height: float = 30.0, y: float = 0.0) -> OCRResult:
    """An OCR region with a rectangular box of the given height."""
    return OCRResult(
        text=text,
        confidence=confidence,
        bbox=[[0.0, y], [400.0, y], [400.0, y + height], [0.0, y + height]],
    )


def compliant_label() -> list[OCRResult]:
    return [
        region("TASTY CRUNCH BISCUITS", height=48),
        region("MRP Rs. 45.00 (incl. of all taxes)"),
        region("Net Wt. 250 g"),
        region("MFG DATE: 03/2026"),
        region("Marketed by: Tasty Foods Pvt Ltd"),
        region("Plot 14, MIDC Industrial Area, Pune 411019"),
        region("Consumer care: 1800 123 4567"),
        region("care@tastyfoods.example"),
    ]


def status_of(report, field_name: str) -> str:
    for f in report.fields:
        if f.field_name == field_name:
            return f.status
    raise AssertionError(f"no result for field {field_name}")


def matched_of(report, field_name: str):
    for f in report.fields:
        if f.field_name == field_name:
            return f.matched_text
    raise AssertionError(f"no result for field {field_name}")


# --- cases --------------------------------------------------------------------

CASES = []


def case(name):
    def wrap(fn):
        CASES.append((name, fn))
        return fn
    return wrap


@case("fully compliant label passes every check")
def test_compliant():
    report = check_compliance(compliant_label())
    for f in report.fields:
        assert f.status == PASS, f"{f.field_name} was {f.status}: {f.note}"
    assert report.overall_status == "compliant"
    assert report.message is None


@case("missing MRP fails the mrp check and the whole label")
def test_missing_mrp():
    regions = [r for r in compliant_label() if "MRP" not in r.text]
    report = check_compliance(regions)
    assert status_of(report, "mrp") == FAIL
    assert status_of(report, "net_quantity") == PASS
    assert report.overall_status == "non_compliant"


@case("missing address fails when no trigger phrase and no PIN are present")
def test_missing_address():
    regions = [
        r for r in compliant_label()
        if "Marketed by" not in r.text and "MIDC" not in r.text
    ]
    report = check_compliance(regions)
    assert status_of(report, "manufacturer_address") == FAIL
    assert report.overall_status == "non_compliant"


@case("address trigger with no PIN code nearby fails")
def test_address_trigger_without_pin():
    regions = [r for r in compliant_label() if "MIDC" not in r.text]
    regions.append(region("Plot 14, MIDC Industrial Area, Pune"))
    report = check_compliance(regions)
    assert status_of(report, "manufacturer_address") == FAIL


@case("PIN code with no address wording goes to review, not failure")
def test_pin_without_trigger():
    regions = [r for r in compliant_label() if "Marketed by" not in r.text]
    report = check_compliance(regions)
    assert status_of(report, "manufacturer_address") == NEEDS_REVIEW


@case("low-confidence MRP goes to review rather than a false failure")
def test_low_confidence_mrp():
    regions = [r for r in compliant_label() if "MRP" not in r.text]
    regions.append(region("MRP Rs. 45.00", confidence=0.31))
    report = check_compliance(regions)
    assert status_of(report, "mrp") == NEEDS_REVIEW
    assert report.overall_status == "needs_review"


@case("OCR misreading MRP as MPR still matches")
def test_fuzzy_mrp_misread():
    regions = [r for r in compliant_label() if "MRP" not in r.text]
    regions.append(region("MPR 45.00"))
    report = check_compliance(regions)
    assert status_of(report, "mrp") == PASS


@case("bare MM/YY date with no trigger phrase goes to review, not a guess")
def test_ambiguous_date():
    regions = [r for r in compliant_label() if "MFG" not in r.text]
    regions.append(region("03/26"))
    report = check_compliance(regions)
    assert status_of(report, "mfg_date") == NEEDS_REVIEW
    assert report.overall_status == "needs_review"


@case("month-name date passes without any trigger phrase")
def test_month_name_date():
    regions = [r for r in compliant_label() if "MFG" not in r.text]
    regions.append(region("JAN 2026"))
    report = check_compliance(regions)
    assert status_of(report, "mfg_date") == PASS


@case("no date at all fails")
def test_missing_date():
    regions = [r for r in compliant_label() if "MFG" not in r.text]
    report = check_compliance(regions)
    assert status_of(report, "mfg_date") == FAIL


@case("email alone satisfies consumer care")
def test_consumer_care_email_only():
    regions = [r for r in compliant_label() if "1800" not in r.text]
    report = check_compliance(regions)
    assert status_of(report, "consumer_care") == PASS
    assert "@" in matched_of(report, "consumer_care")


@case("no phone and no email fails consumer care")
def test_missing_consumer_care():
    regions = [
        r for r in compliant_label()
        if "1800" not in r.text and "@" not in r.text
    ]
    report = check_compliance(regions)
    assert status_of(report, "consumer_care") == FAIL


@case("disproportionately small declaration is flagged for review, never failed")
def test_font_size_flagged():
    regions = [
        region("TASTY CRUNCH BISCUITS", height=60),
        region("A PRODUCT YOU WILL LOVE", height=44),
        region("100% VEGETARIAN", height=40),
        region("BEST BEFORE 9 MONTHS FROM MFG", height=38),
        region("Net Wt. 250 g", height=36),
        region("MFG DATE: 03/2026", height=34),
        region("Marketed by: Tasty Foods Pvt Ltd", height=32),
        region("Plot 14, MIDC Area, Pune 411019", height=30),
        region("Consumer care: 1800 123 4567", height=28),
        region("MRP Rs. 45.00", height=4),  # printed far smaller than everything else
    ]
    report = check_compliance(regions)
    assert status_of(report, "mrp") == PASS
    assert status_of(report, "font_size") == NEEDS_REVIEW
    assert "mrp" in matched_of(report, "font_size")
    assert report.overall_status == "needs_review"


@case("font size check never returns fail")
def test_font_size_never_fails():
    for regions in (compliant_label(), [region("MRP Rs. 45.00", height=2)] * 6):
        report = check_compliance(regions)
        assert status_of(report, "font_size") != FAIL


@case("unreadable photo asks for a retake instead of declaring non-compliance")
def test_low_quality_image():
    report = check_compliance([region("l1", confidence=0.2, height=8)])
    assert report.overall_status == "needs_review"
    assert report.message is not None
    assert all(f.status == NEEDS_REVIEW for f in report.fields)


@case("empty OCR output does not crash")
def test_empty():
    report = check_compliance([])
    assert report.overall_status == "needs_review"
    assert report.message is not None


# --- runner -------------------------------------------------------------------


def main() -> int:
    failures = 0
    for name, fn in CASES:
        try:
            fn()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {name}\n        {exc}")
        except Exception as exc:  # noqa: BLE001 - surface anything unexpected
            failures += 1
            print(f"ERROR {name}\n        {type(exc).__name__}: {exc}")
        else:
            print(f"ok    {name}")

    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
