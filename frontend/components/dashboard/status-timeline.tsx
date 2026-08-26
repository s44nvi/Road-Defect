import { cn } from "@/lib/cn";
import { statusTone } from "@/lib/defect-status";
import { StatusChip } from "@/components/ui/status-chip";
import { CheckCircleIcon } from "@/components/icons";

// The full officer workflow RoadSense is designed around. `available: true`
// stages are ones the backend actually supports today via
// PATCH /defects/{id} (see lib/api.ts's updateDefectStatus) and that this
// app actually sends — right now that's only "reported" (the initial
// value the backend sets) and "confirmed" (sent by the Confirm button).
// The rest are drawn as a preview of where the workflow is headed, never
// as clickable actions — clicking them would send a status the backend/UI
// contract was never agreed to support, which is exactly what this task
// says not to fake.
export interface StatusStageInfo {
  key: string;
  label: string;
  available: boolean;
}

// Matches the real backend lifecycle: reported / confirmed / in_progress /
// resolved / rejected. Only "reported" and "confirmed" are ever actually
// sent by this app (see updateDefectStatus call sites in
// app/defect/[id]/page.tsx) — "in_progress"/"resolved" are drawn as the
// planned next stages of the real, intended lifecycle, not invented ones.
export const OFFICER_STATUS_STAGES: StatusStageInfo[] = [
  { key: "reported", label: "Reported", available: true },
  { key: "confirmed", label: "Confirmed", available: true },
  { key: "in_progress", label: "In Progress", available: false },
  { key: "resolved", label: "Resolved", available: false },
];

function matchStageIndex(status: string): number {
  const normalized = status.trim().toLowerCase();
  if (normalized.includes("resolv") || normalized.includes("complet")) return 3;
  if (normalized.includes("progress") || normalized.includes("repair") || normalized.includes("assign")) return 2;
  if (normalized.includes("confirm")) return 1;
  return 0;
}

export function StatusTimeline({ currentStatus }: { currentStatus: string }) {
  const normalized = currentStatus.trim().toLowerCase();

  // "Rejected" isn't a step on the forward pipeline — show it as a
  // distinct terminal outcome instead of forcing it into the stepper.
  if (normalized.includes("reject")) {
    return (
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
          Workflow status
        </p>
        <StatusChip tone={statusTone(currentStatus)}>Rejected</StatusChip>
        <p className="mt-2 text-xs text-on-surface-variant">
          This report was rejected and is not moving through the repair workflow.
        </p>
      </div>
    );
  }

  const activeIndex = matchStageIndex(normalized);

  return (
    <div>
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
        Workflow status
      </p>
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-3">
        {OFFICER_STATUS_STAGES.map((stage, index) => {
          const isCurrent = index === activeIndex;
          const isPast = index < activeIndex;
          const stateLabel = isCurrent ? "Current: " : isPast ? "Completed: " : "Planned: ";
          return (
            <li key={stage.key} className="flex items-center gap-2">
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
                  isCurrent && "border-primary bg-primary/10 text-primary",
                  isPast && !isCurrent && "border-primary/40 bg-primary/5 text-on-surface",
                  !isPast && !isCurrent && stage.available && "border-border-subtle text-on-surface-variant",
                  !stage.available && "border-dashed border-outline text-outline",
                )}
                title={stage.available ? undefined : "Not yet available in the backend"}
              >
                <span className="sr-only">{stateLabel}</span>
                {isPast && !isCurrent && <CheckCircleIcon className="h-3.5 w-3.5 text-primary" aria-hidden />}
                {isCurrent && (
                  <span className="h-2 w-2 rounded-full bg-primary" aria-hidden />
                )}
                {!isPast && !isCurrent && (
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full border",
                      stage.available ? "border-on-surface-variant" : "border-outline",
                    )}
                    aria-hidden
                  />
                )}
                {stage.label}
                {isCurrent && <span className="ml-0.5 text-[10px] uppercase">· current</span>}
                {!stage.available && <span className="ml-0.5 text-[10px]">(planned)</span>}
              </span>
              {index < OFFICER_STATUS_STAGES.length - 1 && (
                <span className="text-outline" aria-hidden>
                  →
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
