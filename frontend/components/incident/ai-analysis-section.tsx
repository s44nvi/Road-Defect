import { AlertIcon } from "@/components/icons";
import type { AIDetectionResult } from "@/lib/api";

const DEFAULT_EMPTY_MESSAGE = "AI analysis will appear after submission.";

// Shared by the citizen report page and the officer incident detail page —
// see lib/api.ts's AIDetectionResult for why `result` is always undefined
// today (no ML wiring into the backend yet). Never render placeholder
// numbers here; the honest empty state is the real, expected state.
export function AIAnalysisSection({
  result,
  emptyMessage = DEFAULT_EMPTY_MESSAGE,
}: {
  result?: AIDetectionResult | null;
  emptyMessage?: string;
}) {
  if (!result) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-dashed border-outline bg-surface-container-low px-4 py-3">
        <AlertIcon className="mt-0.5 h-4 w-4 shrink-0 text-on-surface-variant" />
        <p className="text-sm text-on-surface-variant">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-container-low p-4">
      <dl className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
            Detected Class
          </dt>
          <dd className="mt-1 font-semibold text-on-surface">{result.detected_class}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
            Confidence
          </dt>
          <dd className="mt-1 font-semibold text-on-surface">
            {(result.confidence * 100).toFixed(1)}%
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
            Model Source
          </dt>
          <dd className="mt-1 text-on-surface">{result.model_source}</dd>
        </div>
        {result.bbox && (
          <div className="col-span-2">
            <dt className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
              Bounding Box
            </dt>
            <dd className="mt-1 font-mono text-xs text-on-surface">
              x: {result.bbox.x}, y: {result.bbox.y}, w: {result.bbox.width}, h: {result.bbox.height}
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}
