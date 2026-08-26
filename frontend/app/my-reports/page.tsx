"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireSession } from "@/components/auth/require-session";
import { CitizenShell } from "@/components/layout/citizen-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusChip } from "@/components/ui/status-chip";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { useMyReports } from "@/components/my-reports/use-my-reports";
import { MyReportCard } from "@/components/my-reports/my-report-card";
import { MyReportsEmptyState } from "@/components/my-reports/empty-state";
import { LocationSearchInput, type GeocodeResult } from "@/components/report/location-search-input";
import { fetchNearbyReports, ApiError, type NearbyIncidentResponse } from "@/lib/api";
import { defectTypeLabel } from "@/lib/defect-types";
import { statusTone, statusLabel } from "@/lib/defect-status";
import { formatDistanceAway } from "@/lib/geo";
import { formatIST } from "@/lib/format-datetime";

const NEARBY_RADIUS_KM = 5;

type NearbyState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; items: NearbyIncidentResponse[] };

function NearbyReportRow({ item }: { item: NearbyIncidentResponse }) {
  return (
    <Link
      href={`/my-reports/${item.defect_id}`}
      className="flex items-center justify-between gap-3 rounded-lg border border-border-subtle bg-surface-container-lowest px-4 py-3 transition-colors hover:bg-surface-container-low"
    >
      <div className="min-w-0">
        <p className="text-sm font-medium text-on-surface">{defectTypeLabel(item.defect_type)}</p>
        <div className="mt-1 flex items-center gap-2">
          <SeverityBadge severity={item.defect_severity} />
          <StatusChip tone={statusTone(item.defect_status)}>{statusLabel(item.defect_status)}</StatusChip>
        </div>
        {item.reported_at && (
          <p className="mt-1 text-xs text-on-surface-variant">{formatIST(item.reported_at)}</p>
        )}
      </div>
      <div className="shrink-0 text-right">
        <p className="text-sm font-semibold text-primary">{formatDistanceAway(item.distance_km)}</p>
        <p className="text-xs text-on-surface-variant">#{item.defect_id}</p>
      </div>
    </Link>
  );
}

function MyReportsContent({ name, token }: { name: string; token: string }) {
  const reportsState = useMyReports(token);
  const [reference, setReference] = useState<GeocodeResult | null>(null);
  const [nearbyState, setNearbyState] = useState<NearbyState>({ status: "idle" });

  // GET /reports/nearby — real backend-computed haversine distance, never
  // a client-side approximation. Searches all reports near the selected
  // point, not just this citizen's own (matching "Nearby Road Issues").
  useEffect(() => {
    if (!reference) {
      setNearbyState({ status: "idle" });
      return;
    }
    let cancelled = false;
    setNearbyState({ status: "loading" });
    fetchNearbyReports({ latitude: reference.latitude, longitude: reference.longitude, radiusKm: NEARBY_RADIUS_KM }, token)
      .then((items) => {
        if (!cancelled) setNearbyState({ status: "ready", items });
      })
      .catch((error) => {
        if (!cancelled) {
          setNearbyState({
            status: "error",
            message: error instanceof ApiError ? error.message : "Failed to load nearby reports.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reference, token]);

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
            Search nearby road issues
          </p>
          <LocationSearchInput
            placeholder="Search a location… e.g. Thakur Village"
            onSelect={(result) => setReference(result)}
          />
          {reference && (
            <div className="mt-2 flex items-center justify-between text-xs text-on-surface-variant">
              <span>
                Showing issues within {NEARBY_RADIUS_KM} km of: {reference.label}
              </span>
              <button
                type="button"
                onClick={() => setReference(null)}
                className="font-medium text-primary hover:underline"
              >
                Clear
              </button>
            </div>
          )}
        </Card>

        {nearbyState.status !== "idle" && (
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-on-surface">Nearby road issues</h2>
            {nearbyState.status === "loading" ? (
              <Card className="p-6 text-center">
                <p className="text-sm text-on-surface-variant">Searching nearby reports…</p>
              </Card>
            ) : nearbyState.status === "error" ? (
              <Card className="p-6 text-center">
                <p className="text-sm text-on-surface-variant">Couldn&apos;t load nearby reports: {nearbyState.message}</p>
              </Card>
            ) : nearbyState.items.length === 0 ? (
              <Card className="p-6 text-center">
                <p className="text-sm text-on-surface-variant">No road issues found within {NEARBY_RADIUS_KM} km.</p>
              </Card>
            ) : (
              <div className="space-y-2">
                {nearbyState.items.map((item) => (
                  <NearbyReportRow key={item.defect_id} item={item} />
                ))}
              </div>
            )}
          </div>
        )}

        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-on-surface">My reports</h2>
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
          ) : reportsState.defects.length === 0 ? (
            <MyReportsEmptyState />
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {[...reportsState.defects]
                .sort((a, b) => b.defect_id - a.defect_id)
                .map((defect) => (
                  <MyReportCard key={defect.defect_id} defect={defect} />
                ))}
            </div>
          )}
        </div>
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
