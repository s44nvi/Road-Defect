"use client";

import { useState } from "react";
import { RequireSession } from "@/components/auth/require-session";
import { CitizenShell } from "@/components/layout/citizen-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertIcon } from "@/components/icons";
import { ImageUpload, type ImageUploadValue } from "@/components/report/image-upload";
import { LocationPicker, type Coordinates } from "@/components/report/location-picker";
import { DefectTypeSelect } from "@/components/report/defect-type-select";
import { SeveritySelect } from "@/components/report/severity-select";
import { ReportSuccess } from "@/components/report/report-success";
import { runHawkerAnalysis, AiResult } from "@/components/report/ai-detection";
import { submitReport, ApiError, type DefectResponse } from "@/lib/api";
import type { DefectTypeKey } from "@/lib/defect-types";
import type { Severity } from "@/components/ui/severity-badge";

// The pothole detector is intentionally absent from the Analyze flow.
// See components/report/ai-detection.tsx for the documented reason.
// Only these two require a manual submit (no AI save their report):
const MANUAL_SUBMIT_CATEGORIES: DefectTypeKey[] = ["manhole", "road_crack", "pothole"];

type AnalysisStatus = "idle" | "loading" | "done";

// Hawker outcome type mirrored from ai-detection for the state shape.
type HawkerOutcome =
  | { status: "found"; data: import("@/lib/api").HawkerDetectionResponse }
  | { status: "not_found" }
  | { status: "error"; message: string };

interface FieldErrors {
  category?: string;
  severity?: string;
  location?: string;
}

