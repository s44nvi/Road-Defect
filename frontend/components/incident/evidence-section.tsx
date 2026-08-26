import { CameraIcon } from "@/components/icons";

// The backend has no image upload endpoint and no image column on the
// Defect table (see the cross-layer integration audit), so `imageUrl` is
// always undefined today for every real incident. This renders the
// honest absence rather than a broken-image icon or a placeholder photo.
export function EvidenceSection({ imageUrl }: { imageUrl?: string | null }) {
  if (!imageUrl) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-outline bg-surface-container-low px-4 py-8 text-center">
        <CameraIcon className="h-6 w-6 text-on-surface-variant" />
        <p className="text-sm text-on-surface-variant">No evidence image available for this incident.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border-subtle">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={imageUrl} alt="Submitted evidence" className="h-64 w-full object-cover" />
    </div>
  );
}
