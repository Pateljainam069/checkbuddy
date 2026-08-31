# Legal Metrology Compliance Scanner — Project Context
(SIH26034 — Software System to check compliance of Packaged Commodities under Legal Metrology Rules, 2011)

## What this is
A web app (mobile + desktop browser, no native app) that lets a user:
1. Scan a product's barcode/QR code using the device camera
2. Photograph the product's label
3. Get an automated pass/fail compliance report against India's Legal Metrology (Packaged Commodities) Rules, 2011

This is a hackathon prototype for an internal round. Prioritize a working end-to-end flow over completeness or production polish. Functionality scope is intentionally LOW — see "Scope boundary" below.

## Read these specs before building anything, in this order
1. `SPEC_database.md` — Supabase schema (build this first, everything else depends on it)
2. `SPEC_rule_checklist.md` — the exact compliance checklist and matching logic. Read this carefully — it is regulatory content, not ordinary engineering, and it is not open to creative reinterpretation.
3. `SPEC_backend.md` — FastAPI service: OCR + rule engine + Supabase writes
4. `SPEC_frontend.md` — Next.js app: scan flow, camera capture, result display
5. `SPEC_tier1_roadmap.md` — future additions. NOT part of this build. Do not implement anything from this file unless explicitly asked to.

## Scope boundary — read this twice
Build ONLY the MVP flow: scan barcode → photograph label → OCR → rule check → save → show result → view history list.

Do NOT build: authentication, user roles, bulk upload, e-commerce URL scanning, analytics dashboards with charts, PDF export, or any third-party barcode-lookup API. These are explicitly out of scope for this build. They are documented in `SPEC_tier1_roadmap.md` as future phases only — do not pull work forward from that file.

## Tech stack
- Backend: Python, FastAPI, PaddleOCR, RapidFuzz
- Frontend: Next.js (App Router), TypeScript, Tailwind CSS, html5-qrcode
- Database/Storage: Supabase (Postgres + Storage). No Supabase Auth in this build.
- No paid APIs. No API keys except Supabase (provided separately — see below).

## Credentials
Supabase URL and keys are NOT yet available — I will provide them separately when ready.

Until then: create `.env.example` (backend) and `.env.local.example` (frontend) with the variable names listed in `SPEC_backend.md` / `SPEC_frontend.md`, but do not attempt to run anything that requires a live Supabase connection. Build and test the OCR + rule engine in isolation first — see `SPEC_backend.md`, Phase 1. That phase needs zero external credentials.

## Dependencies
Install everything needed automatically — don't pause to ask me to install packages manually. Use `pip install -r requirements.txt` (backend) and `npm install` (frontend). If a package needs a system-level dependency (e.g. PaddleOCR's PaddlePaddle backend), install it and note in your response what was needed, in case it needs to be repeated on another machine.

## How to run locally
- Backend: `uvicorn main:app --reload --port 8000` from `/backend`
- Frontend: `npm run dev` from `/frontend` (runs on `http://localhost:3000`)
- Both must run simultaneously for the app to work end to end.
- Deployment (Vercel / hosted backend) is NOT part of this build — local only for now.

## Build order
Follow the phase order inside `SPEC_backend.md` exactly. OCR accuracy must be validated in isolation (no UI, no API, no Supabase) before any rule engine or frontend work starts. Do not skip ahead to UI polish while the core OCR pipeline is unproven — this is the single biggest risk in the whole project and it must be de-risked first.

## Folder structure
```
/backend
  main.py
  ocr.py
  rules.py
  supabase_client.py
  requirements.txt
  schema.sql
  .env.example
/frontend
  app/
    page.tsx
    history/page.tsx
  components/
    BarcodeScanner.tsx
    LabelCapture.tsx
    ResultCard.tsx
  lib/
    supabaseClient.ts
    api.ts
  .env.local.example
/specs
  (this file + all SPEC_*.md files)
```

## When something is ambiguous
Don't silently guess on regulatory or business logic (checklist wording, pass/fail thresholds, what counts as "present"). Flag it and ask, or make the most conservative assumption and clearly comment it in code (`# ASSUMPTION: ...`) so it's visible for review later. Silent assumptions on the checklist logic are the one category of mistake that's expensive to discover late — everything else in this project is cheap to fix.
