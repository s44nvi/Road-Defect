import Link from "next/link";
import { Card } from "@/components/ui/card";
import { StatusChip } from "@/components/ui/status-chip";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { defectTypeLabel } from "@/lib/defect-types";
import { statusTone, statusLabel } from "@/lib/defect-status";
import { formatDistanceAway } from "@/lib/geo";
import type { DefectResponse, DefectResponseWithPriority } from "@/lib/api";

export function MyReportCard({
  defect,
  distanceKm,
}: {
  defect: DefectResponse | DefectResponseWithPriority;
  /** Real haversine distance from a searched/current location — see
   * lib/geo.ts. Omitted entirely (not "0 km") when no reference point is
   * set. There is no report creation timestamp anywhere in the current
   * backend contract (see lib/format-datetime.ts), so none is shown here. */
  distanceKm?: number;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">
            Report #{defect.defect_id}
          </p>
          <h3 className="mt-1 text-base font-semibold text-on-surface">
            {defectTypeLabel(defect.defect_type)}
          </h3>
        </div>
        <StatusChip tone={statusTone(defect.defect_status)}>{statusLabel(defect.defect_status)}</StatusChip>
      </div>

      {"canonical_defect_id" in defect && defect.canonical_defect_id != null && (
        <p className="mt-2 rounded-md bg-surface-container-low px-2 py-1 text-xs text-on-surface-variant">
          Your report was matched to an existing defect other citizens also
          reported. It still counts as your observation.
        </p>
      )}

      <div className="mt-3 flex items-center justify-between">
        <SeverityBadge severity={defect.defect_severity} />
        <span className="text-xs text-on-surface-variant">
          {distanceKm != null ? formatDistanceAway(distanceKm) : `${defect.latitude.toFixed(4)}, ${defect.longitude.toFixed(4)}`}
        </span>
      </div>

      <Link
        href={`/my-reports/${defect.defect_id}`}
        className="mt-4 flex items-center justify-center gap-1 rounded-md border border-primary/30 bg-primary/5 py-2 text-sm font-semibold text-primary transition-colors hover:bg-primary/10"
      >
        View report →
      </Link>
    </Card>
  );
}
