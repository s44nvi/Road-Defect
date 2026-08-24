import type { StatusTone } from "@/components/ui/status-chip";

// defect_status is a free-form string on the backend (models.py: plain
// String column, not an enum) — this is presentation-only normalization,
// shared by the citizen recent-reports list and the officer dashboard/
// detail pages so both read status the same way.
export function statusTone(status: string): StatusTone {
  const normalized = status.trim().toLowerCase();
  if (normalized.includes("resolv") || normalized.includes("complet")) return "success";
  if (normalized.includes("reject")) return "critical";
  if (normalized.includes("schedul") || normalized.includes("confirm")) return "info";
  return "neutral";
}

export function statusLabel(status: string): string {
  return status
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}
