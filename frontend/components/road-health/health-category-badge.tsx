import { HEALTH_BAND_BG_CLASS, HEALTH_BAND_LABEL, type HealthBand } from "@/lib/road-health";

export function HealthCategoryBadge({ category }: { category: HealthBand }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-on-surface">
      <span className={`h-2.5 w-2.5 rounded-full ${HEALTH_BAND_BG_CLASS[category]}`} />
      {HEALTH_BAND_LABEL[category]}
    </span>
  );
}
