/**
 * Backend client.
 *
 * Every screen reads through here so the shape of a scan is defined once. The
 * field names mirror the API in SPEC_backend.md exactly — renaming them on the
 * way in would only make the two halves harder to compare when something breaks.
 */

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export type FieldStatus = "pass" | "fail" | "needs_review";
export type OverallStatus = "compliant" | "non_compliant" | "needs_review";

export const FIELD_ORDER = [
  "mrp",
  "net_quantity",
  "mfg_date",
  "manufacturer_address",
  "consumer_care",
  "font_size",
] as const;

export type FieldName = (typeof FIELD_ORDER)[number];

/** Plain-language names. The API's snake_case is a database concern, not a label. */
export const FIELD_LABELS: Record<string, string> = {
  mrp: "Maximum retail price",
  net_quantity: "Net quantity",
  mfg_date: "Manufacturing date",
  manufacturer_address: "Manufacturer address",
  consumer_care: "Consumer care details",
  font_size: "Relative text size",
};

export interface FieldResult {
  field_name: string;
  status: FieldStatus;
  matched_text: string | null;
  confidence: number | null;
  note: string | null;
}

export interface ScanResult {
  scan_id: string | null;
  barcode: string | null;
  image_url: string | null;
  overall_status: OverallStatus;
  fields: FieldResult[];
  ocr_raw_text: string;
  message: string | null;
}

export interface HistoryEntry {
  id: string;
  barcode: string | null;
  overall_status: OverallStatus;
  image_url: string | null;
  created_at: string;
}

export interface ScanDetail {
  id: string;
  barcode: string | null;
  image_url: string | null;
  ocr_raw_text: string;
  overall_status: OverallStatus;
  created_at: string;
  fields: FieldResult[];
}

/** Local storage returns a relative /uploads path; Supabase returns an absolute URL. */
export function imageSrc(url: string | null | undefined): string | null {
  if (!url) return null;
  return url.startsWith("http") ? url : `${BASE}${url}`;
}

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // Non-JSON error body; the status line is all we have.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function submitScan(image: Blob, barcode: string | null): Promise<ScanResult> {
  const form = new FormData();
  form.append("image", image, "label.jpg");
  if (barcode) form.append("barcode", barcode);

  const response = await fetch(`${BASE}/scan`, { method: "POST", body: form });
  return unwrap<ScanResult>(response);
}

export async function fetchHistory(): Promise<HistoryEntry[]> {
  return unwrap<HistoryEntry[]>(await fetch(`${BASE}/history`, { cache: "no-store" }));
}

export async function fetchScan(scanId: string): Promise<ScanDetail> {
  return unwrap<ScanDetail>(await fetch(`${BASE}/scan/${scanId}`, { cache: "no-store" }));
}
