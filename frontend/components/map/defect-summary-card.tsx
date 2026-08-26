import Link from "next/link";
import { Card } from "@/components/ui/card";
import { StatusChip } from "@/components/ui/status-chip";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { CloseIcon } from "@/components/icons";
import { defectTypeLabel } from "@/lib/defect-types";
import type { DefectResponse } from "@/lib/api";

export function DefectSummaryCard({
  defect,
  onClose,
  detailsHref,
}: {
  defect: DefectResponse;
  onClose: () => void;
  /** Optional "View Incident" link — used by the officer dashboard, unused by citizen /home. */
  detailsHref?: string;
}) {
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
      <div className="mt-3 flex items-center gap-3">
        <SeverityBadge severity={defect.defect_severity} />
        <StatusChip>{defect.defect_status}</StatusChip>
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
