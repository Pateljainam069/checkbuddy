<img src="Logo.png" alt="CheckBuddy" width="120" />

# CheckBuddy

Photograph a packaged product label, get a pass/fail report against six declarations required by India's Legal Metrology (Packaged Commodities) Rules, 2011.

Built for SIH26034. Prototype, browser-only, runs locally.

**Stack:** FastAPI + PaddleOCR backend, Next.js 16 / React 19 frontend, SQLite locally with an optional Supabase (Postgres + Storage) swap.

## Get the code

```bash
git clone https://github.com/Pateljainam069/checkbuddy.git
cd checkbuddy
```

The backend and frontend are two independent processes that both need to be running at once — see the two quick-start sections below. Neither depends on the other being installed first, so the backend and frontend team can each start with the section that's theirs.

## Backend team quick start

Requires **Python 3.11**. Not 3.13 or 3.14 — `paddlepaddle` publishes no wheels for 3.14, and the `python` on this machine's PATH is a uv shim without pip.

```bash
cd backend
py -3.11 -m venv .venv          # or: <path-to-python311>\python.exe -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/uvicorn.exe main:app --reload --port 8000
```

The first OCR run downloads about 100MB of PaddleOCR models and takes a few minutes. Every run after that reads them from `~/.paddlex/official_models`. If the download stalls on "Checking connectivity to the model hosters", set `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` and rerun.

