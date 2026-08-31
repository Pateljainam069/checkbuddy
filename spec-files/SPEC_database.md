# Database Spec — Supabase Schema

## Overview
Two tables. Keep it flat and simple — no auth tables, no separate `products` table for MVP (see `SPEC_tier1_roadmap.md` for why a products table might be added later, once barcode-based product grouping matters).

## Table: `scans`
One row per completed scan attempt (one barcode + one label photo).

| Column | Type | Notes |
|---|---|---|
| id | uuid, primary key, default `gen_random_uuid()` | |
| barcode | text, nullable | raw string decoded from the QR/barcode step. Nullable — a scan must be able to proceed even if the barcode step is skipped or fails; don't hard-block the flow on it |
| image_url | text | path/URL to the label photo in Supabase Storage |
| ocr_raw_text | text | full raw text PaddleOCR extracted, stored for debugging and so judges can see "what the model actually read" if asked |
| overall_status | text | one of: `compliant`, `non_compliant`, `needs_review` — computed by the backend at write time, see `SPEC_backend.md` |
| created_at | timestamptz | default `now()` |

## Table: `scan_results`
One row per checklist field per scan. This normalized shape (rather than one wide row) is what makes any future dashboard query (Tier 1) a simple GROUP BY instead of a rewrite.

| Column | Type | Notes |
|---|---|---|
| id | uuid, primary key, default `gen_random_uuid()` | |
| scan_id | uuid, foreign key → `scans.id`, on delete cascade | |
| field_name | text | one of: `mrp`, `net_quantity`, `mfg_date`, `manufacturer_address`, `consumer_care`, `font_size` — exact definitions in `SPEC_rule_checklist.md` |
| status | text | one of: `pass`, `fail`, `needs_review` |
| matched_text | text, nullable | the actual substring the rule engine matched, if any |
| confidence | float, nullable | OCR confidence score (0–1) for the region this field was matched in; nullable where not applicable (e.g. the font_size heuristic doesn't produce an OCR confidence value) |

## Storage bucket
Create a Supabase Storage bucket named `label-photos`, public read. Do not spend time on signed URLs or fine-grained access control for this MVP — it's a prototype, not a production system handling sensitive data.

## Row Level Security (RLS)
Disable RLS entirely for both tables in this build — there is no auth layer in the MVP (see scope boundary in `CLAUDE.md`). Add a code comment at the top of `schema.sql` noting RLS must be enabled before any real deployment, so this isn't forgotten later.

## Deliverable
Write the actual `CREATE TABLE` and bucket-creation statements as `schema.sql` inside `/backend`, so the schema is reproducible and reviewable — don't only create the tables by hand in the Supabase dashboard.
