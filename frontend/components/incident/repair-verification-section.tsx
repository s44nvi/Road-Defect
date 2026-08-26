import { AIAnalysisSection } from "./ai-analysis-section";
import type { AIDetectionResult } from "@/lib/api";

function ImageSlot({ label, imageUrl }: { label: string; imageUrl?: string | null }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{label}</p>
      {imageUrl ? (
        <div className="mt-2 overflow-hidden rounded-lg border border-border-subtle">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={imageUrl} alt={label} className="h-40 w-full object-cover" />
        </div>
      ) : (
        <div className="mt-2 flex h-40 items-center justify-center rounded-lg border border-dashed border-outline bg-surface-container-low">
          <p className="text-xs text-on-surface-variant">Not available yet</p>
        </div>
      )}
    </div>
  );
}

// Repair verification has no backend support at all yet — no repair
// workflow, no second-image upload, no verification model. Per spec, this
// section stays out of the way entirely (renders nothing) until at least
// one of these three pieces of data actually exists for an incident,
// rather than always showing three empty boxes on every incident.
export function RepairVerificationSection({
  beforeImageUrl,
  afterImageUrl,
  verification,
}: {
  beforeImageUrl?: string | null;
  afterImageUrl?: string | null;
  verification?: AIDetectionResult | null;
}) {
  if (!beforeImageUrl && !afterImageUrl && !verification) {
    return null;
  }

  return (
    <div>
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
        Repair Verification
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ImageSlot label="Before Repair" imageUrl={beforeImageUrl} />
        <ImageSlot label="After Repair" imageUrl={afterImageUrl} />
      </div>
      <div className="mt-4">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-on-surface-variant">
          AI Verification
        </p>
        <AIAnalysisSection
          result={verification}
          emptyMessage="AI verification will appear here once a repair photo is submitted."
        />
      </div>
    </div>
  );
}
