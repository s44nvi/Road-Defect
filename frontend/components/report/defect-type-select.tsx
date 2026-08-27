"use client";

import { cn } from "@/lib/cn";
import { PotholeIcon, CrackIcon, PersonIcon, CheckCircleIcon } from "@/components/icons";
import type { DefectTypeKey } from "@/lib/defect-types";

// Exactly RoadSense's four supported citizen-report categories.
// All four are always clickable — the citizen can always change their
// selection. AI analysis may pre-select a category by passing `value`,
// but that is just an initial state, not a lock.
//
// NOTE: Manhole has been intentionally removed. Supported categories are:
// Pothole, Crack – Alligator, Crack – Longitudinal, Encroachment / Vendor.
const OPTIONS: {
  value: DefectTypeKey;
  label: string;
  description?: string;
  icon: typeof PotholeIcon;
}[] = [
  { value: "pothole", label: "Pothole", icon: PotholeIcon },
  {
    value: "alligator_crack",
    label: "Crack – Alligator",
    description: "Interconnected cracking pattern",
    icon: CrackIcon,
  },
  {
    value: "longitudinal_crack",
    label: "Crack – Longitudinal",
    description: "Along the road direction",
    icon: CrackIcon,
  },
  {
    value: "hawker_encroachment",
    label: "Encroachment / Vendor",
    description: "Vendors or structures encroaching on roads",
    icon: PersonIcon,
  },
];

export function DefectTypeSelect({
  value,
  onChange,
}: {
  /** The currently selected category — AI-pre-selected or citizen-chosen.
   * `null` before either has happened. */
  value: DefectTypeKey | null;
  /** Fires for any of the four categories. */
  onChange: (value: DefectTypeKey) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {OPTIONS.map((option) => {
        const selected = value === option.value;
        const Icon = option.icon;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              "relative flex flex-col items-center gap-2 rounded-xl border p-4 text-center transition-colors",
              selected
                ? "border-primary bg-primary/10"
                : "border-border-subtle hover:bg-surface-container-low",
            )}
          >
            <Icon className={cn("h-6 w-6", selected ? "text-primary" : "text-on-surface-variant")} />
            <span className="text-sm font-medium text-on-surface">{option.label}</span>
            {option.description && (
              <span className="text-xs leading-tight text-on-surface-variant">{option.description}</span>
            )}
            {selected && (
              <span className="absolute right-2 top-2 text-primary">
                <CheckCircleIcon className="h-4 w-4" />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
