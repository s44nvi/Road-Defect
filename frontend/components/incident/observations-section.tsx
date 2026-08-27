// Number of individual citizen observations consolidated into this one
// physical defect (see the officer defect-detail `reports[]` and
// backend consolidation). Always >= 1.
export function ObservationsSection({ count }: { count?: number | null }) {
  if (count == null) {
    return <span className="font-normal text-on-surface-variant">Not available yet</span>;
  }
  return (
    <p className="text-sm font-semibold text-on-surface">
      {count} citizen {count === 1 ? "report" : "reports"} of this physical defect
    </p>
  );
}
