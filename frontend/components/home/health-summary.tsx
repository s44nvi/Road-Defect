import { Card } from "@/components/ui/card";
import { normalizeSeverity } from "@/components/ui/severity-badge";
import type { DefectResponse } from "@/lib/api";

// Real aggregate counts from GET /defects — not the "My reports" count from
// the Stitch reference, since the backend has no per-user ownership yet.
export function HealthSummary({ defects }: { defects: DefectResponse[] }) {
  const critical = defects.filter((d) => normalizeSeverity(d.defect_severity) === "critical").length;

  return (
    <Card className="px-4 py-3">
      <p className="text-xs font-medium text-on-surface-variant">Roads around you</p>
      <div className="mt-2 flex items-center gap-6">
        <div>
          <p className="text-2xl font-bold text-primary">{defects.length}</p>
          <p className="text-xs text-on-surface-variant">Issues reported</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-error">{critical}</p>
          <p className="text-xs text-on-surface-variant">Critical</p>
        </div>
      </div>
    </Card>
  );
}
