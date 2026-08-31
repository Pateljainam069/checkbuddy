# Frontend Spec — Next.js App

## Responsibility
Two screens, browser-only (mobile + desktop), no native app, no Expo:
1. **Scan flow** (home page) — barcode/QR scan step → label photo step → submit → show result
2. **History** — list of past scans with their status

(A charts/analytics dashboard is Tier 1 — not built now. See `SPEC_tier1_roadmap.md`.)

## Pages

### `/` — Scan flow
Build as a step-by-step flow, not all fields on one screen — this matches how someone would actually use it standing in front of a product.

**Step 1: Barcode/QR scan.**
Use `html5-qrcode` to open the device camera and decode a barcode or QR code (the library handles both formats). On a successful scan, store the decoded value and move to Step 2 automatically.

Include a visible "Skip this step" button. The barcode is optional (see `SPEC_database.md` — `barcode` is nullable) — don't block the whole flow if scanning fails repeatedly or the product has no readable code.

Note for implementation: most packaged goods carry a standard 1D barcode (EAN/UPC), not a true QR code — `html5-qrcode` reads both, so this doesn't need separate handling, just don't assume every product will present a QR-style code specifically.

**Step 2: Label photo.**
Use a plain HTML file input with `capture="environment"` to open the rear camera directly — this works on both Android Chrome and iOS Safari with no extra library. Show a preview of the captured photo with a "retake" button before allowing submission.

**Step 3: Submit.**
POST the image (and barcode, if captured) to the backend `POST /scan` endpoint. Show a clear loading state — OCR can take a few seconds, and an unexplained pause reads as broken during a live demo.

**Step 4: Result.**
Display `overall_status` prominently, color-coded (green = compliant, red = non_compliant, amber = needs_review). Below that, a table of each checklist field with its status and matched text (or "not found" / "flagged for review" as appropriate — see `SPEC_rule_checklist.md` for what each status means per field, especially `font_size`, which should never be shown as a hard fail). Show the barcode value if one was captured.

### `/history`
List of past scans (call `GET /history`): thumbnail image, barcode (if present), overall status badge, timestamp. Tapping a row navigates to a detail view showing the full report (reuse `ResultCard`, fetched via `GET /scan/{scan_id}`).

## Components
- `BarcodeScanner.tsx` — wraps `html5-qrcode`, exposes an `onScan(value: string)` callback and a "skip" affordance
- `LabelCapture.tsx` — wraps the file input + camera capture + preview + retake
- `ResultCard.tsx` — renders the pass/fail table for a single scan result; reused on both the scan flow's Step 4 and the history detail view

## Dependencies (`package.json` additions)
```
html5-qrcode
@supabase/supabase-js
```
The Supabase client is optional here — either have the frontend call the backend's `GET /history` route, or query the `scans` table directly from the frontend using the anon key. Pick whichever is less code; both are fine for this MVP. If querying Supabase directly from the frontend, use ONLY the anon key — never the service role key client-side, that key must stay backend-only.

## Environment variables (`.env.local`)
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```
Values provided separately (see `CLAUDE.md`).

## Styling
Tailwind CSS. Keep it minimal and clean — this is a hackathon demo, not a design showcase. Prioritize working functionality and unambiguous pass/fail visual signaling (color, not just text) over visual polish. Mobile-first layout, since the primary demo device is a phone browser held up to a physical product.

## Explicitly out of scope for this build
No login/auth screens, no multi-user accounts, no bulk upload UI, no charts/analytics page, no e-commerce URL input. All of these are Tier 1 — see `SPEC_tier1_roadmap.md`.
