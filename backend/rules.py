"""Legal Metrology compliance rule engine.

Implements the six checks defined in SPEC_rule_checklist.md against OCR output.

What this does: checks whether a required declaration is PRESENT and readable on
the label. What this does not do: verify that a declared value is factually
correct — there is no reference database of correct values to check against.
This is a completeness/readability checker, not a fraud detector, and the six
checks are a deliberately scoped subset of the Legal Metrology (Packaged
Commodities) Rules, 2011 — not the complete legal standard.

Pure module: no I/O, no network, no PaddleOCR import. It takes a list of
OCRResult and returns a ComplianceReport, so the checklist logic can be verified
independently of OCR accuracy (see test_rules.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Iterable

from rapidfuzz import fuzz

from ocr import OCRResult

# --- statuses -----------------------------------------------------------------

PASS = "pass"
FAIL = "fail"
NEEDS_REVIEW = "needs_review"

COMPLIANT = "compliant"
NON_COMPLIANT = "non_compliant"
REVIEW = "needs_review"

FIELD_NAMES = [
    "mrp",
    "net_quantity",
    "mfg_date",
    "manufacturer_address",
    "consumer_care",
    "font_size",
]

# --- tunables -----------------------------------------------------------------
# SPEC_rule_checklist.md is explicit that these regexes and windows are starting
# points to be tuned against real OCR output, not final values. They are grouped
# here so that tuning after Phase 1 photo testing is a single-place edit.

LOW_CONFIDENCE = 0.5  # below this, a match is flagged rather than trusted

MRP_WINDOW = 12  # chars between a rupee/MRP indicator and its number
ADDRESS_WINDOW = 200  # chars between an address trigger and a PIN code
TRIGGER_WINDOW = 40  # chars for "trigger phrase nearby" confidence boosts

# A single OCR character substitution in a 3-character token ("MRP" -> "MPR",
# "MEP") scores 66.7 on RapidFuzz's indel ratio, so the cutoff has to sit below
# that to catch the misreads SPEC_rule_checklist.md calls out by name.
FUZZY_TOKEN_CUTOFF = 65
FUZZY_PHRASE_CUTOFF = 80  # multi-word triggers; longer strings tolerate a higher bar

# Region separator used when flattening OCR regions into one searchable string.
# Contains no letters or digits, so it can never fabricate a match across two
# regions that PaddleOCR detected separately.
SEP = " | "

# ASSUMPTION: SPEC_backend.md requires a "near-empty text" guard but does not
# quantify it. Treating fewer than 3 detected regions OR under 15 total
# characters as an unusable photo. This returns needs_review with a retake
# prompt — never a false non_compliant verdict on what is really a bad photo.
MIN_REGIONS = 3
MIN_CHARS = 15

LOW_QUALITY_MESSAGE = (
    "Very little text could be read from this photo. Retake it in better light, "
    "holding the camera steady and square to the label."
)


# --- result types -------------------------------------------------------------


@dataclass
class FieldResult:
    field_name: str
    status: str
    matched_text: str | None = None
    confidence: float | None = None
    note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ComplianceReport:
    overall_status: str
    fields: list[FieldResult]
    ocr_raw_text: str
    message: str | None = None

    def to_dict(self) -> dict:
        return {
            "overall_status": self.overall_status,
            "fields": [f.to_dict() for f in self.fields],
            "ocr_raw_text": self.ocr_raw_text,
            "message": self.message,
        }


# --- flattened label text with region traceability ----------------------------


class LabelText:
    """OCR regions flattened into one string, with every character traceable
    back to the region it came from.

    Matching has to happen across the whole label (a declaration is often split
    over several detected regions), but confidence and bounding-box height are
    per region — so a match is useless unless we can find its source region
    again. This class is what keeps both true at once.
    """

    def __init__(self, results: list[OCRResult]):
        self.results = results
        self._spans: list[tuple[int, int, int]] = []  # (start, end, region index)

        parts = []
        cursor = 0
        for index, region in enumerate(results):
            text = region.text or ""
            self._spans.append((cursor, cursor + len(text), index))
            parts.append(text)
            cursor += len(text) + len(SEP)

        self.text = SEP.join(parts)

    def region_at(self, char_index: int) -> OCRResult | None:
        """The OCR region a character offset falls inside (None if in a separator)."""
        for start, end, region_index in self._spans:
            if start <= char_index < end:
                return self.results[region_index]
        return None

    def region_for_span(self, start: int, end: int) -> OCRResult | None:
        """The region a match belongs to.

        A match spanning several regions is attributed to the first region it
        touches — that is where its leading characters were actually read from.
        """
        for offset in range(start, min(end, len(self.text))):
            region = self.region_at(offset)
            if region is not None:
                return region
        return None

    def snippet(self, start: int, end: int, pad: int = 0) -> str:
        lo = max(0, start - pad)
        hi = min(len(self.text), end + pad)
        return self.text[lo:hi].strip(" |")


def _confidence_of(region: OCRResult | None) -> float | None:
    return region.confidence if region is not None else None


# --- fuzzy helpers ------------------------------------------------------------

_TOKEN_RE = re.compile(r"[A-Za-z.]{2,8}")


def _fuzzy_token_present(window: str, target: str, cutoff: int = FUZZY_TOKEN_CUTOFF) -> bool:
    """True if any short alphabetic token in `window` fuzzily matches `target`.

    Token-by-token rather than a partial ratio over the whole window: against a
    3-character target like "MRP", a partial ratio scores high on almost any text
    containing an "M" and an "R", which would make the check meaningless.
    """
    target = target.upper().replace(".", "")
    for token in _TOKEN_RE.findall(window):
        cleaned = token.upper().replace(".", "")
        if not cleaned:
            continue
        if fuzz.ratio(cleaned, target) >= cutoff:
            return True
    return False


def _fuzzy_phrase_positions(haystack: str, phrases: Iterable[str]) -> list[tuple[int, int, str]]:
    """Best fuzzy position of each phrase in `haystack`, as (start, end, phrase).

    Tolerates the character-level noise OCR introduces into trigger phrases
    ("Marketed by" read as "Marketedby", "Manufactured bv", and so on).
    """
    found = []
    upper = haystack.upper()
    for phrase in phrases:
        needle = phrase.upper()
        alignment = fuzz.partial_ratio_alignment(needle, upper, score_cutoff=FUZZY_PHRASE_CUTOFF)
        if alignment is not None:
            found.append((alignment.dest_start, alignment.dest_end, phrase))
    return found


def _trigger_near(label: LabelText, start: int, end: int, phrases: Iterable[str],
                  window: int = TRIGGER_WINDOW) -> str | None:
    """The trigger phrase found within `window` characters of a match, if any."""
    lo = max(0, start - window)
    hi = min(len(label.text), end + window)
    context = label.text[lo:hi]
    hits = _fuzzy_phrase_positions(context, phrases)
    return hits[0][2] if hits else None


# --- Field 1: MRP -------------------------------------------------------------

MRP_INDICATOR_RE = re.compile(r"(?:₹|\bRs\.?|\bINR\b|\bM\.?\s?R\.?\s?P\.?)", re.IGNORECASE)
PRICE_VALUE_RE = re.compile(r"\d+(?:[.,]\d{1,2})?")


def check_mrp(label: LabelText) -> FieldResult:
    """Rupee/MRP indicator immediately adjacent to a numeric value.

    Fuzzy on the indicator because OCR routinely misreads "MRP" as "MPR", "MEP".

    The indicator and its number must sit in the SAME detected region — the spec
    requires the number be "immediately followed or preceded by" the indicator,
    which is to say printed on the same line. Searching a character window across
    the flattened label instead lets a number on one line pair with an indicator
    on the next: the last four digits of a consumer care phone number will happily
    claim an "MRP" printed on the line below it and report a price of 4567.

    KNOWN LIMITATION: where OCR splits a genuine "MRP ₹45" across two regions,
    this misses it. That direction of error is the safe one — it produces a
    reviewable fail rather than a confidently wrong price.
    """
    best: tuple[str, OCRResult] | None = None
    low_confidence_candidate: tuple[str, OCRResult] | None = None

    for region in label.results:
        text = region.text or ""
        for value in PRICE_VALUE_RE.finditer(text):
            lo = max(0, value.start() - MRP_WINDOW)
            hi = min(len(text), value.end() + MRP_WINDOW)
            window = text[lo:hi]

            has_indicator = (
                bool(MRP_INDICATOR_RE.search(window)) or _fuzzy_token_present(window, "MRP")
            )
            if not has_indicator:
                continue

            matched = window.strip(" |")
            if region.confidence < LOW_CONFIDENCE:
                if low_confidence_candidate is None:
                    low_confidence_candidate = (matched, region)
                continue
            if best is None:
                best = (matched, region)

    if best is not None:
        matched, region = best
        return FieldResult("mrp", PASS, matched, region.confidence)

    if low_confidence_candidate is not None:
        matched, region = low_confidence_candidate
        return FieldResult(
            "mrp", NEEDS_REVIEW, matched, region.confidence,
            note="A price-like value was found but read with low confidence.",
        )

    return FieldResult("mrp", FAIL, None, None, note="No maximum retail price declaration found.")


# --- Field 2: net quantity ----------------------------------------------------

QUANTITY_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s?(kgs?|kg|gms?|gm|g|mg|ml|litres?|litre|ltrs?|ltr|l)\b",
    re.IGNORECASE,
)
QUANTITY_TRIGGERS = ["net quantity", "net weight", "net qty", "net wt", "net vol", "net"]


def check_net_quantity(label: LabelText) -> FieldResult:
    """A number followed by a standard unit of mass or volume."""
    low_confidence_candidate: tuple[str, OCRResult | None] | None = None

    for match in QUANTITY_RE.finditer(label.text):
        region = label.region_for_span(match.start(), match.end())
        confidence = _confidence_of(region)
        matched = match.group(0).strip()

        if confidence is not None and confidence < LOW_CONFIDENCE:
            if low_confidence_candidate is None:
                low_confidence_candidate = (matched, region)
            continue

        # A nearby trigger phrase is not required for a pass, but it is worth
        # recording — it is the difference between a confident match and a bare
        # number that happens to carry a unit.
        trigger = _trigger_near(label, match.start(), match.end(), QUANTITY_TRIGGERS)
        note = f'Declared with trigger phrase "{trigger}".' if trigger else None
        return FieldResult("net_quantity", PASS, matched, confidence, note=note)

    if low_confidence_candidate is not None:
        matched, region = low_confidence_candidate
        return FieldResult(
            "net_quantity", NEEDS_REVIEW, matched, _confidence_of(region),
            note="A quantity was found but read with low confidence.",
        )

    return FieldResult(
        "net_quantity", FAIL, None, None, note="No net quantity declaration found."
    )


# --- Field 3: manufacturing date ----------------------------------------------

MONTHS = (
    "JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC|"
    "JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"
)

# Day and month components are range-bounded (1-31, 1-12) rather than any one or
# two digits. Without that bound, "MRP Rs. 45.00" matches a MM.YY date pattern and
# a price gets read as a manufacturing date.
DAY = r"(?:0?[1-9]|[12]\d|3[01])"
MONTH = r"(?:0?[1-9]|1[0-2])"
YEAR = r"(?:19|20)\d{2}"

# Unambiguous by shape: a full separator-and-four-digit-year date, or a month name.
STRONG_DATE_RES = [
    re.compile(rf"\b{DAY}[/\-.]{MONTH}[/\-.]{YEAR}\b"),  # DD/MM/YYYY
    re.compile(rf"\b{MONTH}[/\-.]{YEAR}\b"),  # MM/YYYY
    re.compile(rf"\b(?:{MONTHS})[\s.\-/]*{YEAR}\b", re.IGNORECASE),  # JAN 2026
    re.compile(rf"\b{DAY}[\s.\-/]*(?:{MONTHS})[\s.\-/]*{YEAR}\b", re.IGNORECASE),  # 15 JAN 2026
]

# Date-shaped but could equally be a batch or lot code. The "." separator is
# excluded here — with a two-digit tail it collides with decimal prices.
WEAK_DATE_RES = [
    re.compile(rf"\b{MONTH}[/\-]\d{{2}}\b"),  # MM/YY
    re.compile(rf"\b(?:{MONTHS})[\s\-/]*\d{{2}}\b", re.IGNORECASE),  # JAN 26
]

DATE_TRIGGERS = [
    "manufactured on", "mfg date", "mfg dt", "date of mfg", "packed on",
    "mfg", "mfd", "pkd", "packed",
]


def check_mfg_date(label: LabelText) -> FieldResult:
    """A date-like pattern; a trigger phrase raises confidence but is not required.

    ASSUMPTION: SPEC_rule_checklist.md says a trigger phrase is not required for a
    pass, but also that ambiguous patterns "that could be a date or could be
    another number sequence" go to needs_review. Resolved by shape: a date with
    separators and a four-digit year, or one carrying a month name, is
    unambiguous and passes on its own. A short numeric form (MM/YY, "JAN 26") is
    genuinely ambiguous against a batch code, so it passes only when a trigger
    phrase disambiguates it, and goes to review otherwise rather than guessing.
    """
    weak_candidate: tuple[str, OCRResult | None] | None = None
    low_confidence_candidate: tuple[str, OCRResult | None] | None = None

    for pattern in STRONG_DATE_RES:
        for match in pattern.finditer(label.text):
            region = label.region_for_span(match.start(), match.end())
            confidence = _confidence_of(region)
            matched = match.group(0).strip()

            if confidence is not None and confidence < LOW_CONFIDENCE:
                if low_confidence_candidate is None:
                    low_confidence_candidate = (matched, region)
                continue

            trigger = _trigger_near(label, match.start(), match.end(), DATE_TRIGGERS)
            note = f'Declared with trigger phrase "{trigger}".' if trigger else None
            return FieldResult("mfg_date", PASS, matched, confidence, note=note)

    for pattern in WEAK_DATE_RES:
        for match in pattern.finditer(label.text):
            region = label.region_for_span(match.start(), match.end())
            confidence = _confidence_of(region)
            matched = match.group(0).strip()
            trigger = _trigger_near(label, match.start(), match.end(), DATE_TRIGGERS)

            if trigger and (confidence is None or confidence >= LOW_CONFIDENCE):
                return FieldResult(
                    "mfg_date", PASS, matched, confidence,
                    note=f'Declared with trigger phrase "{trigger}".',
                )
            if weak_candidate is None:
                weak_candidate = (matched, region)

    if low_confidence_candidate is not None:
        matched, region = low_confidence_candidate
        return FieldResult(
            "mfg_date", NEEDS_REVIEW, matched, _confidence_of(region),
            note="A date was found but read with low confidence.",
        )

    if weak_candidate is not None:
        matched, region = weak_candidate
        return FieldResult(
            "mfg_date", NEEDS_REVIEW, matched, _confidence_of(region),
            note="This could be a manufacturing date or a batch code — no labelling "
                 "nearby to tell them apart. Confirm by eye.",
        )

    return FieldResult("mfg_date", FAIL, None, None, note="No manufacturing or packing date found.")


# --- Field 4: manufacturer address --------------------------------------------

ADDRESS_TRIGGERS = [
    "marketed by", "manufactured by", "mfd by", "packed by", "address",
]
PIN_RE = re.compile(r"\b\d{6}\b")


def check_manufacturer_address(label: LabelText) -> FieldResult:
    """An address trigger phrase with a 6-digit PIN code near it.

    Addresses are free text and defeat direct pattern matching, so the check is a
    two-part structural proxy: the declaration phrase that must legally precede an
    address, plus an Indian PIN code — a reliable structural marker that survives
    OCR noise in the rest of the address block.
    """
    triggers = _fuzzy_phrase_positions(label.text, ADDRESS_TRIGGERS)
    pins = list(PIN_RE.finditer(label.text))

    for t_start, t_end, phrase in triggers:
        for pin in pins:
            distance = min(abs(pin.start() - t_end), abs(t_start - pin.end()))
            if distance <= ADDRESS_WINDOW:
                lo, hi = min(t_start, pin.start()), max(t_end, pin.end())
                region = label.region_for_span(t_start, t_end)
                return FieldResult(
                    "manufacturer_address", PASS,
                    label.snippet(lo, hi), _confidence_of(region),
                    note=f'Address block located via "{phrase}" and PIN code {pin.group(0)}.',
                )

    if triggers:
        # Note on precedence: a trigger phrase with no PIN near it and a stray PIN
        # elsewhere satisfies both the fail and the needs_review condition in the
        # spec. The spec states the fail condition first and unconditionally
        # ("trigger phrase found but no PIN code nearby"), so trigger presence wins.
        _, _, phrase = triggers[0]
        return FieldResult(
            "manufacturer_address", FAIL, None, None,
            note=f'"{phrase}" appears on the label but no PIN code was found near it — '
                 "the address block looks incomplete.",
        )

    if pins:
        pin = pins[0]
        region = label.region_for_span(pin.start(), pin.end())
        return FieldResult(
            "manufacturer_address", NEEDS_REVIEW, pin.group(0), _confidence_of(region),
            note="A 6-digit number was found with no address wording near it. It may be "
                 "a PIN code or an unrelated number. Confirm by eye.",
        )

    return FieldResult(
        "manufacturer_address", FAIL, None, None,
        note="No manufacturer or packer address declaration found.",
    )


# --- Field 5: consumer care ---------------------------------------------------

PHONE_RES = [
    re.compile(r"\b1800[\s\-]?\d{2,4}[\s\-]?\d{3,4}\b"),  # toll free
    re.compile(r"\b[6-9]\d{9}\b"),  # 10-digit Indian mobile
    re.compile(r"\b0\d{2,4}[\s\-]\d{6,8}\b"),  # landline with STD code
]
EMAIL_RE = re.compile(r"[^\s|]+@[^\s|]+\.[^\s|]+")
CARE_TRIGGERS = ["consumer care", "customer care", "toll free", "helpline"]


def check_consumer_care(label: LabelText) -> FieldResult:
    """A phone number or email address.

    Per spec this field has no needs_review state: once a valid phone or email
    pattern matches, presence is unambiguous.
    """
    candidates: list[re.Match] = []
    for pattern in PHONE_RES:
        candidates.extend(pattern.finditer(label.text))
    candidates.extend(EMAIL_RE.finditer(label.text))

    for match in candidates:
        region = label.region_for_span(match.start(), match.end())
        trigger = _trigger_near(label, match.start(), match.end(), CARE_TRIGGERS)
        note = f'Declared with trigger phrase "{trigger}".' if trigger else None
        return FieldResult(
            "consumer_care", PASS, match.group(0).strip(), _confidence_of(region), note=note
        )

    return FieldResult(
        "consumer_care", FAIL, None, None,
        note="No consumer care phone number or email address found.",
    )


# --- Field 6: relative font size ----------------------------------------------

FONT_SIZE_CAVEAT = (
    "Declared text is unusually small relative to the rest of the label — manual "
    "verification recommended, not a certified measurement."
)

# ASSUMPTION: SPEC_rule_checklist.md defines relative height as a region's height
# divided by the tallest text height on the label, then says to flag text falling
# "in the bottom 20% compared to other detected text on the same label". That
# reads two ways: relative height at or below 0.20, or the bottom fifth of the
# label's height distribution.
#
# Taking the ratio reading, for two reasons. It is the more literal one — step 2
# of the spec defines the quantity being tested as a ratio, and step 4 tests "that
# relative height". And the percentile reading is unusable in practice: it flags
# a fifth of all regions by construction, whether or not anything on the label is
# actually anomalous. Most label text is set at one or two sizes, so on a
# perfectly ordinary label the percentile lands on the common height and flags
# every declaration set at it. That yields noise, not caution — it would push
# nearly every scan to needs_review and destroy the signal this check exists to
# carry. A ratio threshold flags text genuinely dwarfed by the rest of the label,
# which is the thing the Rules are concerned about.
FONT_SIZE_RATIO = 0.20

# Below a handful of regions there is not enough text to compare against.
MIN_REGIONS_FOR_FONT_CHECK = 5


def check_font_size(label: LabelText, matched_fields: list[FieldResult]) -> FieldResult:
    """Flag declarations printed disproportionately small.

    This is explicitly NOT a legal font-size measurement. The Rules specify
    minimum letter height in millimetres, scaled to the package's display panel
    area. Converting pixels to millimetres needs a physical size reference in the
    photo — a ruler, or a calibrated camera distance — which this system does not
    have and does not pretend to have.

    What it does instead: compares the height of each matched declaration against
    the other text on the same label, and flags anything unusually small for a
    human to check. It never returns fail, because it does not know millimetres.
    """
    heights = sorted(r.height_px for r in label.results if r.text.strip() and r.height_px > 0)

    if len(heights) < MIN_REGIONS_FOR_FONT_CHECK:
        return FieldResult(
            "font_size", PASS, None, None,
            note="Too few text regions on this label to compare relative text sizes.",
        )

    tallest = heights[-1]
    if tallest <= 0:
        return FieldResult("font_size", PASS, None, None, note="No measurable text regions.")

    small: list[tuple[str, float]] = []

    for result in matched_fields:
        if result.status == FAIL or not result.matched_text:
            continue
        region = _region_for_field(label, result)
        if region is None or region.height_px <= 0:
            continue
        relative = region.height_px / tallest
        if relative <= FONT_SIZE_RATIO:
            small.append((result.field_name, relative))

    if small:
        listed = ", ".join(
            f"{name.replace('_', ' ')} ({relative:.0%} of the largest text)"
            for name, relative in small
        )
        return FieldResult(
            "font_size", NEEDS_REVIEW, listed, None,
            note=FONT_SIZE_CAVEAT,
        )

    return FieldResult(
        "font_size", PASS, None, None,
        note="No declaration was printed unusually small relative to the rest of the label.",
    )


def _region_for_field(label: LabelText, result: FieldResult) -> OCRResult | None:
    """Find the OCR region a field's matched text came from."""
    if not result.matched_text:
        return None
    index = label.text.find(result.matched_text)
    if index == -1:
        # The match may be a reconstructed snippet spanning a separator; fall back
        # to its first word, which always came from a single region.
        first_word = result.matched_text.split()[0] if result.matched_text.split() else ""
        if not first_word:
            return None
        index = label.text.find(first_word)
        if index == -1:
            return None
        return label.region_for_span(index, index + len(first_word))
    return label.region_for_span(index, index + len(result.matched_text))


