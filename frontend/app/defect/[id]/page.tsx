"use client";

import { useState } from "react";
import Link from "next/link";
import { RequireSession } from "@/components/auth/require-session";
import { OfficerShell } from "@/components/layout/officer-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusChip } from "@/components/ui/status-chip";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { useDefects } from "@/components/map/use-defects";
import { defectTypeLabel } from "@/lib/defect-types";
import { statusTone, statusLabel } from "@/lib/defect-status";
import { updateDefectStatus, ApiError, type DefectResponse } from "@/lib/api";

// GET /defects/{id} does not exist on the backend — only GET /defects
// (the full list) does. So this page fetches the full list via the same
// useDefects() hook /home and /dashboard use, and finds the matching row
// client-side, rather than inventing a single-defect endpoint.
function DefectDetailContent({ name, defectId }: { name: string; defectId: number }) {
  const defectsState = useDefects();
  const [override, setOverride] = useState<DefectResponse | null>(null);
  const [updating, setUpdating] = useState<"confirmed" | "rejected" | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);

  async function handleUpdate(nextStatus: "confirmed" | "rejected") {
    setUpdating(nextStatus);
    setUpdateError(null);
    try {
      const updated = await updateDefectStatus(defectId, { defect_status: nextStatus });
      setOverride(updated);
    } catch (error) {
      setUpdateError(
        error instanceof ApiError
          ? error.message
          : "Something went wrong updating this defect. Please try again.",
      );
    } finally {
      setUpdating(null);
    }
  }

  const fetched =
    defectsState.status === "ready"
      ? defectsState.defects.find((d) => d.defect_id === defectId) ?? null
      : null;
  const defect = override ?? fetched;

  return (
    <OfficerShell name={name}>
      <PageContainer className="max-w-2xl space-y-6 py-8">
        <div>
          <Link href="/dashboard" className="text-sm font-medium text-primary hover:underline">
            ← Back to dashboard
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-on-surface">Incident #{defectId}</h1>
        </div>

        {defectsState.status === "loading" && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Loading defect…</p>
          </Card>
        )}

        {defectsState.status === "error" && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Couldn&apos;t load defect data.</p>
            <Button variant="secondary" className="mt-3" onClick={defectsState.reload}>
              Retry
            </Button>
          </Card>
        )}

        {defectsState.status === "ready" && !fetched && !override && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">
              No defect with ID #{defectId} was found in the current GET /defects response.
            </p>
          </Card>
        )}

        {defect && (
          <Card className="p-6">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-on-surface">
                {defectTypeLabel(defect.defect_type)}
              </h2>
              <StatusChip tone={statusTone(defect.defect_status)}>
                {statusLabel(defect.defect_status)}
              </StatusChip>
            </div>

            <div className="mt-4 space-y-2 rounded-lg bg-surface-container-low p-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-on-surface-variant">Severity</span>
                <SeverityBadge severity={defect.defect_severity} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-on-surface-variant">Location</span>
                <span className="font-medium text-on-surface">
                  {defect.latitude.toFixed(5)}, {defect.longitude.toFixed(5)}
                </span>
              </div>
            </div>

            {updateError && (
              <p className="mt-4 rounded-md bg-error-container px-3 py-2 text-sm text-on-error-container">
                {updateError}
              </p>
            )}

            <div className="mt-6 flex gap-3">
              <Button
                variant="primary"
                disabled={updating !== null}
                onClick={() => handleUpdate("confirmed")}
              >
                {updating === "confirmed" ? "Confirming…" : "Confirm Incident"}
              </Button>
              <Button
                variant="destructive"
                disabled={updating !== null}
                onClick={() => handleUpdate("rejected")}
              >
                {updating === "rejected" ? "Rejecting…" : "Reject"}
              </Button>
            </div>
          </Card>
        )}
      </PageContainer>
    </OfficerShell>
  );
}

export default function DefectDetailPage({ params }: { params: { id: string } }) {
  const defectId = Number(params.id);

  return (
    <RequireSession role="officer">
      {(session) => <DefectDetailContent name={session.name} defectId={defectId} />}
    </RequireSession>
  );
}
