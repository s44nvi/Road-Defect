"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusChip } from "@/components/ui/status-chip";
import { SeverityBadge, normalizeSeverity, type Severity } from "@/components/ui/severity-badge";
import { defectTypeLabel, normalizeDefectType, type DefectTypeKey } from "@/lib/defect-types";
import { statusTone, statusLabel } from "@/lib/defect-status";
import { FOCUS_INCIDENT_SEARCH_EVENT } from "@/lib/dashboard-events";
import { SearchIcon, CloseIcon } from "@/components/icons";
import type { DefectResponse } from "@/lib/api";

const SEVERITY_ORDER: Record<Severity, number> = { critical: 0, medium: 1, low: 2 };
const TYPE_OPTIONS: DefectTypeKey[] = ["pothole", "road_crack", "manhole", "hawker_encroachment"];

type SortKey = "newest" | "severity";

// Quick-access grouping on top of the real defect_status values already
// used by the Status dropdown below — this never sends or invents a status
// the backend doesn't have, it just buckets the ones that exist for a
// faster filter. "In Progress" statuses (e.g. assigned/scheduled/repair)
// aren't produced by this backend today, so that tab is honestly empty
// until they are; a status this doesn't recognize (e.g. "rejected") only
// shows up under "All", rather than being mis-bucketed.
type QuickFilter = "all" | "needs_action" | "in_progress" | "resolved";

function quickFilterBucket(status: string): Exclude<QuickFilter, "all"> | "other" {
  const normalized = status.trim().toLowerCase();
  if (normalized.includes("resolv") || normalized.includes("complet")) return "resolved";
  if (normalized.includes("report") || normalized.includes("confirm")) return "needs_action";
  if (
    normalized.includes("progress") ||
    normalized.includes("assign") ||
    normalized.includes("schedul") ||
    normalized.includes("review") ||
    normalized.includes("repair")
  ) {
    return "in_progress";
  }
  return "other";
}

