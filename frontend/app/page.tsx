"use client";

import { useCallback, useState } from "react";
import BarcodeScanner from "@/components/BarcodeScanner";
import LabelCapture from "@/components/LabelCapture";
import ResultCard from "@/components/ResultCard";
import StepRail from "@/components/StepRail";
import { imageSrc, submitScan, type ScanResult } from "@/lib/api";

type Stage = "barcode" | "label" | "result";

export default function ScanFlow() {
  const [stage, setStage] = useState<Stage>("barcode");
  const [barcode, setBarcode] = useState<string | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleScan = useCallback((value: string) => {
    setBarcode(value);
    setStage("label");
  }, []);

  const handleSkip = useCallback(() => {
    setBarcode(null);
    setStage("label");
  }, []);

  async function check() {
    if (!photo) return;
    setChecking(true);
    setError(null);
    try {
      const scan = await submitScan(photo, barcode);
      setResult(scan);
      setStage("result");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "The check could not be completed. Is the backend running on port 8000?",
      );
    } finally {
      setChecking(false);
    }
  }

  function startOver() {
    setStage("barcode");
    setBarcode(null);
    setPhoto(null);
    setResult(null);
    setError(null);
  }

  const stepIndex = stage === "barcode" ? 0 : stage === "label" ? 1 : 2;

  return (
    <div>
      <StepRail current={stepIndex} />

      {stage === "barcode" && (
        <section className="pt-6">
          <h1 className="font-display text-[1.375rem] leading-tight font-bold">
            Scan the product barcode
          </h1>
          <p className="mt-2 max-w-prose text-[0.9375rem] text-(--ink-2)">
            The barcode identifies which product this label belongs to. It is optional —
            the compliance check runs on the label photo.
          </p>
          <div className="mt-5">
            <BarcodeScanner onScan={handleScan} onSkip={handleSkip} />
          </div>
        </section>
      )}

      {stage === "label" && (
        <section className="pt-6">
          <h1 className="font-display text-[1.375rem] leading-tight font-bold">
            Photograph the label
          </h1>
          <p className="mt-2 max-w-prose text-[0.9375rem] text-(--ink-2)">
            Get the printed declarations in frame and in focus. Everything the scanner
            reads comes from this one photo.
          </p>

          <div className="mt-3 flex items-baseline gap-3 border-y border-(--rule) py-2.5">
            <span className="marker">Barcode</span>
            <span className="readout text-[0.875rem]">
              {barcode ?? <span className="text-(--ink-3)">skipped</span>}
            </span>
          </div>

          <div className="mt-5">
            <LabelCapture onCapture={setPhoto} disabled={checking} />
          </div>

          {error && (
            <p
              className="mt-4 px-3 py-2.5 text-[0.875rem]"
              style={{ background: "var(--fail-ground)", color: "var(--fail)" }}
              role="alert"
            >
              {error}
            </p>
          )}

          <button
            type="button"
            onClick={check}
            disabled={!photo || checking}
            className="marker mt-4 w-full cursor-pointer py-4 disabled:cursor-not-allowed disabled:opacity-35"
            style={{
              background: "var(--ink)",
              color: "var(--ground)",
              borderRadius: "var(--radius-instrument)",
            }}
          >
            {checking ? "Reading the label…" : "Check this label"}
          </button>

          {checking && (
            <p className="mt-3 text-center text-[0.8125rem] text-(--ink-3)">
              Running text recognition. This takes a few seconds.
            </p>
          )}

          <button
            type="button"
            onClick={startOver}
            disabled={checking}
            className="marker mt-3 w-full cursor-pointer py-2 text-(--ink-3) hover:text-(--ink) disabled:opacity-40"
          >
            Start over
          </button>
        </section>
      )}

      {stage === "result" && result && (
        <section className="pt-6">
          <ResultCard
            animate
            overallStatus={result.overall_status}
            fields={result.fields}
            barcode={result.barcode}
            ocrRawText={result.ocr_raw_text}
            message={result.message}
            imageUrl={imageSrc(result.image_url)}
          />

          {result.scan_id === null && (
            <p className="marker mt-5 border-t border-(--rule) pt-4 text-(--ink-3)">
              This result was not saved — it will not appear in history.
            </p>
          )}

          <button
            type="button"
            onClick={startOver}
            className="marker mt-6 w-full cursor-pointer py-4"
            style={{
              background: "var(--ink)",
              color: "var(--ground)",
              borderRadius: "var(--radius-instrument)",
            }}
          >
            Check another product
          </button>
        </section>
      )}
    </div>
  );
}
