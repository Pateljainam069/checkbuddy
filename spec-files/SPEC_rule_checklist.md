# Rule Checklist Spec — Legal Metrology Compliance Logic

## Read this before writing any matching code
This file defines what "compliant" means. It is the actual product, not boilerplate — the OCR and the UI only exist to serve this logic correctly. Do not loosen or tighten a pass/fail condition without flagging it; these six checks are a deliberately scoped, defensible subset of the full Legal Metrology (Packaged Commodities) Rules, 2011 — not the complete legal standard. State that limitation plainly in the demo, don't paper over it.

## Design principle: presence-checking, not comparison
This system checks whether a required declaration is PRESENT and readable on the label. It does not verify that a declared value (e.g. the MRP number) is factually correct — there is no reference database of "correct" values to check against. Be precise about this distinction if asked by judges: this is a completeness/readability checker, not a fraud-detection system. (A comparison-based fraud check — label text vs. e-commerce listing text — is a real, stronger idea, but it's scoped separately in `SPEC_tier1_roadmap.md`.)

## Overall status computation
Given the per-field results below:
- If ANY field is `fail` → `overall_status = non_compliant`
- Else if ANY field is `needs_review` → `overall_status = needs_review`
- Else → `overall_status = compliant`

---

## Field 1: `mrp` (Maximum Retail Price)
**What counts as present:** a rupee indicator (`₹`, `Rs`, `Rs.`, `INR`, or the literal text `MRP`/`M.R.P.`) immediately followed or preceded by a numeric value.

**Matching approach:** regex for the rupee/MRP indicator within a small character window of a number pattern (e.g. `\d+(\.\d{1,2})?`). Use fuzzy matching (RapidFuzz) on the indicator text itself, since OCR frequently misreads "MRP" as "MPR", "MEP", etc.

**Pass:** at least one such pattern found.
**Fail:** none found.
**needs_review:** a candidate match exists but at OCR confidence below 0.5.

---

## Field 2: `net_quantity`
**What counts as present:** a number followed by a standard unit — `g`, `gm`, `gms`, `kg`, `mg`, `ml`, `l`, `ltr`, `litre` (case-insensitive) — optionally preceded by a trigger phrase (`net`, `net wt`, `net weight`, `net qty`, `net quantity`).

**Matching approach:** regex for `\d+\s?(g|gm|gms|kg|mg|ml|l|ltr)` with fuzzy trigger-phrase detection nearby (not required, but boosts confidence when present).

**Pass:** at least one number+unit pattern found.
**Fail:** none found.
**needs_review:** pattern found only via OCR text below 0.5 confidence.

---

## Field 3: `mfg_date`
**What counts as present:** a date-like pattern, optionally preceded by a trigger phrase (`MFG`, `MFD`, `Mfg Date`, `Packed on`, `PKD`, `Manufactured on`).

**Matching approach:** regex covering common formats — `MM/YYYY`, `MM-YYYY`, `DD/MM/YYYY`, and month-name + year (`JAN 2026`, `January 2026`). Trigger phrase not required for a pass (dates are often printed without an explicit label), but its presence should raise confidence.

**Pass:** at least one date-like pattern found.
**Fail:** none found.
**needs_review:** ambiguous pattern that could be a date or could be another number sequence (e.g. a batch code) — don't force a guess, mark for human review instead.

---

## Field 4: `manufacturer_address`
**What counts as present:** this is the hardest field to pattern-match since addresses are free text. Use a two-part heuristic:
1. A trigger phrase is present: `Marketed by`, `Manufactured by`, `Mfd by`, `Packed by`, `Address`
2. AND a 6-digit PIN code pattern (`\d{6}`) is found within a reasonable character window of that trigger phrase — this is a strong, easy-to-detect proxy for "a real address block is here," since Indian PIN codes are a reliable structural marker even when the rest of the address text is OCR-noisy.

**Pass:** both conditions met.
**Fail:** trigger phrase found but no PIN code nearby, or neither found.
**needs_review:** PIN code found but no trigger phrase nearby (ambiguous — could be an unrelated 6-digit number).

---

## Field 5: `consumer_care`
**What counts as present:** a phone number pattern (10-digit Indian mobile, or a landline with STD code) OR an email pattern (`\S+@\S+\.\S+`), optionally near a trigger phrase (`consumer care`, `customer care`, `toll free`, `helpline`).

**Pass:** a phone number or email pattern found.
**Fail:** neither found.
**needs_review:** not applicable for this field — presence detection is unambiguous once a valid pattern is matched.

---

## Field 6: `font_size` — READ THIS SECTION CAREFULLY, IT IS AN APPROXIMATION
**Legal reality (confirmed from the actual Rules):** minimum letter height is specified in millimeters and scales with the package's principal display panel area / net quantity (e.g. 1mm minimum for small packages under 200g/ml, more for larger packages, 2mm minimum where text is blown/molded/embossed). Measuring this correctly requires converting pixel measurements to real-world millimeters, which requires a known physical size reference in the photo (e.g. a ruler, or a calibrated camera distance). This MVP does not have that, and should not pretend to.

**What we're actually building instead — an honest heuristic:**
1. For every text region PaddleOCR detects on the label, record its bounding-box height in pixels.
2. Compute the relative height of each region = its height ÷ the tallest detected text height on that same label.
3. For any of the five fields above (1–5) that WAS successfully matched, check the relative height of the matched text region.
4. If that relative height falls in the bottom 20% compared to other detected text on the same label → mark `font_size` status as `needs_review` for that scan, with a note: "declared text is unusually small relative to the rest of the label — manual verification recommended, not a certified measurement."
5. If no field's matched text is unusually small → `font_size` status is `pass`.
6. This check never returns `fail` — only `pass` or `needs_review`. It is a flag for a human, never an automatic legal verdict, because it does not know real-world millimeters.

**In the demo, describe this exactly as above** — "we flag disproportionately small text for manual review, we don't claim to measure millimeters without a calibration reference." This is honest engineering, and it reads far better to judges than a fake-precise number would if questioned.

---

## Regex patterns are starting points, not final
The exact patterns above should be tuned against real OCR output from `SPEC_backend.md` Phase 1 testing — real product photos will surface OCR quirks (misread characters, merged words, extra whitespace) that no amount of upfront pattern design can fully anticipate. Expect to iterate this file after Phase 1 testing, not before.