function ReportForm({ token }: { token: string }) {
  const [image, setImage] = useState<ImageUploadValue | null>(null);
  const [location, setLocation] = useState<Coordinates | null>(null);
  const [category, setCategory] = useState<DefectTypeKey | null>(null);
  const [severity, setSeverity] = useState<Severity | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus>("idle");
  const [aiOutcome, setAiOutcome] = useState<HawkerOutcome | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<DefectResponse | null>(null);

  if (result) {
    return <ReportSuccess defect={result} />;
  }

  // Hawker analysis saves its own report server-side — the only categories
  // that need the manual submit button are the non-AI ones.
  const needsManualSubmit = category !== null && MANUAL_SUBMIT_CATEGORIES.includes(category);

  const canAnalyze = Boolean(image && location) && analysisStatus !== "loading";

  const analyzeLabel =
    analysisStatus === "loading"
      ? "Analyzing…"
      : analysisStatus === "done"
        ? "Analyze Again"
        : "Analyze with AI";

  async function handleAnalyze() {
    if (!image || !location) return;
    setAnalysisStatus("loading");
    setAiOutcome(null);

    const outcome = await runHawkerAnalysis(image, location, token, {
      onCategoryDetected: (cat) => setCategory(cat),
      onSeverityDetected: (sev) => setSeverity(sev),
    });

    setAiOutcome(outcome);
    setAnalysisStatus("done");
  }

  function handleCategoryChange(cat: DefectTypeKey) {
    setCategory(cat);
    setFieldErrors((prev) => ({ ...prev, category: undefined }));
  }

  function handleSeverityChange(sev: Severity) {
    setSeverity(sev);
    setFieldErrors((prev) => ({ ...prev, severity: undefined }));
  }

  // Manual submit path for Pothole / Manhole / Crack — Hawker is submitted
  // automatically by the Analyze call above (the backend persists it).
  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!needsManualSubmit) return;

    const errors: FieldErrors = {};
    if (!category) errors.category = "Select what you spotted.";
    if (!severity) errors.severity = "Select how severe this looks.";
    if (!location) errors.location = "Set a location for this report.";
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const defect = await submitReport({
        defect_type: category!,
        defect_severity: severity!,
        latitude: location!.latitude,
        longitude: location!.longitude,
      });
      setResult(defect);
    } catch (error) {
      setSubmitError(
        error instanceof ApiError
          ? error.message
          : "Something went wrong submitting your report. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      {/* ── Row 1: Evidence + Location ───────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Evidence card — image upload + Analyze button live here */}
        <Card className="p-6">
          <h2 className="text-base font-semibold text-on-surface">Road issue evidence</h2>
          <div className="mt-4">
            <ImageUpload value={image} onChange={setImage} />
          </div>

          {/* Analyze button lives directly below the uploaded image */}
          <div className="mt-4">
            <Button
              type="button"
              variant="primary"
              className="w-full"
              disabled={!canAnalyze}
              aria-busy={analysisStatus === "loading"}
              onClick={handleAnalyze}
            >
              {analyzeLabel}
            </Button>
            {!image || !location ? (
              <p className="mt-2 text-xs text-on-surface-variant text-center">
                {!image && !location
                  ? "Upload a photo and set a location to enable AI analysis."
                  : !image
                    ? "Upload a photo to enable AI analysis."
                    : "Set a location to enable AI analysis."}
              </p>
            ) : null}
          </div>
        </Card>

        {/* Location card */}
        <Card className="p-6">
          <h2 className="text-base font-semibold text-on-surface">Location</h2>
          <div className="mt-4">
            <LocationPicker value={location} onChange={setLocation} />
            {fieldErrors.location && (
              <p className="mt-2 text-xs text-error">{fieldErrors.location}</p>
            )}
          </div>
        </Card>
      </div>

      {/* ── Row 2: Category ──────────────────────────────────────────── */}
      <Card className="p-6">
        <h2 className="text-base font-semibold text-on-surface">What did you spot?</h2>
        <p className="mt-1 text-xs text-on-surface-variant">
          AI analysis will pre-select the detected category, but you can always change it.
          Manhole and Crack can also be reported manually without using AI.
        </p>
        <div className="mt-4">
          <DefectTypeSelect value={category} onChange={handleCategoryChange} />
          {fieldErrors.category && (
            <p className="mt-2 text-xs text-error">{fieldErrors.category}</p>
          )}
        </div>
      </Card>

      {/* ── Row 3: Severity ──────────────────────────────────────────── */}
      <Card className="p-6">
        <h2 className="text-base font-semibold text-on-surface">How severe does this look?</h2>
        <p className="mt-1 text-xs text-on-surface-variant">
          AI analysis will pre-select severity from the backend result. You can change it.
        </p>
        <div className="mt-4">
          <SeveritySelect value={severity} onChange={handleSeverityChange} />
          {fieldErrors.severity && (
            <p className="mt-2 text-xs text-error">{fieldErrors.severity}</p>
          )}
        </div>
      </Card>

      {/* ── Row 4: AI result (shown after Analyze) ───────────────────── */}
      {aiOutcome && (
        <AiResult outcome={aiOutcome} image={image} />
      )}

      {/* ── Row 5: Manual submit (Pothole / Manhole / Crack only) ────── */}
      {needsManualSubmit && (
        <>
          {submitError && (
            <div className="flex items-start gap-3 rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
              <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{submitError}</p>
            </div>
          )}

          <div className="flex items-center justify-between gap-4 rounded-lg bg-surface-container-low px-4 py-3">
            <p className="text-xs text-on-surface-variant">
              Your report will be reviewed by a municipal officer before action is taken.
            </p>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? "Submitting…" : "Submit Report"}
            </Button>
          </div>
        </>
      )}

      {/* Hawker / Encroachment: POST /ml/hawkers/detect persists the
          Defect the moment Analyze succeeds — there is no separate
          create-report call for this category, so no second "Submit"
          click is needed or offered here. Shown in the same bottom slot
          as the manual submit bar above so the form still ends with a
          clear final state, without implying a second action happens. */}
      {!needsManualSubmit && category === "hawker_encroachment" && aiOutcome?.status === "found" && (
        <div className="flex items-center justify-between gap-4 rounded-lg bg-primary/10 px-4 py-3">
          <p className="text-xs text-primary">
            ✓ Report already submitted — Hawker / Encroachment reports are saved as soon as AI analysis
            finds a vendor.
          </p>
          <Button type="button" variant="primary" disabled>
            Already Submitted
          </Button>
        </div>
      )}
    </form>
  );
}

function ReportPageContent({ name, token }: { name: string; token: string }) {
  return (
    <CitizenShell name={name}>
      <PageContainer className="space-y-6 py-8">
        <div>
          <h1 className="text-2xl font-semibold text-on-surface">Report a Road Issue</h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            Help RoadSense identify problems on Mumbai&apos;s roads.
          </p>
        </div>
        <ReportForm token={token} />
      </PageContainer>
    </CitizenShell>
  );
}

export default function ReportIssuePage() {
  return (
    <RequireSession role="citizen">
      {(session) => <ReportPageContent name={session.name} token={session.token} />}
    </RequireSession>
  );
}
