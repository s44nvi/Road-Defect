// Road-segment health is a real, live feature as of GET /road-health/segments
// and GET /road-health/segments/{id} (see lib/api.ts's SegmentFeature/
// SegmentDetail for the wire shapes, and components/map/use-road-health.ts
// for how the GeoJSON response is adapted into RoadHealthSegment). The
// backend already computes and returns `health_status`/`health_color` per
// segment — healthBandForScore below is kept only as a fallback for the
// rare case a segment's health_status string doesn't match one of the
// three known bands, so a real health_score is never left unclassified.

import type { HealthCategory } from "./api";

export type HealthBand = HealthCategory;

// 8–10 Healthy, 4–7.99 Needs Attention, 0–3.99 Critical, per spec.
export function healthBandForScore(score: number): HealthBand {
  if (score >= 8) return "healthy";
  if (score >= 4) return "needs_attention";
  return "critical";
}

/** Normalizes the backend's `health_status` string into our HealthBand
 * union, falling back to a score-derived band for any value outside the
 * three we know about (still real data — just a defensive re-derivation,
 * never a fabricated one). */
export function normalizeHealthCategory(status: string, score: number): HealthBand {
  if (status === "healthy" || status === "needs_attention" || status === "critical") {
    return status;
  }
  return healthBandForScore(score);
}

export const HEALTH_BAND_LABEL: Record<HealthBand, string> = {
  healthy: "Healthy",
  needs_attention: "Needs Attention",
  critical: "Critical",
};

export const HEALTH_BAND_RANGE_LABEL: Record<HealthBand, string> = {
  healthy: "8–10",
  needs_attention: "4–7.99",
  critical: "0–3.99",
};

// Real hex values (not Tailwind theme tokens) because MapLibre paint
// expressions need literal color strings, and the legend/badges below need
// to match the map exactly. Healthy/critical reuse the existing
// primary/error design tokens; "needs attention" uses a true orange since
// the closest existing token (tertiary, a brick red) reads too similar to
// the critical red to be usable as a distinct map color.
export const HEALTH_BAND_HEX: Record<HealthBand, string> = {
  healthy: "#006948",
  needs_attention: "#f59e0b",
  critical: "#ba1a1a",
};

export const HEALTH_BAND_TEXT_CLASS: Record<HealthBand, string> = {
  healthy: "text-primary",
  needs_attention: "text-[#f59e0b]",
  critical: "text-error",
};

export const HEALTH_BAND_BG_CLASS: Record<HealthBand, string> = {
  healthy: "bg-primary",
  needs_attention: "bg-[#f59e0b]",
  critical: "bg-error",
};

export const HEALTH_BAND_DOT_CLASS = HEALTH_BAND_BG_CLASS;
