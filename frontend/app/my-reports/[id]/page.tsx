"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { RequireSession } from "@/components/auth/require-session";
import { CitizenShell } from "@/components/layout/citizen-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusChip } from "@/components/ui/status-chip";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { LocationDisplay } from "@/components/ui/location-display";
import { IncidentLocationMap } from "@/components/map/incident-location-map";
import { StatusProgress } from "@/components/my-reports/status-progress";
import { StatusHistoryList } from "@/components/incident/status-history-list";
import { fetchDefect, ApiError, type DefectDetailResponse } from "@/lib/api";
import { defectTypeLabel } from "@/lib/defect-types";
import { statusTone, statusLabel } from "@/lib/defect-status";

// Citizen-facing — no Confirm/Reject or any other officer-only control.
// GET /defects/{id} is a real, public endpoint, fetched directly rather
// than pulling the full GET /defects list and finding a match.
function MyReportDetailContent({ name, defectId }: { name: string; defectId: number }) {
  const [state, setState] = useState<
    { status: "loading" } | { status: "error"; message: string } | { status: "ready"; defect: DefectDetailResponse }
  >({ status: "loading" });

  const load = useCallback(() => {
    setState({ status: "loading" });
    fetchDefect(defectId)
      .then((defect) => setState({ status: "ready", defect }))
      .catch((error) =>
        setState({
          status: "error",
          message: error instanceof ApiError ? error.message : "Failed to load this report.",
        }),
      );
  }, [defectId]);

  useEffect(() => {
    load();
  }, [load]);

  const defect = state.status === "ready" ? state.defect : null;

  return (
    <CitizenShell name={name}>
      <PageContainer className="max-w-2xl space-y-6 py-8">
        <div>
          <Link href="/my-reports" className="text-sm font-medium text-primary hover:underline">
            ← Back to my reports
          </Link>
        </div>

        {state.status === "loading" && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Loading your report…</p>
          </Card>
        )}

        {state.status === "error" && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Couldn&apos;t load this report: {state.message}</p>
            <Button variant="secondary" className="mt-3" onClick={load}>
              Retry
            </Button>
          </Card>
        )}

        {defect && (
          <Card className="p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                  Report #{defectId}
                </p>
                <h1 className="mt-1 text-2xl font-semibold text-on-surface">
                  {defectTypeLabel(defect.defect_type)}
                </h1>
              </div>
              <StatusChip tone={statusTone(defect.defect_status)}>
                {statusLabel(defect.defect_status)}
              </StatusChip>
            </div>

            <dl className="mt-6 grid grid-cols-2 gap-4 rounded-lg bg-surface-container-low p-4 text-sm">
              <div>
                <dt className="text-on-surface-variant">Severity</dt>
                <dd className="mt-1">
                  <SeverityBadge severity={defect.defect_severity} />
                </dd>
              </div>
              <div>
                <dt className="text-on-surface-variant">Status</dt>
                <dd className="mt-1 font-medium text-on-surface">{statusLabel(defect.defect_status)}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-on-surface-variant">Location</dt>
                <dd className="mt-2">
                  <div className="h-40 w-full overflow-hidden rounded-lg border border-border-subtle">
                    <IncidentLocationMap latitude={defect.latitude} longitude={defect.longitude} />
                  </div>
                  <LocationDisplay
                    latitude={defect.latitude}
                    longitude={defect.longitude}
                    className="mt-2"
                  />
                </dd>
              </div>
            </dl>

            <div className="mt-6 border-t border-border-subtle pt-6">
              <StatusProgress status={defect.defect_status} />
            </div>

            <div className="mt-6 border-t border-border-subtle pt-6">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                Status history
              </p>
              <StatusHistoryList defectId={defectId} />
            </div>

            <p className="mt-6 rounded-md bg-surface-container-low px-4 py-3 text-xs text-on-surface-variant">
              Thank you for reporting this issue — a municipal officer will review it. You can check
              back here anytime for updates.
            </p>
          </Card>
        )}
      </PageContainer>
    </CitizenShell>
  );
}

export default function MyReportDetailPage({ params }: { params: { id: string } }) {
  const defectId = Number(params.id);

  return (
    <RequireSession role="citizen">
      {(session) => <MyReportDetailContent name={session.name} defectId={defectId} />}
    </RequireSession>
  );
}
