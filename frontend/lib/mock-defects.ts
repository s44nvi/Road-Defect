import type { DefectResponseWithPriority } from "./api";

// Dev-only sample data. Used ONLY by components/map/use-defects.ts, and
// ONLY when both (a) NEXT_PUBLIC_ENABLE_DEFECT_MOCK=true is set and (b) the
// real GET /defects call actually failed (no backend reachable). It is
// never a silent substitute for a reachable backend, and the UI marks it
// visibly as sample data whenever it's shown. IDs are negative so they can
// never collide with real defect_id values from the database.
export const MOCK_DEFECTS: DefectResponseWithPriority[] = [
  {
    defect_id: -1,
    defect_type: "pothole",
    defect_status: "reported",
    defect_severity: "critical",
    latitude: 19.1197,
    longitude: 72.8468,
    defect_priority: null,
  },
  {
    defect_id: -2,
    defect_type: "road crack",
    defect_status: "scheduled",
    defect_severity: "medium",
    latitude: 19.0596,
    longitude: 72.8656,
    defect_priority: null,
  },
  {
    defect_id: -3,
    defect_type: "manhole",
    defect_status: "reported",
    defect_severity: "low",
    latitude: 18.9633,
    longitude: 72.8306,
    defect_priority: null,
  },
  {
    defect_id: -4,
    defect_type: "road debris",
    defect_status: "under_review",
    defect_severity: "medium",
    latitude: 19.0176,
    longitude: 72.8298,
    defect_priority: null,
  },
  {
    defect_id: -5,
    defect_type: "pothole",
    defect_status: "reported",
    defect_severity: "low",
    latitude: 19.033,
    longitude: 72.8397,
    defect_priority: null,
  },
];
