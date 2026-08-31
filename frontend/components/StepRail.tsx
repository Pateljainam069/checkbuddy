/**
 * Progress through the scan.
 *
 * Numbered because the flow genuinely is a sequence — you cannot photograph a
 * label before deciding about the barcode, and the result cannot exist before the
 * photo. The numbers carry order the reader needs; they are not ornament.
 */

const STEPS = ["Barcode", "Label", "Result"] as const;

export default function StepRail({ current }: { current: 0 | 1 | 2 }) {
  return (
    <ol className="flex items-stretch border-y border-(--rule)">
      {STEPS.map((label, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li
            key={label}
            className="flex-1 border-r border-(--rule) px-3 py-2.5 last:border-r-0"
            style={{ background: active ? "var(--raised)" : "transparent" }}
            aria-current={active ? "step" : undefined}
          >
            <div className="flex items-baseline gap-2">
              <span
                className="readout text-[0.6875rem] font-medium"
                style={{ color: active || done ? "var(--ink)" : "var(--ink-3)" }}
              >
                {done ? "✓" : String(index + 1).padStart(2, "0")}
              </span>
              <span
                className="marker"
                style={{ color: active ? "var(--ink)" : undefined }}
              >
                {label}
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
