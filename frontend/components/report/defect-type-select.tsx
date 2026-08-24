"use client";

import { cn } from "@/lib/cn";
import { PotholeIcon, CrackIcon, DebrisIcon, ManholeIcon, CheckCircleIcon } from "@/components/icons";
import type { DefectTypeKey } from "@/lib/defect-types";

// The RoadSense detection taxonomy is exactly these four types (see
// lib/defect-types.ts). There is no backend endpoint that infers a defect
// type from an uploaded photo — road_intelligence/analyze takes
// pre-computed YOLO detection output (class, confidence, bbox) as input,
// not a raw image — so the citizen picks the type manually instead of the
// UI pretending an AI model looked at the photo.
const OPTIONS: { value: DefectTypeKey; label: string; icon: typeof PotholeIcon }[] = [
  { value: "pothole", label: "Pothole", icon: PotholeIcon },
  { value: "road_crack", label: "Road Crack", icon: CrackIcon },
  { value: "road_debris", label: "Road Debris", icon: DebrisIcon },
  { value: "manhole", label: "Manhole", icon: ManholeIcon },
];

export function DefectTypeSelect({
  value,
  onChange,
}: {
  value: DefectTypeKey | null;
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
