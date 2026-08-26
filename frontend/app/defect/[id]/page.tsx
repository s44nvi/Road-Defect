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
import { LocationDisplay } from "@/components/ui/location-display";
import { StatusTimeline } from "@/components/dashboard/status-timeline";
import { StatusHistoryList } from "@/components/incident/status-history-list";
import { IncidentLocationMap } from "@/components/map/incident-location-map";
import { EvidenceSection } from "@/components/incident/evidence-section";
import { AIAnalysisSection } from "@/components/incident/ai-analysis-section";
import { RoadIntelligenceSection } from "@/components/incident/road-intelligence-section";
import { ObservationsSection } from "@/components/incident/observations-section";
import { RepairVerificationSection } from "@/components/incident/repair-verification-section";
import { defectTypeLabel } from "@/lib/defect-types";
import { statusTone, statusLabel } from "@/lib/defect-status";
import { fetchDefect, updateDefectStatus, ApiError, type DefectDetailResponse } from "@/lib/api";

function Divider() {
  return <hr className="border-t border-border-subtle" />;
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
      {children}
    </p>
  );
}

// GET /defects/{id} is a real, public endpoint now — fetched directly
// rather than pulling the full GET /defects list and finding a match.
//
// None of the fields below (image, AI detection, human-readable location
// name, observation count, repair verification) exist on
// DefectDetailResponse today — every one of these sections is
// intentionally passed `undefined` and renders its own honest "not
// available yet" state. Confirm/Reject, the real defect fields, and the
// real status-history log are the only parts of this page backed by real
// data.
function DefectDetailContent({
  name,
  token,
  defectId,
}: {
  name: string;
  token: string;
  defectId: number;
}) {
  const [defectState, setDefectState] = useState<
    { status: "loading" } | { status: "error"; message: string } | { status: "ready"; defect: DefectDetailResponse }
  >({ status: "loading" });
  const [updating, setUpdating] = useState<string | null>(null);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [justUpdated, setJustUpdated] = useState<string | null>(null);
  const [historyKey, setHistoryKey] = useState(0);

  const loadDefect = useCallback(() => {
    setDefectState({ status: "loading" });
    fetchDefect(defectId)
      .then((defect) => setDefectState({ status: "ready", defect }))
      .catch((error) =>
        setDefectState({
          status: "error",
          message: error instanceof ApiError ? error.message : "Failed to load defect.",
        }),
      );
  }, [defectId]);

  useEffect(() => {
    loadDefect();
  }, [loadDefect]);

  useEffect(() => {
    if (!justUpdated) return;
    const timer = setTimeout(() => setJustUpdated(null), 4000);
    return () => clearTimeout(timer);
  }, [justUpdated]);

  async function handleUpdate(nextStatus: string) {
    if (updating) return; // guard against double-clicks while a request is in flight
    setUpdating(nextStatus);
    setUpdateError(null);
    setJustUpdated(null);
    try {
      const updated = await updateDefectStatus(defectId, { status: nextStatus }, token);
      setDefectState({ status: "ready", defect: updated });
      setJustUpdated(nextStatus);
      setHistoryKey((key) => key + 1);
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

  const defect = defectState.status === "ready" ? defectState.defect : null;

  return (
    <OfficerShell name={name}>
      <PageContainer className="max-w-2xl space-y-6 py-8">
        <div>
          <Link href="/dashboard" className="text-sm font-medium text-primary hover:underline">
            ← Back to dashboard
          </Link>
        </div>

        {defectState.status === "loading" && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Loading defect…</p>
          </Card>
        )}

        {defectState.status === "error" && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Couldn&apos;t load defect data: {defectState.message}</p>
            <Button variant="secondary" className="mt-3" onClick={loadDefect}>
              Retry
            </Button>
          </Card>
        )}

        {defect && (
          <Card className="p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                  Incident #{defectId}
                </p>
                <h1 className="mt-1 text-2xl font-semibold text-on-surface">
                  {defectTypeLabel(defect.defect_type)}
                </h1>
              </div>
              <StatusChip tone={statusTone(defect.defect_status)}>
                {statusLabel(defect.defect_status)}
              </StatusChip>
            </div>

            <div className="mt-6">
              <Divider />
            </div>

            {/* A. Evidence */}
            <div className="mt-4">
              <SectionHeading>Evidence</SectionHeading>
              <EvidenceSection />
            </div>

            <div className="mt-6">
              <Divider />
            </div>

            {/* B. AI Analysis */}
            <div className="mt-4">
              <SectionHeading>AI Analysis</SectionHeading>
              <AIAnalysisSection emptyMessage="AI analysis will appear here once the backend provides an ML result for this incident." />
            </div>

            <div className="mt-6">
              <Divider />
            </div>

            {/* C. Road Intelligence */}
            <div className="mt-4">
              <SectionHeading>Road Intelligence</SectionHeading>
              <RoadIntelligenceSection />
            </div>

            <div className="mt-6">
              <Divider />
            </div>

            <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
                  Severity
                </dt>
                <dd className="mt-1">
                  <SeverityBadge severity={defect.defect_severity} />
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
                  Status
                </dt>
                <dd className="mt-1 font-medium text-on-surface">{statusLabel(defect.defect_status)}</dd>
              </div>
              {/* D. Location */}
              <div className="col-span-2">
                <dt className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
                  Location
                </dt>
                <dd className="mt-2">
                  <div className="h-40 w-full overflow-hidden rounded-lg border border-border-subtle">
                    <IncidentLocationMap latitude={defect.latitude} longitude={defect.longitude} />
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <LocationDisplay latitude={defect.latitude} longitude={defect.longitude} />
                    <a
                      href={`https://www.google.com/maps?q=${defect.latitude},${defect.longitude}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 text-xs font-medium text-primary hover:underline"
                    >
                      Open in Maps →
                    </a>
                  </div>
                </dd>
              </div>
              {/* E. Observations */}
              <div className="col-span-2">
                <dt className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
                  Observations
                </dt>
                <dd className="mt-1">
                  <ObservationsSection />
                </dd>
              </div>
            </dl>

            <div className="mt-6">
              <Divider />
            </div>

            {/* F. Status workflow — real backend lifecycle only */}
            <div className="mt-4">
              <StatusTimeline currentStatus={defect.defect_status} />
            </div>

            <div className="mt-4">
              <SectionHeading>Status history</SectionHeading>
              <StatusHistoryList key={historyKey} defectId={defectId} />
            </div>

            {/* Repair Verification — hidden entirely until real data exists */}
            <RepairVerificationSection />

            <div className="mt-6">
              <Divider />
            </div>

            <div className="mt-4">
              <SectionHeading>Actions</SectionHeading>

              {updateError && (
                <p className="mb-3 rounded-md bg-error-container px-3 py-2 text-sm text-on-error-container">
                  {updateError}
                </p>
              )}

              {justUpdated && !updateError && (
                <p className="mb-3 rounded-md bg-primary/10 px-3 py-2 text-sm text-primary">
                  ✓ Incident marked {statusLabel(justUpdated).toLowerCase()}.
                </p>
              )}

              {/* Real backend lifecycle: reported -> confirmed -> in_progress
                  -> resolved, or rejected at the reported stage. Only the
                  next real action for the CURRENT status is ever offered —
                  Confirm never reappears once a report has moved past it. */}
              {(() => {
                const normalized = defect.defect_status.trim().toLowerCase();
                if (normalized.includes("reject") || normalized.includes("resolv")) {
                  return (
                    <p className="text-sm text-on-surface-variant">
                      This incident&apos;s workflow is complete — no further action is available.
                    </p>
                  );
                }
                if (normalized.includes("progress")) {
                  return (
                    <div className="flex gap-3">
                      <Button
                        variant="primary"
                        disabled={updating !== null}
                        aria-busy={updating === "resolved"}
                        onClick={() => handleUpdate("resolved")}
                      >
                        {updating === "resolved" ? "Marking Resolved…" : "Mark Resolved"}
                      </Button>
                    </div>
                  );
                }
                if (normalized.includes("confirm")) {
                  return (
                    <div className="flex gap-3">
                      <Button
                        variant="primary"
                        disabled={updating !== null}
                        aria-busy={updating === "in_progress"}
                        onClick={() => handleUpdate("in_progress")}
                      >
                        {updating === "in_progress" ? "Updating…" : "Mark In Progress"}
                      </Button>
                    </div>
                  );
                }
                // "reported" (or any unrecognized status) — the only stage
                // Confirm/Reject are still valid actions.
                return (
                  <div className="flex gap-3">
                    <Button
                      variant="primary"
                      disabled={updating !== null}
                      aria-busy={updating === "confirmed"}
                      onClick={() => handleUpdate("confirmed")}
                    >
                      {updating === "confirmed" ? "Confirming…" : "Confirm Incident"}
                    </Button>
                    <Button
                      variant="destructive"
                      disabled={updating !== null}
                      aria-busy={updating === "rejected"}
                      onClick={() => handleUpdate("rejected")}
                    >
                      {updating === "rejected" ? "Rejecting…" : "Reject"}
                    </Button>
                  </div>
                );
              })()}
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
      {(session) => <DefectDetailContent name={session.name} token={session.token} defectId={defectId} />}
    </RequireSession>
  );
}
