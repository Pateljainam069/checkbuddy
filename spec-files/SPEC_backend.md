# Backend Spec — FastAPI Service

## Responsibility
This service does three things only:
1. Run PaddleOCR on an uploaded label image → return raw text + per-region confidence + bounding boxes
2. Run the rule engine (`SPEC_rule_checklist.md`) against that text → pass/fail/needs_review per field
3. Write the scan + results to Supabase, return the result to the frontend

## Build in this exact order — do not skip ahead

### Phase 1 — OCR in isolation, no API, no Supabase
Write a standalone script `ocr.py`, runnable directly: `python ocr.py path/to/image.jpg`

It should:
- Load PaddleOCR (`use_angle_cls=True`, English model to start — Indian packaging is often bilingual with Hindi/regional script, but do not build multilingual support now; leave a code comment noting it as a known gap)
- Run it on the given image path
- Print every detected `(text, confidence, bounding_box)` tuple to console, one per line, human-readable

I will run this manually against real product photos before anything else gets built. Do not write the rule engine or the API until I confirm OCR output quality is usable — this is the single highest-risk part of the whole project and it needs to be proven first.

### Phase 2 — Rule engine, still no API, no Supabase
Implement `rules.py` exactly per `SPEC_rule_checklist.md`. Structure it as a pure function:

```python
def check_compliance(ocr_results: list[OCRResult]) -> ComplianceReport:
    ...
```

Make this testable with hardcoded OCR output (no image, no PaddleOCR call needed) so the checklist logic can be verified independently of OCR accuracy. Write a handful of test cases directly in a `if __name__ == "__main__":` block or a simple test file — at minimum: one fully compliant label, one missing MRP, one missing address, one with an ambiguous/low-confidence match.

### Phase 3 — API endpoint
Single primary endpoint:

**`POST /scan`**
- Multipart form data: `image` (file, required), `barcode` (string, optional)
- Steps: save uploaded image to a temp path → run OCR (Phase 1 code) → run rule engine (Phase 2 code) → upload the image to Supabase Storage bucket `label-photos` → insert one row into `scans` and one row per field into `scan_results` → return the result

Response shape:
```json
{
  "scan_id": "uuid",
  "barcode": "8901030923019",
  "overall_status": "compliant | non_compliant | needs_review",
  "fields": [
    {"field_name": "mrp", "status": "pass", "matched_text": "₹199", "confidence": 0.94},
    {"field_name": "font_size", "status": "needs_review", "matched_text": null, "confidence": null}
  ],
  "ocr_raw_text": "..."
}
```

**`GET /history`**
- Returns the most recent 50 scans from the `scans` table (id, barcode, overall_status, image_url, created_at), most recent first. Used by the frontend history page.

**`GET /scan/{scan_id}`**
- Returns the full detail (scan + all its `scan_results` rows) for one scan — used when a user taps a row on the history page to see the full report again.

## Dependencies (`requirements.txt`)
```
fastapi
uvicorn[standard]
python-multipart
paddleocr
paddlepaddle
rapidfuzz
supabase
python-dotenv
```
Install the CPU build of PaddlePaddle — do not assume GPU availability in this environment.

## Environment variables (`.env`)
```
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```
Values provided separately (see `CLAUDE.md`). Use the service role key backend-side since there's no RLS/auth layer in this MVP — never expose this key to the frontend.

## Error handling
- If OCR returns near-empty text (blurry, dark, or heavily occluded photo), don't crash and don't force a `non_compliant` verdict. Return `overall_status: needs_review` with a `message` field explaining low image quality, so the frontend can prompt "please retake the photo" instead of showing a confusing false failure.
- If the Supabase write fails after OCR/rule-checking succeeded, still return the compliance result to the frontend — don't let a database hiccup block the live demo result. Log the failure server-side (print/log statement is fine for a hackathon).
- CORS: allow `http://localhost:3000` (and later, whatever the Vercel domain becomes) so the Next.js frontend can call this API directly during local development.
