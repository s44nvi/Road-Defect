"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { RequireSession } from "@/components/auth/require-session";
import { OfficerShell } from "@/components/layout/officer-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusChip } from "@/components/ui/status-chip";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { normalizeHealthCategory } from "@/lib/road-health";
import { HealthScoreBadge } from "@/components/road-health/health-score-badge";
import { HealthCategoryBadge } from "@/components/road-health/health-category-badge";
import { RoadStatistics } from "@/components/road-health/road-statistics";
import { defectTypeLabel } from "@/lib/defect-types";
import { statusTone, statusLabel } from "@/lib/defect-status";
import { fetchRoadHealthSegment, ApiError, type SegmentDetail } from "@/lib/api";

// GET /road-health/segments/{segment_id} is a real, live endpoint —
// fetched directly for this one segment rather than pulling the full
// GET /road-health/segments list and finding a match, and it now includes
// the segment's real defects, not just its aggregate counts.
function RoadDetailContent({ name, segmentId }: { name: string; segmentId: string }) {
  const [state, setState] = useState<
    { status: "loading" } | { status: "error"; message: string } | { status: "ready"; segment: SegmentDetail }
  >({ status: "loading" });

  const load = useCallback(() => {
    setState({ status: "loading" });
    fetchRoadHealthSegment(segmentId)
      .then((segment) => setState({ status: "ready", segment }))
      .catch((error) =>
        setState({
          status: "error",
          message: error instanceof ApiError ? error.message : "Failed to load this road segment.",
        }),
      );
  }, [segmentId]);

  useEffect(() => {
    load();
  }, [load]);

  const segment = state.status === "ready" ? state.segment : null;

  return (
    <OfficerShell name={name}>
      <PageContainer className="max-w-2xl space-y-6 py-8">
        <div>
          <Link href="/dashboard" className="text-sm font-medium text-primary hover:underline">
            ← Back to dashboard
          </Link>
        </div>

        {state.status === "loading" && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Loading road segment…</p>
          </Card>
        )}

        {state.status === "error" && (
          <Card className="p-8 text-center">
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">
              Road segment {segmentId}
            </p>
            <p className="mt-3 text-sm text-on-surface-variant">Couldn&apos;t load this segment: {state.message}</p>
            <Button variant="secondary" className="mt-3" onClick={load}>
              Retry
            </Button>
          </Card>
        )}

        {segment && (
          <Card className="p-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">
              Road segment {segment.segment_id}
            </p>
            <h1 className="mt-1 text-2xl font-semibold text-on-surface">{segment.road_name}</h1>
            <p className="mt-1 text-sm text-on-surface-variant">
              {segment.segment_label} · {segment.length_km.toFixed(2)} km
            </p>

            <div className="mt-4 space-y-1">
              <p className="text-xs text-on-surface-variant">Road Health</p>
              <HealthScoreBadge score={segment.health_score} size="lg" />
              <div>
                <HealthCategoryBadge category={normalizeHealthCategory(segment.health_status, segment.health_score)} />
              </div>
            </div>

            <div className="mt-4">
              <RoadStatistics
                stats={{
                  total_issues: segment.total_issues,
                  open_issues: segment.active_issues,
                  resolved_issues: segment.resolved_issues,
                  critical_issues: segment.critical_issues,
                  medium_issues: segment.medium_issues,
                  low_issues: segment.low_issues,
                }}
              />
            </div>

            <div className="mt-6 border-t border-border-subtle pt-4">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                Defects on this segment
              </p>
              {segment.defects.length === 0 ? (
                <p className="text-sm text-on-surface-variant">No defects recorded on this segment.</p>
              ) : (
                <ol className="space-y-2">
                  {segment.defects.map((defect) => (
                    <li
                      key={defect.defect_id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border-subtle px-4 py-3"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-on-surface">
                          #{defect.defect_id} · {defectTypeLabel(defect.defect_type)}
                        </p>
                        <div className="mt-1 flex items-center gap-2">
                          <SeverityBadge severity={defect.defect_severity} />
                          <StatusChip tone={statusTone(defect.defect_status)}>
                            {statusLabel(defect.defect_status)}
                          </StatusChip>
                        </div>
                      </div>
                      <Link
                        href={`/defect/${defect.defect_id}`}
                        className="whitespace-nowrap text-xs font-medium text-primary hover:underline"
                      >
                        View Incident →
                      </Link>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </Card>
        )}
      </PageContainer>
    </OfficerShell>
  );
}

export default function RoadDetailPage({ params }: { params: { id: string } }) {
  return (
    <RequireSession role="officer">
      {(session) => <RoadDetailContent name={session.name} segmentId={params.id} />}
    </RequireSession>
  );
}
