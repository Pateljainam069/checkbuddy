"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import StatusBadge from "@/components/StatusBadge";
import { fetchHistory, imageSrc, type HistoryEntry } from "@/lib/api";

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function History() {
  const [scans, setScans] = useState<HistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHistory()
      .then(setScans)
      .catch((err) =>
        setError(
          err instanceof Error
            ? err.message
            : "History could not be loaded. Is the backend running on port 8000?",
        ),
      );
  }, []);

  return (
    <div>
      <h1 className="font-display text-[1.375rem] leading-tight font-bold">Past checks</h1>
      <p className="mt-2 max-w-prose text-[0.9375rem] text-(--ink-2)">
        The 50 most recent scans, newest first.
      </p>

      {error && (
        <p
          className="mt-5 px-3 py-2.5 text-[0.875rem]"
          style={{ background: "var(--fail-ground)", color: "var(--fail)" }}
          role="alert"
        >
          {error}
        </p>
      )}

      {scans === null && !error && <p className="marker mt-6">Loading</p>}

      {scans?.length === 0 && (
        <div className="mt-6 border-t border-(--rule) pt-6">
          <p className="text-[0.9375rem] text-(--ink-2)">
            Nothing checked yet.{" "}
            <Link href="/" className="underline decoration-(--rule-strong) underline-offset-4">
              Scan a product
            </Link>{" "}
            and it will appear here.
          </p>
        </div>
      )}

      {scans && scans.length > 0 && (
        <ul className="mt-5">
          {scans.map((scan) => {
            const thumb = imageSrc(scan.image_url);
            return (
              <li key={scan.id} className="border-t border-(--rule) last:border-b">
                <Link
                  href={`/history/${scan.id}`}
                  className="flex items-center gap-3.5 py-3 hover:bg-(--raised)"
                >
                  <span
                    className="block h-14 w-14 shrink-0 overflow-hidden border border-(--rule)"
                    style={{ background: "var(--sunken)" }}
                  >
                    {thumb && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={thumb}
                        alt=""
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    )}
                  </span>

                  <span className="min-w-0 flex-1">
                    <span className="readout block truncate text-[0.875rem]">
                      {scan.barcode ?? <span className="text-(--ink-3)">no barcode</span>}
                    </span>
                    <span className="marker mt-1 block">{formatWhen(scan.created_at)}</span>
                  </span>

                  <StatusBadge status={scan.overall_status} />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
