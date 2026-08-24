"use client";

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

function DashboardContent({ name }: { name: string }) {
  const defectsState = useDefects();

  return (
    <OfficerShell name={name}>
      <PageContainer className="space-y-6 py-8">
        <div>
          <h1 className="text-2xl font-semibold text-on-surface">Municipal command center</h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            Real defects reported through RoadSense, loaded from GET /defects.
          </p>
        </div>

        {defectsState.status === "ready" && defectsState.usingMock && (
          <p className="rounded-md bg-tertiary/10 px-3 py-2 text-xs text-tertiary">
            Backend unreachable — showing sample data for development only.
          </p>
        )}

        {defectsState.status === "loading" && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Loading defects…</p>
          </Card>
        )}

        {defectsState.status === "error" && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Couldn&apos;t load defects.</p>
            <Button variant="secondary" className="mt-3" onClick={defectsState.reload}>
              Retry
            </Button>
          </Card>
        )}

        {defectsState.status === "ready" && defectsState.defects.length === 0 && (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">No defects reported yet.</p>
          </Card>
        )}

        {defectsState.status === "ready" && defectsState.defects.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-border-subtle bg-surface-container-lowest">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-container-low text-xs uppercase tracking-wide text-on-surface-variant">
                <tr>
                  <th className="px-4 py-3 font-medium">ID</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Severity</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Location</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border-subtle">
                {[...defectsState.defects]
                  .sort((a, b) => b.defect_id - a.defect_id)
                  .map((defect) => (
                    <tr key={defect.defect_id} className="hover:bg-surface-container-low">
                      <td className="px-4 py-3 font-medium text-on-surface">#{defect.defect_id}</td>
                      <td className="px-4 py-3 text-on-surface">{defectTypeLabel(defect.defect_type)}</td>
                      <td className="px-4 py-3">
                        <SeverityBadge severity={defect.defect_severity} />
                      </td>
                      <td className="px-4 py-3">
                        <StatusChip tone={statusTone(defect.defect_status)}>
                          {statusLabel(defect.defect_status)}
                        </StatusChip>
                      </td>
                      <td className="px-4 py-3 text-xs text-on-surface-variant">
                        {defect.latitude.toFixed(4)}, {defect.longitude.toFixed(4)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          href={`/defect/${defect.defect_id}`}
                          className="text-sm font-medium text-primary hover:underline"
                        >
                          Open
                        </Link>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </PageContainer>
    </OfficerShell>
  );
}

export default function DashboardPage() {
  return (
    <RequireSession role="officer">
      {(session) => <DashboardContent name={session.name} />}
    </RequireSession>
  );
}
