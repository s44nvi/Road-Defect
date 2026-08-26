import type { HealthCategory } from "@/lib/api";

export type RoadHealthCategoryFilter = "all" | HealthCategory;
export type RoadHealthSortKey = "worst_health" | "most_open_issues" | "most_critical_issues";

function Select<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-on-surface-variant">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
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

// Controls which/how the "Roads needing attention" list (below the map) is
// filtered and sorted. Lifted to the dashboard page rather than owned by
// that list component so it can sit in its own row above the map, matching
// the required mobile stacking order: summary → filters → map → roads
// needing attention.
export function RoadHealthFilters({
  categoryFilter,
  onCategoryFilterChange,
  sortKey,
  onSortKeyChange,
}: {
  categoryFilter: RoadHealthCategoryFilter;
  onCategoryFilterChange: (value: RoadHealthCategoryFilter) => void;
  sortKey: RoadHealthSortKey;
  onSortKeyChange: (value: RoadHealthSortKey) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Select
        label="Roads"
        value={categoryFilter}
        onChange={onCategoryFilterChange}
        options={[
          { value: "all", label: "All roads" },
          { value: "healthy", label: "Healthy" },
          { value: "needs_attention", label: "Needs attention" },
          { value: "critical", label: "Critical" },
        ]}
      />
      <Select
        label="Sort"
        value={sortKey}
        onChange={onSortKeyChange}
        options={[
          { value: "worst_health", label: "Worst health" },
          { value: "most_open_issues", label: "Most open issues" },
          { value: "most_critical_issues", label: "Most critical issues" },
        ]}
      />
    </div>
  );
}
