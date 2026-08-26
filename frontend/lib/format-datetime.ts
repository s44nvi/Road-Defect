// Every real timestamp in this app must display in Asia/Kolkata (IST),
// regardless of the viewer's own device timezone — the backend returns
// ISO 8601 (UTC), so this is a display-only conversion, never a
// reinterpretation of the underlying instant.
//
// NOTE: the only real timestamp field anywhere in the current backend
// contract is StatusHistoryEntry.changed_at (GET /defects/{id}/status-history).
// There is no defect creation/submission timestamp on DefectResponse,
// DefectDetailResponse, or any other defect shape today — report cards
// and the officer header cannot show a real "submitted at" time until the
// backend adds one. Nothing here fabricates one from page-load time.
export function formatIST(isoString: string): string {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;

  const formatted = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(date);

  return `${formatted} IST`;
}
