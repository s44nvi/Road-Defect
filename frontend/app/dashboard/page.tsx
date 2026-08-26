"use client";

import { useMemo, useState } from "react";
import { RequireSession } from "@/components/auth/require-session";
import { OfficerShell } from "@/components/layout/officer-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DefectMap } from "@/components/map/defect-map";
import { MapLegend } from "@/components/map/map-legend";
import { RoadHealthLegend } from "@/components/map/road-health-legend";
import { DefectSummaryCard } from "@/components/map/defect-summary-card";
import { useDefects } from "@/components/map/use-defects";
import { useRoadHealth } from "@/components/map/use-road-health";
import { SummaryCards } from "@/components/dashboard/summary-cards";
import { RoadHealthSummary } from "@/components/dashboard/road-health-summary";
import {
  RoadHealthFilters,
  type RoadHealthCategoryFilter,
  type RoadHealthSortKey,
} from "@/components/dashboard/road-health-filters";
import { IncidentQueue } from "@/components/dashboard/incident-queue";
import { RoadHealthPopup } from "@/components/dashboard/road-health-popup";
import { RoadsNeedingAttention } from "@/components/dashboard/roads-needing-attention";
import type { DefectResponse, RoadHealthSegment } from "@/lib/api";

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
        <p className="text-sm text-on-surface-variant">Loading defect data…</p>
      ) : (
        <div className="text-center">
          <p className="text-sm text-on-surface-variant">Couldn&apos;t load defect data.</p>
          <Button variant="secondary" className="mt-3" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}

const EMPTY_SEGMENTS: RoadHealthSegment[] = [];

function DashboardContent({ name }: { name: string }) {
  const defectsState = useDefects();
  const roadHealthState = useRoadHealth();
  const [selected, setSelected] = useState<DefectResponse | null>(null);
  const [selectedSegment, setSelectedSegment] = useState<RoadHealthSegment | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<RoadHealthCategoryFilter>("all");
  const [sortKey, setSortKey] = useState<RoadHealthSortKey>("worst_health");

  const defects = defectsState.status === "ready" ? defectsState.defects : [];

  // Real road segments only — [] whenever the backend endpoint is
  // disabled/unreachable/empty, never a fabricated stand-in. Kept as a
  // stable reference so the map's road-health effect doesn't resync on
  // every unrelated dashboard re-render.
  const roadSegments = roadHealthState.status === "ready" ? roadHealthState.segments : EMPTY_SEGMENTS;
  const hasRoadHealthData = roadHealthState.status === "ready";

  const filteredSortedSegments = useMemo(() => {
    const filtered =
      categoryFilter === "all"
        ? roadSegments
        : roadSegments.filter((s) => s.health_category === categoryFilter);

    const sorted = [...filtered];
    if (sortKey === "most_open_issues") {
      sorted.sort((a, b) => b.open_issues - a.open_issues);
    } else if (sortKey === "most_critical_issues") {
      sorted.sort((a, b) => b.critical_issues - a.critical_issues);
    } else {
      sorted.sort((a, b) => a.health_score - b.health_score);
    }
    return sorted;
  }, [roadSegments, categoryFilter, sortKey]);

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

        <SummaryCards defects={defects} />

        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-on-surface">Road health</h2>
          <RoadHealthSummary state={roadHealthState} />
          <RoadHealthFilters
            categoryFilter={categoryFilter}
            onCategoryFilterChange={setCategoryFilter}
            sortKey={sortKey}
            onSortKeyChange={setSortKey}
          />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_380px]">
          <Card className="relative h-[420px] overflow-hidden p-0 md:h-[560px]">
            <DefectMap
              defects={defects}
              selectedId={selected?.defect_id ?? null}
              onSelect={setSelected}
              roadSegments={roadSegments}
              selectedSegmentId={selectedSegment?.road_segment_id ?? null}
              onSelectSegment={setSelectedSegment}
            />
            <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-4">
              <div className="pointer-events-auto flex justify-end gap-2">
                <RoadHealthLegend active={hasRoadHealthData && roadSegments.length > 0} />
                <MapLegend />
              </div>
              <div className="pointer-events-auto flex items-end justify-between gap-2">
                {selectedSegment ? (
                  <RoadHealthPopup segment={selectedSegment} onClose={() => setSelectedSegment(null)} />
                ) : (
                  <span />
                )}
                {selected && (
                  <DefectSummaryCard
                    defect={selected}
                    onClose={() => setSelected(null)}
                    detailsHref={`/defect/${selected.defect_id}`}
                  />
                )}
              </div>
            </div>
            {(defectsState.status === "loading" || defectsState.status === "error") && (
              <MapStateOverlay
                state={defectsState.status}
                onRetry={defectsState.status === "error" ? defectsState.reload : undefined}
              />
            )}
          </Card>

          <div>
            <h2 className="mb-3 text-lg font-semibold text-on-surface">Incident queue</h2>
            {defectsState.status === "loading" ? (
              <Card className="p-6 text-center">
                <p className="text-sm text-on-surface-variant">Loading…</p>
              </Card>
            ) : defectsState.status === "error" ? (
              <Card className="p-6 text-center">
                <p className="text-sm text-on-surface-variant">Couldn&apos;t load incidents.</p>
                <Button variant="secondary" className="mt-3" onClick={defectsState.reload}>
                  Retry
                </Button>
              </Card>
            ) : (
              <IncidentQueue
                defects={defects}
                selectedId={selected?.defect_id ?? null}
                onSelect={setSelected}
              />
            )}
          </div>
        </div>

        <RoadsNeedingAttention segments={filteredSortedSegments} hasBackendData={hasRoadHealthData} />
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