# --- orchestration ------------------------------------------------------------


def is_low_quality(results: list[OCRResult]) -> bool:
    """Too little text was read for any verdict to mean anything."""
    usable = [r for r in results if r.text.strip()]
    total_chars = sum(len(r.text.strip()) for r in usable)
    return len(usable) < MIN_REGIONS or total_chars < MIN_CHARS


def overall_status(fields: list[FieldResult]) -> str:
    if any(f.status == FAIL for f in fields):
        return NON_COMPLIANT
    if any(f.status == NEEDS_REVIEW for f in fields):
        return REVIEW
    return COMPLIANT


def check_compliance(ocr_results: list[OCRResult]) -> ComplianceReport:
    """Run all six checks and compute an overall verdict."""
    raw_text = "\n".join(r.text for r in ocr_results)

    # A blurry or dark photo must not be reported as a non-compliant product.
    if is_low_quality(ocr_results):
        fields = [
            FieldResult(name, NEEDS_REVIEW, None, None, note="Not assessed — image unreadable.")
            for name in FIELD_NAMES
        ]
        return ComplianceReport(REVIEW, fields, raw_text, message=LOW_QUALITY_MESSAGE)

    label = LabelText(ocr_results)
    fields = [
        check_mrp(label),
        check_net_quantity(label),
        check_mfg_date(label),
        check_manufacturer_address(label),
        check_consumer_care(label),
    ]
    fields.append(check_font_size(label, fields))

    return ComplianceReport(overall_status(fields), fields, raw_text)
