"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { RequireSession } from "@/components/auth/require-session";
import { CitizenShell } from "@/components/layout/citizen-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PlusIcon } from "@/components/icons";
import { DefectMap } from "@/components/map/defect-map";
import { MapLegend } from "@/components/map/map-legend";
import { DefectSummaryCard } from "@/components/map/defect-summary-card";
import { useDefects } from "@/components/map/use-defects";
import { HealthSummary } from "@/components/home/health-summary";
import { RecentReports } from "@/components/home/recent-reports";
import { isPubliclyVisibleStatus } from "@/lib/defect-status";
import type { DefectResponse } from "@/lib/api";

function MapStateOverlay({
  state,
  onRetry,
}: {
  state: "loading" | "error";
  onRetry?: () => void;
}) {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-surface-container-lowest/85 backdrop-blur-sm">
      {state === "loading" ? (
        <p className="text-sm text-on-surface-variant">Loading Mumbai road data…</p>
      ) : (
        <div className="text-center">
          <p className="text-sm text-on-surface-variant">Couldn&apos;t load road defect data.</p>
          <Button variant="secondary" className="mt-3" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}

function CitizenHomeContent({ name }: { name: string }) {
  const defectsState = useDefects();
  const [selected, setSelected] = useState<DefectResponse | null>(null);
  const searchParams = useSearchParams();

  // Community view: only officer-confirmed/in-progress/resolved issues —
  // unverified ("reported") and dismissed ("rejected") reports aren't
  // shown as live community issues here. See lib/defect-status.ts.
  const defects =
    defectsState.status === "ready"
      ? defectsState.defects.filter((d) => isPubliclyVisibleStatus(d.defect_status))
      : [];
  const firstName = name.trim().split(/\s+/)[0] ?? name;

  // Supports the "View Report" link from the report-success screen
  // (app/report/page.tsx), which has nowhere else to send a citizen yet —
  // there's no citizen-facing defect detail route. Selects the matching
  // defect from the already-fetched list once it's loaded, if present.
  useEffect(() => {
    if (defectsState.status !== "ready") return;
    const requestedId = searchParams.get("defect");
    if (!requestedId) return;
    const match = defectsState.defects.find((d) => String(d.defect_id) === requestedId);
    if (match) setSelected(match);
  }, [defectsState, searchParams]);

  return (
    <CitizenShell name={name}>
      <PageContainer className="space-y-6 py-8">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-on-surface">Welcome back, {firstName}</h1>
            <p className="mt-1 text-sm text-on-surface-variant">
              Your reports help RoadSense build a clearer picture of road conditions across Mumbai.
              Showing officer-confirmed and in-progress issues.
            </p>
          </div>
          <Link href="/report">
            <Button variant="primary">
              <PlusIcon className="h-4 w-4" />
              Report an Issue
            </Button>
          </Link>
        </div>

        {defectsState.status === "ready" && defectsState.usingMock && (
          <p className="rounded-md bg-tertiary/10 px-3 py-2 text-xs text-tertiary">
            Backend unreachable — showing sample data for development only.
          </p>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
          <Card className="relative h-[420px] overflow-hidden p-0 md:h-[560px]">
            <DefectMap
              defects={defects}
              selectedId={selected?.defect_id ?? null}
              onSelect={setSelected}
            />
            <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-4">
              <div className="pointer-events-auto flex justify-end">
                <MapLegend />
              </div>
              <div className="pointer-events-auto flex flex-wrap items-end justify-between gap-4">
                <HealthSummary defects={defects} />
                {selected && <DefectSummaryCard defect={selected} onClose={() => setSelected(null)} />}
              </div>
            </div>
            {(defectsState.status === "loading" || defectsState.status === "error") && (
              <MapStateOverlay
                state={defectsState.status}
                onRetry={defectsState.status === "error" ? defectsState.reload : undefined}
              />
            )}
          </Card>

          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-on-surface">Recent reports</h2>
            {defectsState.status === "loading" ? (
              <Card className="p-6 text-center">
                <p className="text-sm text-on-surface-variant">Loading…</p>
              </Card>
            ) : defectsState.status === "error" ? (
              <Card className="p-6 text-center">
                <p className="text-sm text-on-surface-variant">Couldn&apos;t load reports.</p>
                <Button variant="secondary" className="mt-3" onClick={defectsState.reload}>
                  Retry
                </Button>
              </Card>
            ) : (
              <RecentReports
                defects={defects}
                selectedId={selected?.defect_id ?? null}
                onSelect={setSelected}
              />
            )}
          </div>
        </div>
      </PageContainer>
    </CitizenShell>
  );
}

export default function CitizenHomePage() {
  return (
    <Suspense fallback={null}>
      <RequireSession role="citizen">
        {(session) => <CitizenHomeContent name={session.name} />}
      </RequireSession>
    </Suspense>
  );
}
