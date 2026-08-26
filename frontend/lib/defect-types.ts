// RoadSense's supported citizen-report categories — exactly these four,
// matching what the backend can actually detect or accept today (see
// components/report/defect-type-select.tsx and ai-detection.tsx). Backend
// defect_type is a free-form string, so normalization here also covers
// the crack sub-class strings the RDD-trained model uses internally
// (longitudinal/alligator/transverse), for grouping any historical/seed
// data under the "Crack" bucket for icon/label purposes.
export type DefectTypeKey = "pothole" | "manhole" | "road_crack" | "hawker_encroachment";

const DEFECT_TYPE_LABELS: Record<DefectTypeKey, string> = {
  pothole: "Pothole",
  manhole: "Manhole",
  road_crack: "Crack",
  hawker_encroachment: "Hawker / Encroachment",
};

export function normalizeDefectType(value: string): DefectTypeKey | null {
  const normalized = value.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized === "pothole") return "pothole";
  if (normalized === "manhole") return "manhole";
  if (
    normalized === "road_crack" ||
    normalized === "crack" ||
    normalized === "longitudinal_crack" ||
    normalized === "alligator_crack" ||
    normalized === "transverse_crack"
  ) {
    return "road_crack";
  }
  if (
    normalized === "hawker_encroachment" ||
    normalized === "hawker" ||
    normalized === "encroachment" ||
    // POST /ml/hawkers/detect persists the raw model class_name directly as
    // defect_type (confirmed live: GET /defects returns e.g.
    // "fixed-stall-vendor" for a hawker-created row, not
    // "hawker_encroachment"). Every officer-facing view must still show
    // "Hawker / Encroachment" here, never the raw ML class name — see
    // components/report/ai-detection.tsx, which already keeps these three
    // strings out of the citizen-facing result for the same reason.
    normalized === "fixed_stall_vendor" ||
    normalized === "semi_fixed_vendor" ||
    normalized === "itinerant_vendor"
  ) {
    return "hawker_encroachment";
  }
  return null;
}

export function defectTypeLabel(value: string): string {
  const key = normalizeDefectType(value);
  return key ? DEFECT_TYPE_LABELS[key] : value;
}
