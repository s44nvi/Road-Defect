function ScoreField({ label, value }: { label: string; value?: number | null }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{label}</dt>
      <dd className="mt-1 text-sm font-semibold text-on-surface">
        {value != null ? `${value.toFixed(1)} / 100` : <span className="font-normal text-on-surface-variant">Not available yet</span>}
      </dd>
    </div>
  );
}

// backend/app/road_intelligence's severity/priority engine (severity.py,
// scoring.py, ahp.py) is real and unit-tested, but it is only reachable
// via the standalone POST /road-intelligence/analyze endpoint — nothing
// calls it from POST /reports, and Defect has no column to persist its
// output (see the cross-layer integration audit). So `severityScore` /
// `priorityScore` are always undefined for a real incident today.
export function RoadIntelligenceSection({
  severityScore,
  priorityScore,
}: {
  severityScore?: number | null;
  priorityScore?: number | null;
}) {
  return (
    <dl className="grid grid-cols-2 gap-4">
      <ScoreField label="Severity Score" value={severityScore} />
      <ScoreField label="Priority Score" value={priorityScore} />
    </dl>
  );
}
