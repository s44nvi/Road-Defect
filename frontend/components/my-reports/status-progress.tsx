import { cn } from "@/lib/cn";
import { CheckCircleIcon } from "@/components/icons";

type RowState = "done" | "unknown" | "upcoming" | "rejected";

// The backend only ever persists "reported" (set at creation) and whatever
// an officer's Confirm/Reject sends ("confirmed"/"rejected") — see
// lib/api.ts's updateDefectStatus and the officer dashboard's Confirm/Reject
// buttons. "Under Review", "In Progress", and "Resolved" are not real
// statuses this backend produces today; they're drawn as the intended
// future workflow. `available` marks the ones that are.
interface StageInfo {
  key: string;
  label: string;
  available: boolean;
}

const STAGES: StageInfo[] = [
  { key: "reported", label: "Reported", available: true },
  { key: "confirmed", label: "Confirmed", available: true },
  { key: "in_progress", label: "In Progress", available: false },
  { key: "resolved", label: "Resolved", available: false },
];

function matchStageIndex(status: string): number {
  const normalized = status.trim().toLowerCase();
  if (normalized.includes("resolv") || normalized.includes("complet")) return 3;
  if (normalized.includes("progress") || normalized.includes("repair") || normalized.includes("assign")) {
    return 2;
  }
  if (normalized.includes("confirm")) return 1;
  return 0;
}

function TimelineRow({
  label,
  state,
  showConnector,
}: {
  label: string;
  state: RowState;
  showConnector: boolean;
}) {
  return (
    <li className="flex items-start gap-3">
      <div className="flex flex-col items-center">
        {state === "done" && (
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary">
            <CheckCircleIcon className="h-4 w-4" />
          </span>
        )}
        {state === "rejected" && (
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-error text-xs font-bold text-on-error">
            ✕
          </span>
        )}
        {state === "unknown" && (
          <span className="h-6 w-6 shrink-0 rounded-full border-2 border-outline" aria-hidden />
        )}
        {state === "upcoming" && (
          <span
            className="h-6 w-6 shrink-0 rounded-full border-2 border-dashed border-outline-variant"
            aria-hidden
          />
        )}
        {showConnector && <span className="mt-1 h-6 w-px bg-outline-variant" aria-hidden />}
      </div>
      <div className="pt-0.5">
        <p
          className={cn(
            "text-sm font-medium",
            state === "upcoming" ? "text-on-surface-variant" : "text-on-surface",
          )}
        >
          {label}
        </p>
        {state === "upcoming" && <p className="text-xs text-on-surface-variant">Upcoming</p>}
        {state === "unknown" && <p className="text-xs text-on-surface-variant">Not tracked separately</p>}
      </div>
    </li>
  );
}

// Citizen-facing progress view — deliberately simpler and friendlier than
// the officer dashboard's StatusTimeline (components/dashboard/status-timeline.tsx),
// which this intentionally does not reuse or modify.
export function StatusProgress({ status }: { status: string }) {
  const normalized = status.trim().toLowerCase();

  if (normalized.includes("reject")) {
    return (
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
          Progress
        </p>
        <ol>
          <TimelineRow label="Reported" state="done" showConnector />
          <TimelineRow label="Rejected" state="rejected" showConnector={false} />
        </ol>
        <p className="mt-3 rounded-md border border-dashed border-outline px-3 py-2 text-xs text-on-surface-variant">
          This report was reviewed and wasn&apos;t confirmed as a valid road issue. RoadSense doesn&apos;t
          have an additional reason recorded for this decision yet.
        </p>
      </div>
    );
  }

  const currentIndex = matchStageIndex(normalized);

  return (
    <div>
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
        Progress
      </p>
      <ol>
        {STAGES.map((stage, index) => {
          let state: RowState;
          if (index === currentIndex) state = "done";
          else if (index < currentIndex) state = stage.available ? "done" : "unknown";
          else state = "upcoming";
          return (
            <TimelineRow
              key={stage.key}
              label={stage.label}
              state={state}
              showConnector={index < STAGES.length - 1}
            />
          );
        })}
      </ol>
    </div>
  );
}
