"use client";

import { AlertIcon, CheckCircleIcon } from "@/components/icons";
import { SeverityBadge, normalizeSeverity, type Severity } from "@/components/ui/severity-badge";
import { BoundingBoxOverlay } from "@/components/hawker/bounding-box-overlay";
import { analyzeReportImage, ApiError, type AnalyzeImageResponse } from "@/lib/api";
import { normalizeDefectType, defectTypeLabel, type DefectTypeKey } from "@/lib/defect-types";
import type { ImageUploadValue } from "@/components/report/image-upload";
import type { Coordinates } from "@/components/report/location-picker";

// POST /reports/analyze (backend commit 618fbfe) — pure AI analysis, never
// creates a Defect. The image_token it returns is required by the
// separate POST /reports/submit call that actually creates the report
// (see app/report/page.tsx's handleSubmit) — Analyze and Submit are two
// genuinely independent backend calls for every category now, including
// Hawker/Encroachment, unlike the older POST /ml/hawkers/detect and
// POST /reports/image, which persisted immediately.
export type AnalysisOutcome =
  | { status: "found"; result: AnalyzeImageResponse }
  | { status: "not_found" }
  | { status: "error" };

export interface AnalysisCallbacks {
  onCategoryDetected: (category: DefectTypeKey | null) => void;
  onSeverityDetected: (severity: Severity | null) => void;
}

export async function runAnalysis(
  image: ImageUploadValue,
  location: Coordinates | null,
  token: string,
  callbacks: AnalysisCallbacks,
): Promise<AnalysisOutcome> {
  // Never leave a stale pre-selection from a previous photo/analysis in
  // place while a new one is running.
  callbacks.onCategoryDetected(null);
  callbacks.onSeverityDetected(null);

  try {
    const result = await analyzeReportImage(
      { file: image.file, latitude: location?.latitude, longitude: location?.longitude },
      token,
    );

    if (!result.category) {
      // Real "nothing confidently detected" outcome — never defaults to
      // Pothole or any other category (see backend's own AnalyzeImageResponse
      // docstring: category/confidence/bbox are null together, deliberately).
      return { status: "not_found" };
    }

    callbacks.onCategoryDetected(normalizeDefectType(result.category));
    if (result.ai_severity) {
      callbacks.onSeverityDetected(normalizeSeverity(result.ai_severity));
    }

    return { status: "found", result };
  } catch (error) {
    void error; // ApiError already surfaces via the generic failure message below
    return { status: "error" };
  }
}

export function AiResult({
  outcome,
  image,
}: {
  outcome: AnalysisOutcome | null;
  image: ImageUploadValue | null;
}) {
  if (!outcome) return null;

  if (outcome.status === "error") {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
        <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
        <p>AI analysis failed. Please try again.</p>
      </div>
    );
  }

  if (outcome.status === "not_found") {
    return (
      <div className="rounded-lg border border-dashed border-outline bg-surface-container-low px-4 py-3 text-sm text-on-surface-variant">
        No defect confidently detected in this photo. Select a category and severity below to report it
        manually.
      </div>
    );
  }

  const { result } = outcome;
  // result.category is guaranteed non-null here — runAnalysis() only
  // returns "found" when it is. The raw hawker vendor subclasses
  // (fixed-stall-vendor etc.) never reach this label — defectTypeLabel()
  // normalizes them to "Hawker / Encroachment".
  const label = defectTypeLabel(result.category as string);

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-container-low p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-on-surface">
        <CheckCircleIcon className="h-4 w-4 text-primary" />
        {label} detected
        {result.confidence != null && ` — ${(result.confidence * 100).toFixed(1)}%`}
      </div>

      {result.ai_severity && (
        <div className="mt-1 flex items-center gap-2 text-sm text-on-surface-variant">
          AI severity: <SeverityBadge severity={result.ai_severity} />
        </div>
      )}

      {image && result.bbox && (
        <div className="mt-3">
          <BoundingBoxOverlay
            imageUrl={image.previewUrl}
            detections={[{ bbox: result.bbox, confidence: result.confidence ?? 0 }]}
          />
        </div>
      )}
    </div>
  );
}
