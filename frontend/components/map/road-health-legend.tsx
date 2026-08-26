import { Card } from "@/components/ui/card";
import { HEALTH_BAND_HEX, HEALTH_BAND_LABEL, HEALTH_BAND_RANGE_LABEL, type HealthBand } from "@/lib/road-health";

const BANDS: HealthBand[] = ["healthy", "needs_attention", "critical"];

// Compact by design — this sits on top of the map next to the severity
// legend, and the backend has no road-segment endpoint yet, so it must
// never crowd out the map itself. The "unavailable" note is intentionally
// small/secondary rather than a dominant banner.
export function RoadHealthLegend({ active }: { active: boolean }) {
  return (
    <Card className="px-2.5 py-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-on-surface-variant">
        Road Health
      </p>
      <div className="mt-1 space-y-0.5">
        {BANDS.map((band) => (
          <div key={band} className="flex items-center gap-1.5 text-[11px] leading-tight text-on-surface">
            <span
              className="h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ backgroundColor: HEALTH_BAND_HEX[band] }}
            />
            <span>
              {HEALTH_BAND_LABEL[band]} {HEALTH_BAND_RANGE_LABEL[band]}
            </span>
          </div>
        ))}
      </div>
      {!active && (
        <p className="mt-1 text-[10px] italic text-on-surface-variant/70">
          Road-level analysis unavailable
        </p>
      )}
    </Card>
  );
}
