"use client";

import { useState } from "react";
import {
  FIELD_LABELS,
  FIELD_ORDER,
  type FieldResult,
  type OverallStatus,
} from "@/lib/api";
import StatusBadge, { statusToken } from "./StatusBadge";

/**
 * The inspection docket: a verdict impression over a ruled register of the six
 * declarations, one row each.
 *
 * Shared by the scan flow and the history detail view so a result reopened a week
 * later reads identically to the one that came off the camera.
 */

const VERDICT_LINE: Record<OverallStatus, string> = {
  compliant: "All six declarations were found and read cleanly.",
  non_compliant: "At least one required declaration is missing from this label.",
  needs_review: "This label needs a human to look at it.",
};

const SWATCH: Record<string, string> = {
  pass: "var(--pass)",
  fail: "var(--fail)",
  review: "var(--review)",
};

function orderFields(fields: FieldResult[]): FieldResult[] {
  const rank = new Map(FIELD_ORDER.map((name, index) => [name as string, index]));
  return [...fields].sort(
    (a, b) => (rank.get(a.field_name) ?? 99) - (rank.get(b.field_name) ?? 99),
  );
}

function countFailures(fields: FieldResult[]) {
  return {
    failed: fields.filter((f) => f.status === "fail").length,
    review: fields.filter((f) => f.status === "needs_review").length,
  };
}

export default function ResultCard({
  overallStatus,
  fields,
  barcode,
  ocrRawText,
  message,
  imageUrl,
  animate = false,
}: {
  overallStatus: OverallStatus;
  fields: FieldResult[];
  barcode: string | null;
  ocrRawText: string;
  message?: string | null;
  imageUrl?: string | null;
  animate?: boolean;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const ordered = orderFields(fields);
  const counts = countFailures(ordered);
  const accent = SWATCH[statusToken(overallStatus)];

  return (
    <section aria-label="Compliance result">
      {/* The verdict impression — the one moment of colour and the one animation. */}
      <div
        className={animate ? "impress" : undefined}
        style={{
          borderLeft: `6px solid ${accent}`,
          background: "var(--raised)",
          borderTop: "1px solid var(--rule)",
          borderRight: "1px solid var(--rule)",
          borderBottom: "1px solid var(--rule)",
        }}
      >
        <div className="px-4 py-5 sm:px-6">
          <p className="marker">Verdict</p>
          <h2
            className="font-display mt-1.5 text-[1.75rem] leading-none font-black uppercase sm:text-[2.25rem]"
            style={{ color: accent, letterSpacing: "0.02em" }}
          >
            {overallStatus.replace("_", "-")}
          </h2>
          <p className="mt-3 max-w-prose text-[0.9375rem] text-(--ink-2)">
            {VERDICT_LINE[overallStatus]}
          </p>

          {(counts.failed > 0 || counts.review > 0) && (
            <p className="readout mt-3 text-[0.8125rem] text-(--ink-3)">
              {counts.failed > 0 && `${counts.failed} missing`}
              {counts.failed > 0 && counts.review > 0 && " · "}
              {counts.review > 0 && `${counts.review} to review`}
              {" · "}
              {ordered.length} checked
            </p>
          )}

          {message && (
            <p
              className="mt-4 px-3 py-2.5 text-[0.875rem]"
              style={{
                background: "var(--sunken)",
                borderLeft: "3px solid var(--rule-strong)",
              }}
            >
              {message}
            </p>
          )}
        </div>
      </div>

      {/* The register. One ruled row per declaration. */}
      <dl className="mt-5">
        {ordered.map((field) => (
          <div
            key={field.field_name}
            className="grid grid-cols-[1fr_auto] items-start gap-x-3 gap-y-2 border-t border-(--rule) py-3.5"
          >
            <dt className="text-[0.9375rem] font-medium">
              {FIELD_LABELS[field.field_name] ?? field.field_name}
            </dt>
            <dd className="col-start-2 row-start-1">
              <StatusBadge status={field.status} />
            </dd>

            {(field.matched_text || field.note) && (
              <dd className="col-span-2 -mt-0.5">
                {field.matched_text && (
                  <p className="readout text-[0.8125rem] break-words text-(--ink-2)">
                    {field.matched_text}
                    {field.confidence != null && (
                      <span className="text-(--ink-3)">
                        {"  ·  "}
                        {(field.confidence * 100).toFixed(0)}% confidence
                      </span>
                    )}
                  </p>
                )}
                {field.note && (
                  <p className="mt-1 max-w-prose text-[0.8125rem] text-(--ink-3)">{field.note}</p>
                )}
              </dd>
            )}
          </div>
        ))}
      </dl>

      <div className="mt-5 space-y-3 border-t border-(--rule) pt-4">
        {barcode && (
          <div className="flex items-baseline gap-3">
            <span className="marker">Barcode</span>
            <span className="readout text-[0.875rem]">{barcode}</span>
          </div>
        )}

        {imageUrl && (
          <div>
            <p className="marker mb-2">Label photographed</p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageUrl}
              alt="The label that was checked"
              className="max-h-72 w-auto border border-(--rule)"
            />
          </div>
        )}

        {/*
          Showing exactly what the model read is what makes a verdict arguable
          rather than oracular. When a declaration is marked missing, this is
          where you find out whether the label omitted it or OCR missed it.
        */}
        {ocrRawText && (
          <div>
            <button
              type="button"
              onClick={() => setShowRaw((open) => !open)}
              className="marker cursor-pointer underline decoration-(--rule-strong) underline-offset-4 hover:text-(--ink)"
              aria-expanded={showRaw}
            >
              {showRaw ? "Hide what the scanner read" : "Show what the scanner read"}
            </button>
            {showRaw && (
              <pre
                className="readout mt-3 max-h-64 overflow-auto p-3 text-[0.75rem] leading-relaxed whitespace-pre-wrap"
                style={{ background: "var(--sunken)" }}
              >
                {ocrRawText}
              </pre>
            )}
          </div>
        )}
      </div>

      <p className="mt-6 max-w-prose border-t border-(--rule) pt-4 text-[0.75rem] leading-relaxed text-(--ink-3)">
        These six checks are a scoped subset of the Legal Metrology (Packaged
        Commodities) Rules, 2011, not the complete standard. CheckBuddy verifies that a
        required declaration is present and readable. It does not verify that a declared
        value is correct.
      </p>
    </section>
  );
}
