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
import {
  fetchRoadHealthSegment,
  fetchSegmentAssets,
  ApiError,
  type SegmentDetail,
  type SegmentAssetsResponse,
} from "@/lib/api";

// GET /road-health/segments/{segment_id} is a real, live endpoint —
// fetched directly for this one segment rather than pulling the full
// GET /road-health/segments list and finding a match, and it now includes
// the segment's real defects, not just its aggregate counts.
function RoadDetailContent({ name, segmentId }: { name: string; segmentId: string }) {
  const [state, setState] = useState<
    { status: "loading" } | { status: "error"; message: string } | { status: "ready"; segment: SegmentDetail }
  >({ status: "loading" });

  // MCGM assets state — loaded in parallel with the segment detail.
  // A null value means the fetch hasn't completed or this segment has no
  // MCGM asset data (e.g. non-MCGM segment → 404 → null). Failures here
  // are non-fatal: Road Health display is independent of the assets call.
  const [assets, setAssets] = useState<SegmentAssetsResponse | null>(null);

  const load = useCallback(() => {
    setState({ status: "loading" });
    setAssets(null);

    fetchRoadHealthSegment(segmentId)
      .then((segment) => setState({ status: "ready", segment }))
      .catch((error) =>
        setState({
          status: "error",
          message: error instanceof ApiError ? error.message : "Failed to load this road segment.",
        }),
      );

    // Fetch MCGM assets in parallel. A 404 (non-MCGM or no linked assets)
    // or any other error is silently swallowed — the section just won't render.
    fetchSegmentAssets(segmentId)
      .then((data) => setAssets(data))
      .catch(() => {
        // Non-MCGM segments return 404 — expected, not an error to surface.
        setAssets(null);
      });
  }, [segmentId]);

  useEffect(() => {
    load();
  }, [load]);

  const segment = state.status === "ready" ? state.segment : null;

  // Show the MCGM context card only when assets have loaded and there's
  // something to display. Manhole display has been intentionally removed
  // from the officer UI — only encroachment records are shown.
  const hasMcgmAssets =
    assets !== null && assets.encroachment_count > 0;

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

            {/* MCGM metadata row — only shown when the backend provides it */}
            {(segment.ward || segment.mcgm_id || segment.work_status) && (
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-on-surface-variant">
                {segment.mcgm_id && (
                  <span>
                    <span className="font-medium">MCGM ID:</span> {segment.mcgm_id}
                  </span>
                )}
                {segment.ward && (
                  <span>
                    <span className="font-medium">Ward:</span> {segment.ward}
                  </span>
                )}
                {segment.work_status && (
                  <span>
                    <span className="font-medium">Work status:</span> {segment.work_status}
                  </span>
                )}
              </div>
            )}

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

        {/*
          MCGM Infrastructure Context
          ─────────────────────────────────────────────────────────────────────
          Encroachment complaints are sourced from the real MCGM dataset
          and are displayed here as read-only contextual information only.
          They are NOT defects and do NOT affect the Road Health score,
          severity ratings, or defect counts shown above.
          (Manhole display intentionally removed from officer UI.)
          ─────────────────────────────────────────────────────────────────────
        */}
        {hasMcgmAssets && assets && (
          <Card className="p-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                MCGM Infrastructure Context
              </p>
              <p className="mt-0.5 text-xs text-on-surface-variant">
                Read-only records from the MCGM dataset.
                These do <strong>not</strong> affect Road Health scores or defect counts.
              </p>
            </div>

            {assets.encroachment_count > 0 && (
              <div className="mt-4">
                <p className="mb-2 text-sm font-medium text-on-surface">
                  Encroachment Complaints{" "}
                  <span className="ml-1 rounded-full bg-surface-container-low px-2 py-0.5 text-xs font-normal text-on-surface-variant">
                    {assets.encroachment_count}
                  </span>
                </p>
                <ol className="space-y-2">
                  {assets.encroachments.map((e) => (
                    <li
                      key={e.id}
                      className="rounded-lg border border-border-subtle px-4 py-3 text-sm"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium text-on-surface">
                          {e.road_name ?? "Unknown road"}
                          {e.ward ? ` · Ward ${e.ward}` : ""}
                        </span>
                        <div className="flex flex-wrap gap-2 text-xs">
                          {e.status && (
                            <span className="rounded bg-surface-container-low px-1.5 py-0.5 text-on-surface-variant">
                              {e.status}
                            </span>
                          )}
                          {e.complaint_type && (
                            <span className="rounded bg-surface-container-low px-1.5 py-0.5 text-on-surface-variant">
                              {e.complaint_type}
                            </span>
                          )}
                        </div>
                      </div>
                      {e.description && (
                        <p className="mt-1 text-xs text-on-surface-variant">{e.description}</p>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            )}
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
