"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Camera barcode/QR reader.
 *
 * Most packaged goods carry a 1D EAN/UPC barcode rather than a QR code;
 * html5-qrcode reads both, so no format branching is needed here.
 *
 * The skip control is deliberately as prominent as the scanner itself. A barcode
 * is optional — the compliance check runs on the label photo — and a shopper
 * fighting a scuffed barcode in bad light should never conclude the tool is
 * broken.
 */

const READER_ID = "barcode-reader";

export default function BarcodeScanner({
  onScan,
  onSkip,
}: {
  onScan: (value: string) => void;
  onSkip: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(true);
  // Guards against the decode callback firing again while teardown is in flight.
  const doneRef = useRef(false);

  useEffect(() => {
    let scanner: import("html5-qrcode").Html5Qrcode | null = null;
    let states: typeof import("html5-qrcode").Html5QrcodeScannerState | null = null;
    let cancelled = false;

    (async () => {
      try {
        const { Html5Qrcode, Html5QrcodeScannerState } = await import("html5-qrcode");
        if (cancelled) return;
        states = Html5QrcodeScannerState;

        scanner = new Html5Qrcode(READER_ID, { verbose: false });
        await scanner.start(
          { facingMode: "environment" },
          { fps: 10, qrbox: { width: 260, height: 160 } },
          (decoded) => {
            if (doneRef.current) return;
            doneRef.current = true;
            onScan(decoded);
          },
          () => {
            // Fires continuously for every frame without a code. Not an error.
          },
        );
        if (!cancelled) setStarting(false);
      } catch (err) {
        if (cancelled) return;
        setStarting(false);
        setError(
          err instanceof Error && err.name === "NotAllowedError"
            ? "Camera access was blocked. Allow it in your browser settings, or skip this step."
            : "The camera could not be started. Skip this step to carry on with a photo.",
        );
      }
    })();

    return () => {
      cancelled = true;
      const instance = scanner;
      scanner = null;
      if (!instance) return;

      // html5-qrcode's stop() THROWS SYNCHRONOUSLY ("Cannot stop, scanner is not
      // running or paused") when the camera never started, so a .catch() on the
      // returned promise never sees it — the throw escapes into React's unmount
      // and crashes the page. That is the common path, not an edge case: no
      // camera, or a denied permission, then the user taps Skip. Hence the state
      // check and the try/catch around it.
      try {
        const state = instance.getState();
        if (states && (state === states.SCANNING || state === states.PAUSED)) {
          instance.stop().then(() => instance.clear()).catch(() => {});
        } else {
          instance.clear();
        }
      } catch {
        // Never started; there is nothing to tear down.
      }
    };
  }, [onScan]);

  return (
    <div>
      <div
        className="relative overflow-hidden border border-(--rule)"
        style={{ background: "var(--sunken)" }}
      >
        <div id={READER_ID} className="min-h-[240px] w-full [&_video]:w-full" />
        {starting && !error && (
          <p className="marker absolute inset-0 flex items-center justify-center">
            Starting camera
          </p>
        )}
      </div>

      {error ? (
        <p className="mt-3 text-[0.875rem]" style={{ color: "var(--ink-2)" }}>
          {error}
        </p>
      ) : (
        <p className="mt-3 text-[0.875rem] text-(--ink-2)">
          Hold the barcode inside the frame. It reads on its own — there is nothing to press.
        </p>
      )}

      <button
        type="button"
        onClick={onSkip}
        className="marker mt-4 w-full cursor-pointer border border-(--rule-strong) py-3.5 hover:bg-(--sunken)"
        style={{ color: "var(--ink)", borderRadius: "var(--radius-instrument)" }}
      >
        Skip — check the label without a barcode
      </button>
    </div>
  );
}
