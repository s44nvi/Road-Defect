import Link from "next/link";
import { Card } from "@/components/ui/card";
import { CloseIcon } from "@/components/icons";
import { healthBandForScore } from "@/lib/road-health";
import { HealthScoreBadge } from "@/components/road-health/health-score-badge";
import { HealthCategoryBadge } from "@/components/road-health/health-category-badge";
import { RoadStatistics } from "@/components/road-health/road-statistics";
import type { RoadHealthSegment } from "@/lib/api";

// Rendered as a map overlay (see app/dashboard/page.tsx) the moment a real
// road-segment layer exists to click — see components/map/defect-map.tsx's
// roadSegments/onSelectSegment props. `segment={null}` is the honest
// pending state for when nothing is selected or no road-health data exists.
export function RoadHealthPopup({
  segment,
  onClose,
}: {
  segment: RoadHealthSegment | null;
  onClose?: () => void;
}) {
  if (!segment) return null;

  const band = healthBandForScore(segment.health_score);

  return (
    <Card className="w-72 p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-on-surface">{segment.road_name}</p>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-full p-1 text-on-surface-variant transition-colors hover:bg-surface-container-low"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="mt-3 space-y-1">
        <p className="text-xs text-on-surface-variant">Road Health</p>
        <HealthScoreBadge score={segment.health_score} size="lg" />
        <div>
          <HealthCategoryBadge category={band} />
        </div>
      </div>

      <div className="mt-3">
        <RoadStatistics stats={segment} />
      </div>

      <Link
        href={`/road/${segment.road_segment_id}`}
        className="mt-3 block text-center text-xs font-medium text-primary hover:underline"
      >
        View Road Details →
      </Link>
    </Card>
  );
}
