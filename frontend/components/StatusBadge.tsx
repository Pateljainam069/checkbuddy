import type { FieldStatus, OverallStatus } from "@/lib/api";

/**
 * The only place colour enters the interface.
 *
 * Status is never signalled by colour alone — each state carries a distinct mark
 * and a written word, so the verdict survives a monochrome screen, a colour-blind
 * reader, and a photograph of a phone taken across a table.
 */

type AnyStatus = FieldStatus | OverallStatus;

const STATUS = {
  pass: { word: "Pass", mark: "✓", token: "pass" },
  compliant: { word: "Compliant", mark: "✓", token: "pass" },
  fail: { word: "Fail", mark: "✕", token: "fail" },
  non_compliant: { word: "Non-compliant", mark: "✕", token: "fail" },
  needs_review: { word: "Needs review", mark: "!", token: "review" },
} as const satisfies Record<AnyStatus, { word: string; mark: string; token: string }>;

const SWATCH: Record<string, { fg: string; bg: string }> = {
  pass: { fg: "var(--pass)", bg: "var(--pass-ground)" },
  fail: { fg: "var(--fail)", bg: "var(--fail-ground)" },
  review: { fg: "var(--review)", bg: "var(--review-ground)" },
};

export function statusToken(status: AnyStatus) {
  return STATUS[status]?.token ?? "review";
}

export function statusWord(status: AnyStatus) {
  return STATUS[status]?.word ?? status;
}

export default function StatusBadge({ status }: { status: AnyStatus }) {
  const meta = STATUS[status] ?? STATUS.needs_review;
  const swatch = SWATCH[meta.token];

  return (
    <span
      className="marker inline-flex items-center gap-1.5 whitespace-nowrap px-2 py-1"
      style={{ color: swatch.fg, background: swatch.bg, borderRadius: "var(--radius-instrument)" }}
    >
      <span aria-hidden className="text-[0.8125rem] leading-none font-bold">
        {meta.mark}
      </span>
      {meta.word}
    </span>
  );
}
