// The RoadSense defect taxonomy is exactly these four types. Backend
// defect_type is a free-form string (set by the ML pipeline), so this
// normalizes known spellings for icon/label lookup without inventing any
// categories beyond the four RoadSense actually supports.
export type DefectTypeKey = "pothole" | "road_crack" | "road_debris" | "manhole";

const DEFECT_TYPE_LABELS: Record<DefectTypeKey, string> = {
  pothole: "Pothole",
  road_crack: "Road Crack",
  road_debris: "Road Debris",
  manhole: "Manhole",
};

export function normalizeDefectType(value: string): DefectTypeKey | null {
  const normalized = value.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (normalized === "pothole") return "pothole";
  if (normalized === "road_crack" || normalized === "crack") return "road_crack";
  if (normalized === "road_debris" || normalized === "debris") return "road_debris";
  if (normalized === "manhole") return "manhole";
  return null;
}

export function defectTypeLabel(value: string): string {
  const key = normalizeDefectType(value);
  return key ? DEFECT_TYPE_LABELS[key] : value;
}
