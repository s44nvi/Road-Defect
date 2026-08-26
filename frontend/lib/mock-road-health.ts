import type { RoadHealthSegment } from "./api";

// ============================================================================
// DEV-ONLY FIXTURE — NOT WIRED INTO THE APP.
//
// Nothing in components/ or app/ imports this file. useRoadHealth() (see
// components/map/use-road-health.ts) only ever calls the real
// fetchRoadHealth() API function, gated behind NEXT_PUBLIC_ENABLE_ROAD_HEALTH,
// and never falls back to this fixture — unlike lib/mock-defects.ts, which
// use-defects.ts *does* wire in behind its own opt-in flag. That asymmetry
// is deliberate: road-health numbers (health scores, issue breakdowns) are
// exactly the kind of thing this project's rules say must never be shown to
// an officer as if real. If you need sample data to develop against locally,
// import ROAD_SEGMENT_FIXTURE manually in a scratch file/story — do not wire
// it into use-road-health.ts, the dashboard page, or any other production
// code path. Segment IDs are prefixed "mock-" so they can never collide with
// a real backend-issued road_segment_id.
// ============================================================================
export const ROAD_SEGMENT_FIXTURE: RoadHealthSegment[] = [
  {
    road_segment_id: "mock-1",
    road_name: "[MOCK] LBS Marg",
    health_score: 8.6,
    health_category: "healthy",
    total_issues: 3,
    open_issues: 1,
    resolved_issues: 2,
    critical_issues: 0,
    medium_issues: 1,
    low_issues: 2,
    geometry: {
      type: "LineString",
      coordinates: [
        [72.8777, 19.076],
        [72.882, 19.081],
      ],
    },
  },
  {
    road_segment_id: "mock-2",
    road_name: "[MOCK] SCLR",
    health_score: 5.2,
    health_category: "needs_attention",
    total_issues: 9,
    open_issues: 6,
    resolved_issues: 3,
    critical_issues: 1,
    medium_issues: 4,
    low_issues: 4,
    geometry: {
      type: "LineString",
      coordinates: [
        [72.865, 19.06],
        [72.87, 19.065],
      ],
    },
  },
  {
    road_segment_id: "mock-3",
    road_name: "[MOCK] Kurla-Sion Link Road",
    health_score: 2.1,
    health_category: "critical",
    total_issues: 14,
    open_issues: 11,
    resolved_issues: 3,
    critical_issues: 5,
    medium_issues: 6,
    low_issues: 3,
    geometry: {
      type: "LineString",
      coordinates: [
        [72.85, 19.03],
        [72.855, 19.035],
      ],
    },
  },
];
