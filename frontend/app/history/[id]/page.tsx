"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import ResultCard from "@/components/ResultCard";
import { fetchScan, imageSrc, type ScanDetail } from "@/lib/api";

/**
 * A saved scan, reopened.
 *
 * Renders through the same ResultCard as the live scan flow, so a result read a
 * week later is identical to the one that came off the camera — including the
 * notes that explain each verdict.
 */
export default function ScanDetailPage({ params }: PageProps<"/history/[id]">) {
  const { id } = use(params);
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchScan(id)
      .then(setScan)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "This scan could not be loaded."),
      );
  }, [id]);

  return (
    <div>
      <Link
        href="/history"
        className="marker underline decoration-(--rule-strong) underline-offset-4 hover:text-(--ink)"
      >
        ← All checks
      </Link>

      {error && (
        <p
          className="mt-5 px-3 py-2.5 text-[0.875rem]"
          style={{ background: "var(--fail-ground)", color: "var(--fail)" }}
          role="alert"
        >
          {error}
        </p>
      )}

      {!scan && !error && <p className="marker mt-6">Loading</p>}

      {scan && (
        <div className="mt-5">
          <ResultCard
            overallStatus={scan.overall_status}
            fields={scan.fields}
            barcode={scan.barcode}
            ocrRawText={scan.ocr_raw_text}
            imageUrl={imageSrc(scan.image_url)}
          />
        </div>
      )}
    </div>
  );
}
