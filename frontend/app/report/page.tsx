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
import { runAnalysis, AiResult, type AnalysisOutcome } from "@/components/report/ai-detection";
import { submitFinalReport, ApiError, type DefectResponse } from "@/lib/api";
import type { DefectTypeKey } from "@/lib/defect-types";
import type { Severity } from "@/components/ui/severity-badge";

type AnalysisStatus = "idle" | "loading" | "done";

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
  const [analysisOutcome, setAnalysisOutcome] = useState<AnalysisOutcome | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<DefectResponse | null>(null);

  if (result) {
    return <ReportSuccess defect={result} />;
  }

  const canAnalyze = Boolean(image && location) && analysisStatus !== "loading";
  // POST /reports/submit requires an image_token from a prior successful
  // analyze call — there is no way to submit without first analyzing,
  // regardless of which category the citizen ends up choosing.
  const hasImageToken = analysisOutcome?.status === "found";

  const analyzeLabel =
    analysisStatus === "loading" ? "Analyzing…" : analysisStatus === "done" ? "Analyze Again" : "Analyze with AI";

  async function handleAnalyze() {
    if (!image || !location) return;
    setAnalysisStatus("loading");
    setAnalysisOutcome(null);

    const outcome = await runAnalysis(image, location, token, {
      onCategoryDetected: setCategory,
      onSeverityDetected: setSeverity,
    });

    setAnalysisOutcome(outcome);
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

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    const errors: FieldErrors = {};
    if (!category) errors.category = "Select what you spotted.";
    if (!severity) errors.severity = "Select how severe this looks.";
    if (!location) errors.location = "Set a location for this report.";
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    if (analysisOutcome?.status !== "found") {
      setSubmitError("Run Analyze with AI on your photo before submitting — it's required to attach your evidence.");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    try {
      const defect = await submitFinalReport(
        {
          image_token: analysisOutcome.result.image_token,
          latitude: location!.latitude,
          longitude: location!.longitude,
          defect_type: category!,
          defect_severity: severity!,
        },
        token,
      );
      setResult(defect);
    } catch (error) {
      setSubmitError(
        error instanceof ApiError ? error.message : "Something went wrong submitting your report. Please try again.",
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
              <p className="mt-2 text-center text-xs text-on-surface-variant">
                {!image && !location
                  ? "Upload a photo and set a location to enable AI analysis."
                  : !image
                    ? "Upload a photo to enable AI analysis."
                    : "Set a location to enable AI analysis."}
              </p>
            ) : null}
          </div>

          {/* AI result — shown right below Analyze, inside the same card */}
          {analysisOutcome && (
            <div className="mt-4">
              <AiResult outcome={analysisOutcome} image={image} />
            </div>
          )}
        </Card>

        {/* Location card */}
        <Card className="p-6">
          <h2 className="text-base font-semibold text-on-surface">Location</h2>
          <div className="mt-4">
            <LocationPicker value={location} onChange={setLocation} />
            {fieldErrors.location && <p className="mt-2 text-xs text-error">{fieldErrors.location}</p>}
          </div>
        </Card>
      </div>

      {/* ── Row 2: Category ──────────────────────────────────────────── */}
      <Card className="p-6">
        <h2 className="text-base font-semibold text-on-surface">What did you spot?</h2>
        <p className="mt-1 text-xs text-on-surface-variant">
          AI analysis pre-selects the detected category, but you can always change it.
        </p>
        <div className="mt-4">
          <DefectTypeSelect value={category} onChange={handleCategoryChange} />
          {fieldErrors.category && <p className="mt-2 text-xs text-error">{fieldErrors.category}</p>}
        </div>
      </Card>

      {/* ── Row 3: Severity ──────────────────────────────────────────── */}
      <Card className="p-6">
        <h2 className="text-base font-semibold text-on-surface">How severe does this look?</h2>
        <p className="mt-1 text-xs text-on-surface-variant">
          AI analysis pre-selects severity from the backend result, when available. You can change it.
        </p>
        <div className="mt-4">
          <SeveritySelect value={severity} onChange={handleSeverityChange} />
          {fieldErrors.severity && <p className="mt-2 text-xs text-error">{fieldErrors.severity}</p>}
        </div>
      </Card>

      {/* ── Row 4: Review + final submit ─────────────────────────────── */}
      {submitError && (
        <div className="flex items-start gap-3 rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
          <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <p>{submitError}</p>
        </div>
      )}

      <div className="flex items-center justify-between gap-4 rounded-lg bg-surface-container-low px-4 py-3">
        <p className="text-xs text-on-surface-variant">
          {hasImageToken
            ? "Your report will be reviewed by a municipal officer before action is taken."
            : "Run Analyze with AI above to attach your photo before submitting."}
        </p>
        <Button type="submit" variant="primary" disabled={submitting || !hasImageToken}>
          {submitting ? "Submitting…" : "Submit Report"}
        </Button>
      </div>
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
