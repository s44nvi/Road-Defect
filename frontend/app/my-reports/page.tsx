"use client";

import { useMemo, useState } from "react";
import { RequireSession } from "@/components/auth/require-session";
import { CitizenShell } from "@/components/layout/citizen-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useMyReports } from "@/components/my-reports/use-my-reports";
import { MyReportCard } from "@/components/my-reports/my-report-card";
import { MyReportsEmptyState } from "@/components/my-reports/empty-state";
import { LocationSearchInput, type GeocodeResult } from "@/components/report/location-search-input";
import { haversineDistanceKm } from "@/lib/geo";

function MyReportsContent({ name, token }: { name: string; token: string }) {
  const reportsState = useMyReports(token);
  const [reference, setReference] = useState<GeocodeResult | null>(null);

  const sortedReports = useMemo(() => {
    if (reportsState.status !== "ready") return [];
    const withDistance = reportsState.defects.map((defect) => ({
      defect,
      distanceKm: reference
        ? haversineDistanceKm(reference, { latitude: defect.latitude, longitude: defect.longitude })
        : undefined,
    }));
    if (reference) {
      withDistance.sort((a, b) => (a.distanceKm ?? Infinity) - (b.distanceKm ?? Infinity));
    } else {
      withDistance.sort((a, b) => b.defect.defect_id - a.defect.defect_id);
    }
    return withDistance;
  }, [reportsState, reference]);

  return (
    <CitizenShell name={name}>
      <PageContainer className="space-y-6 py-8">
        <div>
          <h1 className="text-2xl font-semibold text-on-surface">My reports</h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            Reports you&apos;ve submitted with a photo, and their current progress.
          </p>
        </div>

        <Card className="p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
            Search nearby reports
          </p>
          <LocationSearchInput
            placeholder="Search a location… e.g. Thakur Village"
            onSelect={(result) => setReference(result)}
          />
          {reference && (
            <div className="mt-2 flex items-center justify-between text-xs text-on-surface-variant">
              <span>Showing distance from: {reference.label}</span>
              <button type="button" onClick={() => setReference(null)} className="font-medium text-primary hover:underline">
                Clear
              </button>
            </div>
          )}
        </Card>

        {reportsState.status === "loading" ? (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Loading your reports…</p>
          </Card>
        ) : reportsState.status === "error" ? (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">
              Couldn&apos;t load your reports: {reportsState.message}
            </p>
            <Button variant="secondary" className="mt-3" onClick={reportsState.reload}>
              Retry
            </Button>
          </Card>
        ) : sortedReports.length === 0 ? (
          <MyReportsEmptyState />
        ) : (
          <>
            {reference && (
              <h2 className="text-sm font-semibold text-on-surface">Nearby road issues</h2>
            )}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {sortedReports.map(({ defect, distanceKm }) => (
                <MyReportCard key={defect.defect_id} defect={defect} distanceKm={distanceKm} />
              ))}
            </div>
          </>
        )}
      </PageContainer>
    </CitizenShell>
  );
}

export default function MyReportsPage() {
  return (
    <RequireSession role="citizen">
      {(session) => <MyReportsContent name={session.name} token={session.token} />}
    </RequireSession>
  );
}
