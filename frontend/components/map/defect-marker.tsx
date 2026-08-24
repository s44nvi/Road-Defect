import { cn } from "@/lib/cn";
import { normalizeDefectType } from "@/lib/defect-types";
import { normalizeSeverity, type Severity } from "@/components/ui/severity-badge";
import { PotholeIcon, CrackIcon, DebrisIcon, ManholeIcon } from "@/components/icons";

const typeIcon = {
  pothole: PotholeIcon,
  road_crack: CrackIcon,
  road_debris: DebrisIcon,
  manhole: ManholeIcon,
} as const;

const severityDotClass: Record<Severity, string> = {
  critical: "bg-error border-error",
  medium: "bg-tertiary border-tertiary",
  low: "bg-inverse-primary border-inverse-primary",
};

export function DefectMarker({
  defectType,
  severity,
  selected,
}: {
  defectType: string;
  severity: string;
  selected?: boolean;
}) {
  const typeKey = normalizeDefectType(defectType);
  const Icon = typeKey ? typeIcon[typeKey] : PotholeIcon;
  const severityKey = normalizeSeverity(severity) ?? "low";

  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-full border-2 text-on-primary shadow-card transition-transform",
        severityDotClass[severityKey],
        selected ? "h-9 w-9 scale-110 ring-2 ring-on-surface/30" : "h-7 w-7",
      )}
    >
      <Icon className="h-3.5 w-3.5" stroke="white" />
    </div>
  );
}
