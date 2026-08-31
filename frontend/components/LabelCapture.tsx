"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Label photo capture.
 *
 * A plain file input with capture="environment" opens the rear camera directly on
 * both Android Chrome and iOS Safari, and falls back to the file picker on
 * desktop. That covers every demo device without a second camera library.
 */

export default function LabelCapture({
  onCapture,
  disabled,
}: {
  onCapture: (file: File | null) => void;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);

  // Object URLs hold the photo in memory until explicitly released.
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  function handleFile(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (preview) URL.revokeObjectURL(preview);
    setPreview(file ? URL.createObjectURL(file) : null);
    onCapture(file);
  }

  function retake() {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    onCapture(null);
    if (inputRef.current) inputRef.current.value = "";
    inputRef.current?.click();
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFile}
        className="sr-only"
        id="label-photo"
      />

      {preview ? (
        <div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={preview}
            alt="The label you photographed"
            className="w-full border border-(--rule)"
          />
          <button
            type="button"
            onClick={retake}
            disabled={disabled}
            className="marker mt-4 w-full cursor-pointer border border-(--rule-strong) py-3.5 hover:bg-(--sunken) disabled:cursor-not-allowed disabled:opacity-40"
            style={{ borderRadius: "var(--radius-instrument)" }}
          >
            Retake photo
          </button>
        </div>
      ) : (
        <label
          htmlFor="label-photo"
          className="flex min-h-[240px] cursor-pointer flex-col items-center justify-center gap-2 border border-dashed border-(--rule-strong) px-6 text-center"
          style={{ background: "var(--sunken)" }}
        >
          <span className="marker">Photograph the label</span>
          <span className="max-w-[36ch] text-[0.875rem] text-(--ink-2)">
            Fill the frame with the printed declarations — price, weight, date, address.
          </span>
        </label>
      )}
    </div>
  );
}
