import type { RoadHealthSegment } from "@/lib/api";

type Stats = Pick<
  RoadHealthSegment,
  "total_issues" | "open_issues" | "resolved_issues" | "critical_issues" | "medium_issues" | "low_issues"
>;

// Reused by the road-health map popup and (once real segment data exists)
// the road detail page — every field here comes straight off a real
// RoadHealthSegment, never fabricated.
export function RoadStatistics({ stats }: { stats: Stats }) {
  return (
    <div>
      <div className="grid grid-cols-3 gap-2 rounded-md bg-surface-container-low p-2 text-center text-xs">
        <div>
          <p className="font-semibold text-on-surface">{stats.total_issues}</p>
          <p className="text-on-surface-variant">Total</p>
        </div>
        <div>
          <p className="font-semibold text-on-surface">{stats.open_issues}</p>
          <p className="text-on-surface-variant">Open</p>
        </div>
        <div>
          <p className="font-semibold text-on-surface">{stats.resolved_issues}</p>
          <p className="text-on-surface-variant">Resolved</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-on-surface-variant">
        <span>
          <span className="text-error">●</span> {stats.critical_issues} Critical
        </span>
        <span>
          <span className="text-[#f59e0b]">●</span> {stats.medium_issues} Medium
        </span>
        <span>
          <span className="text-inverse-primary">●</span> {stats.low_issues} Low
        </span>
      </div>
    </div>
  );
}
