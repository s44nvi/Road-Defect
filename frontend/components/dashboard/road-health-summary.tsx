import { Card } from "@/components/ui/card";
import { healthBandForScore, HEALTH_BAND_LABEL, HEALTH_BAND_TEXT_CLASS } from "@/lib/road-health";
import type { RoadHealthSegment } from "@/lib/api";

type RoadHealthSummaryState =
  | { status: "disabled" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; segments: RoadHealthSegment[] };

function MetricCard({
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
      <p className={`mt-2 text-2xl font-extrabold leading-none text-on-surface ${valueClassName ?? ""}`}>
        {value}
      </p>
      {supporting && <p className="mt-1.5 text-xs text-on-surface-variant">{supporting}</p>}
    </Card>
  );
}

const PENDING = "Analysis pending";

// This is the intended future centerpiece of the officer dashboard (real
// road-network health, not just incident counts) — see lib/road-health.ts
// and lib/api.ts's RoadHealthSegment for why every number here is either a
// real aggregate of a real GET /road-health response, or this honest
// "Analysis pending" placeholder. There is no backend endpoint to compute
// these from today, so in normal operation every card renders the
// placeholder — that is expected, not a bug.
export function RoadHealthSummary({ state }: { state: RoadHealthSummaryState }) {
  const ready = state.status === "ready";
  const segments = ready ? state.segments : [];
  const hasData = ready && segments.length > 0;

  const overallScore = hasData
    ? segments.reduce((sum, s) => sum + s.health_score, 0) / segments.length
    : null;
  const overallBand = overallScore !== null ? healthBandForScore(overallScore) : null;
  const healthyCount = segments.filter((s) => s.health_category === "healthy").length;
  const attentionCount = segments.filter((s) => s.health_category === "needs_attention").length;
  const criticalCount = segments.filter((s) => s.health_category === "critical").length;
  const openIssues = segments.reduce((sum, s) => sum + s.open_issues, 0);

  return (
    <div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <MetricCard
          label="Overall Road Health"
          value={
            overallScore !== null ? (
              <span className={overallBand ? HEALTH_BAND_TEXT_CLASS[overallBand] : undefined}>
                {overallScore.toFixed(1)}/10
              </span>
            ) : (
              PENDING
            )
          }
          valueClassName={overallScore === null ? "text-lg font-semibold text-on-surface-variant" : ""}
          supporting={overallBand ? HEALTH_BAND_LABEL[overallBand] : undefined}
        />
        <MetricCard
          label="Healthy Roads"
          value={hasData ? healthyCount : "—"}
          valueClassName="text-primary"
        />
        <MetricCard
          label="Roads Needing Attention"
          value={hasData ? attentionCount : "—"}
          valueClassName="text-[#f59e0b]"
        />
        <MetricCard
          label="Critical Roads"
          value={hasData ? criticalCount : "—"}
          valueClassName="text-error"
        />
        <MetricCard label="Open Issues" value={hasData ? openIssues : "—"} />
      </div>

      {state.status === "error" && (
        <p className="mt-2 text-xs text-on-surface-variant">
          Couldn&apos;t load road health data: {state.message}
        </p>
      )}
      {(state.status === "disabled" || (ready && segments.length === 0)) && (
        <p className="mt-2 text-xs text-on-surface-variant">
          Road-level health analysis will appear here once the backend provides real segment data.
        </p>
      )}
    </div>
  );
}
