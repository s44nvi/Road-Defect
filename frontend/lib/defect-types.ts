// RoadSense's supported citizen-report categories — exactly these four,
// matching what the backend can actually detect or accept today (see
// components/report/defect-type-select.tsx and ai-detection.tsx). Backend
// defect_type is a free-form string, so normalization here also covers
// the crack sub-class strings the RDD-trained model uses internally.
//
// NOTE: "manhole" has been intentionally removed as a supported category
// for the SIH demo. If the backend returns "manhole" as a defect_type,
// normalizeDefectType() returns null — it is treated as unsupported and
// never displayed or pre-selected in the UI.
export type DefectTypeKey = "pothole" | "alligator_crack" | "longitudinal_crack" | "hawker_encroachment";

const DEFECT_TYPE_LABELS: Record<DefectTypeKey, string> = {
  pothole: "Pothole",
  alligator_crack: "Crack – Alligator",
  longitudinal_crack: "Crack – Longitudinal",
  hawker_encroachment: "Encroachment / Vendor",
};

export function normalizeDefectType(value: string): DefectTypeKey | null {
  const normalized = value.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized === "pothole") return "pothole";
  // Alligator / fatigue crack — also catches generic/legacy crack strings
  // (road_crack, crack, transverse_crack) as the closest safe mapping.
  if (
    normalized === "alligator_crack" ||
    normalized === "road_crack" ||
    normalized === "crack" ||
    normalized === "transverse_crack"
  ) {
    return "alligator_crack";
  }
  if (normalized === "longitudinal_crack") return "longitudinal_crack";
  if (
    normalized === "hawker_encroachment" ||
    normalized === "hawker" ||
    normalized === "encroachment" ||
    // POST /ml/hawkers/detect persists the raw model class_name directly as
    // defect_type (confirmed live: GET /defects returns e.g.
    // "fixed-stall-vendor" for a hawker-created row, not
    // "hawker_encroachment"). Every officer-facing view must still show
    // "Encroachment / Vendor" here, never the raw ML class name — see
    // components/report/ai-detection.tsx, which already keeps these three
    // strings out of the citizen-facing result for the same reason.
    normalized === "fixed_stall_vendor" ||
    normalized === "semi_fixed_vendor" ||
    normalized === "itinerant_vendor"
  ) {
    return "hawker_encroachment";
  }
  // "manhole" and any other unrecognised category intentionally return null.
  return null;
}

export function defectTypeLabel(value: string): string {
  const key = normalizeDefectType(value);
  return key ? DEFECT_TYPE_LABELS[key] : value;
}
