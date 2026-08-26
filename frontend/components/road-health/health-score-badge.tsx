import { healthBandForScore, HEALTH_BAND_TEXT_CLASS } from "@/lib/road-health";

export function HealthScoreBadge({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const band = healthBandForScore(score);
  const sizeClass = size === "lg" ? "text-2xl" : size === "sm" ? "text-sm" : "text-lg";
  return (
    <span className={`font-bold ${sizeClass} ${HEALTH_BAND_TEXT_CLASS[band]}`}>
      {score.toFixed(1)} / 10
    </span>
  );
}
