import Link from "next/link";
import { Card } from "@/components/ui/card";
import { StatusChip } from "@/components/ui/status-chip";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { CloseIcon } from "@/components/icons";
import { defectTypeLabel } from "@/lib/defect-types";
import type { DefectResponse, DefectResponseWithPriority } from "@/lib/api";

export function DefectSummaryCard({
  defect,
  onClose,
  detailsHref,
}: {
  defect: DefectResponse | DefectResponseWithPriority;
  onClose: () => void;
  /** Optional "View Incident" link — used by the officer dashboard, unused by citizen /home. */
  detailsHref?: string;
}) {
  const reportCount = "report_count" in defect ? defect.report_count : 1;
  return (
    <Card className="w-72 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">
            #{defect.defect_id}
          </p>
          <h3 className="text-base font-semibold text-on-surface">
            {defectTypeLabel(defect.defect_type)}
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded-full p-1 text-on-surface-variant transition-colors hover:bg-surface-container-low"
        >
          <CloseIcon className="h-4 w-4" />
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <SeverityBadge severity={defect.defect_severity} />
        <StatusChip>{defect.defect_status}</StatusChip>
        {reportCount > 1 && (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">
            {reportCount} reports
          </span>
        )}
      </div>
      <p className="mt-3 text-xs text-on-surface-variant">
        {defect.latitude.toFixed(5)}, {defect.longitude.toFixed(5)}
      </p>
      {detailsHref && (
        <Link
          href={detailsHref}
          className="mt-3 inline-block text-xs font-medium text-primary hover:underline"
        >
          View Incident →
        </Link>
      )}
    </Card>
  );
}
