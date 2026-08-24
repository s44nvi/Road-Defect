"use client";

import { cn } from "@/lib/cn";
import { Card } from "@/components/ui/card";
import { StatusChip } from "@/components/ui/status-chip";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { defectTypeLabel } from "@/lib/defect-types";
import { statusTone, statusLabel } from "@/lib/defect-status";
import type { DefectResponse } from "@/lib/api";

// Backend has no per-user report ownership and no timestamp field, so this
// shows the most recently created defects city-wide (highest defect_id
// first) rather than a fabricated "my reports" list.
export function RecentReports({
  defects,
  selectedId,
  onSelect,
}: {
  defects: DefectResponse[];
  selectedId: number | null;
  onSelect: (defect: DefectResponse) => void;
}) {
  const recent = [...defects].sort((a, b) => b.defect_id - a.defect_id).slice(0, 8);

  if (recent.length === 0) {
    return (
      <Card className="p-6 text-center">
        <p className="text-sm text-on-surface-variant">No road issues reported yet.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {recent.map((defect) => (
        <button
          key={defect.defect_id}
          type="button"
          onClick={() => onSelect(defect)}
          className={cn(
            "w-full rounded-lg border p-3 text-left transition-colors",
            defect.defect_id === selectedId
              ? "border-primary bg-primary/5"
              : "border-border-subtle bg-surface-container-lowest hover:bg-surface-container-low",
          )}
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-medium text-on-surface">
              {defectTypeLabel(defect.defect_type)}
            </p>
            <StatusChip tone={statusTone(defect.defect_status)}>
              {statusLabel(defect.defect_status)}
            </StatusChip>
          </div>
          <div className="mt-1.5 flex items-center justify-between">
            <SeverityBadge severity={defect.defect_severity} />
            <span className="text-xs text-on-surface-variant">#{defect.defect_id}</span>
          </div>
        </button>
      ))}
    </div>
  );
}
