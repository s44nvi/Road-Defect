// No backend field tracks how many separate observations (citizen +
// re-detections) contributed to an incident today — always undefined.
export function ObservationsSection({ count }: { count?: number | null }) {
  return (
    <p className="text-sm font-semibold text-on-surface">
      {count != null ? count : <span className="font-normal text-on-surface-variant">Not available yet</span>}
    </p>
  );
}