const QUICK_FILTERS: { value: QuickFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "needs_action", label: "Needs Action" },
  { value: "in_progress", label: "In Progress" },
  { value: "resolved", label: "Resolved" },
];

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-on-surface-variant">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-border-subtle bg-surface-container-lowest px-2 py-1 text-xs text-on-surface"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function IncidentQueue({
  defects,
  selectedId,
  onSelect,
}: {
  defects: DefectResponse[];
  selectedId: number | null;
  onSelect: (defect: DefectResponse) => void;
}) {
  const [search, setSearch] = useState("");
  const [quickFilter, setQuickFilter] = useState<QuickFilter>("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("newest");
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    function focusSearch() {
      searchInputRef.current?.focus();
    }
    window.addEventListener(FOCUS_INCIDENT_SEARCH_EVENT, focusSearch);
    return () => window.removeEventListener(FOCUS_INCIDENT_SEARCH_EVENT, focusSearch);
  }, []);

  // Status options are derived from whatever statuses are actually present
  // in the real data — defect_status is a free-form backend string, so
  // this never offers a filter value that doesn't genuinely exist.
  const statusOptions = useMemo(() => {
    const distinct = Array.from(new Set(defects.map((d) => d.defect_status)));
    return distinct.sort();
  }, [defects]);

  const hasActiveFilters =
    search.trim() !== "" ||
    quickFilter !== "all" ||
    severityFilter !== "all" ||
    statusFilter !== "all" ||
    typeFilter !== "all";

  function clearFilters() {
    setSearch("");
    setQuickFilter("all");
    setSeverityFilter("all");
    setStatusFilter("all");
    setTypeFilter("all");
  }

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return defects.filter((defect) => {
      if (quickFilter !== "all" && quickFilterBucket(defect.defect_status) !== quickFilter) {
        return false;
      }
      if (severityFilter !== "all" && normalizeSeverity(defect.defect_severity) !== severityFilter) {
        return false;
      }
      if (statusFilter !== "all" && defect.defect_status !== statusFilter) {
        return false;
      }
      if (typeFilter !== "all" && normalizeDefectType(defect.defect_type) !== typeFilter) {
        return false;
      }
      if (query) {
        const haystack = [
          String(defect.defect_id),
          defect.defect_type,
          defectTypeLabel(defect.defect_type),
          String(defect.latitude),
          String(defect.longitude),
        ]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }, [defects, quickFilter, severityFilter, statusFilter, typeFilter, search]);

  const sorted = useMemo(() => {
    const list = [...filtered];
    if (sortKey === "severity") {
      list.sort((a, b) => {
        const aRank = SEVERITY_ORDER[normalizeSeverity(a.defect_severity) ?? "low"];
        const bRank = SEVERITY_ORDER[normalizeSeverity(b.defect_severity) ?? "low"];
        return aRank - bRank || b.defect_id - a.defect_id;
      });
    } else {
      list.sort((a, b) => b.defect_id - a.defect_id);
    }
    return list;
  }, [filtered, sortKey]);

  return (
    <div className="space-y-3">
      <div>
        <label htmlFor="incident-search" className="sr-only">
          Search incidents by ID, type, or location
        </label>
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-on-surface-variant" />
          <input
            ref={searchInputRef}
            id="incident-search"
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search incidents by ID, type, or location..."
            className="w-full rounded-md border border-border-subtle bg-surface-container-lowest py-2 pl-9 pr-9 text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-2 focus:ring-primary"
          />
          {search !== "" && (
            <button
              type="button"
              onClick={() => setSearch("")}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-on-surface-variant hover:bg-surface-container-low"
            >
              <CloseIcon className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div
        role="tablist"
        aria-label="Filter incidents by workflow stage"
        className="inline-flex flex-wrap gap-1 rounded-md border border-border-subtle bg-surface-container-low p-1"
      >
        {QUICK_FILTERS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={quickFilter === option.value}
            onClick={() => setQuickFilter(option.value)}
            className={cn(
              "rounded px-3 py-1 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary",
              quickFilter === option.value
                ? "bg-surface-container-lowest text-primary shadow-card"
                : "text-on-surface-variant hover:text-on-surface",
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <FilterSelect
          label="Severity"
          value={severityFilter}
          onChange={setSeverityFilter}
          options={[
            { value: "all", label: "All" },
            { value: "critical", label: "Critical" },
            { value: "medium", label: "Medium" },
            { value: "low", label: "Low" },
          ]}
        />
        <FilterSelect
          label="Status"
          value={statusFilter}
          onChange={setStatusFilter}
          options={[{ value: "all", label: "All" }, ...statusOptions.map((s) => ({ value: s, label: statusLabel(s) }))]}
        />
        <FilterSelect
          label="Type"
          value={typeFilter}
          onChange={setTypeFilter}
          options={[
            { value: "all", label: "All" },
            ...TYPE_OPTIONS.map((t) => ({ value: t, label: defectTypeLabel(t) })),
          ]}
        />
        <FilterSelect
          label="Sort"
          value={sortKey}
          onChange={(v) => setSortKey(v as SortKey)}
          options={[
            { value: "newest", label: "Newest" },
            { value: "severity", label: "Highest severity" },
          ]}
        />
      </div>

      <p className="text-xs text-on-surface-variant">
        {hasActiveFilters ? (
          <>
            Showing {sorted.length} of {defects.length} incident{defects.length === 1 ? "" : "s"}
          </>
        ) : (
          <>
            {defects.length} incident{defects.length === 1 ? "" : "s"}
          </>
        )}
      </p>

      {defects.length === 0 ? (
        <Card className="p-6 text-center">
          <p className="text-sm text-on-surface-variant">No incidents reported yet.</p>
        </Card>
      ) : sorted.length === 0 ? (
        <Card className="p-6 text-center">
          <p className="text-sm text-on-surface-variant">No incidents match your filters.</p>
          <Button variant="secondary" className="mt-3" onClick={clearFilters}>
            Clear filters
          </Button>
        </Card>
      ) : (
        <div className="space-y-2">
          {sorted.map((defect) => (
            <button
              key={defect.defect_id}
              type="button"
              onClick={() => onSelect(defect)}
              aria-pressed={defect.defect_id === selectedId}
              className={cn(
                "block w-full rounded-lg border p-3 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-primary",
                defect.defect_id === selectedId
                  ? "border-primary bg-primary/5"
                  : "border-border-subtle bg-surface-container-lowest hover:bg-surface-container-low",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-primary">
                    Incident #{defect.defect_id}
                  </p>
                  <p className="text-sm font-semibold text-on-surface">
                    {defectTypeLabel(defect.defect_type)}
                  </p>
                </div>
                <StatusChip tone={statusTone(defect.defect_status)}>
                  {statusLabel(defect.defect_status)}
                </StatusChip>
              </div>

              <div className="mt-2 flex items-center justify-between gap-2">
                <SeverityBadge severity={defect.defect_severity} />
                <span className="text-xs text-on-surface-variant">
                  {defect.latitude.toFixed(4)}, {defect.longitude.toFixed(4)}
                </span>
              </div>

              <Link
                href={`/defect/${defect.defect_id}`}
                onClick={(e) => e.stopPropagation()}
                className="mt-3 flex items-center justify-center gap-1 rounded-md border border-primary/30 bg-primary/5 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/10"
              >
                Open incident →
              </Link>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
