import Link from "next/link";
import { Card } from "@/components/ui/card";
import { healthBandForScore, HEALTH_BAND_LABEL, HEALTH_BAND_TEXT_CLASS } from "@/lib/road-health";
import type { RoadHealthSegment } from "@/lib/api";

const MAX_ROWS = 10;

// Filtering/sorting is done by the caller (app/dashboard/page.tsx) using
// components/dashboard/road-health-filters.tsx's state, so this component
// stays purely presentational. `segments` is the full real dataset from
// useRoadHealth() — passing an empty array (the default today, since no
// backend road-health endpoint exists yet) renders the honest empty state
// below rather than any fabricated row.
export function RoadsNeedingAttention({
  segments,
  hasBackendData,
}: {
  segments: RoadHealthSegment[];
  /** True only once a real (possibly empty) response has been fetched. */
  hasBackendData: boolean;
}) {
  return (
    <Card className="p-6">
      <h2 className="text-base font-semibold text-on-surface">Roads needing attention</h2>

      {!hasBackendData || segments.length === 0 ? (
        <p className="mt-3 text-sm text-on-surface-variant">
          {hasBackendData
            ? "No roads match the current filters."
            : "Road-level health analysis will appear here once road intelligence data is available."}
        </p>
      ) : (
        <ol className="mt-4 space-y-2">
          {segments.slice(0, MAX_ROWS).map((segment, index) => {
            const band = healthBandForScore(segment.health_score);
            return (
              <li
                key={segment.road_segment_id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-subtle px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-on-surface">
                    {index + 1}. {segment.road_name}
                  </p>
                  <p className="mt-0.5 text-xs text-on-surface-variant">
                    {segment.open_issues} open · {segment.critical_issues} critical
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-sm font-semibold ${HEALTH_BAND_TEXT_CLASS[band]}`}>
                    {segment.health_score.toFixed(1)}/10 — {HEALTH_BAND_LABEL[band]}
                  </span>
                  <Link
                    href={`/road/${segment.road_segment_id}`}
                    className="whitespace-nowrap text-xs font-medium text-primary hover:underline"
                  >
                    View Road →
                  </Link>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
