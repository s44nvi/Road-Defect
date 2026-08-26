"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchRoadHealthSegments, type RoadHealthSegment, type SegmentFeature } from "@/lib/api";
import { normalizeHealthCategory } from "@/lib/road-health";

type RoadHealthState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; segments: RoadHealthSegment[] };

// Adapts one GeoJSON feature from GET /road-health/segments into the
// internal RoadHealthSegment shape the map/dashboard components already
// expect — a rename layer, not a data transformation: every value here is
// read straight off the real SegmentProperties response.
function toRoadHealthSegment(feature: SegmentFeature): RoadHealthSegment {
  const p = feature.properties;
  return {
    road_segment_id: p.segment_id,
    road_name: p.road_name,
    health_score: p.health_score,
    health_category: normalizeHealthCategory(p.health_status, p.health_score),
    total_issues: p.total_issues,
    open_issues: p.active_issues,
    resolved_issues: p.resolved_issues,
    critical_issues: p.critical_issues,
    medium_issues: p.medium_issues,
    low_issues: p.low_issues,
    geometry: feature.geometry,
  };
}

export function useRoadHealth(): RoadHealthState & { reload: () => void } {
  const [state, setState] = useState<RoadHealthState>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    fetchRoadHealthSegments()
      .then((collection) => {
        if (!cancelled) {
          setState({ status: "ready", segments: collection.features.map(toRoadHealthSegment) });
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: error instanceof Error ? error.message : "Failed to load road health.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return { ...state, reload };
}
