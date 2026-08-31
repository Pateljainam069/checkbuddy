-- CheckBuddy — Supabase schema
-- Legal Metrology (Packaged Commodities) Rules, 2011 compliance scanner.
--
-- ============================================================================
-- SECURITY WARNING — READ BEFORE ANY REAL DEPLOYMENT
--
-- Row Level Security is DISABLED on both tables below, and the `label-photos`
-- bucket is world-readable. That is deliberate for this prototype: there is no
-- auth layer in the MVP, and the backend talks to Postgres with the service role
-- key. It is also completely unsuitable for anything running in public — anyone
-- with the anon key could read and write every scan.
--
-- Before deploying anywhere real: enable RLS on both tables, write policies,
-- and move the bucket to signed URLs.
-- ============================================================================

-- Run this in the Supabase SQL editor, or:
--   psql "$SUPABASE_DB_URL" -f schema.sql

create extension if not exists "pgcrypto";

-- One row per completed scan (one barcode + one label photo).
create table if not exists public.scans (
    id             uuid primary key default gen_random_uuid(),

    -- Nullable on purpose. A scan must be able to proceed when the barcode step
    -- is skipped or the product carries no readable code — the label photo is
    -- what the compliance check actually runs on.
    barcode        text,

    image_url      text,

    -- Everything OCR read, kept verbatim. This is what makes a verdict auditable:
    -- when a field is marked missing, this column shows whether the model failed
    -- to read it or the label genuinely omitted it.
    ocr_raw_text   text,

    overall_status text not null
                   check (overall_status in ('compliant', 'non_compliant', 'needs_review')),

    created_at     timestamptz not null default now()
);

-- One row per checklist field per scan.
--
-- Normalised rather than one wide row with six columns: this shape makes the
-- Tier 1 dashboard queries ("which field fails most often", "which barcode has
-- the most violations") a GROUP BY rather than a schema migration.
create table if not exists public.scan_results (
    id           uuid primary key default gen_random_uuid(),
    scan_id      uuid not null references public.scans(id) on delete cascade,

    field_name   text not null
                 check (field_name in ('mrp', 'net_quantity', 'mfg_date',
                                       'manufacturer_address', 'consumer_care', 'font_size')),

    status       text not null check (status in ('pass', 'fail', 'needs_review')),

    -- The actual substring the rule engine matched, where there was one.
    matched_text text,

    -- OCR confidence (0-1) for the region the match came from. Null where the
    -- check does not produce one — the font_size heuristic compares bounding-box
    -- geometry, not recognition confidence.
    confidence   double precision,

    -- ADDITION beyond SPEC_database.md, flagged rather than slipped in: the
    -- plain-language reason behind a status. SPEC_rule_checklist.md requires the
    -- font_size flag to carry its "not a certified measurement" caveat, and
    -- SPEC_frontend.md renders that text on both the result card and the history
    -- detail view. Without persisting it, a scan reopened from history loses the
    -- explanation that made its verdict defensible.
    note         text
);

create index if not exists idx_scan_results_scan_id on public.scan_results(scan_id);
create index if not exists idx_scans_created_at on public.scans(created_at desc);

-- See the security warning above.
alter table public.scans          disable row level security;
alter table public.scan_results   disable row level security;

-- Storage bucket for label photos, public read.
insert into storage.buckets (id, name, public)
values ('label-photos', 'label-photos', true)
on conflict (id) do nothing;
