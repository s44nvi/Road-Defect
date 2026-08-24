import { cn } from "@/lib/cn";

// Matches the map legend on the citizen home screen: a colored severity dot
// plus label. Backend `defect_severity` is a free-form string, so unknown
// values fall back to a neutral dot rather than guessing a color.
export type Severity = "critical" | "medium" | "low";

const severityDotClasses: Record<Severity, string> = {
  critical: "bg-error",
  medium: "bg-tertiary",
  low: "bg-inverse-primary",
};

const severityLabels: Record<Severity, string> = {
  critical: "Critical",
  medium: "Medium",
  low: "Low",
};

export function normalizeSeverity(value: string): Severity | null {
  const normalized = value.trim().toLowerCase();
  if (normalized === "critical" || normalized === "high") return "critical";
  if (normalized === "medium" || normalized === "moderate") return "medium";
  if (normalized === "low") return "low";
  return null;
}

export function SeverityBadge({
  severity,
  label,
  className,
}: {
  severity: string;
  label?: string;
  className?: string;
}) {
  const normalized = normalizeSeverity(severity);

  return (
    <span className={cn("inline-flex items-center gap-1.5 text-sm text-on-surface", className)}>
      <span
        className={cn(
          "h-2.5 w-2.5 rounded-full",
          normalized ? severityDotClasses[normalized] : "bg-outline",
        )}
      />
      {label ?? (normalized ? severityLabels[normalized] : severity)}
    </span>
  );
}
