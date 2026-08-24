"use client";

import { cn } from "@/lib/cn";
import type { Severity } from "@/components/ui/severity-badge";

// defect_severity is a required field on POST /reports (see
// backend/app/schemas.py::ReportCreate). There's no backend inference for
// it from a photo either, so the citizen sets it directly here.
const OPTIONS: { value: Severity; label: string; dotClass: string }[] = [
  { value: "critical", label: "Critical", dotClass: "bg-error" },
  { value: "medium", label: "Medium", dotClass: "bg-tertiary" },
  { value: "low", label: "Low", dotClass: "bg-inverse-primary" },
];

export function SeveritySelect({
  value,
  onChange,
}: {
  value: Severity | null;
  onChange: (value: Severity) => void;
}) {
  return (
    <div className="grid grid-cols-3 gap-3">
      {OPTIONS.map((option) => {
        const selected = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              "flex items-center justify-center gap-2 rounded-lg border p-3 text-sm font-medium transition-colors",
              selected
                ? "border-primary bg-primary/10 text-on-surface"
                : "border-border-subtle text-on-surface-variant hover:bg-surface-container-low",
            )}
          >
            <span className={cn("h-2.5 w-2.5 rounded-full", option.dotClass)} />
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
