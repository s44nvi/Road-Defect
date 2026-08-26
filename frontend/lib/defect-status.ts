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

// Real backend lifecycle (see DefectStatusChangeRequest in the live
// OpenAPI schema): reported, confirmed, in_progress, resolved, rejected.
// The citizen "community issues" view (app/home/page.tsx) should only
// surface issues an officer has actually verified — "reported" is an
// unconfirmed citizen submission an officer hasn't reviewed yet, and
// "rejected" was reviewed and dismissed as not a real issue. Showing
// either as a live community issue would misrepresent unverified/
// dismissed reports as confirmed problems. The officer dashboard is
// unaffected by this — officers need to see every status.
const PUBLICLY_VISIBLE_STATUSES = new Set(["confirmed", "in_progress", "resolved"]);

export function isPubliclyVisibleStatus(status: string): boolean {
  return PUBLICLY_VISIBLE_STATUSES.has(status.trim().toLowerCase());
}