The server comes up on `http://localhost:8000` (`/health` for a liveness check). By default — no `backend/.env` — it stores everything locally: SQLite at `backend/data/checkbuddy.db`, images in `backend/uploads/`. Nothing needs to be configured to start working. See [Supabase](#supabase) below if you want the shared Postgres backend instead.

To touch only the rule-checking logic (`rules.py`) without installing paddle at all:

```bash
cd backend && .venv/Scripts/python.exe test_rules.py
```

Read [Layout](#layout) for what each backend file owns, and [Known gaps](#known-gaps) before tightening any regex in `rules.py`.

## Frontend team quick start

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_BACKEND_URL already points at localhost:8000
npm run dev        # http://localhost:3000
```

The backend must be running (see above) for the scan flow and history pages to return real data — the frontend has no mock mode.

`npm run dev` and `npm run build` both pass `--webpack`. Windows Application Control blocks Next's native SWC binary when the project sits on the `A:` drive, and Turbopack cannot run on the WASM fallback. On a machine without that policy, drop the flag.

Read [Layout](#layout) below for what each frontend folder owns.

## What it checks

Six declarations, each returning `pass`, `fail`, or `needs_review`:

| Field | How it is matched |
|---|---|
| `mrp` | A rupee or MRP indicator next to a number, on the same printed line. Fuzzy on the indicator, because OCR reads "MRP" as "MPR" and "MEP" constantly. |
| `net_quantity` | A number followed by `g`, `kg`, `mg`, `ml`, `l`, `ltr` or a spelled-out litre. |
| `mfg_date` | A date with separators and a four-digit year, or one carrying a month name. Short forms like `03/26` pass only when a trigger phrase such as MFG or PKD sits near them, otherwise they go to review — `03/26` is as likely to be a batch code. |
| `manufacturer_address` | A declaration phrase ("Marketed by", "Mfd by") with a 6-digit PIN code within 200 characters. Addresses are free text and defeat direct matching; a PIN code is a structural marker that survives OCR noise. |
| `consumer_care` | An Indian mobile, a landline with STD code, a 1800 number, or an email address. |
| `font_size` | See below. |

Any `fail` makes the label non-compliant. Otherwise any `needs_review` makes it needs-review. Otherwise compliant.

## Two things this deliberately does not do

**It does not check whether a declared value is correct.** There is no reference database of true MRPs or true weights to compare against. CheckBuddy answers "is the declaration present and readable", not "is it honest". Comparing a label against an e-commerce listing for the same barcode would catch active deception, and it is scoped in `spec-files/SPEC_tier1_roadmap.md`, but it is not built here.

**It does not measure font size in millimetres.** The Rules specify a minimum letter height in millimetres, scaled to the package's display panel area. Converting pixels to millimetres needs a physical size reference in the photo, a ruler or a calibrated camera distance. There is none. So `font_size` compares each matched declaration against the tallest text on the same label and flags anything at or under 20% of it for a human to look at. It returns `pass` or `needs_review` and never `fail`, because it does not know millimetres.

Say both of these plainly in the demo. They hold up better than a fake-precise number does under a question.

The six checks are a scoped subset of the Rules, not the complete standard.

## Supabase

Not connected yet. With `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` empty, the backend writes to SQLite at `backend/data/checkbuddy.db` and stores images in `backend/uploads/`. The scan flow and the history page both work in that mode; nothing is stubbed.

To connect it:

1. Run `backend/schema.sql` in the Supabase SQL editor. It creates both tables and the `label-photos` bucket.
2. Copy `backend/.env.example` to `backend/.env` and fill in the two values.
3. Restart uvicorn. It logs which backend is live on startup.

The local SQLite tables mirror `schema.sql` column for column, so switching is a `.env` edit rather than a migration.

The service role key is backend-only. RLS is disabled on both tables and the bucket is world-readable, which is fine for a local prototype and unsafe for anything else. `schema.sql` says so at the top.

## Layout

```
backend/
  ocr.py          PaddleOCR wrapper. Also a CLI: python ocr.py photo.jpg
  rules.py        The six checks. Pure — no I/O, no paddle import.
  storage.py      Supabase or SQLite behind one interface.
  main.py         POST /scan, GET /history, GET /scan/{id}, GET /health
  schema.sql      Tables, bucket, and an RLS warning.
  test_rules.py   16 checklist tests, runnable without paddle installed.
  test-images/    Synthetic labels. Put real photos here.
frontend/
  app/            Scan flow, history list, history detail.
  components/     BarcodeScanner, LabelCapture, ResultCard, StatusBadge, StepRail.
  lib/api.ts      Typed backend client.
spec-files/       The specs this was built from.
```

`rules.py` imports only the `OCRResult` dataclass from `ocr.py`, and `ocr.py` imports paddle lazily inside its loader. So the rule engine and its tests run with paddle absent:

```bash
cd backend && .venv/Scripts/python.exe test_rules.py
```

That separation is the point. OCR accuracy and checklist correctness are different problems and fail for different reasons, and mixing them makes both harder to debug.

## Known gaps

**The regexes are untuned.** They were written from the spec and tested against synthetic labels rendered with Pillow. Real packaging is gloss, curvature, low-contrast print, and text wrapped around a cylinder. Every pattern in `rules.py` is grouped under one `tunables` heading because they will need tuning against real photos. Until that happens, accuracy on actual products is unproven.

**English only.** Indian packaging is frequently bilingual. PaddleOCR ships models for other scripts, but detecting the script and switching models is real work and is not done here.

**MRP must be on one line.** The indicator and its number have to land in the same detected text region. If OCR splits "MRP ₹45" across two regions, the check misses it and reports a fail. The alternative — searching a character window across the whole label — let the last four digits of a consumer care phone number pair with an "MRP" printed on the line below it, and report a price of 4567. A reviewable miss beats a confident wrong answer.

**No auth.** By design for this build. Anyone who can reach the backend can read every scan.

## What's remaining

Nothing below is built. Full detail and rationale for each is in `spec-files/SPEC_tier1_roadmap.md` — this is the short version so the team has one place to see what's next without opening it.

**Worth building first:**

- **Review queue.** A dedicated frontend view filtered to everything sitting at `needs_review`, so a human reviewer has one list to work rather than paging through full history. The `needs_review` status already exists end to end (`SPEC_rule_checklist.md` → `scan_results.status`) — this is a view on data that's already there, not new backend logic.
- **Brand/manufacturer risk ranking.** `GROUP BY barcode` over non-compliant scans, surfaced as a dashboard panel. This is the highest-value addition — it turns the tool from "checks one product" into "tells an enforcement team where to focus limited inspection resources." Depends on real scan volume and consistent barcode capture (which is why barcode scanning is already in the MVP flow).

**Reasonable next after that:**

- **E-commerce listing URL scanner.** Paste an Amazon/Flipkart URL, run its listing images through the same OCR + rule pipeline already built for photos. The stronger version compares label-derived text against listing-derived text for the same barcode and flags mismatches (package says ₹199, listing says ₹249) — actual deception detection, not just presence-checking. Needs both a physical scan and a listing scan of the same product to exist first.
- **Bulk scan mode.** Upload multiple labels at once, looping the existing `POST /scan` endpoint. No new backend logic, just a batch-upload UI and a summary table.
- **Geographic violation view.** Self-reported city/state at upload time (a dropdown, not device geolocation), then a bar chart of violations by region.

**Real infrastructure work, out of scope for now — pitch-slide only:**

- Scheduled/automated e-commerce monitoring (the URL scanner above, on a cron, with alerts).
- Self-certification API for e-commerce platforms to check compliance before a listing goes live.
- OCR feedback loop — reviewer corrections feeding back into matching accuracy. This is a retraining pipeline, a materially different project.
- Multi-language label support. Indian packaging is frequently bilingual; PaddleOCR has models for other scripts, but script detection and model switching is real work, worth attempting once the English pipeline is solid.
