# Tier 1 Roadmap Spec — NOT part of the current build

## Purpose of this file
This documents what to build AFTER the MVP (`SPEC_backend.md` + `SPEC_frontend.md`) is fully working end to end. Do not implement anything in this file unless explicitly instructed — its purpose right now is to exist as a clear, credible answer when judges ask "what's next," not to be code.

---

## 1. Confidence-based review queue
**Status: partially already built into the MVP.** The `needs_review` status already exists per field in `SPEC_rule_checklist.md` and flows through to `scan_results.status`. The Tier 1 extension is a dedicated frontend view — a filtered list of all scans/fields currently sitting at `needs_review`, so a human reviewer has a single queue to work through, rather than needing to browse full history looking for ambiguous cases.

**Why it matters:** answers the first objection any judge will raise — "what happens when your OCR misreads a real MRP as missing?" Answer: it doesn't get auto-failed, it gets routed to a human.

## 2. Brand/manufacturer risk ranking
**Depends on:** enough real scan volume to be meaningful, and consistent `barcode` capture (this is why barcode scanning was added to the MVP flow — it gives a clean grouping key, since OCR-extracted manufacturer name text is too inconsistent to `GROUP BY` reliably).

**What it is:** a dashboard panel — `SELECT barcode, COUNT(*) FILTER (WHERE overall_status = 'non_compliant') FROM scans GROUP BY barcode ORDER BY count DESC` — surfacing which specific products/brands violate most often. This is the single highest-value addition: it turns the tool from "checks one product" into "tells an enforcement team where to focus limited inspection resources."

**Consider adding a lightweight `products` table at this stage** — `barcode` (primary key), `first_seen_at`, `scan_count` — if querying directly against `scans` becomes awkward at higher volume.

## 3. E-commerce listing URL scanner
**What it is:** an input field where a user pastes an Amazon/Flipkart product URL. Backend fetches the listing's product images (or a screenshot fallback if scraping is blocked), and runs them through the exact same OCR + rule engine already built for physical label photos. This is a new INPUT SOURCE feeding the existing pipeline, not a new pipeline — cheap to add once the core engine is proven.

**Stronger version — the actual comparison logic:** once this exists, compare the label-derived text (from a physical photo) against the listing-derived text for the SAME product (matched by barcode). Flag mismatches — e.g. package says ₹199, listing says ₹249; package says 500g, listing says 450g. This is a genuinely stronger finding than simple presence-checking, because it surfaces active inconsistency/deception rather than sloppy labeling. This requires both a physical photo and a listing scan of the same barcode to exist before it can run.

## 4. Bulk scan mode
**What it is:** upload multiple label images at once instead of one at a time, looping calls to the existing `POST /scan` backend endpoint. No new backend logic — just a frontend batch-upload UI and a results summary table instead of a single result card.

## 5. Geographic violation view
**What it is:** tag each scan with a self-reported city/state at upload time (a simple dropdown, not device geolocation — keep it low-friction), then a bar chart of violations by region. Skip a full interactive map; a bar chart carries the same narrative (regional enforcement targeting) for far less build cost.

## 6. Scheduled/automated e-commerce monitoring
**What it is:** the URL scanner (#3) running on a timer against a whole product category instead of one URL at a time, with alerts on new violations. This is real infrastructure work (a scheduler, a job queue, notification delivery) — genuinely out of scope for a hackathon. Present this as an architecture diagram in the pitch: "this is the same engine, triggered by a cron job instead of a click."

## 7. Self-certification API for e-commerce platforms
**What it is:** instead of scanning listings after they go live, a platform could call this system's API before publishing a listing and self-certify compliance — shifting enforcement from detection to prevention. Real third-party integration work, out of scope. One pitch slide, not a feature.

## 8. OCR feedback loop
**What it is:** when a human reviewer corrects a `needs_review` or wrongly-flagged case, feed that correction back to improve future OCR/matching accuracy. This needs a retraining or fine-tuning pipeline — a materially different project. Roadmap slide only.

## 9. Multi-language label support
**What it is:** Indian packaging is frequently bilingual (English + Hindi or a regional language), and PaddleOCR does support other language models. Auto-detecting script and switching OCR models adds real complexity. Worth testing once the English pipeline (the MVP) is solid and stable — if time runs out before this can be attempted, it's an honest, well-justified roadmap item, not a gap to hide.

---

## How to use this file in the pitch
Present three honest tiers to judges: what's live in the demo (MVP), what's architected but deliberately not built yet (this file, with a one-line reason per item), and what's genuinely future scope (items 6–8). That distinction — stated clearly rather than glossed over — is usually what separates a team that "built a feature" from a team that "understood the problem."
