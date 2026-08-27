import { formatIST } from "@/lib/format-datetime";
import { SeverityBadge } from "@/components/ui/severity-badge";
import type { ContributingReport } from "@/lib/api";

// The officer's "this is ONE physical defect, independently reported N
// times" view. Each entry is a real, unmodified citizen observation
// (its own reporter, photo, GPS, timestamp and AI evidence) that the
// backend consolidated under this physical defect — see
// backend/app/consolidation and GET /defects/{id}'s `reports[]`.
export function CorroborationSection({
  reports,
  canonicalReportId,
}: {
  reports: ContributingReport[];
  canonicalReportId: number;
}) {
  if (!reports || reports.length === 0) {
    return <span className="font-normal text-on-surface-variant">Not available yet</span>;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-on-surface-variant">
        {reports.length === 1
          ? "1 citizen report of this physical defect."
          : `${reports.length} independent citizen reports of the same physical defect.`}
      </p>

      <ol className="space-y-3">
        {reports.map((report) => (
          <li
            key={report.report_id}
            className="rounded-lg border border-border-subtle bg-surface-container-lowest p-3"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-primary">
                  Report #{report.report_id}
                  {report.report_id === canonicalReportId && (
                    <span className="ml-1 rounded bg-primary/10 px-1 py-0.5 text-[9px] text-primary">
                      first report
                    </span>
                  )}
                </p>
                <p className="mt-0.5 text-sm font-medium text-on-surface">
                  {report.reporter ? report.reporter.full_name : "Anonymous citizen"}
                </p>
              </div>
              <SeverityBadge severity={report.defect_severity} />
            </div>

            <div className="mt-2 grid grid-cols-[96px_1fr] gap-3">
              {report.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={report.image_url}
                  alt={`Evidence for report ${report.report_id}`}
                  className="h-24 w-24 rounded-md border border-border-subtle object-cover"
                />
              ) : (
                <div className="flex h-24 w-24 items-center justify-center rounded-md border border-dashed border-outline text-[10px] text-on-surface-variant">
                  no photo
                </div>
              )}

              <dl className="grid grid-cols-1 gap-1 text-xs text-on-surface-variant">
                <div className="flex gap-1">
                  <dt className="font-medium">Time:</dt>
                  <dd>{report.reported_at ? formatIST(report.reported_at) : "—"}</dd>
                </div>
                <div className="flex gap-1">
                  <dt className="font-medium">Location:</dt>
                  <dd>
                    {report.latitude.toFixed(5)}, {report.longitude.toFixed(5)}
                  </dd>
                </div>
                <div className="flex gap-1">
                  <dt className="font-medium">AI:</dt>
                  <dd>
                    {report.ai_confidence != null
                      ? `${(report.ai_confidence * 100).toFixed(1)}% ${report.defect_type}${
                          report.ai_model_source ? ` (${report.ai_model_source})` : ""
                        }`
                      : "no detection"}
                  </dd>
                </div>
              </dl>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
