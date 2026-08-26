import { LocationPinIcon } from "@/components/icons";

// Purely presentational — takes `locationName` as a prop rather than
// resolving it itself, so nothing here triggers a reverse-geocoding call
// (there is no such backend field or endpoint today; every current call
// site passes `locationName={undefined}` and this renders coordinates
// only). Never call a geocoding API per-marker/per-card from this
// component — that decision belongs one level up, once, not here.
export function LocationDisplay({
  locationName,
  latitude,
  longitude,
  className,
}: {
  locationName?: string | null;
  latitude: number;
  longitude: number;
  className?: string;
}) {
  return (
    <div className={className}>
      {locationName && (
        <p className="flex items-center gap-1 text-sm font-medium text-on-surface">
          <LocationPinIcon className="h-3.5 w-3.5 shrink-0 text-primary" />
          {locationName}
        </p>
      )}
      <p className={locationName ? "mt-0.5 text-xs text-on-surface-variant" : "text-sm font-medium text-on-surface"}>
        {latitude.toFixed(5)}, {longitude.toFixed(5)}
      </p>
    </div>
  );
}
