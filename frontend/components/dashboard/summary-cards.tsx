import { Card } from "@/components/ui/card";
import { normalizeSeverity } from "@/components/ui/severity-badge";
import type { DefectResponse } from "@/lib/api";

function isResolvedLike(status: string): boolean {
  const normalized = status.trim().toLowerCase();
  return normalized.includes("resolv") || normalized.includes("complet");
}

function SummaryCard({
  label,
  value,
  valueClassName,
  supporting,
}: {
  label: string;
  value: React.ReactNode;
  valueClassName?: string;
  supporting?: string;
}) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{label}</p>
      <p className={`mt-2 text-3xl font-extrabold leading-none text-on-surface ${valueClassName ?? ""}`}>
        {value}
      </p>
      {supporting && <p className="mt-1.5 text-xs text-on-surface-variant">{supporting}</p>}
    </Card>
  );
}

// Active/Critical/Resolved are real counts derived from the already-loaded
// GET /defects data. Road Health has no backend source at all (see
// lib/road-health.ts) so it honestly says "Analysis pending" instead of a
// fabricated score.
export function SummaryCards({ defects }: { defects: DefectResponse[] }) {
  const active = defects.filter((d) => !isResolvedLike(d.defect_status)).length;
  const critical = defects.filter((d) => normalizeSeverity(d.defect_severity) === "critical").length;
  const resolved = defects.filter((d) => isResolvedLike(d.defect_status)).length;

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <SummaryCard
        label="Road Health"
        value="Analysis pending"
        valueClassName="text-lg font-semibold text-on-surface-variant"
      />
      <SummaryCard label="Active Issues" value={active} supporting="Currently requiring attention" />
      <SummaryCard
        label="Critical Issues"
        value={critical}
        valueClassName="text-error"
        supporting="High-severity reports"
      />
      <SummaryCard
        label="Resolved"
        value={resolved}
        valueClassName="text-primary"
        supporting="Completed repairs"
      />
    </div>
  );
}
