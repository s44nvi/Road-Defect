"use client";

import Link from "next/link";
import { AlertIcon, CheckCircleIcon } from "@/components/icons";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { BoundingBoxOverlay } from "@/components/hawker/bounding-box-overlay";
import { detectHawkers, ApiError, type HawkerDetectionResponse } from "@/lib/api";
import type { ImageUploadValue } from "@/components/report/image-upload";
import type { Coordinates } from "@/components/report/location-picker";
import type { DefectTypeKey } from "@/lib/defect-types";
import type { Severity } from "@/components/ui/severity-badge";

// RoadSense currently has one active AI detector accessible from the
// citizen report flow: POST /ml/hawkers/detect.
//
// The pothole YOLO model (POST /reports/image) is NOT integrated here.
// best.pt was evaluated against 20 real pothole photos at all confidence
// thresholds and never fired D40 — calling it here would create a ghost
// defect record for every uploaded image with 0 real detections. The
// pothole path stays absent until a checkpoint that reliably fires D40 is
// provided. See backend/app/ml/potholes/detector.py's known-limitation
// docstring for the full evidence.
//
// When the pothole model is ready, add its call alongside detectHawkers()
// in handleAnalyze() below — the UI structure already supports it.

type HawkerOutcome =
  | { status: "found"; data: HawkerDetectionResponse }
  | { status: "not_found" }
  | { status: "error"; message: string };

export type AnalysisStatus = "idle" | "loading" | "done";

export interface AnalysisCallbacks {
  onCategoryDetected: (category: DefectTypeKey | null) => void;
  onSeverityDetected: (severity: Severity | null) => void;
}

// A 422 from the hawker route is the backend's real "nothing detected"
// signal — everything else (network failure, 5xx) is a genuine failure.
function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 422;
}

/** Run the hawker detector and return its outcome + callbacks fired. */
export async function runHawkerAnalysis(
  image: ImageUploadValue,
  location: Coordinates,
  token: string,
  callbacks: AnalysisCallbacks,
): Promise<HawkerOutcome> {
  callbacks.onCategoryDetected(null);
  callbacks.onSeverityDetected(null);

  try {
    const data = await detectHawkers(
      { latitude: location.latitude, longitude: location.longitude, file: image.file },
      token,
    );
    const best = data.detections.reduce(
      (a, b) => (b.confidence > a.confidence ? b : a),
      data.detections[0],
    );
    callbacks.onCategoryDetected("hawker_encroachment");
    // Normalize the severity string to one of our known values.
    const rawSev = best?.defect_severity?.toLowerCase() ?? "";
    const sev: Severity | null =
      rawSev === "critical" ? "critical" : rawSev === "medium" ? "medium" : rawSev === "low" ? "low" : null;
    callbacks.onSeverityDetected(sev);
    return { status: "found", data };
  } catch (error) {
    if (isNotFound(error)) return { status: "not_found" };
    return {
      status: "error",
      message:
        error instanceof ApiError
          ? error.message
          : "AI analysis failed. Please try again.",
    };
  }
}

// ---------------------------------------------------------------------------
// Result display — rendered below category/severity sections once analysis
// has completed. The Analyze button itself lives in the evidence card
// (see app/report/page.tsx).
// ---------------------------------------------------------------------------

interface AiResultProps {
  outcome: HawkerOutcome | null;
  image: ImageUploadValue | null;
}

export function AiResult({ outcome, image }: AiResultProps) {
  if (!outcome) return null;

  if (outcome.status === "error") {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
        <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
        <p>{outcome.message}</p>
      </div>
    );
  }

  if (outcome.status === "not_found") {
    return (
      <div className="rounded-lg border border-dashed border-outline bg-surface-container-low px-4 py-3 text-sm text-on-surface-variant">
        No vendor or encroachment detected in this photo. If you spotted a different issue, select
        its category above and choose a severity.
      </div>
    );
  }

  // status === "found"
  const detections = outcome.data.detections;
  const best = detections.reduce((a, b) => (b.confidence > a.confidence ? b : a));
  const label =
    detections.length === 1
      ? `Vendor Detected — ${(detections[0].confidence * 100).toFixed(1)}%`
      : `${detections.length} Vendors Detected — Highest confidence: ${(best.confidence * 100).toFixed(1)}%`;
  const reportIds = detections.map((d) => d.defect_id);

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-container-low p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-on-surface">
        <CheckCircleIcon className="h-4 w-4 text-primary" />
        {label}
      </div>

      <div className="mt-1 flex items-center gap-2 text-sm text-on-surface-variant">
        Severity: <SeverityBadge severity={best.defect_severity} />
      </div>

      {image && (
        <div className="mt-3">
          <BoundingBoxOverlay imageUrl={image.previewUrl} detections={detections} />
        </div>
      )}

      <div className="mt-3 rounded-md bg-primary/10 px-3 py-2 text-xs text-primary">
        {reportIds.length === 1
          ? `Report #${reportIds[0]} saved.`
          : `${reportIds.length} reports saved (#${reportIds.join(", #")}).`}{" "}
        <Link href="/my-reports" className="font-medium underline">
          View in My Reports →
        </Link>
      </div>
    </div>
  );
}
