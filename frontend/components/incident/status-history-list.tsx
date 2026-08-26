"use client";

import { useEffect, useState } from "react";
import { fetchDefectStatusHistory, ApiError, type StatusHistoryEntry } from "@/lib/api";
import { statusLabel } from "@/lib/defect-status";

type HistoryState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; entries: StatusHistoryEntry[] };

// GET /defects/{id}/status-history — the real audit trail behind a
// defect's status, oldest first. Shown alongside (not replacing) the
// forward-looking workflow stepper above it, since that stepper still
// communicates "what's next" in a way a raw log doesn't.
export function StatusHistoryList({ defectId }: { defectId: number }) {
  const [state, setState] = useState<HistoryState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchDefectStatusHistory(defectId)
      .then((entries) => {
        if (!cancelled) setState({ status: "ready", entries });
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: error instanceof ApiError ? error.message : "Failed to load status history.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [defectId]);

  if (state.status === "loading") {
    return <p className="text-xs text-on-surface-variant">Loading status history…</p>;
  }
  if (state.status === "error") {
    return (
      <p className="text-xs text-on-surface-variant">Couldn&apos;t load status history: {state.message}</p>
    );
  }
  if (state.entries.length === 0) {
    return <p className="text-xs text-on-surface-variant">No status changes recorded yet.</p>;
  }

  return (
    <ol className="space-y-2">
      {state.entries.map((entry) => (
        <li key={entry.id} className="rounded-md border border-border-subtle px-3 py-2 text-xs">
          <p className="font-medium text-on-surface">
            {entry.old_status ? `${statusLabel(entry.old_status)} → ` : ""}
            {statusLabel(entry.new_status)}
          </p>
          <p className="mt-0.5 text-on-surface-variant">
            {new Date(entry.changed_at).toLocaleString()}
            {entry.changed_by ? ` · by ${entry.changed_by}` : ""}
          </p>
          {entry.note && <p className="mt-1 text-on-surface-variant">{entry.note}</p>}
        </li>
      ))}
    </ol>
  );
}
